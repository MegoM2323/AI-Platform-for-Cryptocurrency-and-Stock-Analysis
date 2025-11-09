"""
SQL схемы для создания таблиц базы данных
"""

# Таблица пользователей
CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_premium INTEGER DEFAULT 0,
    premium_until TIMESTAMP,
    analyses_count_today INTEGER DEFAULT 0,
    last_analysis_date DATE,
    additional_analyses INTEGER DEFAULT 0,
    token_balance INTEGER DEFAULT 10
)
"""

# Таблица истории анализов
CREATE_ANALYSES_TABLE = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_symbol TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    analysis_text TEXT NOT NULL,
    tokens_spent INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
"""

# Таблица транзакций токенов
CREATE_TOKEN_TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS token_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    description TEXT,
    balance_before INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    payment_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
"""

# Таблица пакетов токенов
CREATE_TOKEN_PACKAGES_TABLE = """
CREATE TABLE IF NOT EXISTS token_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    price_rub REAL NOT NULL,
    price_usd REAL NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# Таблица подписок (рекуррентные начисления токенов)
CREATE_SUBSCRIPTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subscription_type TEXT NOT NULL,
    amount REAL NOT NULL,
    tokens_per_month INTEGER DEFAULT 0,
    payment_method_id TEXT,
    next_charge_at TIMESTAMP,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
"""

# Таблица обработанных платежей (для защиты от дублирования)
CREATE_PROCESSED_PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS processed_payments (
    payment_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    payment_type TEXT NOT NULL,
    subscription_type TEXT,
    analyses_added INTEGER,
    tokens_added INTEGER,
    plan_name TEXT NOT NULL,
    package_name TEXT,
    amount_paid REAL,
    currency TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
"""


# Таблица новостей
CREATE_NEWS_ARTICLES_TABLE = """
CREATE TABLE IF NOT EXISTS news_articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    url TEXT,
    published_at TIMESTAMP,
    source TEXT,
    symbol TEXT,
    sentiment_score REAL,
    relevance_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# Таблица учета использования внешних API
CREATE_API_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    endpoint TEXT,
    requests_count INTEGER DEFAULT 1,
    date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# Таблица кэша результатов анализа
CREATE_ANALYSIS_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    analysis_type TEXT NOT NULL,
    result_data TEXT,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

# Индексы для оптимизации
CREATE_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_users_premium ON users(is_premium, premium_until)",
    "CREATE INDEX IF NOT EXISTS idx_users_token_balance ON users(token_balance)",
    "CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_analyses_user_type ON analyses(user_id, analysis_type, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_token_transactions_user ON token_transactions(user_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_token_transactions_payment ON token_transactions(payment_id)",
    "CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_processed_payments_user ON processed_payments(user_id, processed_at)",
    # Индексы для новостей и кэша
    "CREATE INDEX IF NOT EXISTS idx_news_symbol_time ON news_articles(symbol, published_at)",
    "CREATE INDEX IF NOT EXISTS idx_api_usage_service_date ON api_usage(service, date)",
    "CREATE INDEX IF NOT EXISTS idx_analysis_cache_symbol_type ON analysis_cache(symbol, analysis_type)"
]

# Список всех схем для инициализации
ALL_SCHEMAS = [
    CREATE_USERS_TABLE,
    CREATE_ANALYSES_TABLE,
    CREATE_TOKEN_TRANSACTIONS_TABLE,
    CREATE_TOKEN_PACKAGES_TABLE,
    CREATE_SUBSCRIPTIONS_TABLE,
    CREATE_PROCESSED_PAYMENTS_TABLE,
    CREATE_NEWS_ARTICLES_TABLE,
    CREATE_API_USAGE_TABLE,
    CREATE_ANALYSIS_CACHE_TABLE,
] + CREATE_INDICES

