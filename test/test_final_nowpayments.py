"""
Финальный тест NOWPayments API с правильными параметрами
"""

import asyncio
import sys
import os
import aiohttp
import json
import time

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config


async def test_final_api():
    """Финальный тест API NOWPayments"""
    print("🎯 ФИНАЛЬНЫЙ ТЕСТ NOWPAYMENTS API")
    print("=" * 50)
    
    # Получаем конфигурацию
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    public_api_key = getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    base_url = "https://api-sandbox.nowpayments.io/v1" if sandbox else "https://api.nowpayments.io/v1"
    
    print(f"🔑 Private API Key: {'✅ Установлен' if api_key else '❌ Не установлен'}")
    print(f"🔑 Public API Key: {'✅ Установлен' if public_api_key else '❌ Не установлен'}")
    print(f"🔗 Sandbox: {'✅ Включен' if sandbox else '❌ Выключен'}")
    print(f"🌐 Base URL: {base_url}")
    
    # Тестируем все endpoints
    await test_status_endpoint(base_url, public_api_key or api_key)
    await test_currencies_endpoint(base_url, public_api_key or api_key)
    await test_estimate_endpoint(base_url, public_api_key or api_key)
    await test_create_subscription_payment(base_url, api_key)
    await test_create_analyses_payment(base_url, api_key)


async def test_status_endpoint(base_url, api_key):
    """Тестирование /status endpoint"""
    print(f"\n🧪 Тестирование /status endpoint...")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            async with session.get(f"{base_url}/status", headers=headers) as response:
                status = response.status
                text = await response.text()
                
                print(f"   📊 Status: {status}")
                
                if status == 200:
                    print(f"   ✅ API работает!")
                    try:
                        data = json.loads(text)
                        print(f"   📄 Response: {data}")
                    except:
                        print(f"   📄 Response: {text}")
                else:
                    print(f"   ❌ Ошибка {status}: {text[:100]}...")
                    
    except Exception as e:
        print(f"   ❌ Исключение: {e}")


async def test_currencies_endpoint(base_url, api_key):
    """Тестирование /currencies endpoint"""
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
                        print(f"   ✅ Получено {len(currencies)} криптовалют!")
                        
                        # Показываем первые 10 криптовалют
                        for i, currency in enumerate(currencies[:10]):
                            print(f"      {i+1}. {currency}")
                        
                        if len(currencies) > 10:
                            print(f"      ... и еще {len(currencies) - 10} криптовалют")
                            
                    except json.JSONDecodeError:
                        print(f"   ❌ Ошибка парсинга JSON: {text[:100]}...")
                else:
                    print(f"   ❌ Ошибка {status}: {text[:100]}...")
                    
    except Exception as e:
        print(f"   ❌ Исключение: {e}")


async def test_estimate_endpoint(base_url, api_key):
    """Тестирование /estimate endpoint"""
    print(f"\n🧪 Тестирование /estimate endpoint...")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            # Тестируем валютную пару RUB/BTC
            params = {
                "amount": 500,
                "currency_pair": "rub_btc"
            }
            
            print(f"   🧪 Тест: 500 RUB -> BTC")
            
            async with session.get(f"{base_url}/estimate", headers=headers, params=params) as response:
                status = response.status
                text = await response.text()
                
                print(f"      📊 Status: {status}")
                
                if status == 200:
                    try:
                        data = json.loads(text)
                        estimated_amount = data.get("estimated_amount")
                        if estimated_amount:
                            print(f"      ✅ 500 RUB = {estimated_amount} BTC")
                        else:
                            print(f"      ❌ Нет данных о цене")
                            print(f"      📄 Response: {data}")
                    except json.JSONDecodeError:
                        print(f"      ❌ Ошибка парсинга JSON: {text[:100]}...")
                else:
                    print(f"      ❌ Ошибка {status}: {text[:100]}...")
                    
    except Exception as e:
        print(f"   ❌ Исключение: {e}")


async def test_create_subscription_payment(base_url, api_key):
    """Тестирование создания платежа подписки"""
    print(f"\n🧪 Тестирование создания платежа подписки...")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            # Данные для платежа подписки
            payment_data = {
                "price_amount": 500,
                "price_currency": "rub",
                "pay_currency": "btc",
                "order_id": f"subscription_{int(time.time())}",
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
                        
                        print(f"      ✅ Платеж подписки создан!")
                        print(f"         Payment ID: {payment_id}")
                        print(f"         Status: {payment_status}")
                        print(f"         Pay URL: {pay_url}")
                        
                    except json.JSONDecodeError:
                        print(f"      ❌ Ошибка парсинга JSON: {text[:100]}...")
                else:
                    print(f"      ❌ Ошибка {status}: {text[:200]}...")
                    
    except Exception as e:
        print(f"   ❌ Исключение: {e}")


async def test_create_analyses_payment(base_url, api_key):
    """Тестирование создания платежа анализов"""
    print(f"\n🧪 Тестирование создания платежа анализов...")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            # Данные для платежа анализов
            payment_data = {
                "price_amount": 100,
                "price_currency": "rub",
                "pay_currency": "eth",
                "order_id": f"analyses_{int(time.time())}",
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
                        
                        print(f"      ✅ Платеж анализов создан!")
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
    """Основная функция"""
    print("🎯 ФИНАЛЬНЫЙ ТЕСТ NOWPAYMENTS API")
    print("=" * 50)
    
    await test_final_api()
    
    print("\n" + "=" * 50)
    print("📋 РЕЗУЛЬТАТЫ:")
    print("✅ Если все тесты прошли - API работает корректно")
    print("❌ Если есть ошибки 403 - проверьте права доступа")
    print("⚠️  Если есть ошибки 429 - подождите и повторите")
    print("🔧 Если есть ошибки 404 - проверьте правильность endpoints")


if __name__ == "__main__":
    asyncio.run(main())
