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
        
        limit_text = f"""
❌ <b>Лимит анализов исчерпан!</b>

Ты использовал все доступные анализы в этом месяце.

<b>Твой тариф:</b> {plan_name}
<b>Лимит:</b> {max_analyses} анализов в месяц

<b>Что можно сделать:</b>
• Подождать до следующего месяца
• Оформить подписку на более высокий тариф (/subscribe)

Используй /subscribe для улучшения тарифа
"""
        await message.answer(
            limit_text,
            reply_markup=get_main_keyboard(),
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
    symbol = message.text.strip().upper()
    user_id = message.from_user.id
    
    # Проверяем формат
    if len(symbol) > 10 or not symbol.isalnum():
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
        # Собираем данные
        collector = CryptoCollector(
            timeframe=config.DEFAULT_TIMEFRAME,
            period=config.DEFAULT_PERIOD
        )
        
        # Проверяем существование токена
        if not collector.validate_symbol(symbol):
            await processing_msg.edit_text(
                f"❌ Криптовалюта {symbol} не найдена.\n\n"
                f"Проверь правильность символа и попробуй снова.\n"
                f"Примеры: BTC, ETH, SOL, BNB"
            )
            return
        
        # Получаем данные
        data = collector.get_crypto_data(symbol)
        if data is None or data.empty:
            await processing_msg.edit_text(
                f"❌ Не удалось получить данные для {symbol}"
            )
            return
        
        current_price = collector.get_current_price(symbol)
        
        # Форматируем данные
        formatter = DataFormatter()
        formatted_data = formatter.format_for_analysis(data, symbol, current_price)
        
        # Выполняем AI анализ
        analyzer = AIAnalyzer(
            api_key=config.OPENROUTER_API_KEY,
            model=config.AI_MODEL
        )
        
        analysis_result = await analyzer.analyze_crypto(formatted_data, symbol)
        
        if analysis_result is None:
            await processing_msg.edit_text(
                "❌ Ошибка при выполнении анализа.\n"
                "Попробуй позже."
            )
            return
        
        # Увеличиваем счетчик анализов
        await db.increment_analysis_count(user_id)
        
        # Сохраняем анализ в БД
        await db.save_analysis(user_id, symbol, analysis_result)
        
        # Отправляем результат
        await processing_msg.edit_text(
            f"✅ Анализ завершен для {symbol}"
        )
        
        # Разбиваем длинное сообщение, если нужно
        if len(analysis_result) > 4096:
            # Telegram ограничивает сообщения до 4096 символов
            chunks = [analysis_result[i:i+4096] for i in range(0, len(analysis_result), 4096)]
            for chunk in chunks:
                await message.answer(chunk, parse_mode="HTML")
        else:
            await message.answer(analysis_result, parse_mode="HTML")
        
        # Возвращаем главное меню
        await state.clear()
        await message.answer(
            "Что дальше?",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in analysis: {e}")
        print(f"Full traceback: {error_details}")
        
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

