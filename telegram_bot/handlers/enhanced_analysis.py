"""
Расширенный анализ с учетом новостей, выбор краткого/детального формата и PDF.
"""

import logging
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import config
from database.db import Database
from data_collectors import NewsCollector, RateLimiter, NewsPipeline, CryptoCollector, DataFormatter
from analysis.sentiment_analyzer import SentimentAnalyzer
from analysis.enhanced_engine import EnhancedAnalysisEngine
from AI_block.analyzer import AIAnalyzer
from reports.telegram_report_builder import TelegramReportBuilder
from ..token_manager import TokenManager


router = Router()
_rate_limiter = RateLimiter()


@router.message(Command("enhanced"))
async def enhanced_entry(message: Message, state: FSMContext, db: Database):
    # Показать стоимость и баланс
    tm = TokenManager(db)
    balance = await tm.get_balance(message.from_user.id)
    await message.answer(
        (
            "🚀 <b>Расширенный анализ</b>\n\n"
            f"Стоимость: <b>{config.ENHANCED_ANALYSIS_COST}</b> ток.\n"
            f"Текущий баланс: <b>{balance}</b> ток.\n\n"
            "Отправь символ (например: BTC)."
        ),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    await state.update_data(enhanced_mode=True)
    # Переиспользуем состояние из стандартного обработчика, чтобы не дублировать FSM
    from ..states import AnalysisStates
    await state.set_state(AnalysisStates.waiting_for_symbol)


@router.message(Command("refresh_news"))
async def refresh_news(message: Message, db: Database):
    # Проверка прав администратора через ADMIN_USER_ID
    if not config.ADMIN_USER_ID or str(message.from_user.id) != str(config.ADMIN_USER_ID):
        await message.answer("❌ Доступ ограничен. Эта команда доступна только администратору.")
        return
    
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /refresh_news <SYMBOL>")
        return
    
    symbol = parts[1].upper()
    try:
        pipeline = NewsPipeline(db=db, collector=NewsCollector(rate_limiter=_rate_limiter), analyzer=SentimentAnalyzer())
        count = await pipeline.fetch_analyze_store(symbol=symbol, days=7)
        await message.answer(f"✅ Обновлено новостей для {symbol}: {count} статей")
    except Exception as e:
        await message.answer(f"❌ Не удалось обновить новости для {symbol}: {str(e)}")


async def _run_enhanced(symbol: str, db: Database) -> tuple[dict, list, object]:
    """
    Выполняет расширенный анализ с автопоиском новостей и кэшированием
    
    Returns:
        (analysis_dict, news_articles, market_df)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Получаем рыночные данные
    crypto_collector = CryptoCollector(timeframe=config.DEFAULT_TIMEFRAME, period=config.DEFAULT_PERIOD)
    market_df = crypto_collector.get_crypto_data(symbol)
    
    # Проверяем кэш для полного анализа (не используем кэш для краткого анализа)
    # Всегда выполняем полный анализ для максимальной детализации
    
    # Автопоиск свежих новостей (ОБЯЗАТЕЛЬНО)
    logger.info(f"Запускаем автопоиск новостей для {symbol}")
    news_collector = NewsCollector(rate_limiter=_rate_limiter)
    pipeline = NewsPipeline(db=db, collector=news_collector, analyzer=SentimentAnalyzer())

    news_count = 0
    try:
        # Принудительно обновляем новости
        news_count = await pipeline.fetch_analyze_store(symbol=symbol, days=7)
        logger.info(f"Получено {news_count} новых статей для {symbol}")
        
        if news_count == 0:
            logger.warning(f"Новости не найдены для {symbol}, попробуем получить из кэша")
            # Проверяем, есть ли новости в кэше
            cached_news = await db.get_recent_news(symbol=symbol, hours=24*7, limit=10)
            if not cached_news:
                logger.error(f"Нет новостей для {symbol} - это критично для расширенного анализа")
                # Создаем базовый анализ без новостей
                return {
                    'symbol': symbol,
                    'timeframe': '1day',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'overall_score': 0.0,
                    'risk_level': 'unknown',
                    'recommendation': 'hold',
                    'technical': {'trend': 'unknown', 'moving_averages': {}},
                    'sentiment': {'overall': {'label': 'unknown', 'score': 0.0}, 'articles': [], 'key_themes': []},
                    'key_points': ['Недостаточно данных для анализа'],
                    'data_sources': ['TwelveData'],
                    'confidence_level': 0.0
                }, [], market_df
    except Exception as e:
        logger.error(f"Критическая ошибка при получении новостей: {e}")
        # Новости критичны для расширенного анализа
        return {
            'symbol': symbol,
            'timeframe': '1day', 
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_score': 0.0,
            'risk_level': 'unknown',
            'recommendation': 'hold',
            'technical': {'trend': 'unknown', 'moving_averages': {}},
            'sentiment': {'overall': {'label': 'unknown', 'score': 0.0}, 'articles': [], 'key_themes': []},
            'key_points': ['Ошибка получения данных'],
            'data_sources': ['TwelveData'],
            'confidence_level': 0.0
        }, [], market_df if market_df is not None else None

    # Выполняем полный анализ (новости уже получены)
    engine = EnhancedAnalysisEngine(
        ai_analyzer=AIAnalyzer(api_key=config.OPENROUTER_API_KEY, model=config.AI_MODEL),
        db=db,
        crypto_collector=crypto_collector,
        sentiment_analyzer=SentimentAnalyzer(),
    )
    analysis_dict = await engine.analyze_crypto_comprehensive(symbol)

    # Получаем новости из БД для включения в отчёт
    try:
        news_articles = await db.get_recent_news(symbol=symbol, hours=24*7, limit=200)
    except Exception:
        news_articles = []

    return analysis_dict, news_articles, market_df


@router.message(F.text.regexp(r"^(brief|detailed|pdf)$"))
async def format_choice(message: Message):
    # Заглушка для совместимости; формат выбирается сразу после анализа
    await message.answer("Отправьте символ для анализа (например: BTC)")


@router.message(F.text.regexp(r"^[A-Za-z0-9]{2,10}$"))
async def enhanced_symbol_auto(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    if not data.get("enhanced_mode"):
        return  # не перехватываем стандартный поток

    symbol = message.text.strip().upper()
    # Списываем токены перед выполнением анализа
    tm = TokenManager(db)
    user_id = message.from_user.id
    cost = config.ENHANCED_ANALYSIS_COST
    balance = await tm.get_balance(user_id)
    if balance < cost:
        await message.answer(
            (
                "❌ Недостаточно токенов для расширенного анализа.\n\n"
                f"Требуется: <b>{cost}</b> ток., на счёте: <b>{balance}</b> ток.\n"
                "Пополнить баланс: /buy_tokens"
            ),
            parse_mode="HTML",
        )
        await state.clear()
        return
    debited = await tm.deduct_tokens(
        user_id=user_id,
        amount=cost,
        transaction_type="enhanced_analysis",
        description=f"Списание за расширенный анализ {symbol}",
    )
    if not debited:
        latest = await tm.get_balance(user_id)
        await message.answer(
            (
                "❌ Не удалось списать токены.\n\n"
                f"Требуется: <b>{cost}</b> ток., на счёте: <b>{latest}</b> ток."
            ),
            parse_mode="HTML",
        )
        await state.clear()
        return
    # Информационное сообщение на время выполнения
    processing_msg = await message.answer("🔄 Выполняю расширенный анализ... Это может занять до 30–60 секунд.")

    # Кэш краткого текста на 1 час (не отправляем пользователю)
    cached = await db.get_cached_analysis(symbol, analysis_type="brief_text")
    # Требование: одно сообщение с PDF → кэшированный текст не отправляем

    try:
        analysis_dict, news_articles, market_df = await _run_enhanced(symbol, db)
    except Exception as e:
        # Возврат токенов при ошибке анализа
        try:
            await tm.add_tokens(
                user_id=user_id,
                amount=cost,
                transaction_type="refund",
                description=f"Возврат за ошибку расширенного анализа {symbol}",
            )
        except Exception:
            pass
        await message.answer("❌ Ошибка при выполнении расширенного анализа. Попробуйте позже.")
        await state.clear()
        return

    # Формируем и отправляем Telegram-отчёт (HTML) частями
    builder = TelegramReportBuilder()
    try:
        parts = await builder.build_enhanced_report(
            analysis=analysis_dict,
            news_articles=news_articles,
            market_data=market_df,
        )
    except Exception:
        parts = ["❌ Не удалось сформировать отчёт. Попробуйте позже."]

    # Удаляем информационное сообщение, если возможно
    try:
        await processing_msg.delete()
    except Exception:
        pass

    for idx, chunk in enumerate(parts, 1):
        await message.answer(chunk, parse_mode="HTML")

    await state.clear()


