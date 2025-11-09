from __future__ import annotations

import logging
from typing import Dict

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from database.db import Database
from telegram_bot.token_manager import TokenManager
from telegram_bot.keyboards import get_token_packages_keyboard
from config import config as cfg

logger = logging.getLogger(__name__)
router = Router()


def _get_token_packages() -> Dict[str, Dict]:
    # Всегда читаем из инстанса конфига, чтобы исключить расхождения
    return getattr(cfg, "TOKEN_PACKAGES", {}) or {}


@router.message(Command("balance"))
async def show_balance(message: Message, db: Database):
    """Показать текущий баланс токенов пользователя."""
    await db.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    tm = TokenManager(db)
    balance = await tm.get_balance(message.from_user.id)

    text = (
        f"💰 Баланс токенов: <b>{balance}</b>\n\n"
        "Токены списываются за анализы: базовый — 3, расширенный — 10."
    )

    await message.answer(text, parse_mode="HTML")


@router.message(Command("buy_tokens"))
async def show_token_packages(message: Message):
    """Показать пакеты токенов для покупки (единая клавиатура)."""
    packages = _get_token_packages()
    await message.answer(
        "Выберите пакет токенов:",
        reply_markup=get_token_packages_keyboard(packages),
    )


@router.callback_query(F.data == "show_token_store")
async def show_token_store(callback: CallbackQuery):
    """Открыть список пакетов токенов из магазина."""
    packages = _get_token_packages()
    await callback.message.edit_text(
        "Выберите пакет токенов:",
        reply_markup=get_token_packages_keyboard(packages),
    )


@router.callback_query(F.data.startswith("tokenpkg_"))
async def process_token_purchase(callback: CallbackQuery, db: Database):
    """Создать платёж на покупку токенов (фиат или крипто)."""
    packages = _get_token_packages()
    key = callback.data.replace("tokenpkg_", "").strip()
    # Нормализация ключа: пробелы, регистр
    norm_key = key.lower()
    # Пытаемся найти по исходному и нормализованному ключу
    pkg = packages.get(key) or packages.get(norm_key)
    if not pkg:
        # Переотрисовываем список пакетов, чтобы пользователь выбрал актуальный
        from telegram_bot.keyboards import get_token_packages_keyboard
        kb = get_token_packages_keyboard(packages)
        await callback.message.edit_text(
            "❌ Пакет не найден. Выберите пакет заново:",
            reply_markup=kb,
        )
        return

    # Выбор способа оплаты: крипто отключена
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Оплатить картой (ЮКасса)",
                    callback_data=f"tokenpay_fiat_{norm_key}",
                )
            ]
        ]
    )

    await callback.message.edit_text(
        (
            f"<b>{pkg['name']}</b> — {pkg['tokens']} токенов\n"
            f"Стоимость: {int(pkg['price_rub'])}₽ (~${pkg['price_usd']})\n"
            f"Эквивалент: {pkg['analyses_equivalent']}\n\n"
            "Выберите способ оплаты:"
        ),
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("tokenpay_fiat_"))
async def create_yookassa_payment(callback: CallbackQuery, db: Database):
    from Payments.payment_system import PaymentManager

    key = callback.data.replace("tokenpay_fiat_", "").strip()
    packages = _get_token_packages()
    norm_key = key.lower()
    pkg = packages.get(key) or packages.get(norm_key)
    if not pkg:
        # Дополнительная попытка: нормализуем ключ и проверим прямо по конфигу
        from config import config as _cfg
        cfg_pkgs = getattr(_cfg, "TOKEN_PACKAGES", {}) or {}
        pkg = cfg_pkgs.get(key) or cfg_pkgs.get(norm_key)
        if not pkg:
            # Предложим выбрать пакет заново
            from telegram_bot.keyboards import get_token_packages_keyboard
            kb_retry = get_token_packages_keyboard(packages)
            await callback.message.edit_text(
                "❌ Пакет не найден. Выберите пакет заново:",
                reply_markup=kb_retry,
            )
            return

    await db.get_or_create_user(callback.from_user.id, callback.from_user.username, callback.from_user.first_name, callback.from_user.last_name)

    pm = PaymentManager()
    description = f"Покупка токенов: {pkg['name']} ({pkg['tokens']})"
    payment = await pm.create_token_purchase_payment(
        user_id=callback.from_user.id,
        package_key=norm_key,
        package_name=pkg["name"],
        tokens=pkg["tokens"],
        amount_rub=float(pkg["price_rub"]),
        description=description,
    )

    if not payment:
        await callback.answer("Не удалось создать платеж", show_alert=True)
        return

    # Показать ссылку на оплату и кнопку проверки статуса
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить картой", url=payment.confirmation_url)],
            [InlineKeyboardButton(text="🔄 Проверить статус", callback_data=f"check_payment_{payment.id}")],
        ]
    )
    text = (
        f"✅ Платёж создан.\n\n"
        f"<b>{pkg['name']}</b> — {pkg['tokens']} токенов за {int(pkg['price_rub'])}₽\n\n"
        f"Перейдите по ссылке для оплаты и затем нажмите \"Проверить статус\".\n"
        f"ID платежа: <code>{payment.id}</code>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

    # Запустить авто-мониторинг как для подписок
    try:
        from telegram_bot.handlers.payments import start_payment_monitoring
        await start_payment_monitoring(
            payment_id=payment.id,
            user_id=callback.from_user.id,
            payment_type="yookassa",
            db=db,
            bot=callback.bot,
            timeout_minutes=10,
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("buy_tokens_pay_crypto_"))
async def create_nowpayments_payment(callback: CallbackQuery, db: Database):
    # Временно отключено
    await callback.answer("Криптооплата временно недоступна", show_alert=True)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.message(Command("history"))
async def show_transaction_history(message: Message, db: Database):
    tm = TokenManager(db)
    history = await tm.get_transaction_history(message.from_user.id, limit=10)

    if not history:
        await message.answer("История транзакций пуста.")
        return

    lines = ["🧾 Последние транзакции:"]
    for tx in history:
        amount = tx.get("amount", 0)
        ttype = tx.get("transaction_type", "")
        created = tx.get("created_at", "")
        lines.append(f"• {created} — {ttype}: {amount:+d}")

    await message.answer("\n".join(lines))


@router.callback_query(F.data == "tokens_back")
async def tokens_back(callback: CallbackQuery):
    """Вернуться к списку пакетов токенов."""
    packages = _get_token_packages()
    text = "Выберите пакет токенов:"
    keyboard = get_token_packages_keyboard(packages)
    try:
        # Избегаем ошибки Telegram "message is not modified"
        if (callback.message.text or "") == text:
            # Если текст тот же, попробуем обновить только разметку,
            # а если и она совпадает — игнорируем исключение ниже
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        else:
            await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest as e:
        # Игнорируем неизменённые сообщения
        if "message is not modified" in str(e).lower():
            pass
        else:
            raise


