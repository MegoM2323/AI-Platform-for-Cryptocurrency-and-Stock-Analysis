from typing import List, Dict, Any
from datetime import datetime

from .news_collector import NewsCollector
from analysis.sentiment_analyzer import SentimentAnalyzer
from database.db import Database
from database.news_models import NewsArticle


class NewsPipeline:
    """Конвейер: получить новости -> оценить тональность -> сохранить в БД."""

    def __init__(self, db: Database, collector: NewsCollector, analyzer: SentimentAnalyzer) -> None:
        self._db = db
        self._collector = collector
        self._analyzer = analyzer

    async def fetch_analyze_store(self, symbol: str, days: int = 7, language: str = "en") -> int:
        # Получаем статьи через NewsCollector (используем search_everything для точности)
        query = f"({symbol} OR {symbol.upper()} OR crypto)"
        try:
            data = self._collector.search_everything(query=query, language=language, sort_by="publishedAt", page_size=50, symbol=symbol)
            articles_raw: List[Dict[str, Any]] = data.get("articles", []) if isinstance(data, dict) else []
        except Exception:
            # Фолбэк: используем последние новости из БД без нового запроса к API
            recent = await self._db.get_recent_news(symbol=symbol, hours=24)
            return len(recent)

        articles: List[NewsArticle] = []
        for item in articles_raw:
            title = item.get("title")
            description = item.get("description")
            content = item.get("content")
            url = item.get("url")
            source_name = (item.get("source") or {}).get("name")
            published_at_str = item.get("publishedAt")
            published_at = None
            try:
                if published_at_str:
                    published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
            except Exception:
                published_at = None

            sentiment = self._analyzer.analyze_article_sentiment(title or "", description, content)

            # relevance: по ключам, свежести, источнику
            text_lower = (title or "").lower() + " " + (description or "").lower()
            hits = 0
            synonyms = {symbol.lower(), symbol.upper(), symbol.capitalize()}
            if symbol.upper() == "BTC":
                synonyms.update({"bitcoin"})
            for s in synonyms:
                if s and s in text_lower:
                    hits += 1
            freshness_boost = 1.0
            if published_at:
                age_hours = max(1.0, (datetime.utcnow() - published_at.replace(tzinfo=None)).total_seconds() / 3600.0)
                freshness_boost = max(0.5, min(1.5, 24.0 / age_hours))
            source_boost = 1.2 if (source_name or "").lower() in {"coindesk", "cointelegraph", "reuters", "bloomberg"} else 1.0
            relevance_score = min(1.0, (0.4 * hits + 0.4 * max(0.0, sentiment.score)) * freshness_boost * source_boost)

            # Формируем id как url или published_at+title, если url отсутствует
            article_id = url or f"{symbol}:{published_at_str}:{title}"[:255]

            articles.append(NewsArticle(
                id=article_id,
                title=title or "",
                description=description,
                content=content,
                url=url,
                published_at=published_at or datetime.utcnow(),
                source=source_name,
                symbol=symbol,
                sentiment_score=sentiment.score,
                relevance_score=relevance_score,
            ))

        # Фильтрация по релевантности
        articles = [a for a in articles if (a.relevance_score or 0.0) >= 0.2]

        return await self._db.save_news_articles(articles)


