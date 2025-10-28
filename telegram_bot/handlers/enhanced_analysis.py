"""
Расширенный анализ с учетом новостей, выбор краткого/детального формата и PDF.
"""

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import config
from database.db import Database
from data_collectors import NewsCollector, RateLimiter, NewsPipeline, CryptoCollector, DataFormatter
from analysis.sentiment_analyzer import SentimentAnalyzer
from analysis.enhanced_engine import EnhancedAnalysisEngine
from AI_block.analyzer import AIAnalyzer
from reports.generator import ReportGenerator


router = Router()
_rate_limiter = RateLimiter()


@router.message(Command("enhanced"))
async def enhanced_entry(message: Message, state: FSMContext, db: Database):
    await message.answer(
        "📊 Расширенный анализ: отправь символ (например: BTC).\n"
        "Затем выбери формат: краткий текст или подробный PDF.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.update_data(enhanced_mode=True)
    # Переиспользуем состояние из стандартного обработчика, чтобы не дублировать FSM
    from ..states import AnalysisStates
    await state.set_state(AnalysisStates.waiting_for_symbol)


@router.message(Command("refresh_news"))
async def refresh_news(message: Message, db: Database):
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /refresh_news SYMBOL")
        return
    symbol = parts[1].upper()
    try:
        pipeline = NewsPipeline(db=db, collector=NewsCollector(rate_limiter=_rate_limiter), analyzer=SentimentAnalyzer())
        count = await pipeline.fetch_analyze_store(symbol=symbol, days=7)
        await message.answer(f"Обновлено статей: {count}")
    except Exception as e:
        await message.answer("Не удалось обновить новости (возможно, квота исчерпана)")


async def _run_enhanced(symbol: str, db: Database) -> tuple[dict, bytes, object]:
    crypto_collector = CryptoCollector(timeframe=config.DEFAULT_TIMEFRAME, period=config.DEFAULT_PERIOD)
    market_df = crypto_collector.get_crypto_data(symbol)

    news_collector = NewsCollector(rate_limiter=_rate_limiter)
    pipeline = NewsPipeline(db=db, collector=news_collector, analyzer=SentimentAnalyzer())
    try:
        await pipeline.fetch_analyze_store(symbol=symbol, days=7)
    except Exception:
        # Новости не критичны для работы — продолжаем
        pass

    engine = EnhancedAnalysisEngine(
        ai_analyzer=AIAnalyzer(api_key=config.OPENROUTER_API_KEY, model=config.AI_MODEL),
        db=db,
        crypto_collector=crypto_collector,
        sentiment_analyzer=SentimentAnalyzer(),
    )
    analysis_dict = await engine.analyze_crypto_comprehensive(symbol)

    rg = ReportGenerator()
    # Для графика тональности пробуем подтянуть последние новости из БД
    try:
        news_articles = await db.get_recent_news(symbol=symbol, hours=24*7, limit=200)
    except Exception:
        news_articles = []
    charts = rg.create_charts(market_df, news_articles=news_articles)
    pdf_bytes = rg.generate_pdf_report(analysis_dict, charts)
    return analysis_dict, pdf_bytes, charts


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
    await message.answer("🔄 Запускаю расширенный анализ... Это может занять до 30 секунд.")

    # Кэш краткого текста на 1 час
    cached = await db.get_cached_analysis(symbol, analysis_type="brief_text")
    if cached:
        await message.answer(cached)
        await state.clear()
        return

    try:
        analysis_dict, pdf_bytes, _charts = await _run_enhanced(symbol, db)
    except Exception as e:
        await message.answer("❌ Ошибка при выполнении расширенного анализа. Попробуйте позже.")
        await state.clear()
        return

    rg = ReportGenerator()
    text_summary = rg.add_timeframe_disclaimer(rg.generate_text_summary(analysis_dict))
    await message.answer(text_summary)
    try:
        # Кэшируем краткий текст на 1 час
        await db.set_cached_analysis(symbol, analysis_type="brief_text", result_data=text_summary, ttl_seconds=3600)
    except Exception:
        pass

    # Отправляем PDF
    pdf_file = BufferedInputFile(pdf_bytes, filename=f"analysis_{symbol}.pdf")
    await message.answer_document(pdf_file, caption=f"Подробный отчет по {symbol}")

    await state.clear()


