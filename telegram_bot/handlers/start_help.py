"""
Обработчики команд /start и /help
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from ..keyboards import get_main_keyboard
from database import Database
from config import config

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
    
    welcome_text = f"""
👋 <b>Привет, {user.first_name}!</b>

Я — AI бот для анализа криптовалют. Я помогу тебе:

📊 Анализировать токены
📈 Отслеживать тренды
💡 Принимать взвешенные решения

<b>Доступные команды:</b>
/analyze - Анализ криптовалюты
/help - Помощь
/profile - Твой профиль
/subscribe - Управление подпиской

<b>Тарифные планы:</b>
🆓 Free: {config.FREE_ANALYSES_PER_MONTH} анализов в месяц
🥉 Basic: {config.BASIC_ANALYSES_PER_MONTH} анализов в месяц - 299₽
🥈 Trader: {config.TRADER_ANALYSES_PER_MONTH} анализов в месяц - 899₽
🥇 Pro: {config.PRO_ANALYSES_PER_MONTH} анализов в месяц - 1590₽
💎 Elite: {config.ELITE_ANALYSES_PER_MONTH} анализов в месяц - 2990₽

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
    
    help_text = """
📖 <b>РУКОВОДСТВО ПО ИСПОЛЬЗОВАНИЮ</b>

<b>Как использовать бота:</b>

1️⃣ <b>Анализ токена</b>
   • Нажми "📊 Анализ токена"
   • Введи символ криптовалюты (например: BTC, ETH, SOL)
   • Получи AI анализ

2️⃣ <b>Подписка</b>
   • Нажми "💎 Подписка"
   • Выбери тариф
   • Следуй инструкциям по оплате

3️⃣ <b>Профиль</b>
   • Нажми "📈 Мой профиль"
   • Посмотри свою статистику

<b>Доступные команды:</b>
/start - Начать работу
/analyze - Анализ криптовалюты
/profile - Твой профиль
/subscribe - Подписка
/help - Эта справка

<b>Примеры использования:</b>
• BTC - Bitcoin
• ETH - Ethereum
• SOL - Solana
• BNB - Binance Coin

⚠️ <b>Важно:</b>
Анализ не является финансовым советом!
Всегда проводи собственное исследование.

❓ Вопросы? Напиши в поддержку: @your_support
"""
    
    await message.answer(
        help_text,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "📈 Мой профиль")
@router.message(Command("profile"))
async def cmd_profile(message: Message, db: Database):
    """Показать профиль пользователя"""
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    
    if not user_data:
        await message.answer("❌ Пользователь не найден. Используй /start")
        return
    
    # Получаем план подписки
    subscription_plan = await db.get_user_subscription_plan(user_id)
    
    # Определяем лимиты в зависимости от плана
    if subscription_plan == 'free':
        max_analyses = config.FREE_ANALYSES_PER_MONTH
    elif subscription_plan == 'basic':
        max_analyses = config.BASIC_ANALYSES_PER_MONTH
    elif subscription_plan == 'trader':
        max_analyses = config.TRADER_ANALYSES_PER_MONTH
    elif subscription_plan == 'pro':
        max_analyses = config.PRO_ANALYSES_PER_MONTH
    elif subscription_plan == 'elite':
        max_analyses = config.ELITE_ANALYSES_PER_MONTH
    else:
        max_analyses = config.FREE_ANALYSES_PER_MONTH
    
    # Получаем оставшиеся анализы
    remaining = await db.get_remaining_analyses(
        user_id, 
        config.FREE_ANALYSES_PER_MONTH,
        max_analyses
    )
    
    # Получаем информацию о тарифе
    plan_name = config.SUBSCRIPTION_PLANS.get(subscription_plan, {}).get('name', 'Free')
    is_premium = user_data.get('is_premium', 0)
    premium_text = "✅ Активна" if is_premium else "❌ Не активна"
    
    if is_premium and user_data.get('premium_until'):
        from datetime import datetime
        premium_until = datetime.fromisoformat(user_data['premium_until'])
        premium_text += f"\n📅 До: {premium_until.strftime('%d.%m.%Y')}"
    
    # Получаем количество анализов за месяц
    from datetime import date
    current_month = date.today().replace(day=1)
    monthly_analyses = await db.get_monthly_analyses_count(user_id, current_month)
    
    # Получаем историю анализов
    analyses = await db.get_user_analyses(user_id, limit=5)
    
    profile_text = f"""
👤 <b>ТВОЙ ПРОФИЛЬ</b>

<b>ID:</b> {user_id}
<b>Имя:</b> {user_data.get('first_name', 'N/A')}
<b>Username:</b> @{user_data.get('username', 'N/A')}

💎 <b>Тариф:</b> {plan_name}
<b>Статус:</b> {premium_text}

📊 <b>Анализы в месяце:</b>
• Осталось: {remaining}
• Использовано: {monthly_analyses}
• Лимит: {max_analyses}

📈 <b>Последние анализы ({len(analyses)}):</b>
"""
    
    if analyses:
        for i, analysis in enumerate(analyses, 1):
            from datetime import datetime
            created_at = datetime.fromisoformat(analysis['created_at'])
            profile_text += f"\n{i}. {analysis['token_symbol']} - {created_at.strftime('%d.%m %H:%M')}"
    else:
        profile_text += "\nПока нет анализов"
    
    await message.answer(
        profile_text,
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )

