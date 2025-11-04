from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from reports.telegram_report_builder import TelegramReportBuilder


class _Col:
    def __init__(self, data: List[float]) -> None:
        self._data = list(data)

    class _ILoc:
        def __init__(self, data: List[float]) -> None:
            self._data = data

        def __getitem__(self, idx: int) -> float:
            return self._data[idx]

    @property
    def iloc(self) -> "_Col._ILoc":
        return _Col._ILoc(self._data)


class _MarketStub:
    def __init__(self, closes: List[float]) -> None:
        self._close = _Col(closes)
        self.columns = {"close"}
        self.empty = False if closes else True

    def __getitem__(self, name: str) -> _Col:
        if name == "close":
            return self._close
        raise KeyError(name)


@pytest.mark.asyncio
async def test_build_enhanced_report_basic_structure() -> None:
    builder = TelegramReportBuilder()
    analysis: Dict[str, Any] = {
        "symbol": "BTC",
        "timestamp": "2025-11-03T12:00:00Z",
        "technical": {"trend": "bullish", "moving_averages": {"MA7": 44123.45, "MA30": 42567.89}},
        "sentiment": {"overall": {"label": "positive", "score": 0.65}},
        "recommendation": "hold",
        "overall_score": 0.75,
        "risk_level": "medium",
    }
    news: List[Dict[str, Any]] = [
        {"title": "News A", "sentiment_score": 0.8},
        {"title": "News B", "sentiment_score": 0.6},
    ]
    market = _MarketStub([45234.56, 45321.12])

    parts = await builder.build_enhanced_report(analysis=analysis, news_articles=news, market_data=market)

    assert isinstance(parts, list)
    assert len(parts) >= 1
    joined = "\n".join(parts)
    # Заголовок, разделители и ключевые секции присутствуют
    assert "РАСШИРЕННЫЙ АНАЛИЗ BTC" in joined
    assert "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" in joined
    assert "📊 Обзор рынка" in joined
    assert "📰 Анализ новостей" in joined
    assert "📈 Технический анализ" in joined
    assert "🤖 Рекомендации" in joined


@pytest.mark.asyncio
async def test_html_escaping_in_header_and_sections() -> None:
    builder = TelegramReportBuilder()
    analysis: Dict[str, Any] = {
        "symbol": "<BTC>",
        "timestamp": "2025-11-03T12:00:00Z",
        "technical": {"trend": "<up>", "moving_averages": {}},
        "sentiment": {"overall": {"label": "pos<itive>", "score": 0.5}},
    }
    news: List[Dict[str, Any]] = [{"title": "<b>Danger</b>", "sentiment_score": -0.1}]
    market = _MarketStub([1.0])

    parts = await builder.build_enhanced_report(analysis=analysis, news_articles=news, market_data=market)
    text = "\n".join(parts)

    assert "<BTC>" not in text
    assert "&lt;BTC&gt;" in text
    assert "<b>Danger</b>" not in text
    assert "&lt;b&gt;Danger&lt;/b&gt;" in text


@pytest.mark.asyncio
async def test_split_long_message_respects_limit() -> None:
    builder = TelegramReportBuilder()
    # Сгенерируем очень длинные названия новостей, чтобы гарантировать разбиение
    long_title = "A" * 500
    news = [{"title": f"{long_title} #{i}"} for i in range(50)]
    analysis: Dict[str, Any] = {"symbol": "ETH", "timestamp": "2025-11-03T12:00:00Z"}
    market = _MarketStub([1000.0])

    parts = await builder.build_enhanced_report(analysis=analysis, news_articles=news, market_data=market)

    assert len(parts) >= 2
    for p in parts:
        assert len(p) <= builder.MAX_MESSAGE_LENGTH


