"""
Обработчики команд /start и /help
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from ..keyboards import get_main_keyboard, get_main_keyboard_with_balance
from database import Database
from config import config
from ..token_manager import TokenManager

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db: Database):
    """Обработчик команды /start"""
    # Очищаем состояние
    await state.clear()
    
    # Регистрируем или получаем пользователя
    user = message.from_user
    await db.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    tm = TokenManager(db)
    balance = await tm.get_balance(user.id)
    welcome_text = f"""
👋 <b>Привет, {user.first_name}!</b>

Я — AI бот для анализа криптовалют. Помогу тебе:

📊 Анализировать токены
📈 Отслеживать тренды
💡 Принимать взвешенные решения

<b>Стоимость анализов:</b>
• Базовый: <b>{config.BASIC_ANALYSIS_COST}</b> токенов
• Расширенный: <b>{config.ENHANCED_ANALYSIS_COST}</b> токенов

<b>Баланс:</b> <b>{balance}</b> токенов

<b>Команды:</b>
/analyze — начать анализ
/enhanced — расширенный анализ
/balance — показать баланс
/buy_tokens — купить токены
/help — помощь

Выбери действие из меню ниже 👇
"""
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "❓ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    """Обработчик команды /help"""
    await state.clear()
    
    # Отображаем актуальный баланс в справке
    tm = TokenManager(message.bot['db']) if isinstance(message.bot, dict) and 'db' in message.bot else None
    try:
        balance = await TokenManager(message.bot['db']).get_balance(message.from_user.id) if tm else 0
    except Exception:
        balance = 0

    help_text = f"""
📖 <b>РУКОВОДСТВО ПО ИСПОЛЬЗОВАНИЮ</b>

<b>Как использовать бота:</b>

1️⃣ <b>Базовый анализ</b>
   • Нажми "📊 Анализ токена" или используй /analyze
   • Введи символ криптовалюты (например: BTC, ETH, SOL)
   • Стоимость: <b>{config.BASIC_ANALYSIS_COST}</b> токенов

2️⃣ <b>Расширенный анализ</b>
   • Используй команду /enhanced
   • Введи символ криптовалюты
   • Получишь серию сообщений в Telegram (без PDF)
   • Стоимость: <b>{config.ENHANCED_ANALYSIS_COST}</b> токенов
   • ⚠️ <b>Анализ выполняется на дневном таймфрейме</b>

3️⃣ <b>Покупка токенов</b>
   • Нажми "💰 Купить токены" или /buy_tokens
   • Выбери пакет токенов (есть эквивалент в анализах)
   • Оплата: <b>банковская карта (ЮКасса)</b>

4️⃣ <b>Профиль</b>
   • Нажми "📈 Мой профиль"
   • Посмотри историю и статус

💰 <b>Текущий баланс:</b> <b>{balance}</b> токенов

<b>Команды:</b>
/start — Начать работу
/analyze — Базовый анализ
/enhanced — Расширенный анализ
/balance — Баланс
/buy_tokens — Купить токены
/history — История транзакций
/help — Эта справка

<b>Примеры символов:</b> BTC, ETH, SOL, BNB

⚠️ <b>Важно:</b>
Анализ не является финансовым советом. Проводите собственное исследование.

❓ Вопросы? Поддержка: @your_support
"""
    
    await message.answer(
        help_text,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "📈 Мой профиль")
@router.message(Command("profile"))
async def cmd_profile(message: Message, db: Database):
    """Показать профиль пользователя (по токенам)."""
    user_id = message.from_user.id
    await db.get_or_create_user(user_id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    tm = TokenManager(db)
    balance = await tm.get_balance(user_id)
    history = await tm.get_transaction_history(user_id, limit=5)

    lines = [
        "📈 <b>ПРОФИЛЬ</b>",
        f"\n💰 <b>Баланс токенов:</b> {balance}",
    ]
    if history:
        lines.append("\n🧾 <b>Последние транзакции:</b>")
        for tx in history:
            amount = tx.get("amount", 0)
            ttype = tx.get("transaction_type", "")
            created = tx.get("created_at", "")
            lines.append(f"• {created} — {ttype}: {amount:+d}")

    await message.answer(
        "\n".join(lines),
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

