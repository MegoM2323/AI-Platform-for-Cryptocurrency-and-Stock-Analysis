"""
Класс для работы с базой данных SQLite
"""

import aiosqlite
import asyncio
from datetime import datetime, date
from typing import Optional, Dict, List, Any
from pathlib import Path

from .models import ALL_SCHEMAS
from .news_models import NewsArticle


class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._pool_lock = asyncio.Semaphore(5)
        
    async def init_db(self):
        """Инициализация базы данных - создание таблиц"""
        async with self._pool_lock:
            db = await aiosqlite.connect(self.db_path)
            for schema in ALL_SCHEMAS:
                await db.execute(schema)
            await db.commit()
            # Обновление таблицы subscriptions до новой схемы (добавление недостающих колонок)
            try:
                async with db.execute("PRAGMA table_info(subscriptions)") as cursor:
                    cols = [row[1] for row in await cursor.fetchall()]
                alter_ops = []
                if 'tokens_per_month' not in cols:
                    alter_ops.append("ALTER TABLE subscriptions ADD COLUMN tokens_per_month INTEGER DEFAULT 0")
                if 'payment_method_id' not in cols:
                    alter_ops.append("ALTER TABLE subscriptions ADD COLUMN payment_method_id TEXT")
                if 'next_charge_at' not in cols:
                    alter_ops.append("ALTER TABLE subscriptions ADD COLUMN next_charge_at TIMESTAMP")
                if 'status' not in cols:
                    alter_ops.append("ALTER TABLE subscriptions ADD COLUMN status TEXT DEFAULT 'active'")
                for sql in alter_ops:
                    try:
                        await db.execute(sql)
                    except Exception:
                        pass
                if alter_ops:
                    await db.commit()
            except Exception:
                pass
            await db.close()

    # -------------------
    # News storage layer
    # -------------------
    async def save_news_articles(self, articles: List[NewsArticle]) -> int:
        """Сохранить список новостных статей (upsert по id). Возвращает число сохраненных записей."""
        if not articles:
            return 0
        saved = 0
        async with self._pool_lock:
            db = await aiosqlite.connect(self.db_path)
            for a in articles:
                try:
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO news_articles (
                            id, title, description, content, url, published_at, source, symbol, sentiment_score, relevance_score
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            a.id, a.title, a.description, a.content, a.url,
                            a.published_at.isoformat() if a.published_at else None,
                            a.source, a.symbol, a.sentiment_score, a.relevance_score
                        )
                    )
                    saved += 1
                except Exception:
                    # Пропускаем дубликаты/ошибки отдельных статей, продолжаем сохранять остальные
                    pass
            await db.commit()
            await db.close()
        return saved

    async def get_recent_news(self, symbol: str, hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить новости по символу за последние N часов."""
        async with self._pool_lock:
            db = await aiosqlite.connect(self.db_path)
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM news_articles
                WHERE symbol = ? AND published_at >= datetime('now', ?)
                ORDER BY published_at DESC
                LIMIT ?
                """,
                (symbol, f'-{hours} hours', limit)
            ) as cursor:
                rows = await cursor.fetchall()
            await db.close()
            return [dict(r) for r in rows]

    async def get_cached_analysis(self, symbol: str, analysis_type: str) -> Optional[str]:
        """Получить кэшированный результат анализа, если не истек срок."""
        async with self._pool_lock:
            db = await aiosqlite.connect(self.db_path)
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT result_data FROM analysis_cache
                WHERE symbol = ? AND analysis_type = ? AND (expires_at IS NULL OR expires_at > datetime('now'))
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (symbol, analysis_type)
            ) as cursor:
                row = await cursor.fetchone()
            await db.close()
            return row['result_data'] if row else None

    async def set_cached_analysis(self, symbol: str, analysis_type: str, result_data: str, ttl_seconds: int) -> None:
        """Сохранить кэш результата анализа на ttl_seconds секунд."""
        async with self._pool_lock:
            db = await aiosqlite.connect(self.db_path)
            await db.execute(
                """
                INSERT INTO analysis_cache (symbol, analysis_type, result_data, expires_at)
                VALUES (?, ?, ?, datetime('now', ?))
                """,
                (symbol, analysis_type, result_data, f'+{ttl_seconds} seconds')
            )
            await db.commit()
            await db.close()

    async def cleanup_expired_cache(self) -> int:
        """Удалить просроченные записи кэша. Возвращает число удалённых записей."""
        async with self._pool_lock:
            db = await aiosqlite.connect(self.db_path)
            cur = await db.execute(
                "DELETE FROM analysis_cache WHERE expires_at IS NOT NULL AND expires_at <= datetime('now')"
            )
            await db.commit()
            rowcount = cur.rowcount or 0
            await db.close()
            return rowcount

    async def cleanup_old_news(self, older_than_hours: int = 24 * 14) -> int:
        """Удалить слишком старые новости (по умолчанию старше 14 дней). Возвращает число удалённых записей."""
        async with self._pool_lock:
            db = await aiosqlite.connect(self.db_path)
            cur = await db.execute(
                "DELETE FROM news_articles WHERE published_at < datetime('now', ?)",
                (f'-{older_than_hours} hours',)
            )
            await db.commit()
            rowcount = cur.rowcount or 0
            await db.close()
            return rowcount
    
    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получить пользователя по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?", 
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
    
    async def create_user(self, user_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None):
        """Создать нового пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO users (user_id, username, first_name, last_name) 
                   VALUES (?, ?, ?, ?)""",
                (user_id, username, first_name, last_name)
            )
            await db.commit()
    
    async def get_or_create_user(self, user_id: int, username: str = None,
                                first_name: str = None, last_name: str = None) -> Dict:
        """Получить или создать пользователя"""
        user = await self.get_user(user_id)
        if not user:
            await self.create_user(user_id, username, first_name, last_name)
            user = await self.get_user(user_id)
        return user
    
    async def check_analysis_limit(self, user_id: int, max_free: int, max_premium: int) -> bool:
        """
        Проверить, может ли пользователь выполнить анализ
        Возвращает True, если анализ доступен
        """
        user = await self.get_user(user_id)
        if not user:
            return False
        
        # Проверяем премиум статус
        is_premium = user.get('is_premium', 0)
        if is_premium:
            premium_until = user.get('premium_until')
            if premium_until:
                premium_until = datetime.fromisoformat(premium_until)
                if premium_until < datetime.now():
                    # Премиум истек
                    await self.revoke_premium(user_id)
                    is_premium = 0
        
        # Получаем оставшиеся анализы в месяце
        remaining = await self.get_remaining_analyses(user_id, max_free, max_premium)
        return remaining > 0
    
    async def increment_analysis_count(self, user_id: int):
        """
        Увеличить счетчик анализов (для статистики).
        В токеновой модели лимиты не используются - токены списываются через TokenManager.
        """
        user = await self.get_user(user_id)
        if not user:
            return
        
        # Обновляем счетчик анализов на сегодня (для статистики)
        from datetime import date
        today = date.today()
        
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем текущее значение счетчика
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT analyses_count_today, last_analysis_date FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    last_analysis_date = row['last_analysis_date']
                    if last_analysis_date:
                        try:
                            last_date = date.fromisoformat(last_analysis_date)
                            if last_date != today:
                                # Новый день - сбрасываем счетчик
                                count = 1
                            else:
                                # Тот же день - увеличиваем счетчик
                                count = (row['analyses_count_today'] or 0) + 1
                        except:
                            count = 1
                    else:
                        count = 1
                else:
                    count = 1
            
            # Обновляем счетчик
            await db.execute(
                """UPDATE users 
                   SET analyses_count_today = ?, last_analysis_date = ?
                   WHERE user_id = ?""",
                (count, today.isoformat(), user_id)
            )
            await db.commit()
    
    async def reset_daily_analyses(self, user_id: int):
        """Сбросить счетчик анализов на сегодня"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE users 
                   SET analyses_count_today = 0,
                       last_analysis_date = DATE('now')
                   WHERE user_id = ?""",
                (user_id,)
            )
            await db.commit()
    
    async def save_analysis(self, user_id: int, token_symbol: str, analysis_text: str):
        """Сохранить результат анализа"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO analyses (user_id, token_symbol, analysis_text)
                   VALUES (?, ?, ?)""",
                (user_id, token_symbol, analysis_text)
            )
            await db.commit()
    
    async def get_user_analyses(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Получить историю анализов пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM analyses 
                   WHERE user_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT ?""",
                (user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def grant_premium(self, user_id: int, days: int = 30):
        """Выдать премиум подписку"""
        from datetime import timedelta
        premium_until = datetime.now() + timedelta(days=days)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE users 
                   SET is_premium = 1, premium_until = ?
                   WHERE user_id = ?""",
                (premium_until.isoformat(), user_id)
            )
            await db.commit()
    
    async def revoke_premium(self, user_id: int):
        """Отозвать премиум подписку"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE users 
                   SET is_premium = 0, premium_until = NULL
                   WHERE user_id = ?""",
                (user_id,)
            )
            await db.commit()
    
    async def create_subscription(self, user_id: int, subscription_type: str, amount: float, tokens_per_month: int = 0,
                                  payment_method_id: str = None, next_charge_at: Optional[datetime] = None):
        """Создать/обновить запись о подписке с рекуррентными начислениями токенов."""
        if next_charge_at is None:
            from datetime import timedelta
            next_charge_at = datetime.now() + timedelta(days=30)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO subscriptions (user_id, subscription_type, amount, tokens_per_month, payment_method_id, next_charge_at, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
                """,
                (user_id, subscription_type, amount, tokens_per_month, payment_method_id, next_charge_at.isoformat())
            )
            await db.commit()

    async def update_subscription_payment_method(self, user_id: int, payment_method_id: str):
        """Сохранить идентификатор метода оплаты для рекуррентных списаний."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE subscriptions
                SET payment_method_id = ?
                WHERE user_id = ? AND status = 'active'
                """,
                (payment_method_id, user_id)
            )
            await db.commit()

    async def schedule_next_charge(self, user_id: int, days: int = 30):
        """Передвинуть дату следующего списания."""
        from datetime import timedelta
        next_date = datetime.now() + timedelta(days=days)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE subscriptions
                SET next_charge_at = ?
                WHERE user_id = ? AND status = 'active'
                """,
                (next_date.isoformat(), user_id)
            )
            await db.commit()

    async def get_due_subscriptions(self) -> List[Dict[str, Any]]:
        """Получить активные подписки, требующие списания (next_charge_at <= now)."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM subscriptions
                WHERE status = 'active' AND next_charge_at IS NOT NULL AND next_charge_at <= datetime('now')
                """
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def cancel_subscription(self, user_id: int) -> bool:
        """Отменить подписку пользователя: отключить автопродление и будущие списания."""
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                """
                UPDATE subscriptions
                SET status = 'cancelled', payment_method_id = NULL, next_charge_at = NULL
                WHERE user_id = ? AND status = 'active'
                """,
                (user_id,)
            )
            await db.commit()
            return (cur.rowcount or 0) > 0
    
    
    async def get_remaining_analyses(self, user_id: int, max_free: int, max_premium: int) -> int:
        """
        Получить количество оставшихся анализов
        Возвращает общее количество доступных анализов, включая дополнительные
        """
        user = await self.get_user(user_id)
        if not user:
            return 0
        
        # Получаем количество анализов за текущий месяц
        from datetime import datetime, date
        current_month = date.today().replace(day=1)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT COUNT(*) as count FROM analyses 
                   WHERE user_id = ? AND DATE(created_at) >= ?""",
                (user_id, current_month.isoformat())
            ) as cursor:
                row = await cursor.fetchone()
                monthly_count = row['count'] if row else 0
        
        is_premium = user.get('is_premium', 0)
        limit = max_premium if is_premium else max_free
        
        # Получаем дополнительные анализы
        additional_analyses = user.get('additional_analyses', 0)
        
        # Общее количество доступных анализов = месячный лимит - использованные + дополнительные
        monthly_remaining = max(0, limit - monthly_count)
        total_remaining = monthly_remaining + additional_analyses
        
        return total_remaining
    
    async def add_analyses(self, user_id: int, count: int):
        """Добавить дополнительные анализы пользователю"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE users 
                   SET additional_analyses = additional_analyses + ?
                   WHERE user_id = ?""",
                (count, user_id)
            )
            await db.commit()
    
    async def get_additional_analyses(self, user_id: int) -> int:
        """Получить количество дополнительных анализов"""
        user = await self.get_user(user_id)
        if not user:
            return 0
        return user.get('additional_analyses', 0)
    
    async def get_monthly_analyses_count(self, user_id: int, month_start: date) -> int:
        """Получить количество анализов за месяц"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT COUNT(*) as count FROM analyses 
                   WHERE user_id = ? AND DATE(created_at) >= ?""",
                (user_id, month_start.isoformat())
            ) as cursor:
                row = await cursor.fetchone()
                return row['count'] if row else 0
    
    async def use_additional_analysis(self, user_id: int) -> bool:
        """Использовать дополнительный анализ"""
        user = await self.get_user(user_id)
        if not user:
            return False
        
        additional = user.get('additional_analyses', 0)
        if additional <= 0:
            return False
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE users 
                   SET additional_analyses = additional_analyses - 1
                   WHERE user_id = ?""",
                (user_id,)
            )
            await db.commit()
        return True
    
    async def get_user_subscription_plan(self, user_id: int) -> str:
        """Получить план подписки пользователя"""
        user = await self.get_user(user_id)
        if not user:
            return 'free'
        
        # Проверяем премиум статус
        is_premium = user.get('is_premium', 0)
        if is_premium:
            premium_until = user.get('premium_until')
            if premium_until:
                try:
                    premium_until_dt = datetime.fromisoformat(premium_until.replace('Z', '+00:00'))
                    if premium_until_dt > datetime.now():
                        # Получаем последнюю подписку из базы данных
                        async with aiosqlite.connect(self.db_path) as db_conn:
                            db_conn.row_factory = aiosqlite.Row
                            async with db_conn.execute(
                                "SELECT subscription_type FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                                (user_id,)
                            ) as cursor:
                                row = await cursor.fetchone()
                                if row:
                                    return row['subscription_type']
                                else:
                                    # Если нет записи в subscriptions, определяем по дополнительным анализам
                                    additional_analyses = user.get('additional_analyses', 0)
                                    
                                    if additional_analyses >= 500:
                                        return 'elite'
                                    elif additional_analyses >= 150:
                                        return 'pro'
                                    elif additional_analyses >= 50:
                                        return 'trader'
                                    elif additional_analyses >= 15:
                                        return 'basic'
                                    else:
                                        return 'premium'  # Общий премиум статус
                    else:
                        # Премиум истек
                        await self.revoke_premium(user_id)
                        return 'free'
                except:
                    return 'free'
        
        return 'free'
    
    async def is_payment_processed(self, payment_id: str) -> bool:
        """
        Проверить, был ли платеж уже обработан
        
        Args:
            payment_id: ID платежа
            
        Returns:
            bool: True если платеж уже обработан
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT payment_id FROM processed_payments WHERE payment_id = ?",
                (payment_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None
    
    async def mark_payment_processed(
        self,
        payment_id: str,
        user_id: int, 
        payment_type: str,
        subscription_type: str,
        analyses_added: int,
        plan_name: str,
        tokens_added: int = None
    ) -> bool:
        """
        Пометить платеж как обработанный
        
        Args:
            payment_id: ID платежа
            user_id: ID пользователя
            payment_type: Тип платежа
            subscription_type: Тип подписки
            analyses_added: Количество начисленных анализов (для совместимости)
            plan_name: Название плана
            tokens_added: Количество начисленных токенов (опционально)
            
        Returns:
            bool: True если успешно
        """
        try:
            # Если tokens_added не указан, используем analyses_added (для совместимости)
            if tokens_added is None:
                tokens_added = analyses_added
            
            async with aiosqlite.connect(self.db_path) as db:
                # Проверяем, есть ли колонка tokens_added
                db.row_factory = aiosqlite.Row
                async with db.execute("PRAGMA table_info(processed_payments)") as cursor:
                    columns = [row['name'] for row in await cursor.fetchall()]
                    has_tokens_added = 'tokens_added' in columns
                
                if has_tokens_added:
                    await db.execute(
                        """INSERT INTO processed_payments 
                           (payment_id, user_id, payment_type, subscription_type, analyses_added, tokens_added, plan_name)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (payment_id, user_id, payment_type, subscription_type, analyses_added, tokens_added, plan_name)
                    )
                else:
                    await db.execute(
                        """INSERT INTO processed_payments 
                           (payment_id, user_id, payment_type, subscription_type, analyses_added, plan_name)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (payment_id, user_id, payment_type, subscription_type, analyses_added, plan_name)
                    )
                await db.commit()
                return True
        except Exception as e:
            # Если платеж уже обработан (PRIMARY KEY constraint), это нормально
            if "UNIQUE constraint failed" in str(e) or "PRIMARY KEY constraint failed" in str(e):
                return False
            raise
    
    async def get_processed_payment(self, payment_id: str) -> Optional[Dict]:
        """
        Получить информацию об обработанном платеже
        
        Args:
            payment_id: ID платежа
            
        Returns:
            Dict с информацией о платеже или None
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM processed_payments WHERE payment_id = ?",
                (payment_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

