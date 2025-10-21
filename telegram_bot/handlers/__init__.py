"""
Обработчики команд и сообщений бота
"""

from .start_help import router as start_help_router
from .analysis import router as analysis_router
from .payments import router as payments_router

# Список всех роутеров для регистрации
routers = [
    start_help_router,
    analysis_router,
    payments_router
]

__all__ = ['routers']

