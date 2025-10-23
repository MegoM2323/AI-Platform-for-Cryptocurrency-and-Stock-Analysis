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
    additional_analyses INTEGER DEFAULT 0
)
"""

# Таблица истории анализов
CREATE_ANALYSES_TABLE = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_symbol TEXT NOT NULL,
    analysis_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
"""

# Таблица подписок (платежи)
CREATE_SUBSCRIPTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    subscription_type TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'pending',
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
    analyses_added INTEGER NOT NULL,
    plan_name TEXT NOT NULL,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
"""


# Индексы для оптимизации
CREATE_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_users_premium ON users(is_premium, premium_until)",
    "CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_processed_payments_user ON processed_payments(user_id, processed_at)"
]

# Список всех схем для инициализации
ALL_SCHEMAS = [
    CREATE_USERS_TABLE,
    CREATE_ANALYSES_TABLE,
    CREATE_SUBSCRIPTIONS_TABLE,
    CREATE_PROCESSED_PAYMENTS_TABLE,
] + CREATE_INDICES

