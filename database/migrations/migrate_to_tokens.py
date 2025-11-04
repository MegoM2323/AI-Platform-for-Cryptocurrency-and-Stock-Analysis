"""
Скрипт миграции базы данных для системы токенов

Добавляет поддержку токенов и конвертирует подписки в токены:
- Добавляет колонку token_balance в таблицу users
- Создает таблицы token_transactions и token_packages
- Обновляет таблицу processed_payments
- Обновляет таблицу analyses
- Создает индексы
- Конвертирует активные подписки и дополнительные анализы в токены
- Генерирует уведомления пользователям о новом балансе
"""

import aiosqlite
from pathlib import Path
from datetime import datetime
from shutil import copy2
from typing import Dict, List, Tuple

from database.models import (
    CREATE_TOKEN_TRANSACTIONS_TABLE,
    CREATE_TOKEN_PACKAGES_TABLE,
)
import config


async def check_column_exists(db: aiosqlite.Connection, table: str, column: str) -> bool:
    """Проверить существование колонки в таблице"""
    async with db.execute(f"PRAGMA table_info({table})") as cursor:
        columns = await cursor.fetchall()
        return any(col[1] == column for col in columns)


async def check_table_exists(db: aiosqlite.Connection, table: str) -> bool:
    """Проверить существование таблицы"""
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ) as cursor:
        result = await cursor.fetchone()
        return result is not None


async def initialize_token_packages(db: aiosqlite.Connection):
    """Инициализировать пакеты токенов из конфигурации"""
    async with db.execute("SELECT COUNT(*) as count FROM token_packages") as cursor:
        row = await cursor.fetchone()
        existing_count = row[0] if row else 0
    
    if existing_count == 0:
        packages = config.config.TOKEN_PACKAGES
        for package_key, package_data in packages.items():
            await db.execute(
                """INSERT INTO token_packages (name, tokens, price_rub, price_usd, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                (
                    package_data['name'],
                    package_data['tokens'],
                    package_data['price_rub'],
                    package_data['price_usd']
                )
            )
        print(f"✓ Инициализированы пакеты токенов: {', '.join(packages.keys())}")
    else:
        print(f"⚠ Пакеты токенов уже инициализированы ({existing_count} пакетов)")


async def migrate_database(db_path: Path) -> dict:
    """
    Выполнить миграцию базы данных для поддержки токенов
    
    Returns:
        dict: Результат миграции с информацией о выполненных операциях
    """
    result = {
        'users_table_updated': False,
        'token_transactions_created': False,
        'token_packages_created': False,
        'token_packages_initialized': False,
        'processed_payments_updated': False,
        'analyses_updated': False,
        'indices_created': [],
        'errors': []
    }
    
    async with aiosqlite.connect(db_path) as db:
        try:
            # 1. Проверка и добавление token_balance в users
            if not await check_column_exists(db, 'users', 'token_balance'):
                await db.execute("ALTER TABLE users ADD COLUMN token_balance INTEGER DEFAULT 10")
                await db.commit()
                result['users_table_updated'] = True
                print("✓ Добавлена колонка token_balance в таблицу users")
            else:
                print("⚠ Колонка token_balance уже существует в таблице users")
            
            # 2. Проверка и добавление analysis_type в analyses
            if not await check_column_exists(db, 'analyses', 'analysis_type'):
                await db.execute("ALTER TABLE analyses ADD COLUMN analysis_type TEXT DEFAULT 'basic'")
                await db.commit()
                result['analyses_updated'] = True
                print("✓ Добавлена колонка analysis_type в таблицу analyses")
            else:
                print("⚠ Колонка analysis_type уже существует в таблице analyses")
            
            # 3. Проверка и добавление tokens_spent в analyses
            if not await check_column_exists(db, 'analyses', 'tokens_spent'):
                await db.execute("ALTER TABLE analyses ADD COLUMN tokens_spent INTEGER DEFAULT 0")
                await db.commit()
                result['analyses_updated'] = True
                print("✓ Добавлена колонка tokens_spent в таблицу analyses")
            else:
                print("⚠ Колонка tokens_spent уже существует в таблице analyses")
            
            # 4. Создание таблицы token_transactions
            if not await check_table_exists(db, 'token_transactions'):
                await db.execute(CREATE_TOKEN_TRANSACTIONS_TABLE)
                await db.commit()
                result['token_transactions_created'] = True
                print("✓ Создана таблица token_transactions")
            else:
                print("⚠ Таблица token_transactions уже существует")
            
            # 5. Создание таблицы token_packages
            if not await check_table_exists(db, 'token_packages'):
                await db.execute(CREATE_TOKEN_PACKAGES_TABLE)
                await db.commit()
                result['token_packages_created'] = True
                print("✓ Создана таблица token_packages")
            else:
                print("⚠ Таблица token_packages уже существует")
            
            # 5.1 Инициализация пакетов токенов
            await initialize_token_packages(db)
            await db.commit()
            result['token_packages_initialized'] = True
            
            # 6. Обновление таблицы processed_payments
            processed_payments_updated = False
            
            # Добавление tokens_added
            if not await check_column_exists(db, 'processed_payments', 'tokens_added'):
                await db.execute(
                    "ALTER TABLE processed_payments ADD COLUMN tokens_added INTEGER"
                )
                processed_payments_updated = True
                print("✓ Добавлена колонка tokens_added в таблицу processed_payments")
            
            # Добавление package_name
            if not await check_column_exists(db, 'processed_payments', 'package_name'):
                await db.execute(
                    "ALTER TABLE processed_payments ADD COLUMN package_name TEXT"
                )
                processed_payments_updated = True
                print("✓ Добавлена колонка package_name в таблицу processed_payments")
            
            # Добавление amount_paid
            if not await check_column_exists(db, 'processed_payments', 'amount_paid'):
                await db.execute(
                    "ALTER TABLE processed_payments ADD COLUMN amount_paid REAL"
                )
                processed_payments_updated = True
                print("✓ Добавлена колонка amount_paid в таблицу processed_payments")
            
            # Добавление currency
            if not await check_column_exists(db, 'processed_payments', 'currency'):
                await db.execute(
                    "ALTER TABLE processed_payments ADD COLUMN currency TEXT"
                )
                processed_payments_updated = True
                print("✓ Добавлена колонка currency в таблицу processed_payments")
            
            if processed_payments_updated:
                await db.commit()
                result['processed_payments_updated'] = True
            
            # 7. Создание индексов
            indices = [
                ("idx_users_token_balance", "CREATE INDEX IF NOT EXISTS idx_users_token_balance ON users(token_balance)"),
                ("idx_analyses_user_type", "CREATE INDEX IF NOT EXISTS idx_analyses_user_type ON analyses(user_id, analysis_type, created_at DESC)"),
                ("idx_token_transactions_user", "CREATE INDEX IF NOT EXISTS idx_token_transactions_user ON token_transactions(user_id, created_at DESC)"),
                ("idx_token_transactions_payment", "CREATE INDEX IF NOT EXISTS idx_token_transactions_payment ON token_transactions(payment_id)")
            ]
            
            for index_name, index_sql in indices:
                try:
                    await db.execute(index_sql)
                    result['indices_created'].append(index_name)
                    print(f"✓ Создан индекс {index_name}")
                except Exception as e:
                    result['errors'].append(f"Ошибка создания индекса {index_name}: {e}")
                    print(f"✗ Ошибка создания индекса {index_name}: {e}")
            
            await db.commit()
            
        except Exception as e:
            result['errors'].append(f"Ошибка миграции: {e}")
            print(f"✗ Ошибка миграции: {e}")
            raise
    
    return result


async def _fetch_users_for_migration(db: aiosqlite.Connection) -> List[Dict]:
    """Получить пользователей и минимально необходимые поля для конверсии."""
    db.row_factory = aiosqlite.Row
    async with db.execute(
        """
        SELECT user_id, is_premium, premium_until, additional_analyses, COALESCE(token_balance, 0) AS token_balance
        FROM users
        """
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


def _subscription_to_tokens(plan: str) -> int:
    """Сопоставление подписки количеству токенов согласно требованиям."""
    mapping = {
        'basic': 50,
        'trader': 200,
        'pro': 500,
        'elite': 1500,
    }
    return mapping.get(plan, 0)


async def _detect_subscription_plan(db: aiosqlite.Connection, user_id: int) -> str:
    """Определить последний план подписки пользователя по таблице subscriptions или эвристике."""
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT subscription_type FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        return row['subscription_type'] if row and row['subscription_type'] else 'free'


async def convert_subscriptions_to_tokens(db_path: Path) -> Dict:
    """
    Конвертировать активные подписки и дополнительные анализы в токены.
    - Basic → 50, Trader → 200, Pro → 500, Elite → 1500
    - Доп. анализы → 3 токена за каждый
    - Записать транзакции типа 'bonus' с описанием миграции
    Возвращает суммарную статистику.
    """
    stats = {
        'users_processed': 0,
        'users_with_subscription_tokens': 0,
        'users_with_additional_tokens': 0,
        'total_tokens_added': 0,
        'transactions_created': 0,
    }

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        users = await _fetch_users_for_migration(db)

        async with db.execute('BEGIN'):
            for u in users:
                user_id = u['user_id']
                current_balance = int(u.get('token_balance') or 0)
                tokens_to_add = 0

                # Подписка → токены
                plan = await _detect_subscription_plan(db, user_id)
                plan_tokens = _subscription_to_tokens(plan)
                if plan_tokens > 0:
                    tokens_to_add += plan_tokens
                    stats['users_with_subscription_tokens'] += 1

                # Дополнительные анализы → токены (по 3 за анализ)
                additional = int(u.get('additional_analyses') or 0)
                if additional > 0:
                    add_tokens = additional * 3
                    tokens_to_add += add_tokens
                    stats['users_with_additional_tokens'] += 1

                if tokens_to_add <= 0:
                    stats['users_processed'] += 1
                    continue

                balance_before = current_balance
                balance_after = balance_before + tokens_to_add

                # Обновить баланс пользователя
                await db.execute(
                    "UPDATE users SET token_balance = ? WHERE user_id = ?",
                    (balance_after, user_id)
                )

                # Записать транзакцию миграции
                await db.execute(
                    """
                    INSERT INTO token_transactions (
                        user_id, amount, transaction_type, description, balance_before, balance_after, payment_id
                    ) VALUES (?, ?, 'bonus', ?, ?, ?, NULL)
                    """,
                    (
                        user_id,
                        tokens_to_add,
                        f'Миграция подписки {plan} и дополнительных анализов ({additional})',
                        balance_before,
                        balance_after,
                    )
                )

                stats['users_processed'] += 1
                stats['total_tokens_added'] += tokens_to_add
                stats['transactions_created'] += 1

            await db.commit()

    return stats


def backup_database_file(db_path: Path) -> Path:
    """Создать резервную копию файла БД рядом с исходным файлом."""
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_path = db_path.with_suffix(f".backup_{ts}.sqlite")
    copy2(db_path, backup_path)
    return backup_path


async def verify_migration(db_path: Path) -> Dict:
    """Быстрая проверка корректности миграции: наличие таблиц/колонок и непустой users."""
    checks = {
        'users_has_token_balance': False,
        'has_token_transactions': False,
        'has_token_packages': False,
        'analyses_has_tokens_and_type': False,
        'users_count': 0,
        'token_transactions_count': 0,
    }
    async with aiosqlite.connect(db_path) as db:
        # users.token_balance
        checks['users_has_token_balance'] = await check_column_exists(db, 'users', 'token_balance')
        # analyses columns
        has_type = await check_column_exists(db, 'analyses', 'analysis_type')
        has_spent = await check_column_exists(db, 'analyses', 'tokens_spent')
        checks['analyses_has_tokens_and_type'] = bool(has_type and has_spent)
        # tables
        checks['has_token_transactions'] = await check_table_exists(db, 'token_transactions')
        checks['has_token_packages'] = await check_table_exists(db, 'token_packages')
        # counts
        async with db.execute('SELECT COUNT(*) FROM users') as c:
            checks['users_count'] = (await c.fetchone())[0]
        async with db.execute('SELECT COUNT(*) FROM token_transactions') as c:
            checks['token_transactions_count'] = (await c.fetchone())[0]
    return checks


async def generate_user_notifications(db_path: Path) -> List[Tuple[int, str]]:
    """
    Сформировать тексты уведомлений о миграции для всех пользователей с ненулевым балансом токенов.
    Возвращает список пар (user_id, message).
    """
    notifications: List[Tuple[int, str]] = []
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, token_balance FROM users WHERE COALESCE(token_balance, 0) > 0"
        ) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                uid = r['user_id']
                balance = r['token_balance']
                text = (
                    "🔄 Переход на систему токенов завершён!\n\n"
                    f"Ваш новый баланс: {balance} токенов.\n\n"
                    "Теперь анализы оплачиваются токенами:\n"
                    "• Базовый анализ — 3 токена\n"
                    "• Расширенный анализ — 10 токенов\n\n"
                    "Спасибо, что с нами!"
                )
                notifications.append((uid, text))
    return notifications


async def main():
    """Основная функция для запуска миграции с бэкапом, конверсией и проверкой."""
    db_path = config.config.DATABASE_PATH

    print("=" * 60)
    print("Миграция базы данных для системы токенов")
    print("=" * 60)
    print(f"Путь к БД: {db_path}")
    print()

    if not db_path.exists():
        print(f"❌ База данных не найдена по пути: {db_path}")
        return

    try:
        # Бэкап файла БД
        backup_path = backup_database_file(db_path)
        print(f"🗄 Резервная копия создана: {backup_path}")

        # Схема: столбцы/таблицы/индексы
        result = await migrate_database(db_path)

        # Конверсия подписок/доп.анализов → токены
        conv = await convert_subscriptions_to_tokens(db_path)

        # Проверка
        checks = await verify_migration(db_path)

        print()
        print("=" * 60)
        print("Миграция завершена")
        print("=" * 60)

        if result['errors']:
            print("\n⚠ Ошибки миграции схемы:")
            for error in result['errors']:
                print(f"  - {error}")
        else:
            print("\n✓ Схема обновлена успешно")

        print("\nСтатистика конверсии:")
        print(f"  Пользователей обработано: {conv['users_processed']}")
        print(f"  Пользователей с токенами за подписку: {conv['users_with_subscription_tokens']}")
        print(f"  Пользователей с токенами за доп.анализы: {conv['users_with_additional_tokens']}")
        print(f"  Добавлено токенов всего: {conv['total_tokens_added']}")
        print(f"  Создано транзакций: {conv['transactions_created']}")

        print("\нПроверки:")
        print(f"  users.token_balance: {checks['users_has_token_balance']}")
        print(f"  analyses.*: {checks['analyses_has_tokens_and_type']}")
        print(f"  token_transactions: {checks['has_token_transactions']}")
        print(f"  token_packages: {checks['has_token_packages']}")
        print(f"  users_count: {checks['users_count']}")
        print(f"  token_transactions_count: {checks['token_transactions_count']}")

        # Подготовить тексты уведомлений (отправка выполняется приложением)
        notifications = await generate_user_notifications(db_path)
        print(f"\n📬 Готово уведомлений к отправке: {len(notifications)}")
        sample = notifications[:3]
        if sample:
            print("\nПример уведомления:")
            for uid, msg in sample:
                print(f"- user_id={uid}: {msg.splitlines()[0]}")

        print("\n✓ Все операции завершены")

    except Exception as e:
        print(f"\n❌ Критическая ошибка миграции: {e}")
        raise


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

