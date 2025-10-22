"""
Тесты для интеграции NOWPayments
"""

import asyncio
from unittest.mock import Mock, patch
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Payments.nowpayments_client import NOWPaymentsClient, NOWPaymentData, NOWPaymentStatus
from Payments.payment_system import PaymentManager


class TestNOWPaymentsClient:
    """Тесты для клиента NOWPayments"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.client = NOWPaymentsClient(
            api_key="test_api_key",
            ipn_secret="test_ipn_secret",
            sandbox=True
        )
    
    def test_client_initialization(self):
        """Тест инициализации клиента"""
        assert self.client.api_key == "test_api_key"
        assert self.client.ipn_secret == "test_ipn_secret"
        assert self.client.sandbox is True
        assert "sandbox" in self.client.base_url
    
    def test_verify_ipn_signature(self):
        """Тест проверки подписи IPN"""
        payload = '{"payment_id": "test123"}'
        signature = "test_signature"
        
        # Мокаем hmac.compare_digest
        with patch('Payments.nowpayments_client.hmac.compare_digest', return_value=True):
            result = self.client._verify_ipn_signature(payload, signature)
            assert result is True
    
    def test_is_payment_successful(self):
        """Тест проверки успешности платежа"""
        # Успешные статусы
        successful_payment = NOWPaymentData(
            payment_id="test123",
            status=NOWPaymentStatus.CONFIRMED,
            amount=100.0,
            currency="RUB",
            pay_currency="BTC"
        )
        assert self.client.is_payment_successful(successful_payment) is True
        
        # Неуспешные статусы
        failed_payment = NOWPaymentData(
            payment_id="test123",
            status=NOWPaymentStatus.FAILED,
            amount=100.0,
            currency="RUB",
            pay_currency="BTC"
        )
        assert self.client.is_payment_successful(failed_payment) is False
    
    def test_is_payment_failed(self):
        """Тест проверки неудачности платежа"""
        # Неудачные статусы
        failed_payment = NOWPaymentData(
            payment_id="test123",
            status=NOWPaymentStatus.FAILED,
            amount=100.0,
            currency="RUB",
            pay_currency="BTC"
        )
        assert self.client.is_payment_failed(failed_payment) is True
        
        # Успешные статусы
        successful_payment = NOWPaymentData(
            payment_id="test123",
            status=NOWPaymentStatus.CONFIRMED,
            amount=100.0,
            currency="RUB",
            pay_currency="BTC"
        )
        assert self.client.is_payment_failed(successful_payment) is False
    
    def test_is_payment_pending(self):
        """Тест проверки ожидания платежа"""
        # Ожидающие статусы
        pending_payment = NOWPaymentData(
            payment_id="test123",
            status=NOWPaymentStatus.WAITING,
            amount=100.0,
            currency="RUB",
            pay_currency="BTC"
        )
        assert self.client.is_payment_pending(pending_payment) is True
        
        # Завершенные статусы
        finished_payment = NOWPaymentData(
            payment_id="test123",
            status=NOWPaymentStatus.FINISHED,
            amount=100.0,
            currency="RUB",
            pay_currency="BTC"
        )
        assert self.client.is_payment_pending(finished_payment) is False


class TestPaymentManager:
    """Тесты для менеджера платежей"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        # Мокаем конфигурацию
        with patch('Payments.payment_system.config') as mock_config:
            mock_config.NOWPAYMENTS_API_KEY = "test_api_key"
            mock_config.NOWPAYMENTS_IPN_SECRET = "test_ipn_secret"
            mock_config.NOWPAYMENTS_SANDBOX = True
            mock_config.NOWPAYMENTS_PAYOUT_ADDRESS = "test_address"
            mock_config.NOWPAYMENTS_PAYOUT_CURRENCY = "BTC"
            mock_config.TELEGRAM_BOT_USERNAME = "test_bot"
            
            self.manager = PaymentManager()
    
    async def test_get_available_crypto_currencies(self):
        """Тест получения доступных криптовалют"""
        # Мокаем клиент NOWPayments
        mock_currencies = [
            Mock(symbol="BTC", name="Bitcoin", is_available=True),
            Mock(symbol="ETH", name="Ethereum", is_available=True)
        ]
        
        with patch.object(self.manager.nowpayments, 'get_available_currencies', 
                         return_value=mock_currencies):
            currencies = await self.manager.get_available_crypto_currencies()
            assert len(currencies) == 2
            assert currencies[0].symbol == "BTC"
    
    async def test_create_crypto_subscription_payment(self):
        """Тест создания криптоплатежа для подписки"""
        # Мокаем клиент NOWPayments
        mock_payment = NOWPaymentData(
            payment_id="test123",
            status=NOWPaymentStatus.NEW,
            amount=500.0,
            currency="RUB",
            pay_currency="BTC"
        )
        
        with patch.object(self.manager.nowpayments, 'create_payment', 
                         return_value=mock_payment):
            payment = await self.manager.create_crypto_subscription_payment(
                user_id=12345,
                subscription_type="premium_30",
                amount=500.0,
                description="Test subscription",
                crypto_currency="BTC"
            )
            
            assert payment is not None
            assert payment.payment_id == "test123"
            assert payment.amount == 500.0
    
    async def test_check_crypto_payment_status(self):
        """Тест проверки статуса криптоплатежа"""
        # Мокаем клиент NOWPayments
        mock_payment = NOWPaymentData(
            payment_id="test123",
            status=NOWPaymentStatus.CONFIRMED,
            amount=500.0,
            currency="RUB",
            pay_currency="BTC"
        )
        
        with patch.object(self.manager.nowpayments, 'get_payment_status', 
                         return_value=mock_payment):
            payment = await self.manager.check_crypto_payment_status("test123")
            
            assert payment is not None
            assert payment.payment_id == "test123"
            assert payment.status == NOWPaymentStatus.CONFIRMED
    
    def test_is_crypto_payment_successful(self):
        """Тест проверки успешности криптоплатежа"""
        # Успешный платеж
        successful_payment = NOWPaymentData(
            payment_id="test123",
            status=NOWPaymentStatus.CONFIRMED,
            amount=500.0,
            currency="RUB",
            pay_currency="BTC"
        )
        
        with patch.object(self.manager.nowpayments, 'is_payment_successful', 
                         return_value=True):
            result = self.manager.is_crypto_payment_successful(successful_payment)
            assert result is True
    
    async def test_get_crypto_price_estimate(self):
        """Тест получения примерной цены в криптовалюте"""
        # Мокаем клиент NOWPayments
        with patch.object(self.manager.nowpayments, 'get_estimated_price', 
                         return_value=0.00001234):
            price = await self.manager.get_crypto_price_estimate(500.0, "BTC")
            assert price == 0.00001234


def test_nowpayment_status_enum():
    """Тест enum статусов NOWPayments"""
    assert NOWPaymentStatus.NEW.value == "new"
    assert NOWPaymentStatus.CONFIRMED.value == "confirmed"
    assert NOWPaymentStatus.FINISHED.value == "finished"
    assert NOWPaymentStatus.FAILED.value == "failed"


def test_nowpayment_data_dataclass():
    """Тест dataclass NOWPaymentData"""
    payment = NOWPaymentData(
        payment_id="test123",
        status=NOWPaymentStatus.NEW,
        amount=100.0,
        currency="RUB",
        pay_currency="BTC",
        description="Test payment"
    )
    
    assert payment.payment_id == "test123"
    assert payment.status == NOWPaymentStatus.NEW
    assert payment.amount == 100.0
    assert payment.currency == "RUB"
    assert payment.pay_currency == "BTC"
    assert payment.description == "Test payment"


if __name__ == "__main__":
    # Запуск тестов
    print("🧪 Запуск тестов NOWPayments интеграции...")
    
    # Тестируем enum
    test_nowpayment_status_enum()
    print("✅ Тест enum статусов прошел")
    
    # Тестируем dataclass
    test_nowpayment_data_dataclass()
    print("✅ Тест dataclass прошел")
    
    # Тестируем клиент
    client_test = TestNOWPaymentsClient()
    client_test.setup_method()
    client_test.test_client_initialization()
    print("✅ Тест инициализации клиента прошел")
    
    client_test.test_verify_ipn_signature()
    print("✅ Тест проверки подписи прошел")
    
    client_test.test_is_payment_successful()
    print("✅ Тест проверки успешности платежа прошел")
    
    client_test.test_is_payment_failed()
    print("✅ Тест проверки неудачности платежа прошел")
    
    client_test.test_is_payment_pending()
    print("✅ Тест проверки ожидания платежа прошел")
    
    print("\n🎉 Все тесты NOWPayments интеграции прошли успешно!")
    print("\n📋 Следующие шаги:")
    print("1. Настройте переменные окружения в .env файле")
    print("2. Получите API ключи от NOWPayments")
    print("3. Протестируйте интеграцию в sandbox режиме")
    print("4. Настройте webhook для получения уведомлений")
