from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

import pandas as pd

from AI_block.analyzer import AIAnalyzer
from analysis.sentiment_analyzer import SentimentAnalyzer, SentimentScore
from data_collectors.crypto_collector import CryptoCollector
from database.db import Database


@dataclass
class TechnicalAnalysis:
    moving_averages: Dict[str, float]
    trend: str


@dataclass
class SentimentAnalysis:
    overall: SentimentScore
    articles: List[Dict[str, Any]]
    key_themes: List[str]


@dataclass
class MultiLevelAnalysis:
    symbol: str
    timestamp: datetime
    timeframe: str
    technical: TechnicalAnalysis
    sentiment: SentimentAnalysis
    overall_score: float
    risk_level: str
    recommendation: str
    key_points: List[str]
    data_sources: List[str]
    confidence_level: float


class EnhancedAnalysisEngine:
    def __init__(self, ai_analyzer: AIAnalyzer, db: Database, crypto_collector: CryptoCollector, sentiment_analyzer: SentimentAnalyzer) -> None:
        self._ai = ai_analyzer
        self._db = db
        self._cc = crypto_collector
        self._sa = sentiment_analyzer

    async def analyze_technical(self, market_data: pd.DataFrame) -> TechnicalAnalysis:
        closes = market_data['close'] if 'close' in market_data.columns else market_data.iloc[:, -1]
        ma_short = float(closes.tail(7).mean()) if len(closes) >= 7 else float(closes.mean())
        ma_long = float(closes.tail(30).mean()) if len(closes) >= 30 else float(closes.mean())
        trend = 'bullish' if ma_short > ma_long else ('bearish' if ma_short < ma_long else 'neutral')
        return TechnicalAnalysis(
            moving_averages={"MA7": ma_short, "MA30": ma_long},
            trend=trend,
        )

    async def analyze_sentiment(self, symbol: str) -> SentimentAnalysis:
        articles = await self._db.get_recent_news(symbol=symbol, hours=24*7, limit=50)
        scores: List[SentimentScore] = []
        titles: List[str] = []
        for a in articles:
            titles.append(a.get('title') or '')
            score = self._sa.analyze_article_sentiment(a.get('title') or '', a.get('description'), a.get('content'))
            a['sentiment_score'] = score.score
            scores.append(score)
        overall = self._sa.calculate_overall_sentiment(scores)
        themes = self._sa.extract_key_themes(titles)
        return SentimentAnalysis(overall=overall, articles=articles, key_themes=themes)

    async def generate_multi_level_analysis(self, symbol: str) -> MultiLevelAnalysis:
        # Получаем рыночные данные (дневной таймфрейм по умолчанию)
        df: pd.DataFrame = self._cc.get_crypto_data(symbol)
        
        # Проверяем, что данные получены
        if df is None or df.empty:
            # Создаем пустые данные для технического анализа
            df = pd.DataFrame({'close': [0]})
        
        technical = await self.analyze_technical(df)
        sentiment = await self.analyze_sentiment(symbol)

        # Готовим промпт для AI с учетом новостей
        market_summary = df.tail(10).to_string(index=False)
        news_summary_lines = []
        for a in sentiment.articles[:5]:
            news_summary_lines.append(f"- {a.get('title')} (score={a.get('sentiment_score'):.2f})")
        news_summary = "\n".join(news_summary_lines) or "- (недостаточно новостей)"

        user_prompt = (
            f"Символ: {symbol}\n"
            f"Таймфрейм: 1day\n"
            f"Техническое резюме (последние 10 свечей):\n{market_summary}\n\n"
            f"Скользящие средние: MA7={technical.moving_averages['MA7']:.2f}, MA30={technical.moving_averages['MA30']:.2f}, тренд={technical.trend}\n\n"
            f"Новостной фон (последние 7 дней, топ-5):\n{news_summary}\n"
            f"Ключевые темы: {', '.join(sentiment.key_themes) if sentiment.key_themes else 'нет'}\n"
            f"Общая тональность новостей: {sentiment.overall.label} ({sentiment.overall.score:.2f})\n\n"
            f"Сформируй объединённый анализ: техническая картина, влияние новостей, риски, и четкие рекомендации."
            f" Обязательно отметь, что анализ основан на дневных данных."
        )

        # Выполняем AI-анализ с защитой от ошибок (например, 429 Too Many Requests)
        import logging
        try:
            ai_text = await self._ai.analyze_with_custom_prompt(market_data="", custom_prompt=user_prompt)
        except Exception as ai_error:
            logging.getLogger(__name__).warning(f"AI анализ недоступен, продолжаем без него: {ai_error}")
            ai_text = ""

        # Оценим общий балл и риски на основе тренда и тональности (простая эвристика)
        base = 0.0
        base += 0.3 if technical.trend == 'bullish' else (-0.3 if technical.trend == 'bearish' else 0.0)
        base += max(-0.3, min(0.3, sentiment.overall.score))
        overall_score = max(-1.0, min(1.0, base))
        risk_level = 'low' if abs(overall_score) > 0.5 else ('medium' if abs(overall_score) > 0.2 else 'high')

        recommendation = 'buy' if overall_score > 0.3 else ('sell' if overall_score < -0.3 else 'hold')
        key_points = [
            f"trend={technical.trend}",
            f"news={sentiment.overall.label}",
            f"themes={', '.join(sentiment.key_themes[:3]) if sentiment.key_themes else 'n/a'}",
        ]

        return MultiLevelAnalysis(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc),
            timeframe='1day',
            technical=technical,
            sentiment=sentiment,
            overall_score=overall_score,
            risk_level=risk_level,
            recommendation=recommendation,
            key_points=key_points,
            data_sources=['TwelveData', 'NewsAPI'],
            confidence_level=0.6,
        )

    async def analyze_crypto_comprehensive(self, symbol: str) -> Dict[str, Any]:
        mla = await self.generate_multi_level_analysis(symbol)
        return {
            "symbol": mla.symbol,
            "timeframe": mla.timeframe,
            "timestamp": mla.timestamp.isoformat(),
            "technical": {
                "moving_averages": mla.technical.moving_averages,
                "trend": mla.technical.trend,
            },
            "sentiment": {
                "overall": {"score": mla.sentiment.overall.score, "label": mla.sentiment.overall.label},
                "key_themes": mla.sentiment.key_themes,
                "articles": mla.sentiment.articles,
            },
            "overall_score": mla.overall_score,
            "risk_level": mla.risk_level,
            "recommendation": mla.recommendation,
            "key_points": mla.key_points,
            "disclaimer": "Анализ основан на дневных данных, не является инвестиционной рекомендацией.",
        }


