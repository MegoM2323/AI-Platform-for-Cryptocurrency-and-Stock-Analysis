#!/usr/bin/env python3
"""
Точка входа для управления AI Platform
"""

import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(BASE_DIR))


def run_bot():
    """Запустить Telegram бота"""
    print("🚀 Запуск Telegram бота...")
    from telegram_bot.bot import run
    run()


def init_db():
    """Инициализировать базу данных"""
    print("📦 Инициализация базы данных...")
    import asyncio
    from database import Database
    from config import config
    
    async def init():
        db = Database(config.DATABASE_PATH)
        await db.init_db()
        print(f"✅ База данных инициализирована: {config.DATABASE_PATH}")
    
    asyncio.run(init())


def _run_migration_tokens():
    """Запустить миграцию подписок в токены (c бэкапом и проверками)."""
    print("🛠 Запуск миграции подписок в токены...")
    import asyncio
    from database.migrations import migrate_to_tokens

    asyncio.run(migrate_to_tokens.main())


def test_collector():
    """Тестировать сбор данных"""
    print("🧪 Тестирование сбора данных...")
    from data_collectors import CryptoCollector, DataFormatter
    
    collector = CryptoCollector()
    symbol = "BTC"
    
    print(f"Получение данных для {symbol}...")
    data = collector.get_crypto_data(symbol)
    
    if data is not None:
        print(f"✅ Получено {len(data)} записей")
        current_price = collector.get_current_price(symbol)
        print(f"💰 Текущая цена: ${current_price:.2f}")
        
        formatter = DataFormatter()
        formatted = formatter.format_for_analysis(data, symbol, current_price)
        print("\n📊 Отформатированные данные:")
        print(formatted[:500] + "...")
    else:
        print("❌ Ошибка при получении данных")


def test_ai():
    """Тестировать AI анализ"""
    print("🧪 Тестирование AI анализа...")
    import asyncio
    from data_collectors import CryptoCollector, DataFormatter
    from AI_block import AIAnalyzer
    from config import config
    
    async def test():
        try:
            # Валидация конфигурации
            config.validate()
            
            # Собираем данные
            collector = CryptoCollector()
            symbol = "BTC"
            
            print(f"Получение данных для {symbol}...")
            data = collector.get_crypto_data(symbol)
            current_price = collector.get_current_price(symbol)
            
            if data is None:
                print("❌ Не удалось получить данные")
                return
            
            # Форматируем
            formatter = DataFormatter()
            formatted_data = formatter.format_for_analysis(data, symbol, current_price)
            
            # Анализируем
            print("🤖 Запрос анализа от AI...")
            analyzer = AIAnalyzer(
                api_key=config.OPENROUTER_API_KEY,
                model=config.AI_MODEL
            )
            
            result = await analyzer.analyze_crypto(formatted_data, symbol)
            
            if result:
                print("\n✅ Анализ получен:\n")
                print(result)
            else:
                print("❌ Ошибка при получении анализа")
                
        except ValueError as e:
            print(f"❌ Ошибка конфигурации: {e}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    asyncio.run(test())


def debug_info():
    """Показать debug информацию"""
    print("🔧 Debug информация:")
    print("=" * 50)
    
    from config import config
    
    # Основная информация
    print(f"Debug Mode: {config.DEBUG_MODE}")
    print(f"Log Level: {config.DEBUG_LOG_LEVEL}")
    print(f"Use Mock Data: {config.DEBUG_USE_MOCK_DATA}")
    print(f"Skip Validation: {config.DEBUG_SKIP_VALIDATION}")
    print()
    
    # Конфигурация
    print("Конфигурация:")
    print(f"  Database Path: {config.DATABASE_PATH}")
    print(f"  AI Model: {config.AI_MODEL}")
    print(f"  Free Analyses: {config.FREE_ANALYSES_PER_MONTH}/month")
    print(f"  Basic Analyses: {config.BASIC_ANALYSES_PER_MONTH}/month")
    print(f"  Trader Analyses: {config.TRADER_ANALYSES_PER_MONTH}/month")
    print(f"  Pro Analyses: {config.PRO_ANALYSES_PER_MONTH}/month")
    print(f"  Elite Analyses: {config.ELITE_ANALYSES_PER_MONTH}/month")
    print()
    
    # Переменные окружения
    print("Переменные окружения:")
    import os
    env_vars = [
        'TELEGRAM_BOT_TOKEN', 'OPENROUTER_API_KEY', 'AI_MODEL',
        'DATABASE_PATH', 'DEBUG_MODE', 'DEBUG_LOG_LEVEL',
        'DEBUG_USE_MOCK_DATA', 'DEBUG_SKIP_VALIDATION'
    ]
    
    for var in env_vars:
        value = os.getenv(var, 'НЕ УСТАНОВЛЕНО')
        if var in ['TELEGRAM_BOT_TOKEN', 'OPENROUTER_API_KEY'] and value != 'НЕ УСТАНОВЛЕНО':
            value = f"{value[:8]}..." if len(value) > 8 else value
        print(f"  {var}: {value}")


def debug_test():
    """Запустить полный debug тест"""
    print("🔧 Запуск полного debug теста...")
    print("=" * 50)
    
    # 1. Проверка конфигурации
    print("1. Проверка конфигурации...")
    try:
        from config import config
        config.validate()
        print("✅ Конфигурация валидна")
    except Exception as e:
        print(f"❌ Ошибка конфигурации: {e}")
        return
    
    # 2. Проверка базы данных
    print("\n2. Проверка базы данных...")
    try:
        import asyncio
        from database import Database
        
        async def test_db():
            db = Database(config.DATABASE_PATH)
            await db.init_db()
            print("✅ База данных доступна")
        
        asyncio.run(test_db())
    except Exception as e:
        print(f"❌ Ошибка базы данных: {e}")
    
    # 3. Проверка сбора данных
    print("\n3. Проверка сбора данных...")
    try:
        from data_collectors import CryptoCollector
        collector = CryptoCollector()
        data = collector.get_crypto_data("BTC")
        if data is not None:
            print(f"✅ Получено {len(data)} записей для BTC")
        else:
            print("❌ Не удалось получить данные")
    except Exception as e:
        print(f"❌ Ошибка сбора данных: {e}")
    
    # 4. Проверка AI (если не debug режим с mock данными)
    if not config.DEBUG_USE_MOCK_DATA:
        print("\n4. Проверка AI анализа...")
        try:
            import asyncio
            from data_collectors import CryptoCollector, DataFormatter
            from AI_block import AIAnalyzer
            
            async def test_ai():
                collector = CryptoCollector()
                data = collector.get_crypto_data("BTC")
                current_price = collector.get_current_price("BTC")
                
                if data is not None:
                    formatter = DataFormatter()
                    formatted_data = formatter.format_for_analysis(data, "BTC", current_price)
                    
                    analyzer = AIAnalyzer(
                        api_key=config.OPENROUTER_API_KEY,
                        model=config.AI_MODEL
                    )
                    
                    result = await analyzer.analyze_crypto(formatted_data, "BTC")
                    if result:
                        print("✅ AI анализ работает")
                    else:
                        print("❌ AI анализ не вернул результат")
                else:
                    print("❌ Нет данных для AI анализа")
            
            asyncio.run(test_ai())
        except Exception as e:
            print(f"❌ Ошибка AI анализа: {e}")
    else:
        print("\n4. Пропуск AI теста (используются mock данные)")
    
    print("\n🎉 Debug тест завершен!")


def debug_mock_data():
    """Тестировать с mock данными"""
    print("🧪 Тестирование с mock данными...")
    
    # Создаем тестовые данные
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta
    
    # Генерируем тестовые данные за последние 30 дней
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='1D')
    np.random.seed(42)  # Для воспроизводимости
    
    # Симулируем цену BTC с трендом
    base_price = 45000
    price_changes = np.random.normal(0, 0.05, len(dates))  # 5% волатильность
    prices = [base_price]
    
    for change in price_changes[1:]:
        new_price = prices[-1] * (1 + change)
        prices.append(new_price)
    
    # Создаем DataFrame
    mock_data = pd.DataFrame({
        'Date': dates,
        'Open': prices,
        'High': [p * (1 + abs(np.random.normal(0, 0.02))) for p in prices],
        'Low': [p * (1 - abs(np.random.normal(0, 0.02))) for p in prices],
        'Close': prices,
        'Volume': [np.random.randint(1000000, 5000000) for _ in prices]
    })
    
    print(f"✅ Создано {len(mock_data)} записей mock данных")
    print(f"Цена BTC: ${mock_data['Close'].iloc[-1]:.2f}")
    print(f"Период: {mock_data['Date'].iloc[0].strftime('%Y-%m-%d')} - {mock_data['Date'].iloc[-1].strftime('%Y-%m-%d')}")
    
    # Показываем статистику
    print(f"\nСтатистика mock данных:")
    print(f"  Средняя цена: ${mock_data['Close'].mean():.2f}")
    print(f"  Минимальная цена: ${mock_data['Close'].min():.2f}")
    print(f"  Максимальная цена: ${mock_data['Close'].max():.2f}")
    print(f"  Волатильность: {mock_data['Close'].std():.2f}")
    
    return mock_data


def show_info():
    """Показать информацию о проекте"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║   AI Platform for Cryptocurrency Analysis                ║
║   Платформа для AI анализа криптовалют                   ║
╚═══════════════════════════════════════════════════════════╝

Компоненты:
  📊 Data Collectors - Сбор данных через Twelve Data API
  🤖 AI Block - Анализ через OpenRouter API
  💬 Telegram Bot - Интерфейс пользователя
  💾 Database - SQLite хранилище

Основные команды:
  python manage.py run                 - Запустить бота
  python manage.py init-db             - Инициализировать БД
  python manage.py migrate-to-tokens   - Миграция подписок в токены
  python manage.py test-data           - Тест сбора данных
  python manage.py test-ai             - Тест AI анализа
  python manage.py info                - Эта справка

Debug команды:
  python manage.py debug-info  - Показать debug информацию
  python manage.py debug-test  - Полный debug тест
  python manage.py debug-mock  - Тест с mock данными

Требования:
  ✅ Python 3.8+
  ✅ Виртуальное окружение (.venv)
  ✅ Заполненный .env файл

Debug режим:
  🔧 Установите DEBUG_MODE=true в .env для отладки
  📝 См. docs/ENV_EXAMPLE.md для примеров конфигурации

Документация: README.md
""")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description='AI Platform для анализа криптовалют'
    )
    
    parser.add_argument(
        'command',
        choices=['run', 'init-db', 'migrate-to-tokens', 'test-data', 'test-ai', 'info', 
                'debug-info', 'debug-test', 'debug-mock'],
        help='Команда для выполнения'
    )
    
    args = parser.parse_args()
    
    commands = {
        'run': run_bot,
        'init-db': init_db,
        'migrate-to-tokens': lambda: _run_migration_tokens(),
        'test-data': test_collector,
        'test-ai': test_ai,
        'info': show_info,
        'debug-info': debug_info,
        'debug-test': debug_test,
        'debug-mock': debug_mock_data
    }
    
    try:
        commands[args.command]()
    except KeyboardInterrupt:
        print("\n\n⚠️  Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        show_info()
    else:
        main()

