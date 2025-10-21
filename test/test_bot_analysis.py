#!/usr/bin/env python3
"""
Тест анализа токенов через бота
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent))

from config import config
from data_collectors import CryptoCollector, DataFormatter
from AI_block import AIAnalyzer


async def test_analysis():
    """Тест полного анализа токена"""
    print("🧪 Тестирование анализа токена BTC...")
    
    try:
        # Создаем коллектор
        collector = CryptoCollector()
        print("✅ CryptoCollector создан")
        
        # Получаем данные
        symbol = "BTC"
        data = collector.get_crypto_data(symbol)
        if data is None or data.empty:
            print("❌ Не удалось получить данные")
            return False
        
        print(f"✅ Получено {len(data)} записей данных")
        
        # Получаем текущую цену
        current_price = collector.get_current_price(symbol)
        print(f"✅ Текущая цена: ${current_price:,.2f}")
        
        # Форматируем данные
        formatter = DataFormatter()
        formatted_data = formatter.format_for_analysis(data, symbol, current_price)
        print("✅ Данные отформатированы")
        
        # Создаем анализатор
        analyzer = AIAnalyzer(
            api_key=config.OPENROUTER_API_KEY,
            model=config.AI_MODEL
        )
        print("✅ AIAnalyzer создан")
        
        # Выполняем анализ
        analysis = await analyzer.analyze_crypto(formatted_data, symbol)
        if analysis:
            print("✅ Анализ выполнен успешно!")
            print(f"📊 Длина анализа: {len(analysis)} символов")
            print("\n" + "="*50)
            print("ПЕРВЫЕ 500 СИМВОЛОВ АНАЛИЗА:")
            print("="*50)
            print(analysis[:500] + "...")
            print("="*50)
            return True
        else:
            print("❌ Анализ не выполнен")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Главная функция"""
    print("🚀 ТЕСТ АНАЛИЗА ТОКЕНОВ")
    print("="*50)
    
    success = await test_analysis()
    
    if success:
        print("\n🎉 ТЕСТ ПРОШЕЛ УСПЕШНО!")
        print("Анализ токенов работает корректно!")
    else:
        print("\n❌ ТЕСТ НЕ ПРОШЕЛ!")
        print("Есть проблемы с анализом токенов.")


if __name__ == "__main__":
    asyncio.run(main())
