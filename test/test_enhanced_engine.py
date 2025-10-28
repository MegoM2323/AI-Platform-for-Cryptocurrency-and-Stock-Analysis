import asyncio
import pandas as pd

from analysis.enhanced_engine import EnhancedAnalysisEngine
from analysis.sentiment_analyzer import SentimentAnalyzer
from AI_block.analyzer import AIAnalyzer
from data_collectors.crypto_collector import CryptoCollector


class DummyDB:
    async def get_recent_news(self, symbol: str, hours: int = 168, limit: int = 50):
        return [{"title": "ETF approved", "description": None, "content": None}]


class DummyAI(AIAnalyzer):
    def __init__(self):
        pass
    async def analyze_with_custom_prompt(self, market_data: str, custom_prompt: str):
        return "Summary text"


class DummyCC(CryptoCollector):
    def __init__(self):
        pass
    async def get_daily_ohlcv(self, symbol: str, days: int = 60):
        return pd.DataFrame({"close": [1, 2, 3, 4, 5]})


def test_enhanced_engine_runs():
    engine = EnhancedAnalysisEngine(
        ai_analyzer=DummyAI(),
        db=DummyDB(),
        crypto_collector=DummyCC(),
        sentiment_analyzer=SentimentAnalyzer(),
    )
    result = asyncio.get_event_loop().run_until_complete(engine.analyze_crypto_comprehensive("BTC"))
    assert result["symbol"] == "BTC"
    assert "overall_score" in result


