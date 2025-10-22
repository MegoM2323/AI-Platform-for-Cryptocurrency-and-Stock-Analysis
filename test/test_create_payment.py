"""
Тест создания реального платежа через NOWPayments
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Payments.payment_system import payment_manager
from config import config


async def test_create_subscription_payment():
    """Тест создания платежа для подписки"""
    print("🧪 Тест создания платежа для подписки...")
    
    try:
        # Создаем тестовый платеж
        payment = await payment_manager.create_crypto_subscription_payment(
            user_id=12345,
            subscription_type="premium_30",
            amount=500.0,
            description="Test Premium subscription payment",
            crypto_currency="BTC"
        )
        
        if payment:
            print("✅ Платеж успешно создан!")
            print(f"   Payment ID: {payment.payment_id}")
            print(f"   Status: {payment.status.value}")
            print(f"   Amount: {payment.amount} {payment.currency}")
            print(f"   Pay Currency: {payment.pay_currency}")
            print(f"   Payment URL: {payment.payment_url}")
            return True
        else:
            print("❌ Не удалось создать платеж")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка создания платежа: {e}")
        return False


async def test_create_analyses_payment():
    """Тест создания платежа для покупки анализов"""
    print("\n🧪 Тест создания платежа для анализов...")
    
    try:
        # Создаем тестовый платеж
        payment = await payment_manager.create_crypto_analyses_payment(
            user_id=12345,
            analyses_count=10,
            amount=100.0,
            description="Test analyses purchase payment",
            crypto_currency="ETH"
        )
        
        if payment:
            print("✅ Платеж успешно создан!")
            print(f"   Payment ID: {payment.payment_id}")
            print(f"   Status: {payment.status.value}")
            print(f"   Amount: {payment.amount} {payment.currency}")
            print(f"   Pay Currency: {payment.pay_currency}")
            print(f"   Payment URL: {payment.payment_url}")
            return True
        else:
            print("❌ Не удалось создать платеж")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка создания платежа: {e}")
        return False


async def test_get_crypto_price():
    """Тест получения цены в криптовалюте"""
    print("\n💰 Тест получения цены в криптовалюте...")
    
    try:
        # Тестируем разные криптовалюты
        currencies = ["BTC", "ETH", "USDT"]
        
        for currency in currencies:
            price = await payment_manager.get_crypto_price_estimate(500.0, currency)
            if price:
                print(f"✅ 500 RUB = {price:.8f} {currency}")
            else:
                print(f"❌ Не удалось получить цену для {currency}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка получения цены: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🧪 ТЕСТИРОВАНИЕ СОЗДАНИЯ ПЛАТЕЖЕЙ")
    print("=" * 50)
    
    # Проверяем конфигурацию
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    if not api_key:
        print("❌ NOWPAYMENTS_API_KEY не настроен!")
        return
    
    print(f"🔑 API Key: {'✅ Настроен' if api_key else '❌ Не настроен'}")
    print(f"🔗 Sandbox: {'✅ Включен' if getattr(config, 'NOWPAYMENTS_SANDBOX', True) else '❌ Выключен'}")
    
    # Тест получения цены
    price_ok = await test_get_crypto_price()
    
    if price_ok:
        # Тест создания платежа для подписки
        subscription_ok = await test_create_subscription_payment()
        
        # Тест создания платежа для анализов
        analyses_ok = await test_create_analyses_payment()
        
        if subscription_ok and analyses_ok:
            print("\n🎉 Все тесты создания платежей прошли успешно!")
            print("\n📋 Следующие шаги:")
            print("1. Проверьте платежи в панели NOWPayments")
            print("2. Протестируйте реальную оплату")
            print("3. Настройте webhook для уведомлений")
        else:
            print("\n❌ Некоторые тесты не прошли")
    else:
        print("\n❌ Не удалось получить цены - проверьте API ключи")


if __name__ == "__main__":
    asyncio.run(main())
