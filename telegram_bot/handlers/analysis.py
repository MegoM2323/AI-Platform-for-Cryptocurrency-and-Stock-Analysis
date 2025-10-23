"""
Обработчики для анализа криптовалют
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from ..states import AnalysisStates
from ..keyboards import get_main_keyboard, get_cancel_keyboard
from database import Database
from config import config
from data_collectors import CryptoCollector, DataFormatter
from AI_block import AIAnalyzer

router = Router()


@router.message(F.text == "📊 Анализ токена")
@router.message(Command("analyze"))
async def start_analysis(message: Message, state: FSMContext, db: Database):
    """Начать процесс анализа"""
    user_id = message.from_user.id
    
    # Получаем план подписки пользователя
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
    elif subscription_plan == 'premium':
        # Для общего премиум статуса определяем по дополнительным анализам
        additional_analyses = await db.get_additional_analyses(user_id)
        if additional_analyses >= 500:
            max_analyses = config.ELITE_ANALYSES_PER_MONTH
        elif additional_analyses >= 150:
            max_analyses = config.PRO_ANALYSES_PER_MONTH
        elif additional_analyses >= 50:
            max_analyses = config.TRADER_ANALYSES_PER_MONTH
        else:
            max_analyses = config.BASIC_ANALYSES_PER_MONTH
    else:
        max_analyses = config.FREE_ANALYSES_PER_MONTH
    
    # Проверяем лимит анализов
    can_analyze = await db.check_analysis_limit(
        user_id,
        config.FREE_ANALYSES_PER_MONTH,
        max_analyses
    )
    
    if not can_analyze:
        plan_name = config.SUBSCRIPTION_PLANS.get(subscription_plan, {}).get('name', 'Free')
        
        # Получаем оставшиеся анализы
        remaining = await db.get_remaining_analyses(
            user_id,
            config.FREE_ANALYSES_PER_MONTH,
            max_analyses
        )
        
        # Проверяем дополнительные анализы
        additional_analyses = await db.get_additional_analyses(user_id)
        
        if additional_analyses > 0:
            # Есть дополнительные анализы, предлагаем их использовать
            limit_text = f"""
❌ <b>Лимит анализов исчерпан!</b>

Ты использовал все доступные анализы в этом месяце.

<b>Твой тариф:</b> {plan_name}
<b>Лимит:</b> {max_analyses} анализов в месяц
<b>Дополнительные анализы:</b> {additional_analyses}

У тебя есть дополнительные анализы! Хочешь использовать один?
"""
            from ..keyboards import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Использовать дополнительный анализ", callback_data=f"use_additional_analysis_{user_id}")],
                [InlineKeyboardButton(text="💎 Купить подписку", callback_data="show_subscriptions")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_analysis")]
            ])
            
            await message.answer(
                limit_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Нет дополнительных анализов, предлагаем подписку
            limit_text = f"""
❌ <b>Лимит анализов исчерпан!</b>

Ты использовал все доступные анализы в этом месяце.

<b>Твой тариф:</b> {plan_name}
<b>Лимит:</b> {max_analyses} анализов в месяц

<b>💎 Доступные тарифы:</b>
• 🥉 Basic - 299₽/мес (15 анализов)
• 🥈 Trader - 899₽/мес (50 анализов)  
• 🥇 Pro - 1590₽/мес (150 анализов)
• 💎 Elite - 2990₽/мес (500 анализов)

Выбери подходящий тариф:
"""
            from ..keyboards import InlineKeyboardMarkup, InlineKeyboardButton
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Выбрать подписку", callback_data="show_subscriptions")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_analysis")]
            ])
            
            await message.answer(
                limit_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        return
    
    # Получаем оставшиеся анализы
    remaining = await db.get_remaining_analyses(
        user_id,
        config.FREE_ANALYSES_PER_MONTH,
        max_analyses
    )
    
    await state.set_state(AnalysisStates.waiting_for_symbol)
    await message.answer(
        f"📊 <b>Анализ криптовалюты</b>\n\n"
        f"Осталось анализов в месяце: <b>{remaining - 1}</b>\n\n"
        f"Введи символ криптовалюты для анализа\n"
        f"(например: BTC, ETH, SOL, BNB)\n\n"
        f"Или нажми \"Отмена\" для выхода",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(AnalysisStates.waiting_for_symbol, F.text == "❌ Отмена")
async def cancel_analysis(message: Message, state: FSMContext):
    """Отменить анализ"""
    await state.clear()
    await message.answer(
        "❌ Анализ отменен",
        reply_markup=get_main_keyboard()
    )


@router.message(AnalysisStates.waiting_for_symbol)
async def process_symbol(message: Message, state: FSMContext, db: Database):
    """Обработать введенный символ и выполнить анализ"""
    import logging
    logger = logging.getLogger(__name__)
    
    symbol = message.text.strip().upper()
    user_id = message.from_user.id
    
    logger.info(f"Пользователь {user_id} запросил анализ {symbol}")
    
    # Проверяем, что пользователь действительно в состоянии ожидания символа
    current_state = await state.get_state()
    if current_state != AnalysisStates.waiting_for_symbol:
        logger.warning(f"Пользователь {user_id} не в состоянии ожидания символа. Текущее состояние: {current_state}")
        await message.answer(
            "❌ Неожиданное состояние. Пожалуйста, начни анализ заново.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    # Проверяем формат
    if len(symbol) > 10 or not symbol.isalnum():
        logger.warning(f"Неверный формат символа от пользователя {user_id}: {symbol}")
        await message.answer(
            "❌ Неверный формат символа.\n"
            "Введи корректный символ (например: BTC, ETH)"
        )
        return
    
    # Отправляем сообщение о начале анализа
    processing_msg = await message.answer(
        f"🔄 Анализирую {symbol}...\n"
        f"Это может занять несколько секунд",
        parse_mode="HTML"
    )
    
    try:
        logger.info(f"Начинаем сбор данных для {symbol}")
        
        # Собираем данные
        collector = CryptoCollector(
            timeframe=config.DEFAULT_TIMEFRAME,
            period=config.DEFAULT_PERIOD
        )
        
        # Проверяем существование токена
        logger.info(f"Проверяем валидность символа {symbol}")
        if not collector.validate_symbol(symbol):
            logger.warning(f"Символ {symbol} не прошел валидацию")
            await processing_msg.edit_text(
                f"❌ Криптовалюта {symbol} не найдена.\n\n"
                f"Проверь правильность символа и попробуй снова.\n"
                f"Примеры: BTC, ETH, SOL, BNB"
            )
            return
        
        # Получаем данные
        logger.info(f"Получаем исторические данные для {symbol}")
        data = collector.get_crypto_data(symbol)
        if data is None or data.empty:
            logger.error(f"Не удалось получить данные для {symbol}")
            await processing_msg.edit_text(
                f"❌ Не удалось получить данные для {symbol}"
            )
            return
        
        logger.info(f"Данные получены: {data.shape[0]} записей")
        
        current_price = collector.get_current_price(symbol)
        logger.info(f"Текущая цена {symbol}: {current_price}")
        
        # Форматируем данные
        logger.info("Форматируем данные для анализа")
        formatter = DataFormatter()
        formatted_data = formatter.format_for_analysis(data, symbol, current_price)
        logger.info(f"Данные отформатированы: {len(formatted_data)} символов")
        
        # Выполняем AI анализ
        logger.info("Запускаем AI анализ")
        analyzer = AIAnalyzer(
            api_key=config.OPENROUTER_API_KEY,
            model=config.AI_MODEL
        )
        
        analysis_result = await analyzer.analyze_crypto(formatted_data, symbol)
        
        if analysis_result is None:
            logger.error(f"AI анализ не вернул результат для {symbol}")
            await processing_msg.edit_text(
                "❌ Ошибка при выполнении анализа.\n"
                "Попробуй позже."
            )
            return
        
        logger.info(f"AI анализ завершен: {len(analysis_result)} символов")
        
        # Увеличиваем счетчик анализов
        await db.increment_analysis_count(user_id)
        
        # Сохраняем анализ в БД
        logger.info("Сохраняем анализ в базу данных")
        await db.save_analysis(user_id, symbol, analysis_result)
        
        # Отправляем результат
        await processing_msg.edit_text(
            f"✅ Анализ завершен для {symbol}"
        )
        
        # Разбиваем длинное сообщение, если нужно
        if len(analysis_result) > 4096:
            # Telegram ограничивает сообщения до 4096 символов
            logger.info(f"Разбиваем длинное сообщение на части")
            chunks = [analysis_result[i:i+4096] for i in range(0, len(analysis_result), 4096)]
            for i, chunk in enumerate(chunks):
                await message.answer(f"📄 Часть {i+1}/{len(chunks)}\n\n{chunk}", parse_mode="HTML")
        else:
            await message.answer(analysis_result, parse_mode="HTML")
        
        # Возвращаем главное меню
        await state.clear()
        await message.answer(
            reply_markup=get_main_keyboard()
        )
        
        logger.info(f"Анализ {symbol} успешно завершен для пользователя {user_id}")
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Ошибка при анализе {symbol} для пользователя {user_id}: {e}")
        logger.error(f"Полная ошибка: {error_details}")
        
        # Отправляем детальную ошибку в debug режиме
        if config.DEBUG_MODE:
            await processing_msg.edit_text(
                f"❌ Ошибка при анализе:\n"
                f"<code>{str(e)}</code>\n\n"
                f"Полная ошибка:\n"
                f"<code>{error_details[:1000]}</code>",
                parse_mode="HTML"
            )
        else:
            await processing_msg.edit_text(
                "❌ Произошла ошибка при анализе.\n"
                "Попробуй позже или обратись в поддержку."
            )
        await state.clear()


@router.callback_query(F.data.startswith("use_additional_analysis_"))
async def use_additional_analysis(callback: CallbackQuery, state: FSMContext, db: Database):
    """Использовать дополнительный анализ"""
    await callback.answer()
    
    user_id = callback.from_user.id
    
    # Проверяем, есть ли дополнительные анализы
    additional_analyses = await db.get_additional_analyses(user_id)
    if additional_analyses <= 0:
        await callback.message.edit_text(
            "❌ У вас нет дополнительных анализов",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Используем дополнительный анализ
    success = await db.use_additional_analysis(user_id)
    if not success:
        await callback.message.edit_text(
            "❌ Ошибка использования дополнительного анализа",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Переходим к анализу
    await state.set_state(AnalysisStates.waiting_for_symbol)
    await callback.message.edit_text(
        f"✅ <b>Дополнительный анализ использован!</b>\n\n"
        f"Осталось дополнительных анализов: <b>{additional_analyses - 1}</b>\n\n"
        f"Введи символ криптовалюты для анализа\n"
        f"(например: BTC, ETH, SOL, BNB)\n\n"
        f"Или нажми \"Отмена\" для выхода",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "cancel_analysis")
async def cancel_analysis_callback(callback: CallbackQuery, state: FSMContext):
    """Отменить анализ через callback"""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "❌ Анализ отменен",
        reply_markup=get_main_keyboard()
    )

