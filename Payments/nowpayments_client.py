"""
Модуль для работы с NOWPayments API
"""

import asyncio
import logging
import uuid
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from enum import Enum

import aiohttp
import hmac
import hashlib
import json
from config import config

logger = logging.getLogger(__name__)


class NOWPaymentStatus(Enum):
    """Статусы платежа NOWPayments"""
    NEW = "new"
    WAITING = "waiting"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    SENDING = "sending"
    PARTIALLY_PAID = "partially_paid"
    FINISHED = "finished"
    FAILED = "failed"
    REFUNDED = "refunded"
    EXPIRED = "expired"


@dataclass
class NOWPaymentData:
    """Данные платежа NOWPayments"""
    payment_id: str
    status: NOWPaymentStatus
    amount: float
    currency: str
    pay_currency: str
    description: str = ""
    payment_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class CryptocurrencyInfo:
    """Информация о криптовалюте"""
    symbol: str
    name: str
    is_available: bool
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None


class NOWPaymentsClient:
    """Клиент для работы с API NOWPayments"""
    
    def __init__(self, api_key: str, ipn_secret: str, sandbox: bool = True, public_api_key: str = None):
        self.api_key = api_key
        self.public_api_key = public_api_key
        self.ipn_secret = ipn_secret
        self.sandbox = sandbox
        self.base_url = "https://api.nowpayments.io/v1" if not sandbox else "https://api-sandbox.nowpayments.io/v1"
        
        logger.info(f"NOWPayments клиент инициализирован (sandbox: {sandbox})")
    
    def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки для API запросов"""
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _get_public_headers(self) -> Dict[str, str]:
        """Получить заголовки для публичных API запросов"""
        api_key = self.public_api_key if self.public_api_key else self.api_key
        return {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
    
    def _verify_ipn_signature(self, payload: str, signature: str) -> bool:
        """Проверить подпись IPN уведомления"""
        try:
            expected_signature = hmac.new(
                self.ipn_secret.encode(),
                payload.encode(),
                hashlib.sha512
            ).hexdigest()
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Ошибка проверки подписи IPN: {e}")
            return False
    
    async def get_available_currencies(self) -> List[CryptocurrencyInfo]:
        """
        Получить список доступных криптовалют
        
        Returns:
            List[CryptocurrencyInfo]: Список доступных криптовалют
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/currencies",
                    headers=self._get_public_headers()
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        currencies = []
                        
                        for currency in result.get("currencies", []):
                            currencies.append(CryptocurrencyInfo(
                                symbol=currency.get("symbol", ""),
                                name=currency.get("name", ""),
                                is_available=currency.get("is_available", False),
                                min_amount=currency.get("min_amount"),
                                max_amount=currency.get("max_amount")
                            ))
                        
                        logger.info(f"Получено {len(currencies)} доступных криптовалют")
                        return currencies
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка получения криптовалют: {response.status} - {error_text}")
                        return []
                        
        except Exception as e:
            logger.error(f"Ошибка при получении криптовалют: {e}")
            return []
    
    async def get_estimated_price(
        self, 
        amount: float, 
        currency_from: str, 
        currency_to: str
    ) -> Optional[float]:
        """
        Получить примерную цену конвертации
        
        Args:
            amount: Сумма
            currency_from: Исходная валюта
            currency_to: Целевая валюта
            
        Returns:
            float или None при ошибке
        """
        try:
            params = {
                "amount": amount,
                "currency_pair": f"{currency_from.lower()}_{currency_to.lower()}"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/estimate",
                    headers=self._get_public_headers(),
                    params=params
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        estimated_amount = result.get("estimated_amount")
                        logger.info(f"Примерная цена: {amount} {currency_from} = {estimated_amount} {currency_to}")
                        return float(estimated_amount) if estimated_amount else None
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка получения цены: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Ошибка при получении цены: {e}")
            return None
    
    async def create_payment(
        self,
        price_amount: float,
        price_currency: str,
        pay_currency: str,
        order_id: str,
        order_description: str,
        ipn_callback_url: Optional[str] = None,
        case: Optional[str] = None,
        customer_email: Optional[str] = None,
        payout_address: Optional[str] = None,
        payout_currency: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[NOWPaymentData]:
        """
        Создать платеж
        
        Args:
            price_amount: Сумма платежа
            price_currency: Валюта платежа
            pay_currency: Криптовалюта для оплаты
            order_id: ID заказа
            order_description: Описание заказа
            ipn_callback_url: URL для уведомлений
            case: Тип платежа
            customer_email: Email клиента
            payout_address: Адрес для выплат
            payout_currency: Валюта для выплат
            metadata: Дополнительные данные
            
        Returns:
            NOWPaymentData или None при ошибке
        """
        try:
            payment_data = {
                "price_amount": price_amount,
                "price_currency": price_currency,
                "pay_currency": pay_currency,
                "order_id": order_id,
                "order_description": order_description
            }
            
            if ipn_callback_url:
                payment_data["ipn_callback_url"] = ipn_callback_url
            if case:
                payment_data["case"] = case
            if customer_email:
                payment_data["customer_email"] = customer_email
            if payout_address:
                payment_data["payout_address"] = payout_address
            if payout_currency:
                payment_data["payout_currency"] = payout_currency
            if metadata:
                payment_data["metadata"] = metadata
            
            # Логируем данные запроса для отладки
            logger.info(f"Отправляем запрос к NOWPayments API: {payment_data}")
            logger.info(f"Заголовки: {self._get_headers()}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/payment",
                    json=payment_data,
                    headers=self._get_headers()
                ) as response:
                    if response.status == 201:
                        result = await response.json()
                        
                        payment = NOWPaymentData(
                            payment_id=result["payment_id"],
                            status=NOWPaymentStatus(result["payment_status"]),
                            amount=float(result["price_amount"]),
                            currency=result["price_currency"],
                            pay_currency=result["pay_currency"],
                            description=result.get("order_description", ""),
                            payment_url=result.get("pay_url"),
                            metadata=result.get("metadata", {}),
                            created_at=result.get("created_at"),
                            updated_at=result.get("updated_at")
                        )
                        
                        logger.info(f"Платеж создан: {payment.payment_id}, статус: {payment.status.value}")
                        return payment
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка создания платежа: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Ошибка при создании платежа: {e}")
            return None
    
    async def get_payment_status(self, payment_id: str) -> Optional[NOWPaymentData]:
        """
        Получить статус платежа
        
        Args:
            payment_id: ID платежа
            
        Returns:
            NOWPaymentData или None при ошибке
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/payment/{payment_id}",
                    headers=self._get_headers()
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        payment = NOWPaymentData(
                            payment_id=result["payment_id"],
                            status=NOWPaymentStatus(result["payment_status"]),
                            amount=float(result["price_amount"]),
                            currency=result["price_currency"],
                            pay_currency=result["pay_currency"],
                            description=result.get("order_description", ""),
                            payment_url=result.get("pay_url"),
                            metadata=result.get("metadata", {}),
                            created_at=result.get("created_at"),
                            updated_at=result.get("updated_at")
                        )
                        
                        logger.info(f"Получен платеж: {payment.payment_id}, статус: {payment.status.value}")
                        return payment
                    else:
                        error_text = await response.text()
                        logger.error(f"Ошибка получения платежа: {response.status} - {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Ошибка при получении платежа: {e}")
            return None
    
    def is_payment_successful(self, payment: NOWPaymentData) -> bool:
        """
        Проверить успешность платежа
        
        Args:
            payment: Данные платежа
            
        Returns:
            bool: True если платеж успешен
        """
        return payment.status in [
            NOWPaymentStatus.CONFIRMED,
            NOWPaymentStatus.FINISHED
        ]
    
    def is_payment_failed(self, payment: NOWPaymentData) -> bool:
        """
        Проверить неудачность платежа
        
        Args:
            payment: Данные платежа
            
        Returns:
            bool: True если платеж неудачен
        """
        return payment.status in [
            NOWPaymentStatus.FAILED,
            NOWPaymentStatus.EXPIRED,
            NOWPaymentStatus.REFUNDED
        ]
    
    def is_payment_pending(self, payment: NOWPaymentData) -> bool:
        """
        Проверить ожидание платежа
        
        Args:
            payment: Данные платежа
            
        Returns:
            bool: True если платеж в ожидании
        """
        return payment.status in [
            NOWPaymentStatus.NEW,
            NOWPaymentStatus.WAITING,
            NOWPaymentStatus.CONFIRMING,
            NOWPaymentStatus.SENDING,
            NOWPaymentStatus.PARTIALLY_PAID
        ]
    
    async def process_ipn_notification(self, payload: str, signature: str) -> Optional[NOWPaymentData]:
        """
        Обработать IPN уведомление
        
        Args:
            payload: Тело уведомления
            signature: Подпись уведомления
            
        Returns:
            NOWPaymentData или None при ошибке
        """
        try:
            # Проверяем подпись
            if not self._verify_ipn_signature(payload, signature):
                logger.error("Неверная подпись IPN уведомления")
                return None
            
            # Парсим данные
            data = json.loads(payload)
            payment_id = data.get("payment_id")
            
            if not payment_id:
                logger.error("Отсутствует payment_id в IPN уведомлении")
                return None
            
            # Получаем актуальный статус платежа
            payment = await self.get_payment_status(payment_id)
            
            if payment:
                logger.info(f"IPN уведомление обработано: {payment_id}, статус: {payment.status.value}")
            
            return payment
            
        except Exception as e:
            logger.error(f"Ошибка обработки IPN уведомления: {e}")
            return None
