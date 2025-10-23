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
    
    # YooKassa Payment System
    YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
    YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
    YOOKASSA_TEST_MODE = os.getenv('YOOKASSA_TEST_MODE', 'true').lower() in ('true', '1', 'yes', 'on')
    TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME')
    
    # NOWPayments Crypto Payment System
    NOWPAYMENTS_API_KEY = os.getenv('NOWPAYMENTS_API_KEY')
    NOWPAYMENTS_PUBLIC_API_KEY = os.getenv('NOWPAYMENTS_PUBLIC_API_KEY')
    NOWPAYMENTS_IPN_SECRET = os.getenv('NOWPAYMENTS_IPN_SECRET')
    NOWPAYMENTS_SANDBOX = os.getenv('NOWPAYMENTS_SANDBOX', 'true').lower() in ('true', '1', 'yes', 'on')
    NOWPAYMENTS_PAYOUT_ADDRESS = os.getenv('NOWPAYMENTS_PAYOUT_ADDRESS')
    NOWPAYMENTS_PAYOUT_CURRENCY = os.getenv('NOWPAYMENTS_PAYOUT_CURRENCY', 'BTC')
    
    # Database
    DATABASE_PATH = BASE_DIR / os.getenv('DATABASE_PATH', 'crypto_analysis.db')
    
    # Subscription Limits (Monthly)
    FREE_ANALYSES_PER_MONTH = int(os.getenv('FREE_ANALYSES_PER_MONTH', 3))
    BASIC_ANALYSES_PER_MONTH = int(os.getenv('BASIC_ANALYSES_PER_MONTH', 15))
    TRADER_ANALYSES_PER_MONTH = int(os.getenv('TRADER_ANALYSES_PER_MONTH', 50))
    PRO_ANALYSES_PER_MONTH = int(os.getenv('PRO_ANALYSES_PER_MONTH', 150))
    ELITE_ANALYSES_PER_MONTH = int(os.getenv('ELITE_ANALYSES_PER_MONTH', 500))
    
    # Subscription Plans (Monthly)
    SUBSCRIPTION_PLANS = {
        'free': {
            'name': 'Free',
            'days': 30,
            'price': 0,
            'analyses_per_month': 3,
            'features': ['3 анализа в месяц', 'Базовый анализ']
        },
        'basic': {
            'name': 'Basic',
            'days': 30,
            'price': 299,
            'analyses_per_month': 15,
            'features': ['15 анализов в месяц', 'Базовый анализ']
        },
        'trader': {
            'name': 'Trader',
            'days': 30,
            'price': 899,
            'analyses_per_month': 50,
            'features': ['50 анализов в месяц', 'Расширенный анализ']
        },
        'pro': {
            'name': 'Pro',
            'days': 30,
            'price': 1590,
            'analyses_per_month': 150,
            'features': ['150 анализов в месяц', 'Полный анализ', 'Приоритетная скорость']
        },
        'elite': {
            'name': 'Elite',
            'days': 30,
            'price': 2990,
            'analyses_per_month': 500,
            'features': ['500 анализов в месяц', 'Полный анализ', 'Приоритетная скорость', "Ранний доступ к функциям"]
        }
    }
    
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

