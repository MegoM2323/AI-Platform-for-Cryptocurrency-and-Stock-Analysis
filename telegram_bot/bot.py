"""
Основной файл Telegram бота
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
from database import Database
from .handlers import routers


# Настройка логирования
def setup_logging():
    """Настройка логирования с учетом debug режима"""
    log_level = getattr(logging, config.DEBUG_LOG_LEVEL.upper(), logging.INFO)
    
    # Формат логов
    if config.DEBUG_MODE:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    else:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=log_level,
        format=log_format
    )
    
    # Дополнительная настройка для debug режима
    if config.DEBUG_MODE:
        # Включаем debug для всех модулей
        logging.getLogger('aiogram').setLevel(logging.DEBUG)
        logging.getLogger('aiohttp').setLevel(logging.DEBUG)
        logging.getLogger('twelvedata').setLevel(logging.DEBUG)
        
        logger = logging.getLogger(__name__)
        logger.info("🔧 DEBUG режим активирован")
        logger.debug(f"Debug настройки: {config.get_debug_info()}")
    else:
        logger = logging.getLogger(__name__)
        logger.info("🚀 Продакшн режим")

# Инициализация логирования
setup_logging()
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, db: Database):
    """Действия при запуске бота"""
    logger.info("Инициализация базы данных...")
    await db.init_db()
    logger.info("База данных инициализирована")
    
    # Получаем информацию о боте
    bot_info = await bot.get_me()
    logger.info(f"Бот запущен: @{bot_info.username}")
    
    # Debug информация
    if config.DEBUG_MODE:
        logger.debug(f"Bot ID: {bot_info.id}")
        logger.debug(f"Bot Username: @{bot_info.username}")
        logger.debug(f"Bot First Name: {bot_info.first_name}")
        logger.debug(f"Database Path: {config.DATABASE_PATH}")
        logger.debug(f"AI Model: {config.AI_MODEL}")
        logger.debug(f"Debug Settings: {config.get_debug_info()}")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Бот останавливается...")
    await bot.session.close()


async def start_bot():
    """Запуск бота"""
    try:
        # Debug информация о запуске
        if config.DEBUG_MODE:
            logger.debug("🔧 Запуск в DEBUG режиме")
            logger.debug(f"Config validation: {not config.DEBUG_SKIP_VALIDATION}")
        
        # Валидация конфигурации
        config.validate()
        
        # Создаем экземпляр бота
        bot = Bot(
            token=config.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        if config.DEBUG_MODE:
            logger.debug("Bot instance created successfully")
        
        # Создаем диспетчер
        dp = Dispatcher()
        
        # Создаем экземпляр базы данных
        db = Database(config.DATABASE_PATH)
        
        # Регистрируем middleware для передачи db в handlers
        @dp.update.outer_middleware()
        async def db_middleware(handler, event, data):
            """Middleware для передачи объекта БД в хендлеры"""
            data['db'] = db
            return await handler(event, data)
        
        # Регистрируем роутеры
        for router in routers:
            dp.include_router(router)
        
        # Запуск
        await on_startup(bot, db)
        
        try:
            # Запускаем polling
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        finally:
            await on_shutdown(bot)
            
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise


def run():
    """Запуск бота (синхронная обертка)"""
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise


if __name__ == "__main__":
    run()

