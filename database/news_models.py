from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NewsArticle:
    id: str
    title: str
    description: Optional[str]
    content: Optional[str]
    url: Optional[str]
    published_at: datetime
    source: Optional[str]
    symbol: str
    sentiment_score: Optional[float] = None
    relevance_score: Optional[float] = None


