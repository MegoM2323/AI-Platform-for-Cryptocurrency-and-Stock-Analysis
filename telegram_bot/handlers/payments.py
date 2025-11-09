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
    get_all_crypto_currencies_keyboard,
    get_token_packages_keyboard,
    get_shop_keyboard
)
from database import Database
from config import config
from Payments.payment_system import payment_manager, PaymentStatus
from telegram_bot.token_manager import TokenManager
import logging

logger = logging.getLogger(__name__)
router = Router()
# Покупка токенов (кнопка из главного меню)
@router.message(F.text == "💰 Купить токены")
async def buy_tokens_entry(message: Message):
    try:
        packages = config.TOKEN_PACKAGES
        text = (
            "💰 <b>Покупка токенов</b>\n\n"
            "Выберите пакет токенов. Указан примерный эквивалент в анализах."
        )
        await message.answer(text, reply_markup=get_token_packages_keyboard(packages), parse_mode="HTML")
    except Exception:
        await message.answer("❌ Покупка токенов временно недоступна.")


# Словарь для хранения активных проверок платежей
active_payment_checks = {}

# Словарь для хранения обработанных платежей (защита от дублирования)
processed_payments = {}

# Админ-команда для мониторинга квоты новостей
from data_collectors.rate_limiter import RateLimiter

# Используем тот же экземпляр RateLimiter, что и в enhanced_analysis.py
from .enhanced_analysis import _rate_limiter as _news_rate_limiter

@router.message(Command("news_quota"))
async def news_quota(message: Message):
    # Проверка прав администратора через ADMIN_USER_ID
    if not config.ADMIN_USER_ID or str(message.from_user.id) != str(config.ADMIN_USER_ID):
        await message.answer("❌ Доступ ограничен. Эта команда доступна только администратору.")
        return
    
    stats = _news_rate_limiter.get_usage_stats()
    daily_ratio = stats['daily_used'] / max(1, stats['daily_limit'])
    monthly_ratio = stats['monthly_used'] / max(1, stats['monthly_limit'])
    
    # Форматирование статистики
    usage_percent = int(monthly_ratio * 100)
    status_text = f"📊 <b>Статистика NewsAPI</b>\n\n"
    status_text += f"📅 <b>Дневная квота:</b> {stats['daily_used']}/{stats['daily_limit']} ({int(daily_ratio * 100)}%)\n"
    status_text += f"📆 <b>Месячная квота:</b> {stats['monthly_used']}/{stats['monthly_limit']} ({usage_percent}%)\n"
    
    # Предупреждения
    if usage_percent >= 90:
        status_text += "\n\n⚠️ <b>ВНИМАНИЕ:</b> Вы достигли 90% месячного лимита NewsAPI!"
    elif usage_percent >= 80:
        status_text += "\n\n💡 <b>ПРЕДУПРЕЖДЕНИЕ:</b> Вы достигли 80% месячного лимита NewsAPI."
    
    await message.answer(status_text, parse_mode="HTML")

async def start_payment_monitoring(payment_id: str, user_id: int, payment_type: str, db: Database, bot, timeout_minutes: int = 10, silent_on_timeout: bool = False):
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
            'status': 'monitoring',
            'silent_on_timeout': bool(silent_on_timeout),
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
                if not check_info.get('silent_on_timeout'):
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
            success, plan_name, credited_tokens = await process_successful_payment(
                payment_id, payment_type, user_id, db, subscription_type
            )
            
            if success:
                # Пытаемся сохранить payment_method_id, если мониторинг сработал раньше вебхука
                try:
                    yk_payment = await payment_manager.check_payment_status(payment_id)
                    pm_id = getattr(yk_payment, 'payment_method_id', None) if yk_payment else None
                    md = getattr(yk_payment, 'metadata', {}) if yk_payment else {}
                    is_renewal = bool(md.get('renewal'))
                    # Сохраняем карту только на первом платеже (renewal == False)
                    if pm_id and not is_renewal:
                        try:
                            await db.update_subscription_payment_method(user_id, pm_id)
                        except Exception:
                            pass
                except Exception:
                    pass
                # Уведомляем пользователя только если мы успешно обработали платеж
                await notify_user_about_tokens(user_id, payment_id, plan_name, credited_tokens, bot, db)
                
                # Удаляем из активных проверок
                if payment_id in active_payment_checks:
                    del active_payment_checks[payment_id]
                
                logger.info(f"✅ Платеж {payment_id} успешно обработан автоматически для пользователя {user_id}")
            else:
                logger.warning(f"⚠️ Платеж {payment_id} не был обработан автоматически (возможно, уже обработан)")
        elif payment_type == "token_purchase":
            tokens = int(metadata.get("tokens", "0") or 0)
            package_name = metadata.get("package_name", "Токены")

            # Обработка покупки токенов в общей функции
            success, plan_name, credited = await process_successful_payment(
                payment_id, payment_type, user_id, db
            )

            if success:
                # Уведомление о начислении токенов
                from telegram_bot.bot import bot
                await notify_user_about_tokens(user_id, payment_id, package_name or plan_name, credited, bot, db)
                if payment_id in active_payment_checks:
                    del active_payment_checks[payment_id]
                logger.info(f"✅ Платеж {payment_id} (токены) успешно обработан автоматически для пользователя {user_id}")
            else:
                logger.error(f"Не удалось обработать платеж {payment_id} (токены) для пользователя {user_id}")
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
            success, plan_name, credited_tokens = await process_successful_payment(
                payment_id, payment_type, user_id, db, subscription_type
            )
            
            if success:
                # Уведомляем пользователя только если мы успешно обработали платеж
                await notify_user_about_tokens(user_id, payment_id, plan_name, credited_tokens, bot, db)
                
                # Удаляем из активных проверок
                if payment_id in active_payment_checks:
                    del active_payment_checks[payment_id]
                
                logger.info(f"✅ Криптоплатеж {payment_id} успешно обработан автоматически для пользователя {user_id}")
            else:
                logger.warning(f"⚠️ Криптоплатеж {payment_id} не был обработан автоматически (возможно, уже обработан)")
        elif payment_type == "token_purchase":
            # Обработка покупки токенов
            success, package_name, credited = await process_successful_payment(
                payment.payment_id, payment_type, user_id, db
            )
            if success:
                from telegram_bot.bot import bot
                await notify_user_about_tokens(user_id, payment.payment_id, package_name, credited, bot, db)
                if payment.payment_id in active_payment_checks:
                    del active_payment_checks[payment.payment_id]
                logger.info(f"✅ Криптоплатеж {payment.payment_id} (токены) успешно обработан для пользователя {user_id}")
            else:
                logger.error(f"Не удалось обработать криптоплатеж {payment.payment_id} (токены) для пользователя {user_id}")
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
    """Обработать успешный платеж: подписка (начислить токены) или покупка токенов."""
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
            
            # Получаем план подписки (токеновая модель)
            plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
            days = plan['days']
            tokens_per_month = int(plan.get('tokens_per_month', 0) or 0)
            
            logger.info(f"🔄 Начинаем обработку платежа {payment_id}: пользователь {user_id}, план {subscription_type}")
            
            # Проверяем, есть ли уже активная подписка
            user_data = await db.get_user(user_id)
            is_premium = user_data.get('is_premium', 0)
            premium_until = user_data.get('premium_until')
            
            # Активируем премиум и создаем/обновляем подписку под токены
            await db.grant_premium(user_id, days=days)
            logger.info(f"✨ Подписка {subscription_type} активирована для пользователя {user_id}")
            
            # ✅ КРИТИЧЕСКИ ВАЖНО: СНАЧАЛА помечаем платеж как обработанный В БАЗЕ ДАННЫХ
            # Это должно быть ДО создания подписки для предотвращения дублирования!
            
            # В новой модели подписка начисляет токены, а не лимиты анализов
            # Сначала начисляем токены, чтобы знать их количество для сохранения
            credited_tokens = 0
            try:
                if tokens_per_month > 0:
                    tm = TokenManager(db)
                    added = await tm.add_tokens(
                        user_id=user_id,
                        amount=tokens_per_month,
                        transaction_type='subscription',
                        description=f"Подписка {plan['name']} — ежемесячные токены",
                        payment_id=payment_id,
                    )
                    credited_tokens = tokens_per_month if added else 0
            except Exception as e:
                logger.error(f"Ошибка начисления токенов по подписке: {e}")
            
            payment_marked = await db.mark_payment_processed(
                payment_id=payment_id,
                user_id=user_id,
                payment_type=payment_type,
                subscription_type=subscription_type,
                analyses_added=credited_tokens,  # Для совместимости
                plan_name=plan['name'],
                tokens_added=credited_tokens  # Сохраняем токены в tokens_added
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
            
            # Создаем/обновляем запись о подписке c рекуррентом (без payment_method_id на этом этапе)
            await db.create_subscription(user_id, subscription_type, plan['price'], tokens_per_month=tokens_per_month)
            logger.info(f"📝 Запись о подписке {subscription_type} создана/обновлена для пользователя {user_id}")

            # Сохраняем информацию об обработке платежа в памяти
            result = (True, plan['name'], credited_tokens)
            processed_payments[payment_id] = result
            
            # Логируем информацию о повторной покупке
            if is_premium and premium_until:
                logger.info(f"🎯 Информация о подписке:")
                logger.info(f"   📅 Период: {days} дней")
                logger.info(f"   💰 Токенов в месяц: {tokens_per_month}")
            
            return result
        elif payment_type == "token_purchase":
            # Получаем метаданные платежа через менеджер (оба канала приводят сюда с валидным payment_id)
            # Пытаемся прочитать данные из обоих провайдеров; если не удаётся — используем запись processed_payments
            tokens = 0
            package_name = "Токены"
            try:
                payment = await payment_manager.check_payment_status(payment_id)
                if payment and payment.metadata:
                    md = payment.metadata
                    tokens = int(md.get("tokens", "0") or 0)
                    package_name = md.get("package_name", package_name)
            except Exception:
                pass
            if tokens <= 0:
                # fallback: если метаданные не доступны — не начисляем, но помечаем обработку
                tokens = 0

            payment_marked = await db.mark_payment_processed(
                payment_id=payment_id,
                user_id=user_id,
                payment_type=payment_type,
                subscription_type=None,
                analyses_added=tokens,  # Для совместимости
                plan_name=package_name,
                tokens_added=tokens  # Сохраняем токены в tokens_added
            )

            if not payment_marked:
                processed_info = await db.get_processed_payment(payment_id)
                if processed_info:
                    result = (True, processed_info['plan_name'], processed_info['analyses_added'])
                    processed_payments[payment_id] = result
                    return result
                return (False, None, 0)

            # Пытаемся начислить токены, если есть колонка token_balance
            credited = tokens
            try:
                tm = TokenManager(db)
                if tokens > 0:
                    added = await tm.add_tokens(user_id=user_id, amount=tokens, transaction_type='purchase', description=f'Покупка токенов {package_name}', payment_id=payment_id)
                    if not added:
                        logger.warning("Колонка token_balance отсутствует — токены будут доступны после миграции")
                else:
                    logger.warning("В метаданных платежа не найдено число токенов — начисление пропущено")
            except Exception as e:
                logger.error(f"Ошибка начисления токенов: {e}")

            result = (True, package_name, credited)
            processed_payments[payment_id] = result
            return result

        return False, None, 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки успешного платежа {payment_id}: {e}", exc_info=True)
        # Удаляем из памяти при ошибке, чтобы можно было повторить попытку
        if payment_id in processed_payments:
            del processed_payments[payment_id]
        return False, None, 0


async def notify_user_about_payment_success(user_id: int, payment_id: str, plan_name: str, credited_tokens: int, bot, db: Database = None):
    """Уведомить пользователя об успешной оплате"""
    try:
        logger.info(f"📧 Отправка уведомления пользователю {user_id} о платеже {payment_id}")
        
        # Получаем информацию о пользователе и балансе токенов
        if db:
            user_data = await db.get_user(user_id)
            tm = TokenManager(db)
            current_balance = await tm.get_balance(user_id)
        else:
            current_balance = 0
        
        success_text = f"""
✅ <b>Платеж успешно обработан!</b>

💎 <b>Подписка {plan_name} активирована!</b>

💰 <b>Начислено токенов:</b> {credited_tokens}
💳 <b>Текущий баланс:</b> {current_balance} ток.

<b>ID платежа:</b> <code>{payment_id}</code>

💡 <b>Информация:</b>
• Токены начисляются автоматически каждый месяц
• Вы можете использовать токены для проведения анализов
• Токены не сгорают и накапливаются на вашем счете
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


async def notify_user_about_tokens(user_id: int, payment_id: str, package_name: str, tokens: int, bot, db: Database = None):
    """Уведомить пользователя о начислении токенов."""
    try:
        balance_text = ""
        if db:
            try:
                tm = TokenManager(db)
                balance = await tm.get_balance(user_id)
                balance_text = f"\n💰 Баланс: <b>{balance}</b> токенов"
            except Exception:
                balance_text = ""

        text = (
            "✅ <b>Платеж успешно обработан!</b>\n\n"
            f"💰 <b>Начислено:</b> {tokens} токенов ({package_name})\n"
            f"<b>ID платежа:</b> <code>{payment_id}</code>"
            f"{balance_text}"
        )
        await bot.send_message(user_id, text, reply_markup=get_main_keyboard(), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка уведомления о токенах: {e}")


# Фоновый воркер: рекуррентные списания подписок и начисление токенов
async def _recurring_billing_worker(db: Database, bot):
    from config import config
    while True:
        try:
            due = await db.get_due_subscriptions()
            for sub in due:
                user_id = sub['user_id']
                plan_id = sub['subscription_type']
                payment_method_id = sub.get('payment_method_id')
                plan = config.SUBSCRIPTION_PLANS.get(plan_id, config.SUBSCRIPTION_PLANS['basic'])
                amount = float(plan['price'])
                metadata = {
                    "user_id": str(user_id),
                    "subscription_type": plan_id,
                    "payment_type": "subscription",
                    "renewal": True,
                }
                try:
                    if not payment_manager.yookassa or not payment_method_id:
                        # Нет возможности автосписания — перенесем на сутки и уведомим пользователя
                        await db.schedule_next_charge(user_id, days=1)
                        try:
                            await bot.send_message(user_id, (
                                "⚠️ Автосписание подписки не выполнено: не сохранен способ оплаты.\n"
                                "Пожалуйста, переоформите подписку, чтобы включить автосписания."
                            ))
                        except Exception:
                            pass
                        continue
                    # Рекуррентное списание через сохраненный метод оплаты
                    payment = await payment_manager.yookassa.create_payment(
                        amount=amount,
                        description=f"Подписка {plan.get('name')} — продление",
                        return_url=f"https://t.me/{getattr(config, 'TELEGRAM_BOT_USERNAME', '')}?start=payment_success",
                        metadata=metadata,
                        receipt=None,
                        save_payment_method=False,
                        payment_method_id=payment_method_id,
                    )
                    if payment and payment_manager.is_payment_successful(payment):
                        success, plan_name, credited_tokens = await process_successful_payment(
                            payment.id, "subscription", user_id, db, plan_id
                        )
                        if success:
                            try:
                                await db.schedule_next_charge(user_id, days=plan.get('days', 30))
                            except Exception:
                                pass
                            try:
                                await notify_user_about_tokens(user_id, payment.id, plan_name, credited_tokens, bot, db)
                            except Exception:
                                pass
                    else:
                        # Переносим следующий чардж на сутки
                        await db.schedule_next_charge(user_id, days=1)
                except Exception as e:
                    logger.error(f"Recurring billing error for user {user_id}: {e}")
                    try:
                        await db.schedule_next_charge(user_id, days=1)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Recurring billing loop error: {e}")
        # Спим 1 час между проходами
        await asyncio.sleep(3600)

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
                    payment_method_id = (data.get('object', {}) or {}).get('payment_method', {}) or {}
                    payment_method_id = payment_method_id.get('id')
                    
                    # Инициализируем Database для обработки платежа
                    from database import Database
                    from config import config
                    db = Database(config.DATABASE_PATH)
                    
                    # Обрабатываем успешный платеж
                    success, plan_name, credited_tokens = await process_successful_payment(
                        payment_id, payment_type, user_id, 
                        db,
                        subscription_type
                    )
                    
                    if success:
                        try:
                            if payment_method_id:
                                await db.update_subscription_payment_method(user_id, payment_method_id)
                        except Exception:
                            pass
                        # Получаем экземпляр бота для уведомления
                        from telegram_bot.bot import bot
                        await notify_user_about_tokens(user_id, payment_id, plan_name, credited_tokens, bot, db)
                        logger.info(f"Платеж {payment_id} успешно обработан для пользователя {user_id}")
                    else:
                        logger.error(f"Не удалось обработать платеж {payment_id} для пользователя {user_id}")
                elif user_id and payment_type == "token_purchase":
                    # Обработка покупки токенов через webhook ЮКасса
                    from database import Database
                    from config import config
                    db = Database(config.DATABASE_PATH)
                    success, package_name, credited = await process_successful_payment(
                        payment_id, payment_type, user_id, db
                    )
                    if success:
                        from telegram_bot.bot import bot
                        await notify_user_about_tokens(user_id, payment_id, package_name, credited, bot, db)
                        logger.info(f"Платеж {payment_id} (токены) успешно обработан для пользователя {user_id}")
                    else:
                        logger.error(f"Не удалось обработать платеж {payment_id} (токены) для пользователя {user_id}")
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
                success, plan_name, credited_tokens = await process_successful_payment(
                    payment.payment_id, payment_type, user_id,
                    db,
                    subscription_type
                )
                
                if success:
                    # Получаем экземпляр бота для уведомления
                    from telegram_bot.bot import bot
                    await notify_user_about_payment_success(user_id, payment.payment_id, plan_name, credited_tokens, bot, db)
                    logger.info(f"Криптоплатеж {payment.payment_id} успешно обработан для пользователя {user_id}")
                else:
                    logger.error(f"Не удалось обработать криптоплатеж {payment.payment_id} для пользователя {user_id}")
            elif user_id and payment_type == "token_purchase":
                from database import Database
                from config import config
                db = Database(config.DATABASE_PATH)
                success, package_name, credited = await process_successful_payment(
                    payment.payment_id, payment_type, user_id, db
                )
                if success:
                    from telegram_bot.bot import bot
                    await notify_user_about_tokens(user_id, payment.payment_id, package_name, credited, bot, db)
                    logger.info(f"Криптоплатеж {payment.payment_id} (токены) успешно обработан для пользователя {user_id}")
                else:
                    logger.error(f"Не удалось обработать криптоплатеж {payment.payment_id} (токены) для пользователя {user_id}")
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
    is_premium = user_data.get('is_premium', 0)
    premium_until = user_data.get('premium_until')
    plan_key = await db.get_user_subscription_plan(user_id)
    plan_cfg = config.SUBSCRIPTION_PLANS.get(plan_key, config.SUBSCRIPTION_PLANS['free'])
    plan_name = plan_cfg['name']
    # Текущий баланс токенов
    tm = TokenManager(db)
    balance = await tm.get_balance(user_id)
    # Статус
    if is_premium and premium_until:
        from datetime import datetime
        try:
            premium_until_dt = datetime.fromisoformat(premium_until.replace('Z', '+00:00'))
            if premium_until_dt > datetime.now():
                status_text = f"✅ {plan_name} активна до {premium_until_dt.strftime('%d.%m.%Y')}\nБаланс: {balance} ток."
            else:
                status_text = f"❌ Подписка истекла\nБаланс: {balance} ток."
        except:
            status_text = f"✅ {plan_name} активна\nБаланс: {balance} ток."
    else:
        status_text = f"❌ Бесплатный тариф\nБаланс: {balance} ток."
    
    subscription_text = f"""
💎 <b>ТАРИФЫ (ТОКЕНЫ В МЕСЯЦ)</b>

<b>Текущий статус:</b> {status_text}

<b>🆓 Free:</b>
• 0₽/мес
• Базовые функции

<b>💎 Доступные тарифы:</b>
• 🥉 Basic — {config.SUBSCRIPTION_PLANS['basic']['price']}₽/мес — {config.SUBSCRIPTION_PLANS['basic']['tokens_per_month']} ток./мес
• 🥈 Trader — {config.SUBSCRIPTION_PLANS['trader']['price']}₽/мес — {config.SUBSCRIPTION_PLANS['trader']['tokens_per_month']} ток./мес
• 🥇 Pro — {config.SUBSCRIPTION_PLANS['pro']['price']}₽/мес — {config.SUBSCRIPTION_PLANS['pro']['tokens_per_month']} ток./мес
• 💎 Elite — {config.SUBSCRIPTION_PLANS['elite']['price']}₽/мес — {config.SUBSCRIPTION_PLANS['elite']['tokens_per_month']} ток./мес


Выберите подходящий тариф:
    """
    
    await message.answer(
        subscription_text,
        reply_markup=get_subscription_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("shop"))
@router.message(F.text == "🛒 Магазин")
async def show_shop(message: Message):
    """Открыть витрину магазина: подписки и пакеты токенов."""
    shop_text = (
        "🛒 <b>Магазин</b>\n\n"
        "Выберите, что хотите приобрести:\n"
        "• Подписку с месячным лимитом анализов\n"
        "• Пакеты токенов для гибких списаний"
    )
    await message.answer(shop_text, reply_markup=get_shop_keyboard(), parse_mode="HTML")


# Обработчики для выбора типа покупки
@router.callback_query(F.data == "show_subscriptions")
async def show_subscription_plans(callback: CallbackQuery):
    """Показать планы подписки"""
    await callback.answer()
    
    plans_text = """
💎 <b>ТАРИФЫ (ТОКЕНЫ В МЕСЯЦ)</b>

<b>🆓 Free - 0₽/мес</b>
• Доступ к базовым функциям

<b>🥉 Basic - {b_price}₽/мес</b>
• 50 токенов/мес
• Выгоднее, чем покупать токены отдельно

<b>🥈 Trader - {t_price}₽/мес</b>
• 200 токенов/мес
• Оптимально для активной торговли

<b>🥇 Pro - {p_price}₽/мес</b>
• 500 токенов/мес
• Приоритетная скорость

<b>💎 Elite - {e_price}₽/мес</b>
• 1500 токенов/мес
• Максимальная выгода
• Приоритетная скорость
• Ранний доступ к новым функциям


Выберите тариф:
    """.format(
        b_price=config.SUBSCRIPTION_PLANS['basic']['price'],
        t_price=config.SUBSCRIPTION_PLANS['trader']['price'],
        p_price=config.SUBSCRIPTION_PLANS['pro']['price'],
        e_price=config.SUBSCRIPTION_PLANS['elite']['price'],
    )
    
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
<b>Начисление:</b> {plan['tokens_per_month']} токенов каждый месяц

<b>Преимущества:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}


ℹ️ После успешного первого платежа дальнейшая оплата подписки будет выполняться автоматически каждый месяц.
Автопродление можно отключить в разделе «Подписка» кнопкой «Отменить автопродление».

ℹ️ После успешного первого платежа дальнейшая оплата подписки будет выполняться автоматически каждый месяц.
Автопродление можно отключить в разделе «Подписка» кнопкой «Отменить автопродление».

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
<b>Начисление:</b> {plan['tokens_per_month']} токенов каждый месяц

<b>Преимущества:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}


ℹ️ После успешного первого платежа дальнейшая оплата подписки будет выполняться автоматически каждый месяц.
Автопродление можно отключить в разделе «Подписка» кнопкой «Отменить автопродление».

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
<b>Начисление:</b> {plan['tokens_per_month']} токенов каждый месяц

<b>Преимущества:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}


ℹ️ После успешного первого платежа дальнейшая оплата подписки будет выполняться автоматически каждый месяц.
Автопродление можно отключить в разделе «Подписка» кнопкой «Отменить автопродление».

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
<b>Начисление:</b> {plan['tokens_per_month']} токенов каждый месяц

<b>Преимущества:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}


ℹ️ После успешного первого платежа дальнейшая оплата подписки будет выполняться автоматически каждый месяц.
Автопродление можно отключить в разделе «Подписка» кнопкой «Отменить автопродление».

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
                    
                    # Получаем актуальный баланс токенов
                    tm = TokenManager(db)
                    current_balance = await tm.get_balance(user_id)
                    credited_tokens = processed_info.get('tokens_added', 0) or processed_info.get('analyses_added', 0)
                    
                    success_text = f"""
✅ <b>Платеж уже был обработан ранее</b>

💎 <b>Подписка {processed_info['plan_name']} активирована</b>

💰 <b>Начислено токенов:</b> {credited_tokens}
💳 <b>Текущий баланс:</b> {current_balance} ток.

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
                success, plan_name, credited_tokens = await process_successful_payment(
                    payment_id, payment_type, user_id, db, subscription_type
                )
                
                if success:
                    # Сохранить payment_method_id, если он доступен в платеже
                    try:
                        yk_payment = await payment_manager.check_payment_status(payment_id)
                        pm_id = getattr(yk_payment, 'payment_method_id', None) if yk_payment else None
                        md = getattr(yk_payment, 'metadata', {}) if yk_payment else {}
                        is_renewal = bool(md.get('renewal'))
                        if pm_id and not is_renewal:
                            try:
                                await db.update_subscription_payment_method(user_id, pm_id)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # Получаем актуальный баланс токенов
                    tm = TokenManager(db)
                    current_balance = await tm.get_balance(user_id)
                    
                    # Получаем информацию о плане для отображения
                    plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
                    
                    success_text = f"""
✅ <b>Платеж успешно обработан!</b>

💎 <b>Подписка {plan_name} активирована!</b>

💰 <b>Начислено токенов:</b> {credited_tokens}
💳 <b>Текущий баланс:</b> {current_balance} ток.

<b>Что входит:</b>
{chr(10).join([f"• {feature}" for feature in plan['features']])}

<b>ID платежа:</b> <code>{payment.id}</code>

💡 <b>Информация:</b>
• Токены начисляются автоматически каждый месяц
• Вы можете использовать токены для проведения анализов
• Токены не сгорают и накапливаются на вашем счете
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
            # Обеспечиваем или продлеваем авто-мониторинг без повторного уведомления о таймауте
            if payment_id in active_payment_checks:
                # Обновляем старт и делаем таймаут тихим
                try:
                    active_payment_checks[payment_id]['start_time'] = datetime.now()
                    active_payment_checks[payment_id]['silent_on_timeout'] = True
                except Exception:
                    pass
            else:
                # Запускаем мониторинг для платежа из ЮКасса
                await start_payment_monitoring(
                    payment_id=payment.id,
                    user_id=callback.from_user.id,
                    payment_type="yookassa",
                    db=db,
                    bot=callback.bot,
                    timeout_minutes=10,
                    silent_on_timeout=True,
                )

            status_text = f"""
🔄 <b>Статус платежа: {payment.status.value}</b>

<b>ID платежа:</b> <code>{payment.id}</code>

Автоматическая проверка активна в течение 10 минут. Пожалуйста, подождите.
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
<b>Начисление:</b> {plan.get('tokens_per_month', 0)} токенов каждый месяц
<b>Способ оплаты:</b> 💳 Банковская карта

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in features])}

<b>Статус платежа:</b> {payment.status.value}
<b>ID платежа:</b> <code>{payment.id}</code>

ℹ️ <b>Важно:</b>
• После успешного первого платежа подписка будет продлеваться автоматически каждый месяц.
• Вы всегда можете отключить автопродление в разделе «Подписка» кнопкой «Отменить автопродление».

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
    # Временно отключено
    await callback.answer("Криптооплата временно недоступна", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("crypto_currency_"))
async def process_crypto_currency_selection(callback: CallbackQuery, db: Database, state: FSMContext):
    # Временно отключено
    await callback.answer("Криптооплата временно недоступна", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("check_crypto_payment_"))
async def check_crypto_payment_status(callback: CallbackQuery, db: Database):
    # Временно отключено
    await callback.answer("Криптооплата временно недоступна", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data == "show_all_crypto")
async def show_all_crypto_currencies(callback: CallbackQuery, db: Database):
    # Временно отключено
    await callback.answer("Криптооплата временно недоступна", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


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
                success, plan_name, credited_tokens = await process_successful_payment(
                    payment_id, payment_type, user_id, db, subscription_type
                )
                
                if success:
                    # Сохранить payment_method_id, если он доступен в платеже
                    try:
                        yk_payment = await payment_manager.check_payment_status(payment_id)
                        pm_id = getattr(yk_payment, 'payment_method_id', None) if yk_payment else None
                        md = getattr(yk_payment, 'metadata', {}) if yk_payment else {}
                        is_renewal = bool(md.get('renewal'))
                        if pm_id and not is_renewal:
                            try:
                                await db.update_subscription_payment_method(user_id, pm_id)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # Получаем актуальный баланс токенов
                    tm = TokenManager(db)
                    current_balance = await tm.get_balance(user_id)
                    
                    # Получаем информацию о плане для отображения
                    plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
                    
                    success_text = f"""
✅ <b>Платеж успешно обработан!</b>

💎 <b>Подписка {plan_name} активирована!</b>

💰 <b>Начислено токенов:</b> {credited_tokens}
💳 <b>Текущий баланс:</b> {current_balance} ток.

<b>Что входит:</b>
{chr(10).join([f"• {feature}" for feature in plan['features']])}

<b>ID платежа:</b> <code>{payment.id}</code>

💡 <b>Информация:</b>
• Токены начисляются автоматически каждый месяц
• Вы можете использовать токены для проведения анализов
• Токены не сгорают и накапливаются на вашем счете
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
            # При ручной проверке также включаем/продлеваем тихий мониторинг
            if payment_id in active_payment_checks:
                try:
                    active_payment_checks[payment_id]['start_time'] = datetime.now()
                    active_payment_checks[payment_id]['silent_on_timeout'] = True
                except Exception:
                    pass
            else:
                await start_payment_monitoring(
                    payment_id=payment.id,
                    user_id=callback.from_user.id,
                    payment_type="yookassa",
                    db=db,
                    bot=callback.bot,
                    timeout_minutes=10,
                    silent_on_timeout=True,
                )

            status_text = f"""
🔄 <b>Статус платежа: {payment.status.value}</b>

<b>ID платежа:</b> <code>{payment.id}</code>

Автоматическая проверка активна в течение 10 минут. Пожалуйста, подождите.
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


@router.callback_query(F.data == "unsubscribe")
async def unsubscribe_autorenew(callback: CallbackQuery, db: Database):
    """Отключить автопродление подписки (без немедленной деактивации текущего периода)."""
    await callback.answer()
    user_id = callback.from_user.id
    try:
        changed = await db.cancel_subscription(user_id)
        if changed:
            text = (
                "🚫 <b>Автопродление отключено</b>\n\n"
                "Подписка останется активной до конца оплаченного периода,\n"
                "после чего продление выполняться не будет."
            )
        else:
            text = (
                "ℹ️ Автопродление уже отключено или активная подписка не найдена."
            )
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception as e:
        from logging import getLogger
        getLogger(__name__).error(f"Ошибка отключения автопродления: {e}")
        await callback.message.edit_text(
            "❌ Не удалось отключить автопродление. Попробуйте позже.",
            parse_mode="HTML"
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

