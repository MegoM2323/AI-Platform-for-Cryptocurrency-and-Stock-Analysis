from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import matplotlib.pyplot as plt

from config import config as AppConfig


@dataclass
class Chart:
    title: str
    image_bytes: bytes


class ReportGenerator:
    def __init__(self, template_path: str = None):
        self.template_path = template_path or str(AppConfig.PDF_TEMPLATE_PATH)
        os.makedirs(AppConfig.CHART_CACHE_DIR, exist_ok=True)

    def generate_text_summary(self, analysis: Dict[str, Any]) -> str:
        parts: List[str] = []
        parts.append(f"Символ: {analysis['symbol']}")
        parts.append(f"Таймфрейм: {analysis['timeframe']}")
        parts.append(f"Итоговый скор: {analysis['overall_score']:.2f}, риск: {analysis['risk_level']}, рекомендация: {analysis['recommendation']}")
        parts.append(f"Ключевые пункты: {', '.join(analysis.get('key_points', []))}")
        parts.append("\n" + analysis.get('disclaimer', ''))
        return "\n".join(parts)

    def create_charts(self, market_data, news_articles: Optional[List[Dict[str, Any]]] = None) -> List[Chart]:
        charts: List[Chart] = []
        try:
            fig, ax = plt.subplots(figsize=(6, 3))
            market_data['close'].tail(60).plot(ax=ax, title='Close Price (60d)')
            ax.set_xlabel('Date')
            ax.set_ylabel('Price')
            buf = io.BytesIO()
            plt.tight_layout()
            fig.savefig(buf, format='png')
            plt.close(fig)
            charts.append(Chart(title='Цена (60 дней)', image_bytes=buf.getvalue()))
        except Exception:
            pass

        # Волатильность (STD 14 на 90 дней)
        try:
            if 'close' in market_data.columns:
                rolling_std = market_data['close'].tail(90).rolling(window=14).std()
                fig, ax = plt.subplots(figsize=(6, 3))
                rolling_std.plot(ax=ax, title='Volatility (STD 14, 90d)')
                ax.set_xlabel('Date')
                ax.set_ylabel('STD')
                buf = io.BytesIO()
                plt.tight_layout()
                fig.savefig(buf, format='png')
                plt.close(fig)
                charts.append(Chart(title='Волатильность (90 дней)', image_bytes=buf.getvalue()))
        except Exception:
            pass

        # Объем
        try:
            if 'volume' in market_data.columns:
                fig, ax = plt.subplots(figsize=(6, 3))
                market_data['volume'].tail(60).plot(ax=ax, title='Volume (60d)')
                ax.set_xlabel('Date')
                ax.set_ylabel('Volume')
                buf = io.BytesIO()
                plt.tight_layout()
                fig.savefig(buf, format='png')
                plt.close(fig)
                charts.append(Chart(title='Объем (60 дней)', image_bytes=buf.getvalue()))
        except Exception:
            pass

        # Тональность новостей (7-дневное скользящее среднее по дням)
        try:
            if news_articles:
                import pandas as pd
                rows = []
                for a in news_articles:
                    ts = a.get('published_at') or a.get('publishedAt')
                    score = a.get('sentiment_score')
                    if isinstance(ts, str):
                        try:
                            ts = pd.to_datetime(ts)
                        except Exception:
                            ts = None
                    if ts is not None and score is not None:
                        rows.append({"ts": ts, "score": float(score)})
                if rows:
                    df = pd.DataFrame(rows)
                    df['date'] = df['ts'].dt.date
                    grouped = df.groupby('date')['score'].mean().rolling(7).mean()
                    fig, ax = plt.subplots(figsize=(6, 3))
                    grouped.plot(ax=ax, title='Sentiment (7d MA)')
                    ax.set_xlabel('Date')
                    ax.set_ylabel('Score')
                    buf = io.BytesIO()
                    plt.tight_layout()
                    fig.savefig(buf, format='png')
                    plt.close(fig)
                    charts.append(Chart(title='Тональность новостей (7d MA)', image_bytes=buf.getvalue()))
        except Exception:
            pass
        return charts

    def add_timeframe_disclaimer(self, text: str) -> str:
        disclaimer = "Анализ основан на дневных данных (1d). Используйте с осторожностью для краткосрочной торговли."
        return f"{text}\n\n{disclaimer}"

    def generate_pdf_report(self, analysis: Dict[str, Any], charts: List[Chart] = None) -> bytes:
        charts = charts or []
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        elements: List[Any] = []
        elements.append(Paragraph("Executive Summary", styles['Heading2']))
        elements.append(Paragraph(self.generate_text_summary(analysis).replace('\n', '<br/>'), styles['BodyText']))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Technical Analysis", styles['Heading2']))
        ma = analysis.get('technical', {}).get('moving_averages', {})
        tech_data = [["MA", "Value"], ["MA7", f"{ma.get('MA7', 0):.2f}"], ["MA30", f"{ma.get('MA30', 0):.2f}"]]
        table = Table(tech_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("News Sentiment", styles['Heading2']))
        sentiment = analysis.get('sentiment', {})
        elements.append(Paragraph(f"Overall: {sentiment.get('overall', {}).get('label', 'n/a')} ({sentiment.get('overall', {}).get('score', 0):.2f})", styles['BodyText']))
        elements.append(Paragraph(f"Themes: {', '.join(sentiment.get('themes', []))}", styles['BodyText']))
        elements.append(Spacer(1, 12))

        if charts:
            for ch in charts:
                try:
                    from reportlab.platypus import Image
                    img_buf = io.BytesIO(ch.image_bytes)
                    elements.append(Paragraph(ch.title, styles['Heading3']))
                    elements.append(Image(img_buf, width=480, height=240))
                    elements.append(Spacer(1, 12))
                except Exception:
                    continue

        elements.append(Paragraph("Disclaimer", styles['Heading2']))
        elements.append(Paragraph("Анализ основан на дневных данных (1d). Не является инвестиционной рекомендацией.", styles['BodyText']))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes


