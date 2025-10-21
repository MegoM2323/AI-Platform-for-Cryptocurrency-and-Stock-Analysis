#!/usr/bin/env python3
"""
Скрипт для тестирования всех API используемых в проекте
Помогает найти проблемы с подключениями и ключами
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent))

from config import config
from data_collectors import CryptoCollector, DataFormatter
from AI_block import AIAnalyzer
from database import Database


class APITester:
    """Класс для тестирования всех API"""
    
    def __init__(self):
        self.results = {}
        self.errors = []
    
    def print_header(self, title):
        """Печать заголовка теста"""
        print(f"\n{'='*60}")
        print(f"🧪 {title}")
        print(f"{'='*60}")
    
    def print_result(self, test_name, success, message="", error=None):
        """Печать результата теста"""
        status = "✅ УСПЕХ" if success else "❌ ОШИБКА"
        print(f"{status} {test_name}")
        if message:
            print(f"   📝 {message}")
        if error:
            print(f"   🔥 Ошибка: {error}")
            self.errors.append(f"{test_name}: {error}")
        
        self.results[test_name] = success
    
    async def test_config(self):
        """Тест 1: Проверка конфигурации"""
        self.print_header("ПРОВЕРКА КОНФИГУРАЦИИ")
        
        try:
            # Проверяем загрузку конфигурации
            config.validate()
            self.print_result("Загрузка конфигурации", True, "Все переменные окружения загружены")
            
            # Проверяем наличие ключей
            keys_status = {
                "TELEGRAM_BOT_TOKEN": bool(config.TELEGRAM_BOT_TOKEN),
                "OPENROUTER_API_KEY": bool(config.OPENROUTER_API_KEY),
                "TWELVE_DATA_API_KEY": bool(config.TWELVE_DATA_API_KEY)
            }
            
            for key, present in keys_status.items():
                if present:
                    self.print_result(f"Ключ {key}", True, "Найден")
                else:
                    self.print_result(f"Ключ {key}", False, "ОТСУТСТВУЕТ!")
            
            # Проверяем debug настройки
            debug_info = config.get_debug_info()
            self.print_result("Debug настройки", True, f"Режим: {debug_info}")
            
        except Exception as e:
            self.print_result("Конфигурация", False, error=str(e))
    
    async def test_database(self):
        """Тест 2: Проверка базы данных"""
        self.print_header("ПРОВЕРКА БАЗЫ ДАННЫХ")
        
        try:
            db = Database(config.DATABASE_PATH)
            self.print_result("Инициализация БД", True, "База данных подключена")
            
            # Тестируем создание таблиц
            await db.init_db()
            self.print_result("Создание таблиц", True, "Таблицы созданы/проверены")
            
            # Тестируем простой запрос
            test_user_id = 12345
            user_data = await db.get_user(test_user_id)
            self.print_result("Чтение из БД", True, f"Пользователь: {user_data}")
            
        except Exception as e:
            self.print_result("База данных", False, error=str(e))
    
    async def test_twelvedata_api(self):
        """Тест 3: Проверка Twelve Data API"""
        self.print_header("ПРОВЕРКА TWELVE DATA API")
        
        try:
            collector = CryptoCollector()
            self.print_result("Инициализация коллектора", True, "CryptoCollector создан")
            
            # Тестируем валидацию символа
            test_symbol = "BTC"
            is_valid = collector.validate_symbol(test_symbol)
            self.print_result(f"Валидация символа {test_symbol}", is_valid, 
                            "Символ найден" if is_valid else "Символ не найден")
            
            if is_valid:
                # Тестируем получение данных
                data = collector.get_crypto_data(test_symbol)
                if data is not None and not data.empty:
                    self.print_result(f"Получение данных {test_symbol}", True, 
                                    f"Получено {len(data)} записей")
                else:
                    self.print_result(f"Получение данных {test_symbol}", False, 
                                    "Данные не получены")
                
                # Тестируем получение текущей цены
                current_price = collector.get_current_price(test_symbol)
                if current_price:
                    self.print_result(f"Текущая цена {test_symbol}", True, 
                                    f"Цена: ${current_price:,.2f}")
                else:
                    self.print_result(f"Текущая цена {test_symbol}", False, 
                                    "Цена не получена")
            
        except Exception as e:
            self.print_result("Twelve Data API", False, error=str(e))
    
    async def test_openrouter_api(self):
        """Тест 4: Проверка OpenRouter API"""
        self.print_header("ПРОВЕРКА OPENROUTER API")
        
        try:
            analyzer = AIAnalyzer(
                api_key=config.OPENROUTER_API_KEY,
                model=config.AI_MODEL
            )
            self.print_result("Инициализация анализатора", True, "AIAnalyzer создан")
            
            # Тестируем простой запрос
            test_data = "BTC: $45,000, Volume: 1,000,000"
            test_symbol = "BTC"
            
            analysis = await analyzer.analyze_crypto(test_data, test_symbol)
            if analysis:
                self.print_result("AI анализ", True, f"Анализ получен ({len(analysis)} символов)")
            else:
                self.print_result("AI анализ", False, "Анализ не получен")
            
        except Exception as e:
            self.print_result("OpenRouter API", False, error=str(e))
    
    async def test_telegram_bot(self):
        """Тест 5: Проверка Telegram Bot API"""
        self.print_header("ПРОВЕРКА TELEGRAM BOT API")
        
        try:
            # Простая проверка токена через requests
            import requests
            
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    bot_info = data.get('result', {})
                    self.print_result("Подключение к Telegram", True, 
                                    f"Бот: @{bot_info.get('username', 'N/A')} ({bot_info.get('first_name', 'N/A')})")
                else:
                    self.print_result("Telegram Bot API", False, "Неверный токен бота")
            else:
                self.print_result("Telegram Bot API", False, f"HTTP {response.status_code}")
            
        except Exception as e:
            self.print_result("Telegram Bot API", False, error=str(e))
    
    async def test_full_analysis_flow(self):
        """Тест 6: Полный поток анализа"""
        self.print_header("ПОЛНЫЙ ПОТОК АНАЛИЗА")
        
        try:
            # Создаем все компоненты
            collector = CryptoCollector()
            formatter = DataFormatter()
            analyzer = AIAnalyzer(
                api_key=config.OPENROUTER_API_KEY,
                model=config.AI_MODEL
            )
            
            test_symbol = "BTC"
            
            # Шаг 1: Получение данных
            data = collector.get_crypto_data(test_symbol)
            if data is None or data.empty:
                self.print_result("Получение данных", False, "Данные не получены")
                return
            
            self.print_result("Получение данных", True, f"Получено {len(data)} записей")
            
            # Шаг 2: Форматирование данных
            current_price = collector.get_current_price(test_symbol)
            formatted_data = formatter.format_for_analysis(data, test_symbol, current_price)
            self.print_result("Форматирование данных", True, f"Данные отформатированы")
            
            # Шаг 3: AI анализ
            analysis = await analyzer.analyze_crypto(formatted_data, test_symbol)
            if analysis:
                self.print_result("AI анализ", True, f"Анализ получен ({len(analysis)} символов)")
                print(f"\n📊 Пример анализа (первые 200 символов):")
                print(f"{analysis[:200]}...")
            else:
                self.print_result("AI анализ", False, "Анализ не получен")
            
        except Exception as e:
            self.print_result("Полный поток анализа", False, error=str(e))
    
    def print_summary(self):
        """Печать итогового отчета"""
        self.print_header("ИТОГОВЫЙ ОТЧЕТ")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for success in self.results.values() if success)
        failed_tests = total_tests - passed_tests
        
        print(f"📊 Всего тестов: {total_tests}")
        print(f"✅ Успешных: {passed_tests}")
        print(f"❌ Неудачных: {failed_tests}")
        
        if self.errors:
            print(f"\n🔥 ОШИБКИ:")
            for error in self.errors:
                print(f"   • {error}")
        
        if failed_tests == 0:
            print(f"\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
            print(f"   Анализ токенов должен работать корректно.")
        else:
            print(f"\n⚠️  НАЙДЕНЫ ПРОБЛЕМЫ!")
            print(f"   Исправьте ошибки выше для корректной работы анализа.")
    
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🚀 ЗАПУСК ТЕСТИРОВАНИЯ API")
        print("Этот скрипт проверит все компоненты системы анализа токенов")
        
        await self.test_config()
        await self.test_database()
        await self.test_twelvedata_api()
        await self.test_openrouter_api()
        await self.test_telegram_bot()
        await self.test_full_analysis_flow()
        
        self.print_summary()


async def main():
    """Главная функция"""
    tester = APITester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
