"""
Дополнительные SQL запросы для аналитики и отчетов
"""

# Статистика по пользователям
GET_USER_STATS = """
SELECT 
    COUNT(*) as total_users,
    SUM(is_premium) as premium_users,
    SUM(CASE WHEN DATE(last_analysis_date) = DATE('now') THEN 1 ELSE 0 END) as active_today
FROM users
"""

# Статистика по анализам
GET_ANALYSIS_STATS = """
SELECT 
    COUNT(*) as total_analyses,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT token_symbol) as unique_tokens
FROM analyses
WHERE DATE(created_at) = DATE('now')
"""

# Топ анализируемых токенов
GET_TOP_TOKENS = """
SELECT 
    token_symbol,
    COUNT(*) as analysis_count
FROM analyses
WHERE created_at >= datetime('now', '-7 days')
GROUP BY token_symbol
ORDER BY analysis_count DESC
LIMIT 10
"""

