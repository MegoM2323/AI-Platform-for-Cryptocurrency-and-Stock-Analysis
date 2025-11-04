import time
from dataclasses import dataclass
from typing import Dict, Optional

from config import config as AppConfig


@dataclass
class UsageWindow:
    start_ts: float
    count: int


class RateLimiter:
    """Простой лимитер для NewsAPI с месячной/суточной квотой и приоритетами.

    In-memory реализация (временная). Персистентность и подробная аналитика
    будут добавлены в задачах 3.2/8.2.
    """

    def __init__(self,
                 monthly_limit: int = AppConfig.NEWSAPI_MONTHLY_LIMIT,
                 daily_limit: int = AppConfig.NEWSAPI_DAILY_LIMIT,
                 reserved_user_percent: int = AppConfig.NEWSAPI_RESERVED_USER_PERCENT) -> None:
        self.monthly_limit = monthly_limit
        self.daily_limit = daily_limit
        self.reserved_user_percent = reserved_user_percent
        self._month_usage = UsageWindow(start_ts=self._month_start(), count=0)
        self._day_usage = UsageWindow(start_ts=self._day_start(), count=0)
        self._symbol_demand: Dict[str, int] = {}

    # -----------------
    # Public interface
    # -----------------
    def can_make_request(self, is_user_requested: bool = False) -> bool:
        self._roll_windows()
        if is_user_requested:
            # Резервируем часть месячной квоты для пользовательских запросов
            reserved = int(self.monthly_limit * (self.reserved_user_percent / 100))
            available_reserved = reserved - self._month_usage.count
            if available_reserved <= 0:
                # если резерв исчерпан, падаем на общий пул
                pass
            else:
                # Проверим дневной лимит одновременно
                return self._day_usage.count < self.daily_limit and self._month_usage.count < self.monthly_limit
        return self._day_usage.count < self.daily_limit and self._month_usage.count < self.monthly_limit

    def record_request(self, symbol: Optional[str] = None) -> None:
        self._roll_windows()
        self._day_usage.count += 1
        self._month_usage.count += 1
        if symbol:
            self._symbol_demand[symbol] = self._symbol_demand.get(symbol, 0) + 1

    def get_usage_stats(self) -> Dict[str, int]:
        self._roll_windows()
        return {
            "daily_used": self._day_usage.count,
            "daily_limit": self.daily_limit,
            "monthly_used": self._month_usage.count,
            "monthly_limit": self.monthly_limit,
        }

    def get_priority_score(self, symbol: str) -> int:
        # Простая эвристика: чем выше спрос, тем выше приоритет
        return self._symbol_demand.get(symbol, 0)

    def should_fetch_news(self, symbol: str, is_user_requested: bool = False) -> bool:
        # Приоритетная эвристика: если пользователь запросил — почти всегда да,
        # иначе — тянем только при достаточном приоритете и наличии квоты
        if is_user_requested:
            return self.can_make_request(is_user_requested=True)
        priority = self.get_priority_score(symbol)
        return priority > 0 and self.can_make_request(is_user_requested=False)

    # -----------------
    # Internal helpers
    # -----------------
    def _roll_windows(self) -> None:
        now = time.time()
        # Суточное окно: начинаем с 00:00 текущих суток
        if now - self._day_usage.start_ts >= 24 * 3600:
            self._day_usage = UsageWindow(start_ts=self._day_start(), count=0)
        # Месячное окно: сбрасываем в первый день месяца
        if now - self._month_usage.start_ts >= 30 * 24 * 3600:
            self._month_usage = UsageWindow(start_ts=self._month_start(), count=0)

    def _day_start(self) -> float:
        # Начало текущих суток (00:00)
        import datetime
        today = datetime.date.today()
        return datetime.datetime.combine(today, datetime.time.min).timestamp()

    def _month_start(self) -> float:
        # Начало текущего месяца (1 число, 00:00)
        import datetime
        today = datetime.date.today()
        first_day = today.replace(day=1)
        return datetime.datetime.combine(first_day, datetime.time.min).timestamp()


