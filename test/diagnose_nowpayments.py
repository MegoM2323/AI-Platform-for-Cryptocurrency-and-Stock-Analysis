"""
Диагностика проблемы с NOWPayments API
"""

import asyncio
import sys
import os
import aiohttp

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config


async def test_api_endpoints():
    """Тестирование различных API endpoints"""
    print("🔍 Диагностика NOWPayments API...")
    
    # Получаем конфигурацию
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    public_api_key = getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    print(f"🔑 Private API Key: {'✅ Установлен' if api_key else '❌ Не установлен'}")
    print(f"🔑 Public API Key: {'✅ Установлен' if public_api_key else '❌ Не установлен'}")
    print(f"🔗 Sandbox: {'✅ Включен' if sandbox else '❌ Выключен'}")
    
    base_url = "https://api-sandbox.nowpayments.io/v1" if sandbox else "https://api.nowpayments.io/v1"
    print(f"🌐 Base URL: {base_url}")
    
    # Тестируем разные endpoints
    endpoints_to_test = [
        ("/status", "GET", "Проверка статуса API"),
        ("/currencies", "GET", "Получение криптовалют"),
        ("/estimate", "GET", "Получение цены"),
    ]
    
    for endpoint, method, description in endpoints_to_test:
        print(f"\n🧪 Тестирование: {description}")
        print(f"   Endpoint: {method} {base_url}{endpoint}")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": public_api_key if public_api_key else api_key,
                    "Content-Type": "application/json"
                }
                
                if method == "GET":
                    if endpoint == "/estimate":
                        # Добавляем параметры для estimate
                        params = {
                            "amount": 500,
                            "currency_from": "RUB",
                            "currency_to": "BTC"
                        }
                        async with session.get(f"{base_url}{endpoint}", headers=headers, params=params) as response:
                            await handle_response(response, endpoint)
                    else:
                        async with session.get(f"{base_url}{endpoint}", headers=headers) as response:
                            await handle_response(response, endpoint)
                            
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")


async def handle_response(response, endpoint):
    """Обработка ответа от API"""
    status = response.status
    text = await response.text()
    
    print(f"   📊 Status: {status}")
    
    if status == 200:
        print(f"   ✅ Успешно!")
        if endpoint == "/status":
            print(f"   📄 Response: {text[:200]}...")
    elif status == 403:
        print(f"   ❌ 403 - Invalid API Key")
        print(f"   📄 Response: {text}")
    elif status == 401:
        print(f"   ❌ 401 - Unauthorized")
        print(f"   📄 Response: {text}")
    elif status == 429:
        print(f"   ⚠️  429 - Too Many Requests")
        print(f"   📄 Response: {text}")
    else:
        print(f"   ❌ Ошибка {status}")
        print(f"   📄 Response: {text[:200]}...")


async def test_different_auth_methods():
    """Тестирование разных методов аутентификации"""
    print("\n🔐 Тестирование методов аутентификации...")
    
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    public_api_key = getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    base_url = "https://api-sandbox.nowpayments.io/v1" if sandbox else "https://api.nowpayments.io/v1"
    
    # Тестируем разные заголовки
    auth_methods = [
        ("x-api-key", api_key, "Private API Key"),
        ("x-api-key", public_api_key, "Public API Key"),
        ("Authorization", f"Bearer {api_key}", "Bearer Token (Private)"),
        ("Authorization", f"Bearer {public_api_key}", "Bearer Token (Public)"),
        ("X-API-Key", api_key, "X-API-Key header (Private)"),
        ("X-API-Key", public_api_key, "X-API-Key header (Public)"),
    ]
    
    for header_name, key, description in auth_methods:
        if not key:
            continue
            
        print(f"\n🧪 Тест: {description}")
        print(f"   Header: {header_name}: ***{key[-4:] if len(key) > 4 else '***'}")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    header_name: key,
                    "Content-Type": "application/json"
                }
                
                async with session.get(f"{base_url}/status", headers=headers) as response:
                    status = response.status
                    text = await response.text()
                    
                    if status == 200:
                        print(f"   ✅ Успешно! Status: {status}")
                    else:
                        print(f"   ❌ Ошибка {status}: {text[:100]}...")
                        
        except Exception as e:
            print(f"   ❌ Исключение: {e}")


async def check_sandbox_vs_production():
    """Проверка различий между sandbox и production"""
    print("\n🔍 Проверка sandbox vs production...")
    
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    public_api_key = getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None)
    
    # Тестируем sandbox
    print("\n🧪 Тестирование SANDBOX API...")
    await test_specific_url("https://api-sandbox.nowpayments.io/v1/status", public_api_key or api_key)
    
    # Тестируем production
    print("\n🧪 Тестирование PRODUCTION API...")
    await test_specific_url("https://api.nowpayments.io/v1/status", public_api_key or api_key)


async def test_specific_url(url, api_key):
    """Тестирование конкретного URL"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": api_key,
                "Content-Type": "application/json"
            }
            
            async with session.get(url, headers=headers) as response:
                status = response.status
                text = await response.text()
                
                print(f"   📊 URL: {url}")
                print(f"   📊 Status: {status}")
                print(f"   📄 Response: {text[:200]}...")
                
                if status == 200:
                    print(f"   ✅ Успешно!")
                else:
                    print(f"   ❌ Ошибка {status}")
                    
    except Exception as e:
        print(f"   ❌ Исключение: {e}")


async def main():
    """Основная функция диагностики"""
    print("🔍 ДИАГНОСТИКА NOWPAYMENTS API")
    print("=" * 50)
    
    # Тестируем API endpoints
    await test_api_endpoints()
    
    # Тестируем методы аутентификации
    await test_different_auth_methods()
    
    # Проверяем sandbox vs production
    await check_sandbox_vs_production()
    
    print("\n" + "=" * 50)
    print("📋 РЕКОМЕНДАЦИИ:")
    print("1. Убедитесь, что используете правильный API ключ для sandbox/production")
    print("2. Проверьте, что аккаунт NOWPayments верифицирован")
    print("3. Убедитесь, что API ключ активен и не заблокирован")
    print("4. Проверьте лимиты API запросов")
    print("5. Для sandbox используйте sandbox ключи, для production - production ключи")


if __name__ == "__main__":
    asyncio.run(main())
