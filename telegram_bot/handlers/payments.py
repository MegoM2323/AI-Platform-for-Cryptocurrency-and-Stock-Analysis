"""
Обработчики для подписок и платежей
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebhookInfo
from aiogram.fsm.context import FSMContext
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
import json
import aiosqlite
import asyncio
from datetime import datetime, timedelta

from ..states import SubscriptionStates, PurchaseStates
from ..keyboards import (
    get_main_keyboard, 
    get_subscription_keyboard, 
    get_subscription_plans_keyboard,
    get_payment_method_keyboard,
    get_crypto_currency_keyboard,
    get_all_crypto_currencies_keyboard
)
from database import Database
from config import config
from Payments.payment_system import payment_manager, PaymentStatus
import logging

logger = logging.getLogger(__name__)
router = Router()

# Словарь для хранения активных проверок платежей
active_payment_checks = {}

# Словарь для хранения обработанных платежей (защита от дублирования)
processed_payments = {}

async def start_payment_monitoring(payment_id: str, user_id: int, payment_type: str, db: Database, bot, timeout_minutes: int = 10):
    """Запустить мониторинг платежа с автоматической проверкой"""
    try:
        start_time = datetime.now()
        timeout = timedelta(minutes=timeout_minutes)
        
        logger.info(f"Запуск мониторинга платежа {payment_id} для пользователя {user_id}")
        
        # Сохраняем информацию о проверке
        active_payment_checks[payment_id] = {
            'user_id': user_id,
            'payment_type': payment_type,
            'start_time': start_time,
            'timeout': timeout,
            'db': db,
            'bot': bot,
            'status': 'monitoring'
        }
        
        # Запускаем фоновую задачу мониторинга
        asyncio.create_task(monitor_payment_status(payment_id))
        
    except Exception as e:
        logger.error(f"Ошибка запуска мониторинга платежа {payment_id}: {e}")


async def monitor_payment_status(payment_id: str):
    """Мониторинг статуса платежа в фоновом режиме"""
    try:
        if payment_id not in active_payment_checks:
            logger.warning(f"Платеж {payment_id} не найден в активных проверках")
            return
            
        check_info = active_payment_checks[payment_id]
        user_id = check_info['user_id']
        payment_type = check_info['payment_type']
        db = check_info['db']
        bot = check_info['bot']
        start_time = check_info['start_time']
        timeout = check_info['timeout']
        
        logger.info(f"Начало автоматического мониторинга платежа {payment_id} для пользователя {user_id}, тип: {payment_type}")
        
        # Проверяем каждые 30 секунд в течение 10 минут
        check_interval = 30  # секунд
        max_checks = int(timeout.total_seconds() / check_interval)
        
        for attempt in range(max_checks):
            await asyncio.sleep(check_interval)
            
            # Проверяем, не истек ли таймаут
            if datetime.now() - start_time > timeout:
                logger.info(f"Таймаут автоматического мониторинга платежа {payment_id} (прошло {timeout.total_seconds()/60} минут)")
                await handle_payment_timeout(payment_id, user_id, bot)
                break
            
            # Проверяем статус платежа
            try:
                logger.info(f"Автоматическая проверка {attempt + 1}/{max_checks} для платежа {payment_id}")
                
                if payment_type == "yookassa":
                    payment = await payment_manager.check_payment_status(payment_id)
                    if payment:
                        logger.info(f"Получен статус платежа {payment_id}: {payment.status.value}")
                        if payment_manager.is_payment_successful(payment):
                            logger.info(f"Платеж {payment_id} успешно оплачен, начинаем обработку")
                            await handle_successful_payment(payment_id, user_id, payment, db, bot)
                            break
                    else:
                        logger.warning(f"Не удалось получить статус платежа {payment_id} при попытке {attempt + 1}")
                        
                elif payment_type == "crypto":
                    payment = await payment_manager.check_crypto_payment_status(payment_id)
                    if payment:
                        logger.info(f"Получен статус криптоплатежа {payment_id}: {payment.status.value}")
                        if payment_manager.is_crypto_payment_successful(payment):
                            logger.info(f"Криптоплатеж {payment_id} успешно оплачен, начинаем обработку")
                            await handle_successful_crypto_payment(payment_id, user_id, payment, db, bot)
                            break
                    else:
                        logger.warning(f"Не удалось получить статус криптоплатежа {payment_id} при попытке {attempt + 1}")
                        
            except Exception as e:
                logger.error(f"Ошибка проверки статуса платежа {payment_id} при попытке {attempt + 1}: {e}", exc_info=True)
                # Продолжаем мониторинг даже при ошибке
            
            if attempt < max_checks - 1:
                logger.debug(f"Проверка {attempt + 1}/{max_checks} для платежа {payment_id} - платеж еще не оплачен, следующая проверка через {check_interval} секунд")
        
        # Удаляем из активных проверок
        if payment_id in active_payment_checks:
            del active_payment_checks[payment_id]
            logger.info(f"Платеж {payment_id} удален из активного мониторинга")
            
    except Exception as e:
        logger.error(f"Критическая ошибка мониторинга платежа {payment_id}: {e}", exc_info=True)
        if payment_id in active_payment_checks:
            del active_payment_checks[payment_id]


async def handle_successful_payment(payment_id: str, user_id: int, payment, db: Database, bot):
    """Обработать успешный платеж (автоматическая проверка)"""
    try:
        logger.info(f"🤖 Автоматическая обработка успешного платежа {payment_id} для пользователя {user_id}")
        
        # ✅ Проверяем, не был ли платеж уже обработан (ручной проверкой или другим процессом)
        already_processed = await db.is_payment_processed(payment_id)
        if already_processed:
            logger.info(f"⏭️ Платеж {payment_id} уже обработан (возможно, ручной проверкой), пропускаем автоматическую обработку")
            # Удаляем из активных проверок
            if payment_id in active_payment_checks:
                del active_payment_checks[payment_id]
            return
        
        metadata = payment.metadata or {}
        payment_type = metadata.get("payment_type", "")
        
        if payment_type == "subscription":
            subscription_type = metadata.get("subscription_type", "basic")
            
            # Обрабатываем успешный платеж
            success, plan_name, monthly_limit = await process_successful_payment(
                payment_id, payment_type, user_id, db, subscription_type
            )
            
            if success:
                # Уведомляем пользователя только если мы успешно обработали платеж
                await notify_user_about_payment_success(user_id, payment_id, plan_name, monthly_limit, bot, db)
                
                # Удаляем из активных проверок
                if payment_id in active_payment_checks:
                    del active_payment_checks[payment_id]
                
                logger.info(f"✅ Платеж {payment_id} успешно обработан автоматически для пользователя {user_id}")
            else:
                logger.warning(f"⚠️ Платеж {payment_id} не был обработан автоматически (возможно, уже обработан)")
        else:
            logger.warning(f"⚠️ Неизвестный тип платежа {payment_type} для платежа {payment_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка автоматической обработки успешного платежа {payment_id}: {e}", exc_info=True)


async def handle_successful_crypto_payment(payment_id: str, user_id: int, payment, db: Database, bot):
    """Обработать успешный криптоплатеж (автоматическая проверка)"""
    try:
        logger.info(f"🤖 Автоматическая обработка успешного криптоплатежа {payment_id} для пользователя {user_id}")
        
        # ✅ Проверяем, не был ли платеж уже обработан (ручной проверкой или другим процессом)
        already_processed = await db.is_payment_processed(payment_id)
        if already_processed:
            logger.info(f"⏭️ Криптоплатеж {payment_id} уже обработан (возможно, ручной проверкой), пропускаем автоматическую обработку")
            # Удаляем из активных проверок
            if payment_id in active_payment_checks:
                del active_payment_checks[payment_id]
            return
        
        metadata = payment.metadata or {}
        payment_type = metadata.get("payment_type", "")
        
        if payment_type == "subscription":
            subscription_type = metadata.get("subscription_type", "basic")
            
            # Обрабатываем успешный криптоплатеж
            success, plan_name, monthly_limit = await process_successful_payment(
                payment_id, payment_type, user_id, db, subscription_type
            )
            
            if success:
                # Уведомляем пользователя только если мы успешно обработали платеж
                await notify_user_about_payment_success(user_id, payment_id, plan_name, monthly_limit, bot, db)
                
                # Удаляем из активных проверок
                if payment_id in active_payment_checks:
                    del active_payment_checks[payment_id]
                
                logger.info(f"✅ Криптоплатеж {payment_id} успешно обработан автоматически для пользователя {user_id}")
            else:
                logger.warning(f"⚠️ Криптоплатеж {payment_id} не был обработан автоматически (возможно, уже обработан)")
        else:
            logger.warning(f"⚠️ Неизвестный тип криптоплатежа {payment_type} для платежа {payment_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка автоматической обработки успешного криптоплатежа {payment_id}: {e}", exc_info=True)


async def handle_payment_timeout(payment_id: str, user_id: int, bot):
    """Обработать таймаут платежа"""
    try:
        timeout_text = f"""
⏰ <b>Время ожидания платежа истекло</b>

Платеж <code>{payment_id}</code> не был подтвержден в течение 10 минут.

<b>Что можно сделать:</b>
• Проверить статус платежа вручную
• Создать новый платеж
• Обратиться в поддержку

Если вы уже оплатили, нажмите "Проверить вручную"
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Проверить вручную",
                callback_data=f"manual_check_payment_{payment_id}"
            )],
            [InlineKeyboardButton(
                text="💎 Создать новый платеж",
                callback_data="show_subscriptions"
            )],
            [InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_subscription"
            )]
        ])
        
        await bot.send_message(
            chat_id=user_id,
            text=timeout_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Удаляем из активных проверок
        if payment_id in active_payment_checks:
            del active_payment_checks[payment_id]
            
    except Exception as e:
        logger.error(f"Ошибка обработки таймаута платежа {payment_id}: {e}")


async def process_successful_payment(payment_id: str, payment_type: str, user_id: int, db: Database, subscription_type: str = None):
    """Обработать успешный платеж и активировать подписку"""
    try:
        # ✅ ПРОВЕРКА 1: Проверяем в базе данных, не был ли уже обработан этот платёж
        is_processed = await db.is_payment_processed(payment_id)
        if is_processed:
            logger.warning(f"⚠️ Платёж {payment_id} уже был обработан ранее (найден в БД), пропускаем повторную обработку")
            # Получаем информацию об уже обработанном платеже
            processed_info = await db.get_processed_payment(payment_id)
            if processed_info:
                return (True, processed_info['plan_name'], processed_info['analyses_added'])
            return (False, None, 0)
        
        # ✅ ПРОВЕРКА 2: Проверяем в памяти (на случай быстрых повторных вызовов)
        if payment_id in processed_payments:
            logger.warning(f"⚠️ Платёж {payment_id} уже обрабатывается в данный момент (найден в памяти), пропускаем")
            return processed_payments[payment_id]
        
        # Блокируем платеж в памяти для предотвращения одновременной обработки
        processed_payments[payment_id] = (False, None, 0)
        
        if payment_type == "subscription":
            # Если тип подписки не передан, получаем из базы данных
            if not subscription_type:
                async with aiosqlite.connect(db.db_path) as db_conn:
                    db_conn.row_factory = aiosqlite.Row
                    async with db_conn.execute(
                        "SELECT subscription_type FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                        (user_id,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            subscription_type = row['subscription_type']
                        else:
                            subscription_type = 'basic'  # По умолчанию
            
            # Получаем план подписки
            plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
            days = plan['days']
            
            logger.info(f"🔄 Начинаем обработку платежа {payment_id}: пользователь {user_id}, план {subscription_type}")
            
            # Проверяем, есть ли уже активная подписка
            user_data = await db.get_user(user_id)
            is_premium = user_data.get('is_premium', 0)
            premium_until = user_data.get('premium_until')
            current_additional_analyses = user_data.get('additional_analyses', 0)
            
            # Если подписка уже активна, продлеваем её
            if is_premium and premium_until:
                try:
                    from datetime import datetime
                    premium_until_dt = datetime.fromisoformat(premium_until.replace('Z', '+00:00'))
                    if premium_until_dt > datetime.now():
                        # Подписка активна, продлеваем
                        from datetime import timedelta
                        new_premium_until = premium_until_dt + timedelta(days=days)
                        async with aiosqlite.connect(db.db_path) as db_conn:
                            await db_conn.execute(
                                """UPDATE users 
                                   SET premium_until = ?
                                   WHERE user_id = ?""",
                                (new_premium_until.isoformat(), user_id)
                            )
                            await db_conn.commit()
                        logger.info(f"📅 Подписка продлена для пользователя {user_id} до {new_premium_until}")
                    else:
                        # Подписка истекла, активируем новую
                        await db.grant_premium(user_id, days=days)
                        logger.info(f"✨ Активирована новая подписка для пользователя {user_id}")
                except Exception as e:
                    # Ошибка парсинга даты, активируем новую подписку
                    logger.error(f"Ошибка парсинга даты premium_until: {e}")
                    await db.grant_premium(user_id, days=days)
            else:
                # Нет активной подписки, активируем новую
                await db.grant_premium(user_id, days=days)
                logger.info(f"✨ Активирована первая подписка для пользователя {user_id}")
            
            # ✅ КРИТИЧЕСКИ ВАЖНО: СНАЧАЛА помечаем платеж как обработанный В БАЗЕ ДАННЫХ
            # Это должно быть ДО активации подписки для предотвращения дублирования!
            
            # ✅ ИСПРАВЛЕНИЕ: Подписка НЕ начисляет additional_analyses
            # Подписка только дает месячный лимит анализов согласно тарифу
            # Дополнительные анализы начисляются только при покупке отдельных пакетов!
            analyses_added = 0  # Для подписки не начисляем дополнительные анализы
            
            payment_marked = await db.mark_payment_processed(
                payment_id=payment_id,
                user_id=user_id,
                payment_type=payment_type,
                subscription_type=subscription_type,
                analyses_added=analyses_added,
                plan_name=plan['name']
            )
            
            if not payment_marked:
                # Платеж уже был обработан другим процессом (race condition)
                logger.warning(f"⚠️ Платеж {payment_id} уже помечен как обработанный другим процессом, пропускаем активацию")
                processed_info = await db.get_processed_payment(payment_id)
                if processed_info:
                    result = (True, processed_info['plan_name'], processed_info['analyses_added'])
                    processed_payments[payment_id] = result
                    return result
                return (False, None, 0)
            
            logger.info(f"🔒 Платеж {payment_id} помечен как обработанный в базе данных (атомарная операция)")
            
            # Создаем запись о подписке
            await db.create_subscription(user_id, subscription_type, plan['price'])
            logger.info(f"📝 Создана запись о подписке {subscription_type} для пользователя {user_id}")
            
            # Получаем месячный лимит анализов для тарифа
            monthly_limit = plan['analyses_per_month']
            
            logger.info(f"✅ Подписка {subscription_type} активирована для пользователя {user_id}")
            logger.info(f"📊 Доступно {monthly_limit} анализов в месяц согласно тарифу {subscription_type}")
            
            # Сохраняем информацию об обработке платежа в памяти
            result = (True, plan['name'], monthly_limit)  # Возвращаем месячный лимит для информирования
            processed_payments[payment_id] = result
            
            return result
        
        return False, None, 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки успешного платежа {payment_id}: {e}", exc_info=True)
        # Удаляем из памяти при ошибке, чтобы можно было повторить попытку
        if payment_id in processed_payments:
            del processed_payments[payment_id]
        return False, None, 0


async def notify_user_about_payment_success(user_id: int, payment_id: str, plan_name: str, monthly_limit: int, bot, db: Database = None):
    """Уведомить пользователя об успешной оплате"""
    try:
        logger.info(f"📧 Отправка уведомления пользователю {user_id} о платеже {payment_id}")
        
        # Получаем информацию о пользователе
        if db:
            user_data = await db.get_user(user_id)
            additional_analyses = user_data.get('additional_analyses', 0) if user_data else 0
        else:
            additional_analyses = 0
        
        success_text = f"""
✅ <b>Платеж успешно обработан!</b>

💎 <b>Подписка {plan_name} активирована!</b>

📊 <b>Доступно анализов в месяц:</b> {monthly_limit}
{f'💰 Дополнительные анализы на счету: <b>{additional_analyses}</b>' if additional_analyses > 0 else ''}

<b>ID платежа:</b> <code>{payment_id}</code>

💡 <b>Информация:</b>
• Месячный лимит обновляется каждый месяц
• Дополнительные анализы можно купить отдельно
• Неиспользованные дополнительные анализы не сгорают

Теперь вы можете использовать анализы для исследования криптовалют!
        """
        
        await bot.send_message(
            chat_id=user_id,
            text=success_text,
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        
        logger.info(f"✅ Уведомление отправлено пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}", exc_info=True)


# Webhook обработчики для автоматической обработки платежей
async def yookassa_webhook_handler(request):
    """Обработчик webhook от ЮКасса"""
    try:
        data = await request.json()
        payment_id = data.get('object', {}).get('id')
        status = data.get('object', {}).get('status')
        
        logger.info(f"Получен webhook от ЮКасса: payment_id={payment_id}, status={status}")
        
        if status == 'succeeded' and payment_id:
            # Получаем информацию о платеже
            payment = await payment_manager.check_payment_status(payment_id)
            if payment and payment_manager.is_payment_successful(payment):
                metadata = payment.metadata or {}
                user_id = int(metadata.get('user_id', 0))
                payment_type = metadata.get('payment_type', '')
                
                logger.info(f"Обработка успешного платежа: user_id={user_id}, payment_type={payment_type}")
                
                if user_id and payment_type == "subscription":
                    # Получаем тип подписки из метаданных
                    subscription_type = metadata.get('subscription_type', 'basic')
                    
                    # Инициализируем Database для обработки платежа
                    from database import Database
                    from config import config
                    db = Database(config.DATABASE_PATH)
                    
                    # Обрабатываем успешный платеж
                    success, plan_name, monthly_limit = await process_successful_payment(
                        payment_id, payment_type, user_id, 
                        db,
                        subscription_type
                    )
                    
                    if success:
                        # Получаем экземпляр бота для уведомления
                        from telegram_bot.bot import bot
                        await notify_user_about_payment_success(user_id, payment_id, plan_name, monthly_limit, bot, db)
                        logger.info(f"Платеж {payment_id} успешно обработан для пользователя {user_id}")
                    else:
                        logger.error(f"Не удалось обработать платеж {payment_id} для пользователя {user_id}")
                else:
                    logger.warning(f"Неизвестный тип платежа или отсутствует user_id: {payment_type}, user_id: {user_id}")
        
        return web.Response(text="OK")
        
    except Exception as e:
        logger.error(f"Ошибка обработки webhook ЮКасса: {e}")
        return web.Response(text="ERROR", status=500)


async def nowpayments_webhook_handler(request):
    """Обработчик webhook от NOWPayments"""
    try:
        # Получаем подпись из заголовков
        signature = request.headers.get('x-nowpayments-sig')
        payload = await request.text()
        
        logger.info(f"Получен webhook от NOWPayments: signature={bool(signature)}")
        
        if not signature:
            logger.warning("Отсутствует подпись в webhook NOWPayments")
            return web.Response(text="No signature", status=400)
        
        # Обрабатываем IPN уведомление
        payment = await payment_manager.nowpayments.process_ipn_notification(payload, signature)
        
        if payment and payment_manager.is_crypto_payment_successful(payment):
            metadata = payment.metadata or {}
            user_id = int(metadata.get('user_id', 0))
            payment_type = metadata.get('payment_type', '')
            
            logger.info(f"Обработка успешного криптоплатежа: user_id={user_id}, payment_type={payment_type}")
            
            if user_id and payment_type == "subscription":
                # Получаем тип подписки из метаданных
                subscription_type = metadata.get('subscription_type', 'basic')
                
                # Инициализируем Database для обработки платежа
                from database import Database
                from config import config
                db = Database(config.DATABASE_PATH)
                
                # Обрабатываем успешный криптоплатеж
                success, plan_name, monthly_limit = await process_successful_payment(
                    payment.payment_id, payment_type, user_id,
                    db,
                    subscription_type
                )
                
                if success:
                    # Получаем экземпляр бота для уведомления
                    from telegram_bot.bot import bot
                    await notify_user_about_payment_success(user_id, payment.payment_id, plan_name, monthly_limit, bot, db)
                    logger.info(f"Криптоплатеж {payment.payment_id} успешно обработан для пользователя {user_id}")
                else:
                    logger.error(f"Не удалось обработать криптоплатеж {payment.payment_id} для пользователя {user_id}")
            else:
                logger.warning(f"Неизвестный тип криптоплатежа или отсутствует user_id: {payment_type}, user_id: {user_id}")
        
        return web.Response(text="OK")
        
    except Exception as e:
        logger.error(f"Ошибка обработки webhook NOWPayments: {e}")
        return web.Response(text="ERROR", status=500)


@router.message(Command("subscribe"))
@router.message(F.text == "💎 Подписка")
async def show_subscription_options(message: Message, state: FSMContext, db: Database):
    """Показать варианты подписки"""
    await state.clear()
    
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    # Получаем информацию о подписке
    subscription_plan = await db.get_user_subscription_plan(user_id)
    is_premium = user_data.get('is_premium', 0)
    premium_until = user_data.get('premium_until')
    additional_analyses = await db.get_additional_analyses(user_id)
    
    # Получаем оставшиеся анализы
    from datetime import date
    current_month = date.today().replace(day=1)
    monthly_analyses = await db.get_monthly_analyses_count(user_id, current_month)
    
    # Определяем лимиты и название плана
    if subscription_plan == 'free':
        limit = config.FREE_ANALYSES_PER_MONTH
        plan_name = "Free"
    elif subscription_plan == 'basic':
        plan_name = "Basic"
        limit = config.BASIC_ANALYSES_PER_MONTH
    elif subscription_plan == 'trader':
        plan_name = "Trader"
        limit = config.TRADER_ANALYSES_PER_MONTH
    elif subscription_plan == 'pro':
        plan_name = "Pro"
        limit = config.PRO_ANALYSES_PER_MONTH
    elif subscription_plan == 'elite':
        plan_name = "Elite"
        limit = config.ELITE_ANALYSES_PER_MONTH
    elif subscription_plan == 'premium':
        # Для общего премиум статуса определяем по дополнительным анализам
        if additional_analyses >= 500:
            plan_name = "Elite"
            limit = config.ELITE_ANALYSES_PER_MONTH
        elif additional_analyses >= 150:
            plan_name = "Pro"
            limit = config.PRO_ANALYSES_PER_MONTH
        elif additional_analyses >= 50:
            plan_name = "Trader"
            limit = config.TRADER_ANALYSES_PER_MONTH
        else:
            plan_name = "Basic"
            limit = config.BASIC_ANALYSES_PER_MONTH
    else:
        plan_name = "Free"
        limit = config.FREE_ANALYSES_PER_MONTH
    
    remaining_analyses = max(0, limit - monthly_analyses + additional_analyses)
    
    # Определяем текущий статус
    if is_premium and premium_until:
        from datetime import datetime
        try:
            premium_until_dt = datetime.fromisoformat(premium_until.replace('Z', '+00:00'))
            if premium_until_dt > datetime.now():
                status_text = f"✅ {plan_name} активна до {premium_until_dt.strftime('%d.%m.%Y')}\nОсталось анализов: {remaining_analyses}"
            else:
                status_text = "❌ Подписка истекла"
        except:
            status_text = f"✅ {plan_name} активна\nОсталось анализов: {remaining_analyses}"
    else:
        status_text = f"❌ Бесплатный тариф\nОсталось анализов: {remaining_analyses}"
    
    subscription_text = f"""
💎 <b>ТАРИФНЫЕ ПЛАНЫ</b>

<b>Текущий статус:</b> {status_text}

<b>🆓 Free:</b>
• 3 анализа в месяц
• Базовый анализ

<b>💎 Доступные тарифы:</b>
• 🥉 Basic - 299₽/мес (15 анализов)
• 🥈 Trader - 899₽/мес (50 анализов)
• 🥇 Pro - 1590₽/мес (150 анализов)
• 💎 Elite - 2990₽/мес (500 анализов)

💡 <b>Важно:</b> При повторной покупке подписки анализы накапливаются!
Это означает, что вы можете накопить больше анализов, покупая подписку несколько раз.

Выберите подходящий тариф:
"""
    
    await message.answer(
        subscription_text,
        reply_markup=get_subscription_keyboard(),
        parse_mode="HTML"
    )


# Обработчики для выбора типа покупки
@router.callback_query(F.data == "show_subscriptions")
async def show_subscription_plans(callback: CallbackQuery):
    """Показать планы подписки"""
    await callback.answer()
    
    plans_text = """
💎 <b>ТАРИФНЫЕ ПЛАНЫ</b>

<b>🆓 Free - 0₽/мес</b>
• 3 анализа в месяц
• Базовый анализ

<b>🥉 Basic - 299₽/мес</b>
• 15 анализов в месяц
• Базовый анализ
• Email поддержка

<b>🥈 Trader - 899₽/мес</b>
• 50 анализов в месяц
• Расширенный анализ
• Приоритетная поддержка
• Технические индикаторы

<b>🥇 Pro - 1590₽/мес</b>
• 150 анализов в месяц
• Полный анализ
• Персональная поддержка
• Ранний доступ к новым функциям
• API доступ

<b>💎 Elite - 2990₽/мес</b>
• 500 анализов в месяц
• VIP анализ
• Персональный менеджер
• Эксклюзивные функции
• Приоритетный API
• Кастомные индикаторы

💡 <b>Особенность:</b> При повторной покупке подписки анализы накапливаются!
Это позволяет накопить больше анализов для интенсивного использования.

Выберите тариф:
    """
    
    await callback.message.edit_text(
        plans_text,
        reply_markup=get_subscription_plans_keyboard(),
        parse_mode="HTML"
    )




@router.callback_query(F.data == "back_to_subscription_menu")
async def back_to_subscription_menu(callback: CallbackQuery):
    """Вернуться к главному меню подписки"""
    await callback.answer()
    
    subscription_text = """
💎 <b>ТАРИФНЫЕ ПЛАНЫ</b>

<b>🆓 Free:</b>
• 3 анализа в месяц
• Базовый анализ

<b>💎 Доступные тарифы:</b>
• 🥉 Basic - 299₽/мес (15 анализов)
• 🥈 Trader - 899₽/мес (50 анализов)
• 🥇 Pro - 1590₽/мес (150 анализов)
• 💎 Elite - 2990₽/мес (500 анализов)

Выберите подходящий тариф:
    """
    
    await callback.message.edit_text(
        subscription_text,
        reply_markup=get_subscription_keyboard(),
        parse_mode="HTML"
    )


# Обработчики для планов подписки
@router.callback_query(F.data == "subscribe_basic")
async def process_basic_subscription(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработка подписки Basic"""
    await callback.answer()
    
    # Сохраняем информацию о выбранном плане
    plan = config.SUBSCRIPTION_PLANS['basic']
    await state.update_data(
        purchase_type="subscription",
        plan_id="basic",
        plan_name="Basic",
        amount=plan['price'],
        days=30
    )
    
    plan = config.SUBSCRIPTION_PLANS['basic']
    payment_text = f"""
🥉 <b>{plan['name']}</b>

<b>Стоимость:</b> {plan['price']}₽/мес

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}

💡 <b>Бонус:</b> При повторной покупке анализы накапливаются!

Выберите способ оплаты:
    """
    
    await callback.message.edit_text(
        payment_text,
        reply_markup=get_payment_method_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "subscribe_trader")
async def process_trader_subscription(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработка подписки Trader"""
    await callback.answer()
    
    # Сохраняем информацию о выбранном плане
    plan = config.SUBSCRIPTION_PLANS['trader']
    await state.update_data(
        purchase_type="subscription",
        plan_id="trader",
        plan_name="Trader",
        amount=plan['price'],
        days=30
    )
    
    plan = config.SUBSCRIPTION_PLANS['trader']
    payment_text = f"""
🥈 <b>{plan['name']}</b>

<b>Стоимость:</b> {plan['price']}₽/мес

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}

💡 <b>Бонус:</b> При повторной покупке анализы накапливаются!

Выберите способ оплаты:
    """
    
    await callback.message.edit_text(
        payment_text,
        reply_markup=get_payment_method_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "subscribe_pro")
async def process_pro_subscription(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработка подписки Pro"""
    await callback.answer()
    
    # Сохраняем информацию о выбранном плане
    plan = config.SUBSCRIPTION_PLANS['pro']
    await state.update_data(
        purchase_type="subscription",
        plan_id="pro",
        plan_name="Pro",
        amount=plan['price'],
        days=30
    )
    
    plan = config.SUBSCRIPTION_PLANS['pro']
    payment_text = f"""
🥇 <b>{plan['name']}</b>

<b>Стоимость:</b> {plan['price']}₽/мес

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}

💡 <b>Бонус:</b> При повторной покупке анализы накапливаются!

Выберите способ оплаты:
    """
    
    await callback.message.edit_text(
        payment_text,
        reply_markup=get_payment_method_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "subscribe_elite")
async def process_elite_subscription(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработка подписки Elite"""
    await callback.answer()
    
    # Сохраняем информацию о выбранном плане
    plan = config.SUBSCRIPTION_PLANS['elite']
    await state.update_data(
        purchase_type="subscription",
        plan_id="elite",
        plan_name="Elite",
        amount=plan['price'],
        days=30
    )
    
    plan = config.SUBSCRIPTION_PLANS['elite']
    payment_text = f"""
💎 <b>{plan['name']}</b>

<b>Стоимость:</b> {plan['price']}₽/мес

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}

💡 <b>Бонус:</b> При повторной покупке анализы накапливаются!

Выберите способ оплаты:
    """
    
    await callback.message.edit_text(
        payment_text,
        reply_markup=get_payment_method_keyboard(),
        parse_mode="HTML"
    )




@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: CallbackQuery, db: Database):
    """Проверить статус платежа (ручная проверка)"""
    # Сразу отвечаем на callback для предотвращения повторных нажатий
    await callback.answer("🔄 Проверяем статус платежа...", show_alert=False)
    
    # Извлекаем ID платежа из callback_data
    payment_id = callback.data.replace("check_payment_", "")
    
    # Проверяем инициализацию YooKassa
    if not payment_manager.yookassa:
        logger.error("YooKassa не инициализирована при проверке платежа")
        await callback.message.edit_text(
            "❌ <b>Система платежей недоступна</b>\n\n"
            "YooKassa не настроена. Обратитесь к администратору.",
            parse_mode="HTML"
        )
        return
    
    try:
        logger.info(f"Ручная проверка статуса платежа {payment_id} пользователем {callback.from_user.id}")
        
        # Проверяем статус платежа
        payment = await payment_manager.check_payment_status(payment_id)
        
        if not payment:
            logger.error(f"Не удалось получить данные платежа {payment_id}")
            await callback.message.edit_text(
                "❌ <b>Ошибка проверки платежа</b>\n\n"
                f"Платеж <code>{payment_id}</code> не найден или недоступен.\n\n"
                "Возможные причины:\n"
                "• Платеж еще не создан\n"
                "• Проблемы с API YooKassa\n"
                "• Неверный ID платежа\n"
                "• Платеж был отменен\n\n"
                "Попробуйте позже или свяжитесь с поддержкой.",
                parse_mode="HTML"
            )
            return
        
        logger.info(f"Получен статус платежа {payment_id}: {payment.status.value}")
        
        # Проверяем успешность платежа
        if payment_manager.is_payment_successful(payment):
            # Удаляем из активных проверок, если есть
            if payment_id in active_payment_checks:
                del active_payment_checks[payment_id]
            
            # Обрабатываем успешный платеж
            user_id = callback.from_user.id
            metadata = payment.metadata or {}
            payment_type = metadata.get("payment_type", "")
            
            logger.info(f"Ручная проверка успешного платежа {payment_id} для пользователя {user_id}, тип: {payment_type}")
            
            # ✅ ПРОВЕРЯЕМ: был ли платеж уже обработан ранее
            already_processed = await db.is_payment_processed(payment_id)
            
            if already_processed:
                # Платеж уже обработан - просто показываем информацию
                logger.info(f"✅ Платеж {payment_id} уже был обработан ранее, показываем информацию")
                processed_info = await db.get_processed_payment(payment_id)
                
                if processed_info and payment_type == "subscription":
                    subscription_type = processed_info['subscription_type']
                    plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
                    
                    # Получаем актуальное количество дополнительных анализов
                    updated_user_data = await db.get_user(user_id)
                    additional_analyses = updated_user_data.get('additional_analyses', 0)
                    
                    success_text = f"""
✅ <b>Платеж уже был обработан ранее</b>

💎 <b>Подписка {processed_info['plan_name']} активирована</b>

📊 <b>Месячный лимит:</b> {plan['analyses_per_month']} анализов
{f'💰 Дополнительные анализы: <b>{additional_analyses}</b>' if additional_analyses > 0 else ''}

<b>ID платежа:</b> <code>{payment.id}</code>

<i>Подписка уже активирована, повторная обработка не требуется.</i>
                    """
                else:
                    success_text = f"""
✅ <b>Платеж уже был обработан ранее</b>

<b>ID платежа:</b> <code>{payment.id}</code>
                    """
                
                # Удаляем inline-сообщение
                try:
                    await callback.message.delete()
                except:
                    pass
                # Отправляем новое сообщение
                await callback.message.answer(
                    success_text,
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML"
                )
                return
            
            # Платеж еще не обработан - обрабатываем его
            if payment_type == "subscription":
                # Получаем информацию о подписке из метаданных
                subscription_type = metadata.get("subscription_type", "basic")
                
                # Используем единую функцию обработки платежа
                success, plan_name, monthly_limit = await process_successful_payment(
                    payment_id, payment_type, user_id, db, subscription_type
                )
                
                if success:
                    # Получаем количество дополнительных анализов
                    updated_user_data = await db.get_user(user_id)
                    additional_analyses = updated_user_data.get('additional_analyses', 0)
                    
                    # Получаем информацию о плане для отображения
                    plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
                    
                    success_text = f"""
✅ <b>Платеж успешно обработан!</b>

💎 <b>Подписка {plan_name} активирована!</b>

📊 <b>Месячный лимит:</b> {monthly_limit} анализов
{f'💰 Дополнительные анализы: <b>{additional_analyses}</b>' if additional_analyses > 0 else ''}

<b>Что входит:</b>
{chr(10).join([f"• {feature}" for feature in plan['features']])}

<b>ID платежа:</b> <code>{payment.id}</code>

💡 <b>Информация:</b>
• Месячный лимит обновляется каждый месяц
• Дополнительные анализы можно купить отдельно
                    """
                    
                    logger.info(f"Платеж {payment_id} успешно обработан для пользователя {user_id}")
                else:
                    logger.error(f"Не удалось обработать платеж {payment_id} для пользователя {user_id}")
                    success_text = f"""
❌ <b>Ошибка обработки платежа</b>

Не удалось активировать подписку. Пожалуйста, свяжитесь с поддержкой.

<b>ID платежа:</b> <code>{payment.id}</code>
                    """
            else:
                success_text = f"""
✅ <b>Платеж успешно обработан!</b>

<b>ID платежа:</b> <code>{payment.id}</code>
                """
            
            # Удаляем inline-сообщение
            try:
                await callback.message.delete()
            except:
                pass
            # Отправляем новое сообщение с главным меню
            await callback.message.answer(
                success_text,
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            
        else:
            # Проверяем, не идет ли уже автоматический мониторинг
            if payment_id in active_payment_checks:
                status_text = f"""
🔄 <b>Автоматическая проверка уже активна</b>

<b>Статус платежа:</b> {payment.status.value}
<b>ID платежа:</b> <code>{payment.id}</code>

Система автоматически проверит оплату в течение 10 минут.
Пожалуйста, подождите.
                """
            else:
                # Платеж еще не обработан
                status_text = f"""
🔄 <b>Статус платежа: {payment.status.value}</b>

<b>ID платежа:</b> <code>{payment.id}</code>

Платеж еще обрабатывается. Попробуйте проверить статус через несколько минут.

<i>Обычно обработка платежа занимает 1-3 минуты.</i>
                """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔄 Проверить снова",
                    callback_data=f"check_payment_{payment.id}"
                )],
                [InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel_subscription"
                )]
            ])
            
            await callback.message.edit_text(
                status_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Ошибка проверки статуса платежа {payment_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ <b>Ошибка проверки платежа</b>\n\n"
            "Попробуйте позже или свяжитесь с поддержкой.\n\n"
            f"<i>Детали ошибки: {str(e)[:100]}</i>",
            parse_mode="HTML"
        )


# Обработчики для выбора способа оплаты
@router.callback_query(F.data == "payment_method_yookassa")
async def process_yookassa_payment(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработка оплаты через ЮКасса"""
    await callback.answer()
    
    user_id = callback.from_user.id
    
    # Получаем информацию о покупке из состояния
    data = await state.get_data()
    purchase_type = data.get('purchase_type')
    plan_id = data.get('plan_id')
    plan_name = data.get('plan_name')
    amount = data.get('amount')
    
    try:
        if purchase_type == "subscription":
            # Создаем платеж для подписки
            days = data.get('days')
            # Получаем email пользователя если доступен
            user_data = await db.get_user(user_id)
            user_email = user_data.get('email') if user_data else None
            
            # Если email не найден, используем Telegram username
            if not user_email and user_data:
                username = user_data.get('username')
                if username:
                    user_email = f"{username}@telegram.user"
            
            payment = await payment_manager.create_subscription_payment(
                user_id=user_id,
                subscription_type=plan_id,
                amount=float(amount),
                description=f"{plan_name} на {days} дней",
                user_email=user_email
            )
        else:
            raise ValueError("Неизвестный тип покупки")
        
        if not payment:
            logger.error(f"Не удалось создать платеж для пользователя {user_id}, план: {plan_id}")
            await callback.message.edit_text(
                "❌ <b>Ошибка создания платежа</b>\n\n"
                "Возможные причины:\n"
                "• Проблемы с API ЮКасса\n"
                "• Неверные настройки платежной системы\n"
                "• Временные технические проблемы\n\n"
                "Попробуйте позже или свяжитесь с поддержкой.",
                parse_mode="HTML"
            )
            return
        
        # Создаем клавиатуру с кнопкой оплаты
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💳 Оплатить картой",
                url=payment.confirmation_url
            )],
            [InlineKeyboardButton(
                text="🔄 Проверить статус",
                callback_data=f"check_payment_{payment.id}"
            )],
            [InlineKeyboardButton(
                text="❌ Отменить",
                callback_data="cancel_subscription"
            )]
        ])
        
        # Запускаем автоматический мониторинг платежа
        await start_payment_monitoring(
            payment_id=payment.id,
            user_id=user_id,
            payment_type="yookassa",
            db=db,
            bot=callback.bot,
            timeout_minutes=10
        )
        
        # Формируем текст для подписки
        plan = config.SUBSCRIPTION_PLANS.get(plan_id, {})
        features = plan.get('features', [])
        payment_text = f"""
💎 <b>{plan_name}</b>

<b>Стоимость:</b> {amount}₽/мес
<b>Способ оплаты:</b> 💳 Банковская карта

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in features])}

<b>Статус платежа:</b> {payment.status.value}
<b>ID платежа:</b> <code>{payment.id}</code>

🔄 <b>Автоматическая проверка активна</b>
Система автоматически проверит оплату в течение 10 минут.

Нажмите кнопку "Оплатить картой" для перехода к оплате.
После оплаты система автоматически обработает платеж.
        """
        
        await callback.message.edit_text(
            payment_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания платежа ЮКасса: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка создания платежа</b>\n\n"
            "Попробуйте позже или свяжитесь с поддержкой.",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "payment_method_crypto")
async def process_crypto_payment_selection(callback: CallbackQuery, db: Database):
    """Обработка выбора криптоплатежа"""
    await callback.answer()
    
    try:
        # Получаем доступные криптовалюты
        available_currencies = await payment_manager.get_available_crypto_currencies()
        
        if not available_currencies:
            await callback.message.edit_text(
                "❌ <b>Криптоплатежи временно недоступны</b>\n\n"
                "Попробуйте оплатить картой или свяжитесь с поддержкой.",
                parse_mode="HTML"
            )
            return
        
        # Показываем выбор криптовалюты
        crypto_text = """
₿ <b>Оплата криптовалютой</b>

Выберите криптовалюту для оплаты:

<b>Популярные криптовалюты:</b>
        """
        
        await callback.message.edit_text(
            crypto_text,
            reply_markup=get_crypto_currency_keyboard(available_currencies),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения криптовалют: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка загрузки криптовалют</b>\n\n"
            "Попробуйте позже или выберите оплату картой.",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("crypto_currency_"))
async def process_crypto_currency_selection(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработка выбора криптовалюты"""
    await callback.answer()
    
    # Извлекаем валюту из callback_data
    currency = callback.data.replace("crypto_currency_", "")
    user_id = callback.from_user.id
    
    # Получаем информацию о покупке из состояния
    data = await state.get_data()
    purchase_type = data.get('purchase_type')
    plan_id = data.get('plan_id')
    plan_name = data.get('plan_name')
    amount = data.get('amount')
    
    try:
        if purchase_type == "subscription":
            # Создаем криптоплатеж для подписки
            days = data.get('days')
            payment = await payment_manager.create_crypto_subscription_payment(
                user_id=user_id,
                subscription_type=plan_id,
                amount=float(amount),
                description=f"{plan_name} на {days} дней",
                crypto_currency=currency
            )
        else:
            raise ValueError("Неизвестный тип покупки")
        
        if not payment:
            await callback.message.edit_text(
                "❌ <b>Ошибка создания криптоплатежа</b>\n\n"
                "Попробуйте позже или свяжитесь с поддержкой.",
                parse_mode="HTML"
            )
            return
        
        # Получаем примерную цену в криптовалюте
        crypto_amount = await payment_manager.get_crypto_price_estimate(float(amount), currency)
        
        # Создаем клавиатуру с кнопкой оплаты
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"₿ Оплатить {currency}",
                url=payment.payment_url
            )],
            [InlineKeyboardButton(
                text="🔄 Проверить статус",
                callback_data=f"check_crypto_payment_{payment.payment_id}"
            )],
            [InlineKeyboardButton(
                text="❌ Отменить",
                callback_data="cancel_subscription"
            )]
        ])
        
        # Запускаем автоматический мониторинг криптоплатежа
        await start_payment_monitoring(
            payment_id=payment.payment_id,
            user_id=user_id,
            payment_type="crypto",
            db=db,
            bot=callback.bot,
            timeout_minutes=10
        )
        
        # Формируем текст для подписки
        plan = config.SUBSCRIPTION_PLANS.get(plan_id, {})
        features = plan.get('features', [])
        payment_text = f"""
💎 <b>{plan_name}</b>

<b>Стоимость:</b> {amount}₽/мес
<b>Способ оплаты:</b> ₿ {currency}
{f'<b>Примерная сумма:</b> {crypto_amount:.8f} {currency}' if crypto_amount else ''}

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in features])}

<b>Статус платежа:</b> {payment.status.value}
<b>ID платежа:</b> <code>{payment.payment_id}</code>

🔄 <b>Автоматическая проверка активна</b>
Система автоматически проверит оплату в течение 10 минут.

Нажмите кнопку "Оплатить {currency}" для перехода к оплате.
После оплаты система автоматически обработает платеж.
        """
        
        await callback.message.edit_text(
            payment_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания криптоплатежа: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка создания криптоплатежа</b>\n\n"
            "Попробуйте позже или свяжитесь с поддержкой.",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("check_crypto_payment_"))
async def check_crypto_payment_status(callback: CallbackQuery, db: Database):
    """Проверить статус криптоплатежа (ручная проверка)"""
    await callback.answer()
    
    # Извлекаем ID платежа из callback_data
    payment_id = callback.data.replace("check_crypto_payment_", "")
    
    try:
        logger.info(f"Ручная проверка статуса криптоплатежа {payment_id} пользователем {callback.from_user.id}")
        
        # Проверяем статус криптоплатежа
        payment = await payment_manager.check_crypto_payment_status(payment_id)
        
        if not payment:
            logger.error(f"Не удалось получить данные криптоплатежа {payment_id}")
            await callback.message.edit_text(
                "❌ <b>Ошибка проверки криптоплатежа</b>\n\n"
                f"Криптоплатеж <code>{payment_id}</code> не найден или недоступен.\n\n"
                "Попробуйте позже или свяжитесь с поддержкой.",
                parse_mode="HTML"
            )
            return
        
        logger.info(f"Получен статус криптоплатежа {payment_id}: {payment.status.value}")
        
        # Проверяем успешность платежа
        if payment_manager.is_crypto_payment_successful(payment):
            # Удаляем из активных проверок, если есть
            if payment_id in active_payment_checks:
                del active_payment_checks[payment_id]
            
            # Обрабатываем успешный платеж
            user_id = callback.from_user.id
            metadata = payment.metadata or {}
            payment_type = metadata.get("payment_type", "")
            
            logger.info(f"Обработка успешного криптоплатежа {payment_id} для пользователя {user_id}, тип: {payment_type}")
            
            if payment_type == "subscription":
                # Получаем информацию о подписке из метаданных
                subscription_type = metadata.get("subscription_type", "basic")
                
                # Используем единую функцию обработки платежа
                success, plan_name, monthly_limit = await process_successful_payment(
                    payment_id, payment_type, user_id, db, subscription_type
                )
                
                if success:
                    # Получаем количество дополнительных анализов
                    updated_user_data = await db.get_user(user_id)
                    additional_analyses = updated_user_data.get('additional_analyses', 0)
                    
                    # Получаем информацию о плане для отображения
                    plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
                    
                    success_text = f"""
✅ <b>Криптоплатеж успешно обработан!</b>

💎 <b>Подписка {plan_name} активирована!</b>

📊 <b>Месячный лимит:</b> {monthly_limit} анализов
{f'💰 Дополнительные анализы: <b>{additional_analyses}</b>' if additional_analyses > 0 else ''}

<b>Что входит:</b>
{chr(10).join([f"• {feature}" for feature in plan['features']])}

<b>ID платежа:</b> <code>{payment.payment_id}</code>

💡 <b>Информация:</b>
• Месячный лимит обновляется каждый месяц
• Дополнительные анализы можно купить отдельно
                    """
                    
                    logger.info(f"Криптоплатеж {payment_id} успешно обработан для пользователя {user_id}")
                else:
                    logger.error(f"Не удалось обработать криптоплатеж {payment_id} для пользователя {user_id}")
                    success_text = f"""
❌ <b>Ошибка обработки криптоплатежа</b>

Не удалось активировать подписку. Пожалуйста, свяжитесь с поддержкой.

<b>ID платежа:</b> <code>{payment.payment_id}</code>
                    """
            else:
                success_text = f"""
✅ <b>Криптоплатеж успешно обработан!</b>

<b>ID платежа:</b> <code>{payment.payment_id}</code>
                """
            
            # Удаляем inline-сообщение
            try:
                await callback.message.delete()
            except:
                pass
            # Отправляем новое сообщение с главным меню
            await callback.message.answer(
                success_text,
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            
        else:
            # Проверяем, не идет ли уже автоматический мониторинг
            if payment_id in active_payment_checks:
                status_text = f"""
🔄 <b>Автоматическая проверка уже активна</b>

<b>Статус криптоплатежа:</b> {payment.status.value}
<b>ID платежа:</b> <code>{payment.payment_id}</code>

Система автоматически проверит оплату в течение 10 минут.
Пожалуйста, подождите.
                """
            else:
                # Платеж еще не обработан
                status_text = f"""
🔄 <b>Статус криптоплатежа: {payment.status.value}</b>

<b>ID платежа:</b> <code>{payment.payment_id}</code>

Криптоплатеж еще обрабатывается. Попробуйте проверить статус через несколько минут.

<i>Обработка криптоплатежа может занять до 30 минут в зависимости от блокчейна.</i>
                """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔄 Проверить снова",
                    callback_data=f"check_crypto_payment_{payment.payment_id}"
                )],
                [InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel_subscription"
                )]
            ])
            
            await callback.message.edit_text(
                status_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Ошибка проверки статуса криптоплатежа {payment_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ <b>Ошибка проверки криптоплатежа</b>\n\n"
            "Попробуйте позже или свяжитесь с поддержкой.\n\n"
            f"<i>Детали ошибки: {str(e)[:100]}</i>",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "show_all_crypto")
async def show_all_crypto_currencies(callback: CallbackQuery, db: Database):
    """Показать все доступные криптовалюты"""
    await callback.answer()
    
    try:
        # Получаем все доступные криптовалюты
        available_currencies = await payment_manager.get_available_crypto_currencies()
        
        if not available_currencies:
            await callback.message.edit_text(
                "❌ <b>Криптовалюты недоступны</b>\n\n"
                "Попробуйте позже или выберите оплату картой.",
                parse_mode="HTML"
            )
            return
        
        crypto_text = f"""
₿ <b>Все доступные криптовалюты</b>

Выберите криптовалюту для оплаты:

<b>Доступно:</b> {len(available_currencies)} криптовалют
        """
        
        await callback.message.edit_text(
            crypto_text,
            reply_markup=get_all_crypto_currencies_keyboard(available_currencies),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения всех криптовалют: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка загрузки криптовалют</b>\n\n"
            "Попробуйте позже или выберите оплату картой.",
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("manual_check_payment_"))
async def manual_check_payment(callback: CallbackQuery, db: Database):
    """Ручная проверка платежа после таймаута"""
    await callback.answer()
    
    # Извлекаем ID платежа из callback_data
    payment_id = callback.data.replace("manual_check_payment_", "")
    
    # Проверяем инициализацию YooKassa
    if not payment_manager.yookassa:
        logger.error("YooKassa не инициализирована при ручной проверке платежа")
        await callback.message.edit_text(
            "❌ <b>Система платежей недоступна</b>\n\n"
            "YooKassa не настроена. Обратитесь к администратору.",
            parse_mode="HTML"
        )
        return
    
    try:
        logger.info(f"Ручная проверка платежа {payment_id} после таймаута пользователем {callback.from_user.id}")
        
        # Проверяем статус платежа
        payment = await payment_manager.check_payment_status(payment_id)
        
        if not payment:
            logger.error(f"Не удалось получить данные платежа {payment_id}")
            await callback.message.edit_text(
                "❌ <b>Ошибка проверки платежа</b>\n\n"
                f"Платеж <code>{payment_id}</code> не найден или недоступен.\n\n"
                "Возможные причины:\n"
                "• Платеж еще не создан\n"
                "• Проблемы с API YooKassa\n"
                "• Неверный ID платежа\n"
                "• Платеж был отменен\n\n"
                "Попробуйте позже или свяжитесь с поддержкой.",
                parse_mode="HTML"
            )
            return
        
        logger.info(f"Получен статус платежа {payment_id}: {payment.status.value}")
        
        # Проверяем успешность платежа
        if payment_manager.is_payment_successful(payment):
            # Обрабатываем успешный платеж
            user_id = callback.from_user.id
            metadata = payment.metadata or {}
            payment_type = metadata.get("payment_type", "")
            
            logger.info(f"Обработка успешного платежа {payment_id} для пользователя {user_id}, тип: {payment_type}")
            
            if payment_type == "subscription":
                subscription_type = metadata.get("subscription_type", "basic")
                
                # Используем единую функцию обработки платежа
                success, plan_name, monthly_limit = await process_successful_payment(
                    payment_id, payment_type, user_id, db, subscription_type
                )
                
                if success:
                    # Получаем количество дополнительных анализов
                    updated_user_data = await db.get_user(user_id)
                    additional_analyses = updated_user_data.get('additional_analyses', 0)
                    
                    # Получаем информацию о плане для отображения
                    plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
                    
                    success_text = f"""
✅ <b>Платеж успешно обработан!</b>

💎 <b>Подписка {plan_name} активирована!</b>

📊 <b>Месячный лимит:</b> {monthly_limit} анализов
{f'💰 Дополнительные анализы: <b>{additional_analyses}</b>' if additional_analyses > 0 else ''}

<b>Что входит:</b>
{chr(10).join([f"• {feature}" for feature in plan['features']])}

<b>ID платежа:</b> <code>{payment.id}</code>

💡 <b>Информация:</b>
• Месячный лимит обновляется каждый месяц
• Дополнительные анализы можно купить отдельно
                    """
                    
                    logger.info(f"Платеж {payment_id} успешно обработан для пользователя {user_id}")
                else:
                    logger.error(f"Не удалось обработать платеж {payment_id} для пользователя {user_id}")
                    success_text = f"""
❌ <b>Ошибка обработки платежа</b>

Не удалось активировать подписку. Пожалуйста, свяжитесь с поддержкой.

<b>ID платежа:</b> <code>{payment.id}</code>
                    """
            else:
                success_text = f"""
✅ <b>Платеж успешно обработан!</b>

<b>ID платежа:</b> <code>{payment.id}</code>
                """
            
            # Удаляем inline-сообщение
            try:
                await callback.message.delete()
            except:
                pass
            # Отправляем новое сообщение с главным меню
            await callback.message.answer(
                success_text,
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            
        else:
            # Платеж еще не обработан
            status_text = f"""
🔄 <b>Статус платежа: {payment.status.value}</b>

<b>ID платежа:</b> <code>{payment.id}</code>

Платеж еще обрабатывается. Попробуйте проверить статус через несколько минут.

<i>Обычно обработка платежа занимает 1-3 минуты.</i>
            """
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔄 Проверить снова",
                    callback_data=f"manual_check_payment_{payment.id}"
                )],
                [InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data="cancel_subscription"
                )]
            ])
            
            await callback.message.edit_text(
                status_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Ошибка ручной проверки платежа {payment_id}: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ <b>Ошибка проверки платежа</b>\n\n"
            "Попробуйте позже или свяжитесь с поддержкой.\n\n"
            f"<i>Детали ошибки: {str(e)[:100]}</i>",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "cancel_subscription")
async def cancel_subscription(callback: CallbackQuery):
    """Отменить выбор подписки"""
    await callback.answer("Отменено")
    await callback.message.edit_text(
        "❌ Действие отменено",
    )


# Команда для тестовой активации премиума (для разработки)
@router.message(Command("activate_premium_test"))
async def activate_premium_test(message: Message, db: Database):
    """Тестовая активация премиума (только для разработки)"""
    user_id = message.from_user.id
    
    # Активируем премиум на 30 дней
    await db.grant_premium(user_id, days=30)
    
    await message.answer(
        "✅ Premium подписка активирована на 30 дней!\n\n"
        "Это тестовый режим для разработки.\n"
        f"Теперь доступно {config.PREMIUM_ANALYSES_PER_DAY} анализов в день.",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("deactivate_premium_test"))
async def deactivate_premium_test(message: Message, db: Database):
    """Тестовая деактивация премиума"""
    user_id = message.from_user.id
    
    await db.revoke_premium(user_id)
    
    await message.answer(
        "❌ Premium подписка деактивирована.\n\n"
        f"Вернулись {config.FREE_ANALYSES_PER_DAY} анализов в день.",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("payment_status"))
async def payment_system_status(message: Message):
    """Проверить статус платежной системы"""
    try:
        yookassa_status = payment_manager.get_yookassa_status()
        
        status_text = f"""
🔧 <b>Статус платежной системы</b>

<b>YooKassa:</b>
• Инициализирована: {'✅' if yookassa_status['initialized'] else '❌'}
• Shop ID настроен: {'✅' if yookassa_status['shop_id_configured'] else '❌'}
• Secret Key настроен: {'✅' if yookassa_status['secret_key_configured'] else '❌'}
• Тестовый режим: {'✅' if yookassa_status['test_mode'] else '❌'}
• Shop ID: {yookassa_status.get('shop_id_preview', 'Не настроен')}
• Secret Key: {yookassa_status.get('secret_key_preview', 'Не настроен')}

<b>NOWPayments:</b>
• Инициализирована: {'✅' if payment_manager.nowpayments else '❌'}

<b>Рекомендации:</b>
"""
        
        if not yookassa_status['initialized']:
            status_text += "\n• Проверьте настройки YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY в .env"
        
        if not yookassa_status['shop_id_configured']:
            status_text += "\n• Добавьте YOOKASSA_SHOP_ID в .env файл"
            
        if not yookassa_status['secret_key_configured']:
            status_text += "\n• Добавьте YOOKASSA_SECRET_KEY в .env файл"
        
        # Дополнительные рекомендации
        if yookassa_status.get('shop_id_length', 0) < 4:
            status_text += "\n• Shop ID слишком короткий - проверьте правильность"
            
        if yookassa_status.get('secret_key_length', 0) < 8:
            status_text += "\n• Secret Key слишком короткий - проверьте правильность"
        
        # Проверка тестового режима
        if yookassa_status.get('test_mode', True):
            status_text += "\n• Включен тестовый режим - для продакшена установите YOOKASSA_TEST_MODE=false"
        
        # Проверка NOWPayments
        if not payment_manager.nowpayments:
            status_text += "\n• NOWPayments не инициализирована - проверьте настройки криптоплатежей"
        
        await message.answer(status_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка проверки статуса платежной системы: {e}")
        await message.answer(
            "❌ <b>Ошибка проверки статуса</b>\n\n"
            "Не удалось получить информацию о платежной системе.\n\n"
            f"Детали ошибки: {str(e)}",
            parse_mode="HTML"
        )

