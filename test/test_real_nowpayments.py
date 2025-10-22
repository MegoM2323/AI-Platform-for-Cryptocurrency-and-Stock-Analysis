"""
Тест реальной работы с NOWPayments API
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Payments.nowpayments_client import NOWPaymentsClient
from Payments.payment_system import PaymentManager
from config import config


async def test_nowpayments_connection():
    """Тест подключения к NOWPayments API"""
    print("🔍 Проверка конфигурации NOWPayments...")
    
    # Проверяем наличие API ключей
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    ipn_secret = getattr(config, 'NOWPAYMENTS_IPN_SECRET', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    print(f"API Key: {'✅ Установлен' if api_key else '❌ Не установлен'}")
    print(f"IPN Secret: {'✅ Установлен' if ipn_secret else '❌ Не установлен'}")
    print(f"Sandbox режим: {'✅ Включен' if sandbox else '❌ Выключен'}")
    
    if not api_key or not ipn_secret:
        print("\n❌ Проблема: API ключи NOWPayments не настроены!")
        print("📋 Необходимо добавить в .env файл:")
        print("NOWPAYMENTS_API_KEY=your_api_key")
        print("NOWPAYMENTS_IPN_SECRET=your_ipn_secret")
        return False
    
    # Создаем клиент
    client = NOWPaymentsClient(api_key, ipn_secret, sandbox)
    print(f"\n🔗 Базовый URL: {client.base_url}")
    
    try:
        # Тестируем получение доступных криптовалют
        print("\n🪙 Получение доступных криптовалют...")
        currencies = await client.get_available_currencies()
        
        if currencies:
            print(f"✅ Получено {len(currencies)} криптовалют")
            # Показываем первые 5
            for i, currency in enumerate(currencies[:5]):
                print(f"  {i+1}. {currency.symbol} - {currency.name} ({'✅' if currency.is_available else '❌'})")
            if len(currencies) > 5:
                print(f"  ... и еще {len(currencies) - 5} криптовалют")
        else:
            print("❌ Не удалось получить список криптовалют")
            return False
        
        # Тестируем получение цены
        print("\n💰 Тестирование получения цены...")
        price = await client.get_estimated_price(500.0, "RUB", "BTC")
        
        if price:
            print(f"✅ Примерная цена: 500 RUB = {price:.8f} BTC")
        else:
            print("❌ Не удалось получить примерную цену")
            return False
        
        print("\n✅ Все тесты NOWPayments прошли успешно!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании NOWPayments: {e}")
        return False


async def test_payment_manager():
    """Тест менеджера платежей"""
    print("\n🔧 Тестирование PaymentManager...")
    
    try:
        manager = PaymentManager()
        
        # Проверяем инициализацию
        if manager.nowpayments:
            print("✅ NOWPayments клиент инициализирован")
        else:
            print("❌ NOWPayments клиент не инициализирован")
            return False
        
        # Тестируем получение криптовалют через менеджер
        print("🪙 Получение криптовалют через менеджер...")
        currencies = await manager.get_available_crypto_currencies()
        
        if currencies:
            print(f"✅ Получено {len(currencies)} криптовалют через менеджер")
        else:
            print("❌ Не удалось получить криптовалюты через менеджер")
            return False
        
        print("✅ PaymentManager работает корректно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в PaymentManager: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🧪 Тестирование реальной работы с NOWPayments...")
    print("=" * 50)
    
    # Тест подключения
    connection_ok = await test_nowpayments_connection()
    
    if connection_ok:
        # Тест менеджера платежей
        manager_ok = await test_payment_manager()
        
        if manager_ok:
            print("\n🎉 Все тесты прошли успешно!")
            print("\n📋 Рекомендации:")
            print("1. Убедитесь, что API ключи корректны")
            print("2. Проверьте настройки webhook в панели NOWPayments")
            print("3. Протестируйте создание реального платежа")
        else:
            print("\n❌ Проблемы с PaymentManager")
    else:
        print("\n❌ Проблемы с подключением к NOWPayments")
        print("\n🔧 Возможные решения:")
        print("1. Проверьте правильность API ключей")
        print("2. Убедитесь, что аккаунт NOWPayments активен")
        print("3. Проверьте настройки sandbox/production режима")


if __name__ == "__main__":
    asyncio.run(main())
