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
                    text="💎 Выбрать тариф",
                    callback_data="show_subscriptions"
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


def get_subscription_plans_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора плана подписки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🥉 Basic - 299₽",
                    callback_data="subscribe_basic"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🥈 Trader - 899₽",
                    callback_data="subscribe_trader"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🥇 Pro - 1590₽",
                    callback_data="subscribe_pro"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💎 Elite - 2990₽",
                    callback_data="subscribe_elite"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="back_to_subscription_menu"
                )
            ]
        ]
    )
    return keyboard




def get_payment_method_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора способа оплаты"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Банковская карта (ЮКасса)",
                    callback_data="payment_method_yookassa"
                )
            ],
            # [
            #     InlineKeyboardButton(
            #         text="Криптовалюта",
            #         callback_data="payment_method_crypto"
            #     )
            # ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_subscription"
                )
            ]
        ]
    )
    return keyboard


def get_crypto_currency_keyboard(available_currencies: list) -> InlineKeyboardMarkup:
    """Клавиатура для выбора криптовалюты"""
    keyboard_buttons = []
    
    # Добавляем популярные криптовалюты
    popular_currencies = ["BTC", "ETH", "USDT", "USDC", "LTC", "DOGE"]
    
    for currency in popular_currencies:
        if any(c.symbol == currency for c in available_currencies):
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"₿ {currency}",
                    callback_data=f"crypto_currency_{currency}"
                )
            ])
    
    # Добавляем кнопку "Показать все"
    if len(available_currencies) > len(popular_currencies):
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="📋 Показать все криптовалюты",
                callback_data="show_all_crypto"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_subscription"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_all_crypto_currencies_keyboard(available_currencies: list) -> InlineKeyboardMarkup:
    """Клавиатура со всеми доступными криптовалютами"""
    keyboard_buttons = []
    
    # Группируем по 2 кнопки в ряд
    for i in range(0, len(available_currencies), 2):
        row = []
        for j in range(2):
            if i + j < len(available_currencies):
                currency = available_currencies[i + j]
                row.append(InlineKeyboardButton(
                    text=f"₿ {currency.symbol}",
                    callback_data=f"crypto_currency_{currency.symbol}"
                ))
        keyboard_buttons.append(row)
    
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_subscription"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
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

