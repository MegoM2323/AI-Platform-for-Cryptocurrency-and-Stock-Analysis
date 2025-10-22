"""
Тест NOWPayments с публичным API ключом
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Payments.nowpayments_client import NOWPaymentsClient
from Payments.payment_system import PaymentManager
from config import config


async def test_with_public_key():
    """Тест с публичным API ключом"""
    print("🔍 Проверка конфигурации с публичным ключом...")
    
    # Проверяем наличие всех ключей
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    public_api_key = getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None)
    ipn_secret = getattr(config, 'NOWPAYMENTS_IPN_SECRET', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    print(f"🔑 Private API Key: {'✅ Установлен' if api_key else '❌ Не установлен'}")
    print(f"🔑 Public API Key: {'✅ Установлен' if public_api_key else '❌ Не установлен'}")
    print(f"🔐 IPN Secret: {'✅ Установлен' if ipn_secret else '❌ Не установлен'}")
    print(f"🔗 Sandbox: {'✅ Включен' if sandbox else '❌ Выключен'}")
    
    if not api_key or not ipn_secret:
        print("\n❌ Проблема: Отсутствуют обязательные ключи!")
        return False
    
    if not public_api_key:
        print("\n⚠️  Предупреждение: Публичный API ключ не установлен")
        print("   Некоторые операции могут не работать")
    
    # Создаем клиент
    client = NOWPaymentsClient(api_key, ipn_secret, sandbox, public_api_key)
    print(f"\n🔗 Базовый URL: {client.base_url}")
    
    try:
        # Тестируем получение криптовалют
        print("\n🪙 Получение доступных криптовалют...")
        currencies = await client.get_available_currencies()
        
        if currencies:
            print(f"✅ Получено {len(currencies)} криптовалют")
            # Показываем первые 5
            for i, currency in enumerate(currencies[:5]):
                status = "✅" if currency.is_available else "❌"
                print(f"  {i+1}. {currency.symbol} - {currency.name} {status}")
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
        
        print("\n✅ Все тесты с публичным ключом прошли успешно!")
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        return False


async def test_payment_manager_with_public_key():
    """Тест PaymentManager с публичным ключом"""
    print("\n🔧 Тестирование PaymentManager с публичным ключом...")
    
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
        
        # Тестируем получение цены
        print("💰 Получение цены через менеджер...")
        price = await manager.get_crypto_price_estimate(500.0, "BTC")
        
        if price:
            print(f"✅ Цена через менеджер: 500 RUB = {price:.8f} BTC")
        else:
            print("❌ Не удалось получить цену через менеджер")
            return False
        
        print("✅ PaymentManager с публичным ключом работает корректно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в PaymentManager: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🧪 ТЕСТИРОВАНИЕ NOWPAYMENTS С ПУБЛИЧНЫМ КЛЮЧОМ")
    print("=" * 60)
    
    # Тест с публичным ключом
    public_key_ok = await test_with_public_key()
    
    if public_key_ok:
        # Тест PaymentManager
        manager_ok = await test_payment_manager_with_public_key()
        
        if manager_ok:
            print("\n🎉 Все тесты с публичным ключом прошли успешно!")
            print("\n📋 Рекомендации:")
            print("1. Убедитесь, что публичный API ключ корректный")
            print("2. Проверьте настройки webhook")
            print("3. Протестируйте создание реального платежа")
        else:
            print("\n❌ Проблемы с PaymentManager")
    else:
        print("\n❌ Проблемы с публичным ключом")
        print("\n🔧 Возможные решения:")
        print("1. Добавьте NOWPAYMENTS_PUBLIC_API_KEY в .env файл")
        print("2. Убедитесь, что публичный ключ активен")
        print("3. Проверьте настройки sandbox/production режима")


if __name__ == "__main__":
    asyncio.run(main())
