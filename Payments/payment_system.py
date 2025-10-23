"""
Модуль для работы с платежной системой ЮКасса
"""

import asyncio
import logging
import uuid
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from enum import Enum

import aiohttp
import base64
from config import config
from .nowpayments_client import NOWPaymentsClient, NOWPaymentData, CryptocurrencyInfo

logger = logging.getLogger(__name__)


class PaymentStatus(Enum):
    """Статусы платежа"""
    PENDING = "pending"
    WAITING_FOR_CAPTURE = "waiting_for_capture"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


@dataclass
class PaymentData:
    """Данные платежа"""
    id: str
    status: PaymentStatus
    amount: float
    currency: str = "RUB"
    description: str = ""
    confirmation_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class YooKassaClient:
    """Клиент для работы с API ЮКасса"""
    
    def __init__(self, shop_id: str, secret_key: str, test_mode: bool = True):
        self.shop_id = shop_id
        self.secret_key = secret_key
        self.test_mode = test_mode
        self.base_url = "https://api.yookassa.ru/v3"
        
        # Создаем заголовки для авторизации
        credentials = f"{shop_id}:{secret_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.auth_header = f"Basic {encoded_credentials}"
        
        logger.info(f"YooKassa клиент инициализирован (тестовый режим: {test_mode})")
    
    def _create_receipt(self, amount: float, description: str, user_email: str = None) -> Dict[str, Any]:
        """
        Создать чек для фискализации
        
        Args:
            amount: Сумма платежа
            description: Описание платежа
            user_email: Email пользователя
            
        Returns:
            Dict с данными чека
        """
        return {
            "customer": {
                "email": user_email or "noreply@example.com"
            },
            "items": [
                {
                    "description": description,
                    "quantity": "1",
                    "amount": {
                        "value": f"{amount:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": 1,  # НДС 20%
                    "payment_subject": "service",  # Услуга
                    "payment_mode": "full_payment"  # Полная предоплата
                }
            ]
        }
    
    async def create_payment(
        self,
        amount: float,
        description: str,
        return_url: str,
        metadata: Optional[Dict[str, Any]] = None,
        receipt: Optional[Dict[str, Any]] = None
    ) -> PaymentData:
        """
        Создать платеж
        
        Args:
            amount: Сумма платежа
            description: Описание платежа
            return_url: URL для возврата после оплаты
            metadata: Дополнительные данные
            
        Returns:
            PaymentData: Данные созданного платежа
        """
        try:
            # Генерируем уникальный ключ идемпотентности
            idempotence_key = str(uuid.uuid4())
            
            # Подготавливаем данные для запроса
            payment_data = {
                "amount": {
                    "value": f"{amount:.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url
                },
                "capture": True,
                "description": description,
                "metadata": metadata or {}
            }
            
            # Добавляем чек если передан
            if receipt:
                payment_data["receipt"] = receipt
            
            # Добавляем тестовый режим если включен
            if self.test_mode:
                payment_data["test"] = True
            
            # Логируем данные запроса для отладки
            logger.info(f"Отправляем запрос к ЮКасса API: {payment_data}")
            
            headers = {
                "Authorization": self.auth_header,
                "Idempotence-Key": idempotence_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/payments",
                    json=payment_data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        payment = PaymentData(
                            id=result["id"],
                            status=PaymentStatus(result["status"]),
                            amount=float(result["amount"]["value"]),
                            currency=result["amount"]["currency"],
                            description=result.get("description", ""),
                            confirmation_url=result.get("confirmation", {}).get("confirmation_url"),
                            metadata=result.get("metadata", {})
                        )
                        
                        logger.info(f"Платеж создан: {payment.id}, статус: {payment.status.value}")
                        return payment
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка создания платежа: {response.status} - {error_text}")
                        
                        # Парсим детали ошибки для более информативного сообщения
                        try:
                            error_data = await response.json()
                            error_description = error_data.get('description', 'Неизвестная ошибка')
                            error_parameter = error_data.get('parameter', '')
                            
                            if 'receipt' in error_description.lower():
                                raise Exception(f"Ошибка с чеком: {error_description}. Проверьте настройки фискализации в ЮКасса.")
                            elif 'amount' in error_description.lower():
                                raise Exception(f"Ошибка с суммой: {error_description}")
                            else:
                                raise Exception(f"Ошибка создания платежа: {error_description}")
                        except:
                            raise Exception(f"Ошибка создания платежа: {response.status} - {error_text}")
                        
        except Exception as e:
            logger.error(f"Ошибка при создании платежа: {e}")
            raise
    
    async def get_payment(self, payment_id: str) -> Optional[PaymentData]:
        """
        Получить информацию о платеже
        
        Args:
            payment_id: ID платежа
            
        Returns:
            PaymentData или None при ошибке
        """
        try:
            headers = {
                "Authorization": self.auth_header,
                "Content-Type": "application/json"
            }
            
            logger.info(f"Запрос к YooKassa API для платежа: {payment_id}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/payments/{payment_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        logger.info(f"Ответ YooKassa API для платежа {payment_id}: {result}")
                        
                        payment = PaymentData(
                            id=result["id"],
                            status=PaymentStatus(result["status"]),
                            amount=float(result["amount"]["value"]),
                            currency=result["amount"]["currency"],
                            description=result.get("description", ""),
                            confirmation_url=result.get("confirmation", {}).get("confirmation_url"),
                            metadata=result.get("metadata", {})
                        )
                        
                        logger.info(f"Получен платеж: {payment.id}, статус: {payment.status.value}")
                        return payment
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка получения платежа {payment_id}: {response.status} - {error_text}")
                        
                        # Парсим детали ошибки
                        try:
                            error_data = await response.json()
                            error_description = error_data.get('description', 'Неизвестная ошибка')
                            
                            if response.status == 404:
                                logger.warning(f"Платеж {payment_id} не найден в YooKassa")
                            elif response.status == 401:
                                logger.error(f"Ошибка авторизации при получении платежа {payment_id} - проверьте YOOKASSA_SECRET_KEY")
                            else:
                                logger.error(f"Ошибка получения платежа {payment_id}: {error_description}")
                        except Exception as parse_error:
                            logger.error(f"Не удалось распарсить ошибку для платежа {payment_id}: {parse_error}")
                            logger.error(f"Ошибка получения платежа {payment_id}: {response.status} - {error_text}")
                        
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при получении платежа {payment_id}: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении платежа {payment_id}: {e}", exc_info=True)
            return None
    
    async def capture_payment(self, payment_id: str) -> bool:
        """
        Подтвердить платеж (capture)
        
        Args:
            payment_id: ID платежа
            
        Returns:
            bool: True если платеж успешно подтвержден
        """
        try:
            idempotence_key = str(uuid.uuid4())
            
            headers = {
                "Authorization": self.auth_header,
                "Idempotence-Key": idempotence_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/payments/{payment_id}/capture",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info(f"Платеж {payment_id} успешно подтвержден")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка подтверждения платежа: {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Ошибка при подтверждении платежа: {e}")
            return False


class PaymentManager:
    """Менеджер платежей для интеграции с ботом"""
    
    def __init__(self):
        self.yookassa = None
        self.nowpayments = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Инициализация клиентов платежных систем"""
        # Инициализация ЮКасса
        try:
            shop_id = getattr(config, 'YOOKASSA_SHOP_ID', None)
            secret_key = getattr(config, 'YOOKASSA_SECRET_KEY', None)
            test_mode = getattr(config, 'YOOKASSA_TEST_MODE', True)
            
            if shop_id and secret_key:
                self.yookassa = YooKassaClient(shop_id, secret_key, test_mode)
                logger.info("ЮКасса клиент инициализирован")
            else:
                logger.warning("ЮКасса не настроена - фиатные платежи недоступны")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации ЮКасса: {e}")
        
        # Инициализация NOWPayments
        try:
            api_key = getattr(config, 'NOWPAYMENTS_API_KEY', None)
            public_api_key = getattr(config, 'NOWPAYMENTS_PUBLIC_API_KEY', None)
            ipn_secret = getattr(config, 'NOWPAYMENTS_IPN_SECRET', None)
            sandbox = getattr(config, 'NOWPAYMENTS_SANDBOX', True)
            
            if api_key and ipn_secret:
                self.nowpayments = NOWPaymentsClient(api_key, ipn_secret, sandbox, public_api_key)
                logger.info("NOWPayments клиент инициализирован")
            else:
                logger.warning("NOWPayments не настроена - криптоплатежи недоступны")
                
        except Exception as e:
            logger.error(f"Ошибка инициализации NOWPayments: {e}")
    
    async def create_subscription_payment(
        self,
        user_id: int,
        subscription_type: str,
        amount: float,
        description: str,
        user_email: str = None
    ) -> Optional[PaymentData]:
        """
        Создать платеж для подписки
        
        Args:
            user_id: ID пользователя
            subscription_type: Тип подписки
            amount: Сумма
            description: Описание
            
        Returns:
            PaymentData или None при ошибке
        """
        if not self.yookassa:
            logger.error("ЮКасса не инициализирована")
            return None
        
        try:
            # URL для возврата после оплаты
            return_url = f"https://t.me/{config.TELEGRAM_BOT_USERNAME}?start=payment_success"
            
            # Метаданные платежа
            metadata = {
                "user_id": str(user_id),
                "subscription_type": subscription_type,
                "payment_type": "subscription"
            }
            
            # Создаем чек для фискализации
            receipt = self.yookassa._create_receipt(amount, description, user_email)
            
            payment = await self.yookassa.create_payment(
                amount=amount,
                description=description,
                return_url=return_url,
                metadata=metadata,
                receipt=receipt
            )
            
            logger.info(f"Создан платеж вычисления подписки: {payment.id}")
            return payment
            
        except Exception as e:
            logger.error(f"Ошибка создания платежа подписки: {e}")
            
            # Дополнительная диагностика ошибки
            if "receipt" in str(e).lower():
                logger.error("Ошибка с чеком - проверьте настройки фискализации в ЮКасса")
            elif "amount" in str(e).lower():
                logger.error("Ошибка с суммой платежа")
            elif "401" in str(e):
                logger.error("Ошибка авторизации - проверьте YOOKASSA_SECRET_KEY")
            elif "timeout" in str(e).lower():
                logger.error("Таймаут при обращении к API ЮКасса")
            else:
                logger.error(f"Неизвестная ошибка при создании платежа: {e}")
            
            return None
    
    async def create_analyses_payment(
        self,
        user_id: int,
        analyses_count: int,
        amount: float,
        description: str,
        user_email: str = None
    ) -> Optional[PaymentData]:
        """
        Создать платеж для покупки анализов
        
        Args:
            user_id: ID пользователя
            analyses_count: Количество анализов
            amount: Сумма
            description: Описание
            
        Returns:
            PaymentData или None при ошибке
        """
        if not self.yookassa:
            logger.error("ЮКасса не инициализирована")
            return None
        
        try:
            # URL для возврата после оплаты
            return_url = f"https://t.me/{config.TELEGRAM_BOT_USERNAME}?start=payment_success"
            
            # Метаданные платежа
            metadata = {
                "user_id": str(user_id),
                "analyses_count": str(analyses_count),
                "payment_type": "analyses"
            }
            
            # Создаем чек для фискализации
            receipt = self.yookassa._create_receipt(amount, description, user_email)
            
            payment = await self.yookassa.create_payment(
                amount=amount,
                description=description,
                return_url=return_url,
                metadata=metadata,
                receipt=receipt
            )
            
            logger.info(f"Создан платеж для анализов: {payment.id}")
            return payment
            
        except Exception as e:
            logger.error(f"Ошибка создания платежа анализов: {e}")
            
            # Дополнительная диагностика ошибки
            if "receipt" in str(e).lower():
                logger.error("Ошибка с чеком - проверьте настройки фискализации в ЮКасса")
            elif "amount" in str(e).lower():
                logger.error("Ошибка с суммой платежа")
            elif "401" in str(e):
                logger.error("Ошибка авторизации - проверьте YOOKASSA_SECRET_KEY")
            elif "timeout" in str(e).lower():
                logger.error("Таймаут при обращении к API ЮКасса")
            else:
                logger.error(f"Неизвестная ошибка при создании платежа: {e}")
            
            return None
    
    async def check_payment_status(self, payment_id: str) -> Optional[PaymentData]:
        """
        Проверить статус платежа
        
        Args:
            payment_id: ID платежа
            
        Returns:
            PaymentData или None при ошибке
        """
        if not self.yookassa:
            logger.error("ЮКасса не инициализирована - проверьте настройки YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY")
            return None
        
        try:
            logger.info(f"Проверка статуса платежа: {payment_id}")
            payment = await self.yookassa.get_payment(payment_id)
            
            if payment:
                logger.info(f"Статус платежа {payment_id}: {payment.status.value}")
            else:
                logger.warning(f"Не удалось получить данные платежа {payment_id}")
            
            return payment
            
        except Exception as e:
            logger.error(f"Ошибка проверки статуса платежа {payment_id}: {e}")
            
            # Дополнительная диагностика ошибки
            if "401" in str(e):
                logger.error("Ошибка авторизации - проверьте YOOKASSA_SECRET_KEY")
            elif "404" in str(e):
                logger.warning(f"Платеж {payment_id} не найден")
            elif "timeout" in str(e).lower():
                logger.error("Таймаут при обращении к API ЮКасса")
            else:
                logger.error(f"Неизвестная ошибка при проверке платежа: {e}")
            
            return None
    
    def is_payment_successful(self, payment: PaymentData) -> bool:
        """
        Проверить успешность платежа
        
        Args:
            payment: Данные платежа
            
        Returns:
            bool: True если платеж успешен
        """
        return payment.status == PaymentStatus.SUCCEEDED
    
    def get_yookassa_status(self) -> Dict[str, Any]:
        """
        Получить статус инициализации YooKassa
        
        Returns:
            Dict с информацией о статусе
        """
        shop_id = getattr(config, 'YOOKASSA_SHOP_ID', None)
        secret_key = getattr(config, 'YOOKASSA_SECRET_KEY', None)
        
        return {
            "initialized": self.yookassa is not None,
            "shop_id_configured": bool(shop_id),
            "secret_key_configured": bool(secret_key),
            "test_mode": getattr(config, 'YOOKASSA_TEST_MODE', True),
            "shop_id_length": len(shop_id) if shop_id else 0,
            "secret_key_length": len(secret_key) if secret_key else 0,
            "shop_id_preview": f"{shop_id[:4]}..." if shop_id and len(shop_id) > 4 else shop_id,
            "secret_key_preview": f"{secret_key[:8]}..." if secret_key and len(secret_key) > 8 else secret_key
        }
    
    # NOWPayments методы
    async def get_available_crypto_currencies(self) -> List[CryptocurrencyInfo]:
        """
        Получить список доступных криптовалют
        
        Returns:
            List[CryptocurrencyInfo]: Список доступных криптовалют
        """
        if not self.nowpayments:
            logger.error("NOWPayments не инициализирована")
            return []
        
        try:
            return await self.nowpayments.get_available_currencies()
        except Exception as e:
            logger.error(f"Ошибка получения криптовалют: {e}")
            return []
    
    async def create_crypto_subscription_payment(
        self,
        user_id: int,
        subscription_type: str,
        amount: float,
        description: str,
        crypto_currency: str = "BTC"
    ) -> Optional[NOWPaymentData]:
        """
        Создать криптоплатеж для подписки
        
        Args:
            user_id: ID пользователя
            subscription_type: Тип подписки
            amount: Сумма в фиатной валюте
            description: Описание
            crypto_currency: Криптовалюта для оплаты
            
        Returns:
            NOWPaymentData или None при ошибке
        """
        if not self.nowpayments:
            logger.error("NOWPayments не инициализирована")
            return None
        
        try:
            # Генерируем уникальный ID заказа
            order_id = f"sub_{user_id}_{subscription_type}_{uuid.uuid4().hex[:8]}"
            
            # URL для уведомлений
            ipn_callback_url = f"https://t.me/{config.TELEGRAM_BOT_USERNAME}/webhook/nowpayments"
            
            # Метаданные платежа
            metadata = {
                "user_id": str(user_id),
                "subscription_type": subscription_type,
                "payment_type": "subscription"
            }
            
            payment = await self.nowpayments.create_payment(
                price_amount=amount,
                price_currency="RUB",
                pay_currency=crypto_currency,
                order_id=order_id,
                order_description=description,
                ipn_callback_url=ipn_callback_url,
                customer_email=None,
                payout_address=getattr(config, 'NOWPAYMENTS_PAYOUT_ADDRESS', None),
                payout_currency=getattr(config, 'NOWPAYMENTS_PAYOUT_CURRENCY', 'BTC'),
                metadata=metadata
            )
            
            if payment:
                logger.info(f"Создан криптоплатеж для подписки: {payment.payment_id}")
            
            return payment
            
        except Exception as e:
            logger.error(f"Ошибка создания криптоплатежа подписки: {e}")
            return None
    
    async def create_crypto_analyses_payment(
        self,
        user_id: int,
        analyses_count: int,
        amount: float,
        description: str,
        crypto_currency: str = "BTC"
    ) -> Optional[NOWPaymentData]:
        """
        Создать криптоплатеж для покупки анализов
        
        Args:
            user_id: ID пользователя
            analyses_count: Количество анализов
            amount: Сумма в фиатной валюте
            description: Описание
            crypto_currency: Криптовалюта для оплаты
            
        Returns:
            NOWPaymentData или None при ошибке
        """
        if not self.nowpayments:
            logger.error("NOWPayments не инициализирована")
            return None
        
        try:
            # Генерируем уникальный ID заказа
            order_id = f"analyses_{user_id}_{analyses_count}_{uuid.uuid4().hex[:8]}"
            
            # URL для уведомлений
            ipn_callback_url = f"https://t.me/{config.TELEGRAM_BOT_USERNAME}/webhook/nowpayments"
            
            # Метаданные платежа
            metadata = {
                "user_id": str(user_id),
                "analyses_count": str(analyses_count),
                "payment_type": "analyses"
            }
            
            payment = await self.nowpayments.create_payment(
                price_amount=amount,
                price_currency="RUB",
                pay_currency=crypto_currency,
                order_id=order_id,
                order_description=description,
                ipn_callback_url=ipn_callback_url,
                customer_email=None,
                payout_address=getattr(config, 'NOWPAYMENTS_PAYOUT_ADDRESS', None),
                payout_currency=getattr(config, 'NOWPAYMENTS_PAYOUT_CURRENCY', 'BTC'),
                metadata=metadata
            )
            
            if payment:
                logger.info(f"Создан криптоплатеж для анализов: {payment.payment_id}")
            
            return payment
            
        except Exception as e:
            logger.error(f"Ошибка создания криптоплатежа анализов: {e}")
            return None
    
    async def check_crypto_payment_status(self, payment_id: str) -> Optional[NOWPaymentData]:
        """
        Проверить статус криптоплатежа
        
        Args:
            payment_id: ID платежа
            
        Returns:
            NOWPaymentData или None при ошибке
        """
        if not self.nowpayments:
            logger.error("NOWPayments не инициализирована")
            return None
        
        try:
            return await self.nowpayments.get_payment_status(payment_id)
        except Exception as e:
            logger.error(f"Ошибка проверки статуса криптоплатежа: {e}")
            return None
    
    def is_crypto_payment_successful(self, payment: NOWPaymentData) -> bool:
        """
        Проверить успешность криптоплатежа
        
        Args:
            payment: Данные криптоплатежа
            
        Returns:
            bool: True если платеж успешен
        """
        if not self.nowpayments:
            return False
        
        return self.nowpayments.is_payment_successful(payment)
    
    async def get_crypto_price_estimate(
        self, 
        amount: float, 
        crypto_currency: str
    ) -> Optional[float]:
        """
        Получить примерную цену в криптовалюте
        
        Args:
            amount: Сумма в фиатной валюте
            crypto_currency: Криптовалюта
            
        Returns:
            float или None при ошибке
        """
        if not self.nowpayments:
            logger.error("NOWPayments не инициализирована")
            return None
        
        try:
            return await self.nowpayments.get_estimated_price(
                amount=amount,
                currency_from="RUB",
                currency_to=crypto_currency
            )
        except Exception as e:
            logger.error(f"Ошибка получения цены криптовалюты: {e}")
            return None


# Глобальный экземпляр менеджера платежей
payment_manager = PaymentManager()
