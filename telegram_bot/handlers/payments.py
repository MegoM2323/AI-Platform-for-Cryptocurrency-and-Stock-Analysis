"""
Обработчики для подписок и платежей
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from ..states import SubscriptionStates
from ..keyboards import get_main_keyboard, get_subscription_keyboard
from database import Database
from config import config

router = Router()


@router.message(Command("subscribe"))
@router.message(F.text == "💎 Подписка")
async def show_subscription_options(message: Message, state: FSMContext, db: Database):
    """Показать варианты подписки"""
    await state.clear()
    
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    is_premium = user_data.get('is_premium', 0)
    
    subscription_text = f"""
💎 <b>ПОДПИСКА</b>

<b>Текущий статус:</b> {'✅ Premium активна' if is_premium else '❌ Бесплатный тариф'}

<b>🎁 Бесплатный тариф:</b>
• {config.FREE_ANALYSES_PER_DAY} анализов в день
• Базовый анализ

<b>💎 Premium тариф:</b>
• {config.PREMIUM_ANALYSES_PER_DAY} анализов в день
• Расширенный анализ
• Приоритетная поддержка
• Ранний доступ к новым функциям

<b>Цены:</b>
💎 Premium (30 дней) - 500₽
💰 Докупить анализы (10 шт) - 100₽

Выбери вариант ниже:
"""
    
    await message.answer(
        subscription_text,
        reply_markup=get_subscription_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "subscribe_premium_30")
async def process_premium_subscription(callback: CallbackQuery, db: Database):
    """Обработка подписки Premium на 30 дней"""
    await callback.answer()
    
    # В MVP это заглушка для демонстрации
    payment_text = """
💎 <b>Premium подписка (30 дней)</b>

<b>Стоимость:</b> 500₽

<b>Что входит:</b>
✅ {premium_analyses} анализов в день
✅ Расширенная аналитика
✅ Приоритетная поддержка

<b>Для оплаты:</b>
В MVP оплата не реализована.
Это демо-версия функционала.

<b>В полной версии будет:</b>
• Интеграция с платежными системами
• Автоматическая активация подписки
• История платежей

Для активации Premium в тестовом режиме
свяжись с администратором.
""".format(premium_analyses=config.PREMIUM_ANALYSES_PER_DAY)
    
    await callback.message.edit_text(
        payment_text,
        parse_mode="HTML"
    )
    
    # В реальной версии здесь будет:
    # 1. Создание платежа в БД
    # 2. Генерация ссылки на оплату
    # 3. Отправка инструкций по оплате
    # 4. Ожидание подтверждения
    # 5. Активация подписки


@router.callback_query(F.data == "buy_analyses_10")
async def process_buy_analyses(callback: CallbackQuery):
    """Обработка докупки анализов"""
    await callback.answer()
    
    payment_text = """
💰 <b>Докупить анализы (10 шт)</b>

<b>Стоимость:</b> 100₽

<b>Что получишь:</b>
✅ 10 дополнительных анализов
✅ Не сгорают в конце дня
✅ Можно использовать когда угодно

<b>Для оплаты:</b>
В MVP оплата не реализована.
Это демо-версия функционала.

<b>В полной версии будет:</b>
• Интеграция с платежными системами
• Мгновенное зачисление анализов
• История покупок
"""
    
    await callback.message.edit_text(
        payment_text,
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

