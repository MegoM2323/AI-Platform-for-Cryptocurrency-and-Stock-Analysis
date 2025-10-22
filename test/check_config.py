"""
Диагностика конфигурации платежной системы
"""

import os
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config


def check_env_file():
    """Проверка .env файла"""
    print("🔍 Проверка .env файла...")
    
    env_path = Path(__file__).parent.parent / '.env'
    
    if not env_path.exists():
        print("❌ Файл .env не найден!")
        return False
    
    print(f"✅ Файл .env найден: {env_path}")
    
    # Читаем содержимое .env файла
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        nowpayments_lines = [line for line in lines if 'NOWPAYMENTS' in line]
        
        print(f"\n📋 Найдено {len(nowpayments_lines)} строк с NOWPAYMENTS:")
        for line in nowpayments_lines:
            if line.strip():
                # Скрываем значения для безопасности
                if '=' in line:
                    key, value = line.split('=', 1)
                    if value.strip():
                        print(f"  {key}=***{value[-4:] if len(value) > 4 else '***'}")
                    else:
                        print(f"  {key}= (пустое значение)")
                else:
                    print(f"  {line}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка чтения .env файла: {e}")
        return False


def check_config_values():
    """Проверка значений конфигурации"""
    print("\n🔧 Проверка значений конфигурации...")
    
    # Проверяем NOWPayments настройки
    nowpayments_settings = {
        'NOWPAYMENTS_API_KEY': getattr(config, 'NOWPAYMENTS_API_KEY', None),
        'NOWPAYMENTS_PUBLIC_API_KEY': getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None),
        'NOWPAYMENTS_IPN_SECRET': getattr(config, 'NOWPAYMENTS_IPN_SECRET', None),
        'NOWPAYMENTS_SANDBOX': getattr(config, 'NOWPAYMENTS_SANDBOX', None),
        'NOWPAYMENTS_PAYOUT_ADDRESS': getattr(config, 'NOWPAYMENTS_PAYOUT_ADDRESS', None),
        'NOWPAYMENTS_PAYOUT_CURRENCY': getattr(config, 'NOWPAYMENTS_PAYOUT_CURRENCY', None),
    }
    
    print("\n📊 Настройки NOWPayments:")
    for key, value in nowpayments_settings.items():
        if value is None:
            print(f"  {key}: ❌ Не установлено")
        elif key in ['NOWPAYMENTS_API_KEY', 'NOWPAYMENTS_IPN_SECRET']:
            # Скрываем API ключи
            if value:
                print(f"  {key}: ✅ Установлено (***{value[-4:] if len(value) > 4 else '***'})")
            else:
                print(f"  {key}: ❌ Пустое значение")
        else:
            print(f"  {key}: ✅ {value}")
    
    # Проверяем YooKassa настройки
    yookassa_settings = {
        'YOOKASSA_SHOP_ID': getattr(config, 'YOOKASSA_SHOP_ID', None),
        'YOOKASSA_SECRET_KEY': getattr(config, 'YOOKASSA_SECRET_KEY', None),
        'YOOKASSA_TEST_MODE': getattr(config, 'YOOKASSA_TEST_MODE', None),
    }
    
    print("\n📊 Настройки YooKassa:")
    for key, value in yookassa_settings.items():
        if value is None:
            print(f"  {key}: ❌ Не установлено")
        elif key in ['YOOKASSA_SECRET_KEY']:
            # Скрываем секретные ключи
            if value:
                print(f"  {key}: ✅ Установлено (***{value[-4:] if len(value) > 4 else '***'})")
            else:
                print(f"  {key}: ❌ Пустое значение")
        else:
            print(f"  {key}: ✅ {value}")
    
    return nowpayments_settings, yookassa_settings


def check_required_settings():
    """Проверка обязательных настроек"""
    print("\n✅ Проверка обязательных настроек...")
    
    required_nowpayments = ['NOWPAYMENTS_API_KEY', 'NOWPAYMENTS_IPN_SECRET']
    missing_settings = []
    
    for setting in required_nowpayments:
        value = getattr(config, setting, None)
        if not value:
            missing_settings.append(setting)
    
    if missing_settings:
        print(f"❌ Отсутствуют обязательные настройки: {', '.join(missing_settings)}")
        return False
    else:
        print("✅ Все обязательные настройки присутствуют")
        return True


def provide_solution():
    """Предоставить решение проблемы"""
    print("\n🔧 РЕШЕНИЕ ПРОБЛЕМЫ:")
    print("=" * 50)
    
    print("\n1️⃣ Получите API ключи от NOWPayments:")
    print("   • Зайдите на https://nowpayments.io/")
    print("   • Зарегистрируйтесь или войдите в аккаунт")
    print("   • Перейдите в раздел 'API Settings'")
    print("   • Скопируйте API Key и IPN Secret")
    
    print("\n2️⃣ Добавьте ключи в .env файл:")
    print("   NOWPAYMENTS_API_KEY=your_actual_api_key_here")
    print("   NOWPAYMENTS_PUBLIC_API_KEY=your_actual_public_api_key_here")
    print("   NOWPAYMENTS_IPN_SECRET=your_actual_ipn_secret_here")
    print("   NOWPAYMENTS_SANDBOX=true")
    
    print("\n3️⃣ Проверьте статус аккаунта:")
    print("   • Убедитесь, что аккаунт верифицирован")
    print("   • Проверьте, что API ключи активны")
    print("   • Для sandbox режима используйте тестовые ключи")
    
    print("\n4️⃣ Настройте webhook (опционально):")
    print("   • В панели NOWPayments добавьте webhook URL")
    print("   • URL должен быть доступен из интернета")
    print("   • Пример: https://yourdomain.com/webhook/nowpayments")


def main():
    """Основная функция диагностики"""
    print("🔍 ДИАГНОСТИКА КОНФИГУРАЦИИ ПЛАТЕЖНОЙ СИСТЕМЫ")
    print("=" * 60)
    
    # Проверяем .env файл
    env_ok = check_env_file()
    
    # Проверяем значения конфигурации
    nowpayments_settings, yookassa_settings = check_config_values()
    
    # Проверяем обязательные настройки
    required_ok = check_required_settings()
    
    print("\n" + "=" * 60)
    
    if not required_ok:
        print("❌ ПРОБЛЕМА НАЙДЕНА: Отсутствуют обязательные настройки NOWPayments")
        provide_solution()
    else:
        print("✅ Все настройки присутствуют, но API ключ может быть неверным")
        print("\n🔧 Проверьте:")
        print("1. Правильность API ключа")
        print("2. Активность аккаунта NOWPayments")
        print("3. Настройки sandbox/production режима")


if __name__ == "__main__":
    main()
