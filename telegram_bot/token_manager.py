"""
Управление балансом токенов и историей транзакций.

Зависит от database.Database (SQLite + aiosqlite).
Файл не меняет глобальную схему БД в других местах, но обеспечивает
наличие необходимых таблиц/колонок локально при первом использовании.
"""

from __future__ import annotations

import aiosqlite
from typing import List, Dict, Optional

from database import Database


class TokenManager:
    """Менеджер токенов с атомарными операциями.

    Обеспечивает:
    - хранение и получение баланса токенов у пользователя
    - начисления/списания с записью истории транзакций
    - атомарность через транзакции SQLite
    - инициализацию необходимых таблиц/колонок при первом использовании
    """

    def __init__(self, db: Database, initial_bonus: int = 0):
        self.db = db
        self.initial_bonus = int(initial_bonus)

    async def _ensure_schema(self) -> None:
        """Гарантирует наличие таблиц для токенов и колонки token_balance у users.

        Не требует общей миграции (блок 1), работает локально и безопасно
        для существующей схемы: CREATE IF NOT EXISTS и условное ALTER TABLE.
        """
        async with aiosqlite.connect(self.db.db_path) as db:
            # Включаем строгий режим foreign_keys
            await db.execute("PRAGMA foreign_keys = ON")

            # Добавляем колонку token_balance в users при отсутствии
            async with db.execute("PRAGMA table_info(users)") as cursor:
                cols = [row[1] async for row in cursor]
            if "token_balance" not in cols:
                await db.execute("ALTER TABLE users ADD COLUMN token_balance INTEGER DEFAULT 0")

            # Таблица транзакций токенов
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS token_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    description TEXT,
                    balance_before INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    payment_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )

            # Индекс для ускорения выборок
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_token_transactions_user ON token_transactions(user_id, created_at DESC)"
            )

            await db.commit()

    async def get_balance(self, user_id: int) -> int:
        """Получить текущий баланс токенов пользователя.

        Args:
            user_id: Telegram user id.

        Returns:
            Текущее целое количество токенов.
        """
        await self._ensure_schema()
        async with aiosqlite.connect(self.db.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,)) as cur:
                row = await cur.fetchone()
                if row is None:
                    # Пользователь не создан в общей системе — создадим с начальным бонусом (если задан)
                    await db.execute(
                        "INSERT INTO users(user_id, token_balance) VALUES(?, ?)",
                        (user_id, max(self.initial_bonus, 0)),
                    )
                    await db.commit()
                    return max(self.initial_bonus, 0)
                return int(row["token_balance"] if row["token_balance"] is not None else 0)

    async def has_sufficient_balance(self, user_id: int, required_amount: int) -> bool:
        """Проверить достаточность баланса.

        Args:
            user_id: Идентификатор пользователя.
            required_amount: Требуемое число токенов (>= 0).

        Returns:
            True, если баланс >= required_amount.
        """
        if required_amount <= 0:
            return True
        balance = await self.get_balance(user_id)
        return balance >= required_amount

    async def add_tokens(
        self,
        user_id: int,
        amount: int,
        transaction_type: str,
        description: str = "",
        payment_id: Optional[str] = None,
    ) -> bool:
        """Начислить токены пользователю с записью транзакции.

        Операция атомарная. amount должен быть > 0 для начислений.
        """
        if amount <= 0:
            return False
        return await self._apply_delta(user_id, delta=amount, transaction_type=transaction_type, description=description, payment_id=payment_id)

    async def deduct_tokens(
        self,
        user_id: int,
        amount: int,
        transaction_type: str,
        description: str = "",
    ) -> bool:
        """Списать токены у пользователя с записью транзакции.

        Предотвращает отрицательный баланс. amount должен быть > 0.
        """
        if amount <= 0:
            return False
        # delta отрицательная для списания
        return await self._apply_delta(user_id, delta=-amount, transaction_type=transaction_type, description=description)

    async def _apply_delta(
        self,
        user_id: int,
        delta: int,
        transaction_type: str,
        description: str = "",
        payment_id: Optional[str] = None,
    ) -> bool:
        """Применить изменение к балансу с атомарной транзакцией и записью истории."""
        await self._ensure_schema()
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("BEGIN IMMEDIATE")
            try:
                # Текущий баланс
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT token_balance FROM users WHERE user_id = ?", (user_id,)) as cur:
                    row = await cur.fetchone()
                if row is None:
                    # Автосоздание пользователя с 0/initial_bonus для совместимости
                    starting = max(self.initial_bonus, 0)
                    await db.execute(
                        "INSERT INTO users(user_id, token_balance) VALUES(?, ?)",
                        (user_id, starting),
                    )
                    balance_before = starting
                else:
                    balance_before = int(row["token_balance"] if row["token_balance"] is not None else 0)

                balance_after = balance_before + delta
                if balance_after < 0:
                    await db.execute("ROLLBACK")
                    return False

                # Обновляем баланс
                await db.execute(
                    "UPDATE users SET token_balance = ? WHERE user_id = ?",
                    (balance_after, user_id),
                )

                # Записываем транзакцию
                await db.execute(
                    """
                    INSERT INTO token_transactions (
                        user_id, amount, transaction_type, description, balance_before, balance_after, payment_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, delta, transaction_type, description, balance_before, balance_after, payment_id),
                )

                await db.commit()
                return True
            except Exception:
                await db.execute("ROLLBACK")
                raise

    async def get_transaction_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получить историю транзакций пользователя (последние N)."""
        await self._ensure_schema()
        async with aiosqlite.connect(self.db.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT id, user_id, amount, transaction_type, description,
                       balance_before, balance_after, payment_id, created_at
                FROM token_transactions
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
