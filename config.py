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
    ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')  # ID администратора для админ-команд
    
    # OpenRouter API
    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    AI_MODEL = os.getenv('AI_MODEL', 'meta-llama/llama-3.1-8b-instruct:free')
    
    # Twelve Data API
    TWELVE_DATA_API_KEY = os.getenv('TWELVE_DATA_API_KEY')
    
    # NewsAPI (новостной фон для анализа)
    NEWSAPI_KEY = os.getenv('NEWSAPI_KEY')
    NEWSAPI_BASE_URL = os.getenv('NEWSAPI_BASE_URL', 'https://newsapi.org/v2')
    NEWSAPI_TIMEOUT_SECONDS = float(os.getenv('NEWSAPI_TIMEOUT_SECONDS', 10))
    NEWSAPI_MAX_RETRIES = int(os.getenv('NEWSAPI_MAX_RETRIES', 3))
    NEWSAPI_BACKOFF_SECONDS = float(os.getenv('NEWSAPI_BACKOFF_SECONDS', 1.0))
    
    # NewsAPI Rate Limits
    NEWSAPI_MONTHLY_LIMIT = int(os.getenv('NEWSAPI_MONTHLY_LIMIT', 500))
    NEWSAPI_DAILY_LIMIT = int(os.getenv('NEWSAPI_DAILY_LIMIT', 50))
    NEWSAPI_RESERVED_USER_PERCENT = int(os.getenv('NEWSAPI_RESERVED_USER_PERCENT', 20))  # % квоты зарезервировано под запросы пользователей
    NEWS_CACHE_HOURS = int(os.getenv('NEWS_CACHE_HOURS', 24))

    # Report Generation
    PDF_TEMPLATE_PATH = os.getenv('PDF_TEMPLATE_PATH', './templates/')
    CHART_CACHE_DIR = os.getenv('CHART_CACHE_DIR', './charts/')
    
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
    
    # Subscription Limits (Monthly) - DEPRECATED: Используются только для миграции и совместимости
    FREE_ANALYSES_PER_MONTH = int(os.getenv('FREE_ANALYSES_PER_MONTH', 3))
    BASIC_ANALYSES_PER_MONTH = int(os.getenv('BASIC_ANALYSES_PER_MONTH', 15))
    TRADER_ANALYSES_PER_MONTH = int(os.getenv('TRADER_ANALYSES_PER_MONTH', 50))
    PRO_ANALYSES_PER_MONTH = int(os.getenv('PRO_ANALYSES_PER_MONTH', 150))
    ELITE_ANALYSES_PER_MONTH = int(os.getenv('ELITE_ANALYSES_PER_MONTH', 500))
    
    # Subscription Plans (Monthly, token-based): подписка начисляет токены ежемесячно по выгодной цене
    # Примечание: тексты UI обновлены под токены; лимиты анализов больше не используются
    SUBSCRIPTION_PLANS = {
        'free': {
            'name': 'Free',
            'days': 30,
            'price': 0,
            'tokens_per_month': 0,
            'features': ['Доступ к базовым функциям']
        },
        'basic': {
            'name': 'Basic',
            'days': 30,
            'price': 249,  # немного выгоднее, чем покупать 50 токенов отдельно
            'tokens_per_month': 50,
            'features': ['50 токенов/мес', 'Выгодная цена', 'Подходит для периодического использования']
        },
        'trader': {
            'name': 'Trader',
            'days': 30,
            'price': 799,
            'tokens_per_month': 200,
            'features': ['200 токенов/мес', 'Оптимально для активной торговли']
        },
        'pro': {
            'name': 'Pro',
            'days': 30,
            'price': 1490,
            'tokens_per_month': 500,
            'features': ['500 токенов/мес', 'Приоритетная скорость']
        },
        'elite': {
            'name': 'Elite',
            'days': 30,
            'price': 2790,
            'tokens_per_month': 1500,
            'features': ['1500 токенов/мес', 'Максимальная выгода', 'Приоритетная скорость', 'Ранний доступ к функциям']
        }
    }
    
    # Token System - Стоимость анализов в токенах
    BASIC_ANALYSIS_COST = 3
    ENHANCED_ANALYSIS_COST = 10
    INITIAL_TOKEN_BONUS = 10
    
    # Token Packages - Пакеты токенов для покупки
    TOKEN_PACKAGES = {
        'starter': {
            'name': 'Стартовый',
            'tokens': 50,
            'price_rub': 299,
            'price_usd': 3.5,
            'analyses_equivalent': '16 базовых или 5 расширенных'
        },
        'standard': {
            'name': 'Стандартный',
            'tokens': 200,
            'price_rub': 999,
            'price_usd': 11.5,
            'analyses_equivalent': '66 базовых или 20 расширенных'
        },
        'pro': {
            'name': 'Профессиональный',
            'tokens': 500,
            'price_rub': 1990,
            'price_usd': 23,
            'analyses_equivalent': '166 базовых или 50 расширенных'
        },
        'ultimate': {
            'name': 'Максимальный',
            'tokens': 1500,
            'price_rub': 4990,
            'price_usd': 58,
            'analyses_equivalent': '500 базовых или 150 расширенных'
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

