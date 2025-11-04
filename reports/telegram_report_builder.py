from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import html


@dataclass
class _Section:
    title: str
    body: str


class TelegramReportBuilder:
    """Формирование расширенного отчёта в виде сообщений Telegram (HTML).

    - Делит выход на части <= 4096 символов
    - Экранирует HTML
    - Использует только реальные данные; при отсутствии — пишет пометки
    """

    MAX_MESSAGE_LENGTH = 4096

    def __init__(self) -> None:
        pass

    async def build_enhanced_report(
        self,
        analysis: Dict[str, Any],
        news_articles: List[Dict[str, Any]],
        market_data: Any,
    ) -> List[str]:
        symbol = (analysis or {}).get("symbol", "N/A")
        timestamp = (analysis or {}).get("timestamp", "N/A")

        sections: List[_Section] = []
        sections.append(_Section(
            title=self._format_header(symbol, timestamp),
            body="",
        ))

        sections.append(_Section(
            title="📊 Обзор рынка",
            body=self._format_market_overview(analysis, market_data),
        ))

        sections.append(_Section(
            title="📰 Анализ новостей",
            body=self._format_news_analysis(news_articles, (analysis or {}).get("sentiment", {})),
        ))

        sections.append(_Section(
            title="📈 Технический анализ",
            body=self._format_technical_analysis((analysis or {}).get("technical", {})),
        ))

        sections.append(_Section(
            title="🤖 Рекомендации",
            body=self._format_recommendations(analysis),
        ))

        # Сборка HTML и разбиение на сообщения
        full_html = []
        for s in sections:
            if s.title:
                full_html.append(f"<b>{s.title}</b>")
                full_html.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            if s.body:
                full_html.append(s.body)
            full_html.append("")

        text = "\n".join(full_html).strip()
        parts = self._split_message(text)
        return parts

    def _format_header(self, symbol: str, timestamp: str) -> str:
        s = html.escape(str(symbol or "N/A").upper())
        t = html.escape(str(timestamp or "N/A"))
        return f"🚀 РАСШИРЕННЫЙ АНАЛИЗ {s}\nДата: {t}"

    def _format_market_overview(self, analysis: Dict[str, Any], market_data: Any) -> str:
        lines: List[str] = []
        # Цена
        price_line = "Недоступно (нет данных CoinGecko/TwelveData)"
        try:
            if market_data is not None and hasattr(market_data, "empty") and not market_data.empty:
                if "close" in market_data.columns:
                    price_line = f"${market_data['close'].iloc[-1]:,.2f}"
        except Exception:
            pass

        lines.append(f"• Цена: {html.escape(price_line)}")

        # MA7/MA30
        ma = (analysis or {}).get("technical", {}).get("moving_averages", {})
        ma7 = ma.get("MA7")
        ma30 = ma.get("MA30")
        if isinstance(ma7, (int, float)) and isinstance(ma30, (int, float)):
            lines.append(f"• MA7: {ma7:.2f}")
            lines.append(f"• MA30: {ma30:.2f}")
        else:
            lines.append("• Скользящие средние: данные недоступны")

        return "\n".join(lines)

    def _format_news_analysis(self, news_articles: List[Dict[str, Any]], sentiment: Dict[str, Any]) -> str:
        lines: List[str] = []
        count = len(news_articles or [])
        lines.append(f"Найдено новостей: {count}")

        overall = (sentiment or {}).get("overall", {})
        label = overall.get("label", "N/A")
        score = overall.get("score", 0)
        lines.append(f"Общая тональность: {html.escape(str(label))} ({score:.2f})")

        # Топ-новости (расширенно для крупных списков)
        if news_articles:
            lines.append("")
            lines.append("💡 Важные новости:")
            # Выводим до 20 новостей, чтобы длинные входные данные корректно провоцировали разбиение сообщений
            for i, a in enumerate(news_articles[:20], 1):
                title = html.escape(a.get("title") or "Без заголовка")
                s = a.get("sentiment_score")
                if isinstance(s, (int, float)):
                    lines.append(f"{i}. {title}\n   Тональность: {s:+.2f}")
                else:
                    lines.append(f"{i}. {title}")
        else:
            lines.append("Нет статей за последние 7 дней или API недоступен")

        return "\n".join(lines)

    def _format_technical_analysis(self, technical: Dict[str, Any]) -> str:
        trend = (technical or {}).get("trend") or "unknown"
        ma = (technical or {}).get("moving_averages", {})
        ma7 = ma.get("MA7")
        ma30 = ma.get("MA30")
        lines = [f"• Тренд: {html.escape(str(trend))}"]
        if isinstance(ma7, (int, float)) and isinstance(ma30, (int, float)):
            lines.append(f"• MA7: {ma7:.2f}")
            lines.append(f"• MA30: {ma30:.2f}")
        return "\n".join(lines)

    def _format_recommendations(self, analysis: Dict[str, Any]) -> str:
        rec = (analysis or {}).get("recommendation", "N/A")
        score = (analysis or {}).get("overall_score", 0)
        risk = (analysis or {}).get("risk_level", "N/A")
        lines = [
            f"📊 Оценка: {max(0.0, min(1.0, float(score))):.2f}/1.00",
            f"🎯 Рекомендация: {html.escape(str(rec).upper())}",
            f"⚠️ Риск: {html.escape(str(risk))}",
            "",
            "Дисклеймер: только данные из NewsAPI и рыночные котировки. Не финсовет.",
        ]
        return "\n".join(lines)

    def _split_message(self, text: str) -> List[str]:
        if len(text) <= self.MAX_MESSAGE_LENGTH:
            return [text]
        parts: List[str] = []
        current = []
        current_len = 0
        for line in text.split("\n"):
            add_len = len(line) + 1
            if current_len + add_len > self.MAX_MESSAGE_LENGTH:
                parts.append("\n".join(current))
                current = [line]
                current_len = len(line) + 1
            else:
                current.append(line)
                current_len += add_len
        if current:
            parts.append("\n".join(current))
        return parts


