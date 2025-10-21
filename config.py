"""
Конфигурация приложения.
Загружает настройки из .env файла.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загрузка переменных окружения
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


class Config:
    """Класс конфигурации приложения"""
    
    # Debug Mode
    DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() in ('true', '1', 'yes', 'on')
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    # OpenRouter API
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    AI_MODEL = os.getenv('AI_MODEL', 'meta-llama/llama-3.1-8b-instruct:free')
    
    # Twelve Data API
    TWELVE_DATA_API_KEY = os.getenv('TWELVE_DATA_API_KEY')
    
    # Database
    DATABASE_PATH = BASE_DIR / os.getenv('DATABASE_PATH', 'crypto_analysis.db')
    
    # Subscription Limits
    FREE_ANALYSES_PER_DAY = int(os.getenv('FREE_ANALYSES_PER_DAY', 3))
    PREMIUM_ANALYSES_PER_DAY = int(os.getenv('PREMIUM_ANALYSES_PER_DAY', 50))
    
    # Timeframe
    DEFAULT_TIMEFRAME = '1day'  # 1 day
    DEFAULT_PERIOD = 30  # 30 days history
    
    # Debug Settings
    DEBUG_LOG_LEVEL = os.getenv('DEBUG_LOG_LEVEL', 'DEBUG' if DEBUG_MODE else 'INFO')
    DEBUG_USE_MOCK_DATA = os.getenv('DEBUG_USE_MOCK_DATA', 'false').lower() in ('true', '1', 'yes', 'on')
    DEBUG_SKIP_VALIDATION = os.getenv('DEBUG_SKIP_VALIDATION', 'false').lower() in ('true', '1', 'yes', 'on')
    
    @classmethod
    def validate(cls):
        """Проверка наличия обязательных переменных окружения"""
        if cls.DEBUG_SKIP_VALIDATION:
            print("🔧 DEBUG: Пропуск валидации конфигурации")
            return True
            
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле")
        if not cls.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY не найден в .env файле")
        if not cls.TWELVE_DATA_API_KEY:
            raise ValueError("TWELVE_DATA_API_KEY не найден в .env файле")
        return True
    
    @classmethod
    def get_debug_info(cls):
        """Получить информацию о debug режиме"""
        return {
            'debug_mode': cls.DEBUG_MODE,
            'log_level': cls.DEBUG_LOG_LEVEL,
            'use_mock_data': cls.DEBUG_USE_MOCK_DATA,
            'skip_validation': cls.DEBUG_SKIP_VALIDATION
        }


# Создаем экземпляр конфигурации
config = Config()

