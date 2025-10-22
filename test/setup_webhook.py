"""
Настройка webhook для NOWPayments
"""

import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Payments.nowpayments_client import NOWPaymentsClient
from config import config


async def setup_webhook():
    """Настройка webhook для NOWPayments"""
    print("🔧 Настройка webhook для NOWPayments...")
    
    # Получаем конфигурацию
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    ipn_secret = getattr(config, 'NOWPAYMENTS_IPN_SECRET', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    if not api_key or not ipn_secret:
        print("❌ API ключи NOWPayments не настроены!")
        return False
    
    # Создаем клиент
    client = NOWPaymentsClient(api_key, ipn_secret, sandbox)
    
    # Webhook URL
    webhook_url = "https://vextratrading.ru/nowpayments-webhook"
    
    print(f"🔗 Webhook URL: {webhook_url}")
    print(f"🔑 IPN Secret: ***{ipn_secret[-4:] if len(ipn_secret) > 4 else '***'}")
    
    print("\n📋 Инструкции по настройке webhook:")
    print("=" * 50)
    print("1. Зайдите в панель NOWPayments:")
    print("   - https://nowpayments.io/ (production)")
    print("   - https://sandbox.nowpayments.io/ (sandbox)")
    print()
    print("2. Перейдите в раздел 'API Settings' или 'Webhooks'")
    print()
    print("3. Добавьте webhook с настройками:")
    print(f"   URL: {webhook_url}")
    print(f"   IPN Secret: {ipn_secret}")
    print("   Events: payment_status_changed")
    print()
    print("4. Сохраните настройки")
    print()
    print("5. Протестируйте webhook:")
    print("   - Создайте тестовый платеж")
    print("   - Проверьте получение уведомлений")
    
    return True


async def test_webhook_verification():
    """Тест проверки подписи webhook"""
    print("\n🧪 Тест проверки подписи webhook...")
    
    # Получаем конфигурацию
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    ipn_secret = getattr(config, 'NOWPAYMENTS_IPN_SECRET', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    if not api_key or not ipn_secret:
        print("❌ API ключи не настроены!")
        return False
    
    # Создаем клиент
    client = NOWPaymentsClient(api_key, ipn_secret, sandbox)
    
    # Тестовые данные
    test_payload = '{"payment_id": "test123", "status": "finished"}'
    test_signature = "test_signature"
    
    print(f"📝 Тестовый payload: {test_payload}")
    print(f"🔐 Тестовая подпись: {test_signature}")
    
    # Тестируем проверку подписи
    try:
        result = client._verify_ipn_signature(test_payload, test_signature)
        print(f"✅ Проверка подписи: {'Успешно' if result else 'Неудачно'}")
        return True
    except Exception as e:
        print(f"❌ Ошибка проверки подписи: {e}")
        return False


async def main():
    """Основная функция"""
    print("🔧 НАСТРОЙКА WEBHOOK ДЛЯ NOWPAYMENTS")
    print("=" * 50)
    
    # Настройка webhook
    webhook_ok = await setup_webhook()
    
    if webhook_ok:
        # Тест проверки подписи
        verification_ok = await test_webhook_verification()
        
        if verification_ok:
            print("\n✅ Настройка webhook завершена!")
            print("\n📋 Следующие шаги:")
            print("1. Настройте webhook в панели NOWPayments")
            print("2. Протестируйте создание платежа")
            print("3. Проверьте получение уведомлений")
            print("4. Убедитесь, что webhook URL доступен из интернета")
        else:
            print("\n❌ Проблемы с проверкой подписи")
    else:
        print("\n❌ Не удалось настроить webhook")


if __name__ == "__main__":
    asyncio.run(main())
