"""
Класс для работы с базой данных SQLite
"""

import aiosqlite
from datetime import datetime, date
from typing import Optional, Dict, List
from pathlib import Path

from .models import ALL_SCHEMAS


class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        
    async def init_db(self):
        """Инициализация базы данных - создание таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            for schema in ALL_SCHEMAS:
                await db.execute(schema)
            await db.commit()
    
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
        """Увеличить счетчик анализов (теперь не нужен, так как считаем по месяцам)"""
        # Метод оставлен для совместимости, но логика теперь в get_remaining_analyses
        pass
    
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
    
    async def create_subscription(self, user_id: int, subscription_type: str, amount: float):
        """Создать запись о подписке"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO subscriptions (user_id, subscription_type, amount)
                   VALUES (?, ?, ?)""",
                (user_id, subscription_type, amount)
            )
            await db.commit()
    
    
    async def get_remaining_analyses(self, user_id: int, max_free: int, max_premium: int) -> int:
        """Получить количество оставшихся анализов в месяце"""
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
        return max(0, limit - monthly_count)
    
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
                        # Определяем тип подписки по количеству анализов
                        # Это упрощенная логика, можно расширить
                        return 'premium'
                    else:
                        # Премиум истек
                        await self.revoke_premium(user_id)
                        return 'free'
                except:
                    return 'free'
        
        return 'free'

