"""
Тест исправленного API NOWPayments с правильными параметрами
"""

import asyncio
import sys
import os
import aiohttp
import json

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config


async def test_corrected_endpoints():
    """Тестирование исправленных endpoints"""
    print("🔧 Тестирование исправленного API NOWPayments...")
    
    # Получаем конфигурацию
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    public_api_key = getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    base_url = "https://api-sandbox.nowpayments.io/v1" if sandbox else "https://api.nowpayments.io/v1"
    
    print(f"🔑 Private API Key: {'✅ Установлен' if api_key else '❌ Не установлен'}")
    print(f"🔑 Public API Key: {'✅ Установлен' if public_api_key else '❌ Не установлен'}")
    print(f"🔗 Sandbox: {'✅ Включен' if sandbox else '❌ Выключен'}")
    print(f"🌐 Base URL: {base_url}")
    
    # Тестируем исправленные endpoints
    await test_currencies_endpoint(base_url, public_api_key or api_key)
    await test_estimated_price_endpoint(base_url, public_api_key or api_key)
    await test_create_payment_endpoint(base_url, api_key)


async def test_currencies_endpoint(base_url, api_key):
    """Тестирование endpoint получения криптовалют"""
    print(f"\n🧪 Тестирование /currencies endpoint...")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            async with session.get(f"{base_url}/currencies", headers=headers) as response:
                status = response.status
                text = await response.text()
                
                print(f"   📊 Status: {status}")
                
                if status == 200:
                    try:
                        data = json.loads(text)
                        currencies = data.get("currencies", [])
                        print(f"   ✅ Успешно! Получено {len(currencies)} криптовалют")
                        
                        # Показываем первые 5 криптовалют
                        for i, currency in enumerate(currencies[:5]):
                            print(f"      {i+1}. {currency}")
                        
                        if len(currencies) > 5:
                            print(f"      ... и еще {len(currencies) - 5} криптовалют")
                            
                    except json.JSONDecodeError:
                        print(f"   ❌ Ошибка парсинга JSON: {text[:100]}...")
                else:
                    print(f"   ❌ Ошибка {status}: {text[:100]}...")
                    
    except Exception as e:
        print(f"   ❌ Исключение: {e}")


async def test_estimated_price_endpoint(base_url, api_key):
    """Тестирование endpoint получения цены"""
    print(f"\n🧪 Тестирование /estimated-price endpoint...")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            # Тестируем разные валютные пары
            currency_pairs = [
                ("rub", "btc"),
                ("usd", "btc"),
                ("rub", "eth"),
            ]
            
            for currency_from, currency_to in currency_pairs:
                print(f"   🧪 Тест пары {currency_from.upper()}/{currency_to.upper()}...")
                
                params = {
                    "amount": 500,
                    "currency_pair": f"{currency_from}_{currency_to}"
                }
                
                async with session.get(f"{base_url}/estimate", headers=headers, params=params) as response:
                    status = response.status
                    text = await response.text()
                    
                    print(f"      📊 Status: {status}")
                    
                    if status == 200:
                        try:
                            data = json.loads(text)
                            estimated_amount = data.get("estimated_amount")
                            if estimated_amount:
                                print(f"      ✅ 500 {currency_from.upper()} = {estimated_amount} {currency_to.upper()}")
                            else:
                                print(f"      ❌ Нет данных о цене")
                        except json.JSONDecodeError:
                            print(f"      ❌ Ошибка парсинга JSON: {text[:100]}...")
                    else:
                        print(f"      ❌ Ошибка {status}: {text[:100]}...")
                        
    except Exception as e:
        print(f"   ❌ Исключение: {e}")


async def test_create_payment_endpoint(base_url, api_key):
    """Тестирование endpoint создания платежа"""
    print(f"\n🧪 Тестирование /payment endpoint...")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            # Тестовые данные для платежа подписки
            payment_data = {
                "price_amount": 500,
                "price_currency": "rub",
                "pay_currency": "btc",
                "order_id": f"test_subscription_{int(asyncio.get_event_loop().time())}",
                "order_description": "Premium subscription for 30 days",
                "ipn_callback_url": "https://vextratrading.ru/nowpayments-webhook",
                "metadata": {
                    "user_id": "12345",
                    "subscription_type": "premium_30",
                    "payment_type": "subscription"
                }
            }
            
            print(f"   📝 Создание платежа подписки...")
            print(f"      Order ID: {payment_data['order_id']}")
            print(f"      Amount: {payment_data['price_amount']} {payment_data['price_currency']}")
            print(f"      Pay Currency: {payment_data['pay_currency']}")
            
            async with session.post(f"{base_url}/payment", json=payment_data, headers=headers) as response:
                status = response.status
                text = await response.text()
                
                print(f"      📊 Status: {status}")
                
                if status == 201:
                    try:
                        data = json.loads(text)
                        payment_id = data.get("payment_id")
                        payment_status = data.get("payment_status")
                        pay_url = data.get("pay_url")
                        
                        print(f"      ✅ Платеж создан!")
                        print(f"         Payment ID: {payment_id}")
                        print(f"         Status: {payment_status}")
                        print(f"         Pay URL: {pay_url}")
                        
                    except json.JSONDecodeError:
                        print(f"      ❌ Ошибка парсинга JSON: {text[:100]}...")
                else:
                    print(f"      ❌ Ошибка {status}: {text[:200]}...")
                    
    except Exception as e:
        print(f"   ❌ Исключение: {e}")


async def test_analyses_payment():
    """Тестирование создания платежа для анализов"""
    print(f"\n🧪 Тестирование платежа для анализов...")
    
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    base_url = "https://api-sandbox.nowpayments.io/v1" if sandbox else "https://api.nowpayments.io/v1"
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            # Тестовые данные для платежа анализов
            payment_data = {
                "price_amount": 100,
                "price_currency": "rub",
                "pay_currency": "eth",
                "order_id": f"test_analyses_{int(asyncio.get_event_loop().time())}",
                "order_description": "Purchase 10 additional analyses",
                "ipn_callback_url": "https://vextratrading.ru/nowpayments-webhook",
                "metadata": {
                    "user_id": "12345",
                    "analyses_count": "10",
                    "payment_type": "analyses"
                }
            }
            
            print(f"   📝 Создание платежа анализов...")
            print(f"      Order ID: {payment_data['order_id']}")
            print(f"      Amount: {payment_data['price_amount']} {payment_data['price_currency']}")
            print(f"      Pay Currency: {payment_data['pay_currency']}")
            
            async with session.post(f"{base_url}/payment", json=payment_data, headers=headers) as response:
                status = response.status
                text = await response.text()
                
                print(f"      📊 Status: {status}")
                
                if status == 201:
                    try:
                        data = json.loads(text)
                        payment_id = data.get("payment_id")
                        payment_status = data.get("payment_status")
                        pay_url = data.get("pay_url")
                        
                        print(f"      ✅ Платеж создан!")
                        print(f"         Payment ID: {payment_id}")
                        print(f"         Status: {payment_status}")
                        print(f"         Pay URL: {pay_url}")
                        
                    except json.JSONDecodeError:
                        print(f"      ❌ Ошибка парсинга JSON: {text[:100]}...")
                else:
                    print(f"      ❌ Ошибка {status}: {text[:200]}...")
                    
    except Exception as e:
        print(f"   ❌ Исключение: {e}")


async def main():
    """Основная функция тестирования"""
    print("🔧 ТЕСТИРОВАНИЕ ИСПРАВЛЕННОГО API NOWPAYMENTS")
    print("=" * 60)
    
    # Тестируем исправленные endpoints
    await test_corrected_endpoints()
    
    # Тестируем платеж для анализов
    await test_analyses_payment()
    
    print("\n" + "=" * 60)
    print("📋 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print("✅ Если все тесты прошли успешно - API работает корректно")
    print("❌ Если есть ошибки 403 - проверьте права доступа в панели NOWPayments")
    print("🔧 Если есть ошибки 429 - подождите и повторите тест")


if __name__ == "__main__":
    asyncio.run(main())
