"""
Исправление проблемы с правами доступа NOWPayments API
"""

import asyncio
import sys
import os
import aiohttp

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config


async def test_with_correct_permissions():
    """Тестирование с правильными правами доступа"""
    print("🔧 Исправление проблемы с правами доступа...")
    
    # Получаем конфигурацию
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    public_api_key = getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    base_url = "https://api-sandbox.nowpayments.io/v1" if sandbox else "https://api.nowpayments.io/v1"
    
    print(f"🔑 Private API Key: {'✅ Установлен' if api_key else '❌ Не установлен'}")
    print(f"🔑 Public API Key: {'✅ Установлен' if public_api_key else '❌ Не установлен'}")
    print(f"🔗 Sandbox: {'✅ Включен' if sandbox else '❌ Выключен'}")
    
    # Тестируем с приватным ключом (должен иметь полные права)
    print(f"\n🧪 Тестирование с PRIVATE API KEY...")
    await test_endpoints_with_key(base_url, api_key, "Private")
    
    # Тестируем с публичным ключом (может иметь ограниченные права)
    print(f"\n🧪 Тестирование с PUBLIC API KEY...")
    await test_endpoints_with_key(base_url, public_api_key, "Public")


async def test_endpoints_with_key(base_url, api_key, key_type):
    """Тестирование endpoints с конкретным ключом"""
    if not api_key:
        print(f"   ❌ {key_type} API ключ не установлен")
        return
    
    endpoints = [
        ("/status", "Проверка статуса"),
        ("/currencies", "Получение криптовалют"),
        ("/estimate", "Получение цены"),
    ]
    
    for endpoint, description in endpoints:
        print(f"\n   🧪 {description} ({endpoint})")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": api_key,
                    "Content-Type": "application/json"
                }
                
                if endpoint == "/estimate":
                    # Добавляем параметры для estimate
                    params = {
                        "amount": 500,
                        "currency_from": "RUB",
                        "currency_to": "BTC"
                    }
                    async with session.get(f"{base_url}{endpoint}", headers=headers, params=params) as response:
                        await handle_endpoint_response(response, endpoint, key_type)
                else:
                    async with session.get(f"{base_url}{endpoint}", headers=headers) as response:
                        await handle_endpoint_response(response, endpoint, key_type)
                        
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")


async def handle_endpoint_response(response, endpoint, key_type):
    """Обработка ответа от endpoint"""
    status = response.status
    text = await response.text()
    
    print(f"      📊 Status: {status}")
    
    if status == 200:
        print(f"      ✅ Успешно с {key_type} ключом!")
        if endpoint == "/currencies":
            try:
                import json
                data = json.loads(text)
                currencies = data.get("currencies", [])
                print(f"      📊 Получено {len(currencies)} криптовалют")
            except:
                pass
        elif endpoint == "/estimate":
            try:
                import json
                data = json.loads(text)
                estimated_amount = data.get("estimated_amount")
                if estimated_amount:
                    print(f"      📊 Цена: 500 RUB = {estimated_amount} BTC")
            except:
                pass
    elif status == 403:
        print(f"      ❌ 403 - Недостаточно прав с {key_type} ключом")
        print(f"      📄 Response: {text}")
    elif status == 401:
        print(f"      ❌ 401 - Неавторизован с {key_type} ключом")
        print(f"      📄 Response: {text}")
    else:
        print(f"      ❌ Ошибка {status} с {key_type} ключом")
        print(f"      📄 Response: {text[:100]}...")


async def check_api_key_permissions():
    """Проверка прав API ключей"""
    print("\n🔍 Проверка прав API ключей...")
    
    api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
    public_api_key = getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None)
    sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
    
    base_url = "https://api-sandbox.nowpayments.io/v1" if sandbox else "https://api.nowpayments.io/v1"
    
    # Тестируем разные комбинации ключей
    key_combinations = [
        (api_key, "Private API Key"),
        (public_api_key, "Public API Key"),
    ]
    
    for key, key_name in key_combinations:
        if not key:
            continue
            
        print(f"\n🔑 Тестирование {key_name}:")
        
        # Тестируем все endpoints
        await test_all_endpoints_with_key(base_url, key, key_name)


async def test_all_endpoints_with_key(base_url, api_key, key_name):
    """Тестирование всех endpoints с конкретным ключом"""
    endpoints = [
        ("/status", "GET", "Проверка статуса"),
        ("/currencies", "GET", "Получение криптовалют"),
        ("/estimate", "GET", "Получение цены"),
    ]
    
    for endpoint, method, description in endpoints:
        print(f"   🧪 {description}...")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "x-api-key": api_key,
                    "Content-Type": "application/json"
                }
                
                if endpoint == "/estimate":
                    params = {
                        "amount": 500,
                        "currency_from": "RUB",
                        "currency_to": "BTC"
                    }
                    async with session.get(f"{base_url}{endpoint}", headers=headers, params=params) as response:
                        status = response.status
                        text = await response.text()
                        
                        if status == 200:
                            print(f"      ✅ Успешно!")
                        else:
                            print(f"      ❌ Ошибка {status}: {text[:50]}...")
                else:
                    async with session.get(f"{base_url}{endpoint}", headers=headers) as response:
                        status = response.status
                        text = await response.text()
                        
                        if status == 200:
                            print(f"      ✅ Успешно!")
                        else:
                            print(f"      ❌ Ошибка {status}: {text[:50]}...")
                            
        except Exception as e:
            print(f"      ❌ Исключение: {e}")


async def main():
    """Основная функция"""
    print("🔧 ИСПРАВЛЕНИЕ ПРОБЛЕМЫ С ПРАВАМИ ДОСТУПА")
    print("=" * 60)
    
    # Тестируем с правильными правами
    await test_with_correct_permissions()
    
    # Проверяем права API ключей
    await check_api_key_permissions()
    
    print("\n" + "=" * 60)
    print("📋 ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("\n🔧 ВОЗМОЖНЫЕ РЕШЕНИЯ:")
    print("1. Убедитесь, что используете правильный API ключ для нужных операций")
    print("2. Проверьте права доступа в панели NOWPayments")
    print("3. Убедитесь, что аккаунт полностью верифицирован")
    print("4. Проверьте, что API ключ имеет права на чтение криптовалют и цен")
    print("5. Попробуйте создать новый API ключ с полными правами")


if __name__ == "__main__":
    asyncio.run(main())
