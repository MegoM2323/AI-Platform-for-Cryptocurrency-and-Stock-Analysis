# 🤖 AI Platform для анализа криптовалют

Платформа для автоматического AI-анализа криптовалют с использованием OpenRouter API и Telegram бота.

## 📋 Описание

Это MVP (Minimum Viable Product) платформы для анализа криптовалют, которая предоставляет:
- 📊 Анализ данных криптовалют (таймфрейм 1 day)
- 🤖 AI анализ рынка через OpenRouter API (бесплатные модели)
- 💬 Telegram бот для взаимодействия с пользователями
- 💎 Система подписок и ограничений

## 🏗️ Архитектура

```
AI-Platform-for-Cryptocurrency-and-Stock-Analysis/
├── AI_block/                    # Модуль AI анализа
│   ├── __init__.py
│   ├── analyzer.py             # Интеграция с OpenRouter
│   └── prompts.py              # Промпты для анализа
├── data_collectors/             # Модуль сбора данных
│   ├── __init__.py
│   ├── crypto_collector.py     # Сбор данных через Twelve Data API
│   └── data_formatter.py       # Форматирование данных
├── telegram_bot/                # Telegram бот
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start_help.py       # /start, /help, /profile
│   │   ├── analysis.py         # Анализ токенов
│   │   └── payments.py         # Подписки
│   ├── __init__.py
│   ├── bot.py                  # Основной файл бота
│   ├── keyboards.py            # Клавиатуры
│   └── states.py               # FSM состояния
├── database/                    # Модуль БД
│   ├── __init__.py
│   ├── db.py                   # Работа с SQLite
│   ├── models.py               # Схемы таблиц
│   └── queries.py              # Дополнительные запросы
├── manage.py                    # Точка входа
├── config.py                    # Конфигурация
├── requirements.txt             # Зависимости
├── .env.example                 # Пример конфигурации
└── README.md                    # Этот файл
```

## 🔧 Технологии

- **Python 3.8+** - Основной язык
- **aiogram 3.7** - Telegram Bot Framework
- **twelvedata** - Получение данных о криптовалютах
- **OpenRouter API** - AI анализ (бесплатные модели)
- **SQLite** - База данных
- **aiosqlite** - Асинхронная работа с БД

## 🚀 Установка и запуск

### 1. Клонирование репозитория

```bash
cd "AI-Platform-for-Cryptocurrency-and-Stock-Analysis"
```

### 2. Создание виртуального окружения

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Заполните `.env` файл:

```env
# Токен Telegram бота (получить у @BotFather)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# API ключ OpenRouter (получить на https://openrouter.ai/)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# База данных
DATABASE_PATH=crypto_analysis.db

# AI модель (бесплатная)
AI_MODEL=meta-llama/llama-3.1-8b-instruct:free

# Лимиты анализов
FREE_ANALYSES_PER_DAY=3
PREMIUM_ANALYSES_PER_DAY=50
```

## 📱 Использование

### Команды бота:

- `/start` - Начать работу с ботом
- `/help` - Помощь и инструкции
- `/analyze` - Анализ криптовалюты
- `/profile` - Твой профиль и статистика
- `/subscribe` - Управление подпиской

### Кнопки меню:

- 📊 **Анализ токена** - Получить AI анализ криптовалюты
- ❓ **Помощь** - Руководство по использованию
- 💎 **Подписка** - Управление подпиской
- 📈 **Мой профиль** - Статистика и лимиты

### Примеры анализа:

1. Нажми "📊 Анализ токена"
2. Введи символ криптовалюты: `BTC`, `ETH`, `SOL`, `BNB`
3. Получи детальный AI анализ

### Настройки debug режима

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DEBUG_MODE` | Включить debug режим | `false` |
| `DEBUG_LOG_LEVEL` | Уровень логирования | `INFO` |
| `DEBUG_USE_MOCK_DATA` | Использовать тестовые данные | `false` |
| `DEBUG_SKIP_VALIDATION` | Пропустить валидацию конфигурации | `false` |

## 💎 Подписки

### Бесплатный тариф:
- ✅ 3 анализа в день
- ✅ Базовый анализ

### Premium тариф:
- ✅ 50 анализов в день
- ✅ Расширенный анализ
- ✅ Приоритетная поддержка

**Примечание:** В MVP оплата не реализована. Используй `/activate_premium_test` для тестирования.

## 🗄️ База данных

Структура таблиц:

### users
- `user_id` - ID пользователя Telegram
- `username` - Username
- `first_name`, `last_name` - Имя и фамилия
- `created_at` - Дата регистрации
- `is_premium` - Статус Premium
- `premium_until` - До какой даты активен Premium
- `analyses_count_today` - Количество анализов сегодня
- `last_analysis_date` - Дата последнего анализа

### analyses
- `id` - ID анализа
- `user_id` - ID пользователя
- `token_symbol` - Символ криптовалюты
- `analysis_text` - Текст анализа
- `created_at` - Дата создания

### subscriptions
- `id` - ID подписки
- `user_id` - ID пользователя
- `subscription_type` - Тип подписки
- `amount` - Сумма
- `status` - Статус платежа
- `created_at` - Дата создания

## 🔒 Безопасность

- ✅ Все ключи хранятся в `.env` (не коммитятся в git)
- ✅ `.gitignore` настроен для защиты чувствительных данных
- ✅ База данных локальная (SQLite)

## 📊 Особенности анализа

Платформа предоставляет:

1. **Технический анализ:**
   - Текущий тренд
   - SMA (Simple Moving Average)
   - RSI (Relative Strength Index)
   - Волатильность

2. **Данные:**
   - История за 30 дней (таймфрейм 1 day)
   - OHLC (Open, High, Low, Close)
   - Объемы торгов

3. **AI выводы:**
   - Ключевые наблюдения
   - Потенциальные риски
   - Прогноз развития

## 🛠️ Команды manage.py

### Основные команды:
```bash
# Запустить бота
python manage.py run

# Инициализировать БД
python manage.py init-db

# Тест сбора данных
python manage.py test-data

# Тест AI анализа
python manage.py test-ai

# Информация о проекте
python manage.py info
```

### Debug команды:
```bash
# Показать debug информацию
python manage.py debug-info

# Полный debug тест
python manage.py debug-test

# Тест с mock данными
python manage.py debug-mock
```

## 📄 Лицензия

**ПРОПРИЕТАРНАЯ ЛИЦЕНЗИЯ - ВСЕ ПРАВА ЗАЩИЩЕНЫ**

Copyright (c) 2025.10.21 Панин Михаил Павлович. Все права защищены.

⚠️ **ВНИМАНИЕ:** Данное программное обеспечение является проприетарным и конфиденциальным.

**ЗАПРЕЩЕНО:**
- Копирование, распространение, модификация без письменного разрешения
- Коммерческое использование без письменного разрешения
- Обратная инженерия, декомпиляция
- Создание форков, клонов или аналогов
- Публикация или передача третьим лицам

**РАЗРЕШЕНО ТОЛЬКО:**
- Просмотр исходного кода для образовательных целей

Нарушение данных условий влечет за собой правовые последствия в соответствии с законодательством РФ.

Для получения разрешения на использование обращайтесь к автору.
