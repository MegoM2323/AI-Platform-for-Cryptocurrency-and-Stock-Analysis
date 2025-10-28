from dataclasses import dataclass
from typing import List, Optional
import math


@dataclass
class SentimentScore:
    score: float  # -1..1
    label: str    # negative/neutral/positive


class SentimentAnalyzer:
    """Простой rule-based анализатор тональности для новостей.

    Может быть заменён на AI-модель позже. Реализует:
    - оценку тональности одной статьи
    - агрегирование по списку статей
    - извлечение ключевых тем (наивно по ключевым словам)
    """

    NEGATIVE_WORDS = {
        "hack", "scam", "fraud", "lawsuit", "ban", "fall", "drop", "bearish",
        "fud", "exploit", "loss", "down", "risk", "fine", "penalty"
    }
    POSITIVE_WORDS = {
        "surge", "rise", "growth", "bullish", "adoption", "partnership", "profit",
        "up", "gain", "win", "approve", "etf", "funding"
    }

    def analyze_article_sentiment(self, title: str, description: Optional[str], content: Optional[str]) -> SentimentScore:
        text = " ".join([t for t in [title or "", description or "", content or ""] if t])
        text_lower = text.lower()
        pos = sum(1 for w in self.POSITIVE_WORDS if w in text_lower)
        neg = sum(1 for w in self.NEGATIVE_WORDS if w in text_lower)
        # Нормируем: (pos - neg) / (pos + neg + 1)
        score = (pos - neg) / float(pos + neg + 1)
        label = "positive" if score > 0.2 else ("negative" if score < -0.2 else "neutral")
        return SentimentScore(score=score, label=label)

    def calculate_overall_sentiment(self, items: List[SentimentScore]) -> SentimentScore:
        if not items:
            return SentimentScore(score=0.0, label="neutral")
        avg = sum(x.score for x in items) / len(items)
        label = "positive" if avg > 0.2 else ("negative" if avg < -0.2 else "neutral")
        return SentimentScore(score=avg, label=label)

    def extract_key_themes(self, titles: List[str]) -> List[str]:
        # Наивный метод: выбираем часто встречающиеся ключевые слова из белого списка тем
        themes = [
            ("etf", 0), ("regulation", 0), ("adoption", 0), ("hack", 0), ("partnership", 0),
            ("upgrade", 0), ("halving", 0), ("funding", 0), ("lawsuit", 0)
        ]
        counts = {k: 0 for k, _ in themes}
        for t in titles:
            tl = (t or "").lower()
            for k in counts.keys():
                if k in tl:
                    counts[k] += 1
        # Вернём топ-5 тем с ненулевым счётом
        ranked = [k for k, c in sorted(counts.items(), key=lambda x: x[1], reverse=True) if c > 0]
        return ranked[:5]


