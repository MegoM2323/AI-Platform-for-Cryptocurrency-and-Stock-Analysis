"""
Обработчики команд и сообщений бота
"""

from .start_help import router as start_help_router
from .analysis import router as analysis_router
from .payments import router as payments_router
from .enhanced_analysis import router as enhanced_analysis_router
from .token_payments import router as token_payments_router

# Список всех роутеров для регистрации
routers = [
    start_help_router,
    analysis_router,
    payments_router,
    token_payments_router,
    enhanced_analysis_router,
]

__all__ = ['routers']

