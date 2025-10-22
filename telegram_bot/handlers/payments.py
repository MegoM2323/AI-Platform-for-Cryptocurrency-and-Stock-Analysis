"""
Обработчики для подписок и платежей
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

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


@router.message(Command("subscribe"))
@router.message(F.text == "💎 Подписка")
async def show_subscription_options(message: Message, state: FSMContext, db: Database):
    """Показать варианты подписки"""
    await state.clear()
    
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    is_premium = user_data.get('is_premium', 0)
    premium_until = user_data.get('premium_until')
    
    # Определяем текущий статус
    if is_premium and premium_until:
        from datetime import datetime
        try:
            premium_until_dt = datetime.fromisoformat(premium_until.replace('Z', '+00:00'))
            if premium_until_dt > datetime.now():
                status_text = f"✅ Premium активна до {premium_until_dt.strftime('%d.%m.%Y')}"
            else:
                status_text = "❌ Premium истекла"
        except:
            status_text = "✅ Premium активна"
    else:
        status_text = "❌ Бесплатный тариф"
    
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
@router.callback_query(F.data == "subscribe_free")
async def process_free_subscription(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработка Free тарифа"""
    await callback.answer()
    
    # Free тариф не требует оплаты
    await callback.message.edit_text(
        "🆓 <b>Free тариф уже активен!</b>\n\n"
        "Вам доступно:\n"
        "• 3 анализа в месяц\n"
        "• Базовый анализ\n\n"
        "Для расширения возможностей выберите платный тариф.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "subscribe_basic")
async def process_basic_subscription(callback: CallbackQuery, db: Database, state: FSMContext):
    """Обработка подписки Basic"""
    await callback.answer()
    
    # Сохраняем информацию о выбранном плане
    await state.update_data(
        purchase_type="subscription",
        plan_id="basic",
        plan_name="Basic",
        amount=299,
        days=30
    )
    
    plan = config.SUBSCRIPTION_PLANS['basic']
    payment_text = f"""
🥉 <b>{plan['name']}</b>

<b>Стоимость:</b> {plan['price']}₽/мес

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}

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
    await state.update_data(
        purchase_type="subscription",
        plan_id="trader",
        plan_name="Trader",
        amount=899,
        days=30
    )
    
    plan = config.SUBSCRIPTION_PLANS['trader']
    payment_text = f"""
🥈 <b>{plan['name']}</b>

<b>Стоимость:</b> {plan['price']}₽/мес

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}

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
    await state.update_data(
        purchase_type="subscription",
        plan_id="pro",
        plan_name="Pro",
        amount=1590,
        days=30
    )
    
    plan = config.SUBSCRIPTION_PLANS['pro']
    payment_text = f"""
🥇 <b>{plan['name']}</b>

<b>Стоимость:</b> {plan['price']}₽/мес

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}

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
    await state.update_data(
        purchase_type="subscription",
        plan_id="elite",
        plan_name="Elite",
        amount=2990,
        days=30
    )
    
    plan = config.SUBSCRIPTION_PLANS['elite']
    payment_text = f"""
💎 <b>{plan['name']}</b>

<b>Стоимость:</b> {plan['price']}₽/мес

<b>Что входит:</b>
{chr(10).join([f"✅ {feature}" for feature in plan['features']])}

Выберите способ оплаты:
    """
    
    await callback.message.edit_text(
        payment_text,
        reply_markup=get_payment_method_keyboard(),
        parse_mode="HTML"
    )




@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback: CallbackQuery, db: Database):
    """Проверить статус платежа"""
    await callback.answer()
    
    # Извлекаем ID платежа из callback_data
    payment_id = callback.data.replace("check_payment_", "")
    
    try:
        # Проверяем статус платежа
        payment = await payment_manager.check_payment_status(payment_id)
        
        if not payment:
            await callback.message.edit_text(
                "❌ <b>Ошибка проверки платежа</b>\n\n"
                "Попробуйте позже или свяжитесь с поддержкой.",
                parse_mode="HTML"
            )
            return
        
        # Проверяем успешность платежа
        if payment_manager.is_payment_successful(payment):
            # Обрабатываем успешный платеж
            user_id = callback.from_user.id
            metadata = payment.metadata or {}
            payment_type = metadata.get("payment_type", "")
            
            if payment_type == "subscription":
                # Получаем информацию о подписке из метаданных
                subscription_type = metadata.get("subscription_type", "basic")
                plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
                days = plan['days']
                
                # Активируем подписку
                await db.grant_premium(user_id, days=days)
                await db.create_subscription(user_id, subscription_type, plan['price'])
                
                success_text = f"""
✅ <b>Платеж успешно обработан!</b>

💎 <b>{plan['name']} активирована</b>

Теперь вам доступно:
• {plan['analyses_per_month']} анализов в месяц
{chr(10).join([f"• {feature}" for feature in plan['features']])}

<b>ID платежа:</b> <code>{payment.id}</code>
                """
            else:
                success_text = f"""
✅ <b>Платеж успешно обработан!</b>

<b>ID платежа:</b> <code>{payment.id}</code>
                """
            
            await callback.message.edit_text(
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
        logger.error(f"Ошибка проверки статуса платежа: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка проверки платежа</b>\n\n"
            "Попробуйте позже или свяжитесь с поддержкой.",
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
            payment = await payment_manager.create_subscription_payment(
                user_id=user_id,
                subscription_type=plan_id,
                amount=float(amount),
                description=f"{plan_name} на {days} дней"
            )
        else:
            raise ValueError("Неизвестный тип покупки")
        
        if not payment:
            await callback.message.edit_text(
                "❌ <b>Ошибка создания платежа</b>\n\n"
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

Нажмите кнопку "Оплатить картой" для перехода к оплате.
После оплаты нажмите "Проверить статус".
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

Нажмите кнопку "Оплатить {currency}" для перехода к оплате.
После оплаты нажмите "Проверить статус".
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
    """Проверить статус криптоплатежа"""
    await callback.answer()
    
    # Извлекаем ID платежа из callback_data
    payment_id = callback.data.replace("check_crypto_payment_", "")
    
    try:
        # Проверяем статус криптоплатежа
        payment = await payment_manager.check_crypto_payment_status(payment_id)
        
        if not payment:
            await callback.message.edit_text(
                "❌ <b>Ошибка проверки криптоплатежа</b>\n\n"
                "Попробуйте позже или свяжитесь с поддержкой.",
                parse_mode="HTML"
            )
            return
        
        # Проверяем успешность платежа
        if payment_manager.is_crypto_payment_successful(payment):
            # Обрабатываем успешный платеж
            user_id = callback.from_user.id
            metadata = payment.metadata or {}
            payment_type = metadata.get("payment_type", "")
            
            if payment_type == "subscription":
                # Получаем информацию о подписке из метаданных
                subscription_type = metadata.get("subscription_type", "basic")
                plan = config.SUBSCRIPTION_PLANS.get(subscription_type, config.SUBSCRIPTION_PLANS['basic'])
                days = plan['days']
                
                # Активируем подписку
                await db.grant_premium(user_id, days=days)
                await db.create_subscription(user_id, subscription_type, plan['price'])
                
                success_text = f"""
✅ <b>Криптоплатеж успешно обработан!</b>

💎 <b>{plan['name']} активирована</b>

Теперь вам доступно:
• {plan['analyses_per_month']} анализов в месяц
{chr(10).join([f"• {feature}" for feature in plan['features']])}

<b>ID платежа:</b> <code>{payment.payment_id}</code>
                """
            else:
                success_text = f"""
✅ <b>Криптоплатеж успешно обработан!</b>

<b>ID платежа:</b> <code>{payment.payment_id}</code>
                """
            
            await callback.message.edit_text(
                success_text,
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
            
        else:
            # Платеж еще не обработан
            status_text = f"""
🔄 <b>Статус криптоплатежа: {payment.status.value}</b>

<b>ID платежа:</b> <code>{payment.payment_id}</code>

Криптоплатеж еще обрабатывается. Попробуйте проверить статус через несколько минут.
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
        logger.error(f"Ошибка проверки статуса криптоплатежа: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка проверки криптоплатежа</b>\n\n"
            "Попробуйте позже или свяжитесь с поддержкой.",
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

