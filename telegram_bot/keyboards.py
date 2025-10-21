"""
Клавиатуры для Telegram бота
"""

from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Анализ токена"),
                KeyboardButton(text="❓ Помощь")
            ],
            [
                KeyboardButton(text="💎 Подписка"),
                KeyboardButton(text="📈 Мой профиль")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора подписки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 Premium (30 дней)",
                    callback_data="subscribe_premium_30"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Докупить анализы (10 шт)",
                    callback_data="buy_analyses_10"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_subscription"
                )
            ]
        ]
    )
    return keyboard


def get_payment_keyboard(payment_id: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для оплаты
    
    Args:
        payment_id: ID платежа
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Я оплатил",
                    callback_data=f"payment_confirm_{payment_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="payment_cancel"
                )
            ]
        ]
    )
    return keyboard


def get_analysis_options_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с опциями анализа"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Полный анализ",
                    callback_data="analysis_full"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚡️ Быстрый анализ",
                    callback_data="analysis_quick"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="analysis_cancel"
                )
            ]
        ]
    )
    return keyboard

