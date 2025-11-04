from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import timezone
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
        parts.append(f"Таймфрейм: {analysis.get('timeframe', '1day')}")
        parts.append(f"Итоговый скор: {analysis['overall_score']:.2f}, риск: {analysis['risk_level']}, рекомендация: {analysis['recommendation']}")
        parts.append(f"Ключевые пункты: {', '.join(analysis.get('key_points', []))}")
        parts.append("\n" + analysis.get('disclaimer', ''))
        return "\n".join(parts)

    def generate_detailed_text_report(self, analysis: Dict[str, Any]) -> str:
        """Генерирует подробный текстовый отчет для расширенного анализа"""
        parts: List[str] = []
        
        # Заголовок
        parts.append(f"🚀 <b>РАСШИРЕННЫЙ АНАЛИЗ {analysis['symbol']}</b>")
        parts.append("=" * 50)
        
        # Основная информация
        parts.append(f"\n📊 <b>ОСНОВНЫЕ ПОКАЗАТЕЛИ</b>")
        parts.append(f"• Символ: {analysis['symbol']}")
        parts.append(f"• Таймфрейм: {analysis.get('timeframe', '1day')} (дневные данные)")
        parts.append(f"• Время анализа: {analysis.get('timestamp', 'N/A')}")
        
        # Технический анализ
        if 'technical' in analysis:
            tech = analysis['technical']
            parts.append(f"\n📈 <b>ТЕХНИЧЕСКИЙ АНАЛИЗ</b>")
            parts.append(f"• Тренд: {tech.get('trend', 'N/A')}")
            if 'moving_averages' in tech:
                ma = tech['moving_averages']
                parts.append(f"• MA7: {ma.get('MA7', 0):.2f}")
                parts.append(f"• MA30: {ma.get('MA30', 0):.2f}")
        
        # Анализ настроений
        if 'sentiment' in analysis:
            sent = analysis['sentiment']
            parts.append(f"\n📰 <b>АНАЛИЗ НАСТРОЕНИЙ</b>")
            if 'overall' in sent:
                overall = sent['overall']
                parts.append(f"• Общая тональность: {overall.get('label', 'N/A')} ({overall.get('score', 0):.2f})")
            if 'key_themes' in sent:
                themes = sent['key_themes']
                if themes:
                    parts.append(f"• Ключевые темы: {', '.join(themes[:5])}")
        
        # Рекомендации
        parts.append(f"\n💡 <b>РЕКОМЕНДАЦИИ</b>")
        parts.append(f"• Общий скор: {analysis.get('overall_score', 0):.2f}/1.0")
        parts.append(f"• Уровень риска: {analysis.get('risk_level', 'N/A')}")
        parts.append(f"• Рекомендация: {analysis.get('recommendation', 'N/A').upper()}")
        
        # Ключевые пункты
        if 'key_points' in analysis and analysis['key_points']:
            parts.append(f"\n🔑 <b>КЛЮЧЕВЫЕ МОМЕНТЫ</b>")
            for i, point in enumerate(analysis['key_points'][:5], 1):
                parts.append(f"{i}. {point}")
        
        # Источники данных
        if 'data_sources' in analysis:
            parts.append(f"\n📋 <b>ИСТОЧНИКИ ДАННЫХ</b>")
            parts.append(f"• {', '.join(analysis['data_sources'])}")
        
        # Уровень уверенности
        if 'confidence_level' in analysis:
            parts.append(f"\n🎯 <b>УРОВЕНЬ УВЕРЕННОСТИ</b>")
            parts.append(f"• {analysis['confidence_level']:.1%}")
        
        # Дисклеймер
        parts.append(f"\n⚠️ <b>ВАЖНО</b>")
        parts.append("• Анализ основан на дневных данных и актуальных новостях")
        parts.append("• Не является финансовой рекомендацией")
        parts.append("• Проводите собственное исследование перед инвестированием")
        
        return "\n".join(parts)

    def generate_readable_report_from_template(self, analysis: Dict[str, Any], market_data=None) -> str:
        """
        Генерирует полностью читаемый отчет из шаблона markdown
        
        Args:
            analysis: Словарь с данными анализа
            market_data: DataFrame с рыночными данными (опционально)
            
        Returns:
            Заполненный отчет в виде текста (markdown)
        """
        from datetime import datetime
        import pandas as pd
        
        # Читаем шаблон
        template_path = Path(self.template_path) / "Расширенный отчет структура.md"
        if not template_path.exists():
            # Пробуем альтернативный путь
            template_path = Path(__file__).parent.parent / "templates" / "Расширенный отчет структура.md"
        
        if not template_path.exists():
            return "❌ Шаблон отчета не найден"
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        except Exception as e:
            return f"❌ Ошибка при чтении шаблона: {e}"
        
        # Подготовка данных для замены
        symbol = analysis.get('symbol', 'N/A')
        sentiment = analysis.get('sentiment', {})
        overall_sentiment = sentiment.get('overall', {})
        technical = analysis.get('technical', {})
        ma = technical.get('moving_averages', {})
        
        # Получаем текущую цену из market_data если доступно
        current_price = 'N/A'
        if market_data is not None and not market_data.empty:
            try:
                if 'close' in market_data.columns:
                    current_price = f"${market_data['close'].iloc[-1]:,.2f}"
                elif len(market_data.columns) > 0:
                    current_price = f"${market_data.iloc[-1, -1]:,.2f}"
            except Exception:
                pass
        
        # Вычисляем изменение за 30 дней
        change_30d = 'N/A'
        if market_data is not None and not market_data.empty:
            try:
                if 'close' in market_data.columns and len(market_data) >= 30:
                    price_now = market_data['close'].iloc[-1]
                    price_30d = market_data['close'].iloc[-30]
                    change_30d = f"{(price_now - price_30d) / price_30d * 100:+.2f}"
            except Exception:
                pass
        
        # Подсчитываем позитивные/негативные новости
        articles = sentiment.get('articles', [])
        positive_count = sum(1 for a in articles if (a.get('sentiment_score', 0) or 0) > 0.1)
        negative_count = sum(1 for a in articles if (a.get('sentiment_score', 0) or 0) < -0.1)
        
        # Формируем рекомендацию на русском
        recommendation = analysis.get('recommendation', 'hold').upper()
        rec_map = {'BUY': 'Покупка', 'SELL': 'Продажа', 'HOLD': 'Удержание'}
        invest_decision = rec_map.get(recommendation, 'Удержание')
        
        # Преобразуем overall_score в шкалу 0-10
        overall_score_raw = analysis.get('overall_score', 0.0)
        total_score = max(0, min(10, (overall_score_raw + 1) * 5))  # -1..1 -> 0..10
        
        # Формируем словарь замен
        replacements = {
            # Дата и автор
            '{{date}}': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            '{{author}}': 'AI-Platform',
            
            # Основные данные
            '{{ASSET_NAME}}': symbol,
            '{{TICKER}}': symbol,
            '{{ASSET}}': symbol,  # Для таблицы сравнения
            '{{PRICE}}': current_price.replace('$', '') if current_price != 'N/A' else 'N/A',
            '{{MARKET_CAP}}': str(analysis.get('market_cap', 'N/A')),
            '{{TVL}}': str(analysis.get('tvl', 'N/A')),
            '{{CHANGE_30D}}': change_30d.replace('%', '') if change_30d != 'N/A' else 'N/A',
            '{{RISK_LEVEL}}': analysis.get('risk_level', 'N/A').upper(),
            '{{FUNDAMENTAL_SCORE}}': f"{analysis.get('fundamental_score', total_score):.1f}",
            '{{TOTAL_SCORE}}': f"{total_score:.1f}",
            
            # Ключевые выводы
            '{{POTENTIAL}}': 'Средний' if total_score > 5 else 'Низкий',
            '{{DRIVERS}}': ', '.join(sentiment.get('key_themes', [])[:3]) or 'Недостаточно данных',
            '{{RISKS}}': f"Уровень риска: {analysis.get('risk_level', 'N/A')}",
            '{{INVEST_DECISION}}': invest_decision,
            '{{SUMMARY_FORECAST}}': f"Оценка {total_score:.1f}/10. Рекомендация: {invest_decision}",
            
            # Santiment данные
            '{{SENTIMENT_SCORE}}': f"{overall_sentiment.get('score', 0):.2f}",
            '{{NEWS_POSITIVE_CHANGE}}': 'N/A',  # Требуются исторические данные
            '{{DEV_ACTIVITY_TREND}}': 'N/A',
            '{{WHALE_ACTIVITY}}': 'N/A',
            
            # Цена и объемы
            '{{PRICE_TRENDS}}': f"Тренд: {technical.get('trend', 'N/A')}. MA7: {ma.get('MA7', 0):.2f}, MA30: {ma.get('MA30', 0):.2f}",
            '{{VOLUME_INSIGHT}}': 'Анализ объемов требует дополнительных данных',
            
            # Sentiment метрики
            '{{POSITIVE_NEWS_COUNT}}': str(positive_count),
            '{{NEGATIVE_NEWS_COUNT}}': str(negative_count),
            '{{SOCIAL_ACTIVITY_CHANGE}}': 'N/A',
            '{{DIVERGENCE_STATUS}}': 'Требует дополнительного анализа',
            '{{SENTIMENT_COMMENT}}': f"Общая тональность: {overall_sentiment.get('label', 'N/A')} ({overall_sentiment.get('score', 0):.2f})",
            
            # On-chain данные (по умолчанию N/A, так как нет реальных данных)
            '{{ACTIVE_ADDRESSES}}': str(analysis.get('onchain', {}).get('active_addresses', 'N/A')),
            '{{CHANGE_ADDRESSES}}': str(analysis.get('onchain', {}).get('change_addresses', 'N/A')),
            '{{TX_PER_DAY}}': str(analysis.get('onchain', {}).get('tx_per_day', 'N/A')),
            '{{CHANGE_TX}}': str(analysis.get('onchain', {}).get('change_tx', 'N/A')),
            '{{WHALE_TX}}': str(analysis.get('onchain', {}).get('whale_tx', 'N/A')),
            '{{CHANGE_WHALE_TX}}': str(analysis.get('onchain', {}).get('change_whale_tx', 'N/A')),
            '{{EX_OUTFLOW}}': str(analysis.get('onchain', {}).get('exchange_outflow', 'N/A')),
            '{{CHANGE_EX_OUTFLOW}}': str(analysis.get('onchain', {}).get('change_exchange_outflow', 'N/A')),
            
            # Network Health
            '{{CHANGE_TVL}}': str(analysis.get('change_tvl', 'N/A')),
            '{{DEV_ACTIVITY}}': str(analysis.get('network_health', {}).get('dev_activity', 'N/A')),
            '{{DEV_ACTIVITY_CHANGE}}': str(analysis.get('network_health', {}).get('dev_activity_change', 'N/A')),
            '{{DAU}}': str(analysis.get('network_health', {}).get('dau', 'N/A')),
            '{{CHANGE_DAU}}': str(analysis.get('network_health', {}).get('change_dau', 'N/A')),
            
            # Сравнение
            '{{ROI}}': str(analysis.get('roi_ytd', 'N/A')),
            
            # Фундаментальный анализ
            '{{PROJECT_DESCRIPTION}}': analysis.get('project_description', 'Требуется дополнительная информация'),
            '{{CONSENSUS}}': analysis.get('consensus', 'N/A'),
            '{{SCALABILITY}}': analysis.get('scalability', 'N/A'),
            '{{SECURITY_FEATURES}}': analysis.get('security_features', 'N/A'),
            '{{INNOVATIONS}}': analysis.get('innovations', 'N/A'),
            '{{FOUNDERS}}': analysis.get('team_investors', 'N/A'),
            '{{FUNDS}}': 'N/A',
            '{{ADVISORS}}': 'N/A',
            
            # Roadmap
            '{{ROADMAP_ITEM_1}}': 'N/A',
            '{{DATE_1}}': 'N/A',
            '{{ROADMAP_ITEM_2}}': 'N/A',
            '{{DATE_2}}': 'N/A',
            '{{ROADMAP_ITEM_3}}': 'N/A',
            '{{DATE_3}}': 'N/A',
            
            # Токеномика
            '{{MAX_SUPPLY}}': str(analysis.get('max_supply', 'N/A')),
            '{{CIRC_SUPPLY}}': str(analysis.get('circulating_supply', 'N/A')),
            '{{INFLATION}}': str(analysis.get('inflation', 'N/A')),
            '{{TOKEN_MECHANISM}}': analysis.get('token_mechanism', 'N/A'),
            '{{STAKING_YIELD}}': str(analysis.get('staking_yield', 'N/A')),
            '{{TOKENOMICS_COMMENT}}': 'Требуется дополнительная информация о токеномике',
            
            # Финансовые показатели
            '{{NVT}}': str(analysis.get('nvt', 'N/A')),
            '{{NVT_COMMENT}}': 'Требуется дополнительный анализ',
            '{{PS_RATIO}}': str(analysis.get('ps_ratio', 'N/A')),
            '{{PS_COMMENT}}': 'Требуется дополнительный анализ',
            '{{SHARPE_RATIO}}': str(analysis.get('sharpe_ratio', 'N/A')),
            '{{SHARPE_COMMENT}}': 'Требуется дополнительный анализ',
            '{{ROI_COMMENT}}': 'Требуется дополнительный анализ',
            '{{VOLATILITY}}': str(analysis.get('volatility', 'N/A')),
            '{{VOL_COMMENT}}': 'Требуется дополнительный анализ',
            
            # Комьюнити
            '{{TWITTER_FOLLOWERS}}': str(analysis.get('social', {}).get('twitter_followers', 'N/A')),
            '{{TWITTER_CHANGE}}': str(analysis.get('social', {}).get('twitter_change', 'N/A')),
            '{{TELEGRAM_MEMBERS}}': str(analysis.get('social', {}).get('telegram_members', 'N/A')),
            '{{TELEGRAM_CHANGE}}': str(analysis.get('social', {}).get('telegram_change', 'N/A')),
            '{{COMMITS}}': str(analysis.get('network_health', {}).get('commits', 'N/A')),
            '{{COMMITS_CHANGE}}': str(analysis.get('network_health', {}).get('commits_change', 'N/A')),
            '{{ECOSYSTEM_SIZE}}': str(analysis.get('ecosystem_size', 'N/A')),
            '{{CHANGE_ECOSYSTEM}}': str(analysis.get('change_ecosystem', 'N/A')),
            '{{COMMUNITY_COMMENT}}': 'Требуется дополнительная информация о комьюнити',
            
            # Новости
            '{{NEWS_COUNT}}': str(len(articles)),
            '{{TOP_SOURCES}}': 'Различные источники',
            '{{TOP_TOPICS}}': ', '.join(sentiment.get('key_themes', [])[:5]) or 'N/A',
            '{{NEWS_SUMMARY}}': f"Найдено {len(articles)} новостей. Общая тональность: {overall_sentiment.get('label', 'N/A')}",
            
            # Социальная активность
            '{{TWITTER_MENTIONS}}': str(analysis.get('social', {}).get('twitter_mentions', 'N/A')),
            '{{TWITTER_CHANGE}}': str(analysis.get('social', {}).get('twitter_change', 'N/A')),
            '{{TWITTER_SENTIMENT}}': str(analysis.get('social', {}).get('twitter_sentiment', 'N/A')),
            '{{REDDIT_POSTS}}': str(analysis.get('social', {}).get('reddit_posts', 'N/A')),
            '{{REDDIT_CHANGE}}': str(analysis.get('social', {}).get('reddit_change', 'N/A')),
            '{{REDDIT_SENTIMENT}}': str(analysis.get('social', {}).get('reddit_sentiment', 'N/A')),
            '{{TELEGRAM_ACTIVITY}}': str(analysis.get('social', {}).get('telegram_activity', 'N/A')),
            '{{TELEGRAM_CHANGE}}': str(analysis.get('social', {}).get('telegram_change', 'N/A')),
            '{{TELEGRAM_SENTIMENT}}': str(analysis.get('social', {}).get('telegram_sentiment', 'N/A')),
            '{{SANTIMENT_SUMMARY}}': analysis.get('santiment_summary', overall_sentiment.get('label', 'N/A')),
            
            # Риски
            '{{TECH_RISK}}': 'N/A',
            '{{PROB1}}': 'N/A',
            '{{IMPACT1}}': 'N/A',
            '{{COMMENT1}}': 'Требуется дополнительный анализ',
            '{{REG_RISK}}': 'N/A',
            '{{PROB2}}': 'N/A',
            '{{IMPACT2}}': 'N/A',
            '{{COMMENT2}}': 'Требуется дополнительный анализ',
            '{{MARKET_RISK}}': analysis.get('risk_level', 'N/A'),
            '{{PROB3}}': 'Средняя',
            '{{IMPACT3}}': 'Высокое',
            '{{COMMENT3}}': f"Уровень риска: {analysis.get('risk_level', 'N/A')}",
            
            # Прогноз
            '{{BULLISH_PROB}}': '30',
            '{{BULLISH_TARGET}}': 'N/A',
            '{{BULLISH_COMMENT}}': 'Требуется дополнительный анализ',
            '{{NEUTRAL_PROB}}': '40',
            '{{NEUTRAL_TARGET}}': current_price.replace('$', '') if current_price != 'N/A' else 'N/A',
            '{{NEUTRAL_COMMENT}}': 'Сохранение текущих уровней',
            '{{BEARISH_PROB}}': '30',
            '{{BEARISH_TARGET}}': 'N/A',
            '{{BEARISH_COMMENT}}': 'Требуется дополнительный анализ',
            '{{FORECAST_SUMMARY}}': f"Оценка: {total_score:.1f}/10. Рекомендация: {invest_decision}",
            
            # Итоговая оценка
            '{{SOCIAL_SCORE}}': f"{analysis.get('social_score', total_score * 0.8):.1f}",
            '{{ONCHAIN_SCORE}}': f"{analysis.get('onchain_score', total_score * 0.7):.1f}",
            '{{TOKEN_SCORE}}': f"{analysis.get('token_score', total_score * 0.6):.1f}",
            '{{GROWTH_SCORE}}': f"{analysis.get('growth_score', total_score * 0.9):.1f}",
            '{{FINAL_RECOMMENDATION}}': invest_decision,
            '{{BUY_ZONE_LOW}}': str(analysis.get('buy_zone_low', 'N/A')),
            '{{BUY_ZONE_HIGH}}': str(analysis.get('buy_zone_high', 'N/A')),
            
            # Источники
            '{{CMC_LINK}}': f"https://coinmarketcap.com/currencies/{symbol.lower()}/",
            '{{SANTIMENT_LINK}}': f"https://santiment.net/{symbol.lower()}",
            '{{DEFI_LLAMA_LINK}}': 'https://defillama.com/',
            '{{GLASSNODE_LINK}}': 'https://glassnode.com/',
            '{{GITHUB_LINK}}': 'N/A',
            '{{WHITEPAPER_LINK}}': 'N/A',
        }
        
        # Заменяем все плейсхолдеры
        report = template
        for placeholder, value in replacements.items():
            report = report.replace(placeholder, str(value))
        
        return report

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
        
        # Создаем собственные стили с правильными шрифтами
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.fonts import addMapping
        from reportlab.lib.colors import HexColor
        
        # Регистрируем шрифты с поддержкой кириллицы (Noto Sans → DejaVu Sans → Liberation Sans)
        try:
            noto_candidates = [
                ('/usr/share/fonts/noto/NotoSans-Regular.ttf', '/usr/share/fonts/noto/NotoSans-Bold.ttf'),
                ('/usr/share/fonts/TTF/NotoSans-Regular.ttf', '/usr/share/fonts/TTF/NotoSans-Bold.ttf'),
            ]
            dejavu_candidates = [
                ('/usr/share/fonts/TTF/DejaVuSans.ttf', '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf'),
                ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
            ]
            liberation_candidates = [
                ('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf')
            ]

            font_name = None
            for regular, bold in noto_candidates + dejavu_candidates + liberation_candidates:
                try:
                    pdfmetrics.registerFont(TTFont('CustomFont', regular))
                    pdfmetrics.registerFont(TTFont('CustomFont-Bold', bold))
                    font_name = 'CustomFont'
                    break
                except Exception:
                    continue

            if not font_name:
                # Используем встроенный шрифт с поддержкой Unicode как последний fallback
                from reportlab.pdfbase.cidfonts import UnicodeCIDFont
                pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
                font_name = 'HeiseiKakuGo-W5'

        except Exception:
            # Fallback на стандартные шрифты
            font_name = 'Helvetica'
        
        # Создаем стили с правильными шрифтами
        styles = getSampleStyleSheet()
        
        # Обновляем стили для использования нашего шрифта
        styles['Normal'].fontName = font_name
        styles['Heading1'].fontName = 'CustomFont-Bold' if font_name == 'CustomFont' else font_name
        styles['Heading2'].fontName = 'CustomFont-Bold' if font_name == 'CustomFont' else font_name
        styles['Title'].fontName = 'CustomFont-Bold' if font_name == 'CustomFont' else font_name
        
        # Создаем дополнительные стили
        custom_styles = {
            'Title': ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontName=font_name,
                fontSize=18,
                spaceAfter=20,
                alignment=1  # Center
            ),
            'Heading1': ParagraphStyle(
                'CustomHeading1',
                parent=styles['Heading1'],
                fontName=('CustomFont-Bold' if font_name == 'CustomFont' else font_name),
                fontSize=14,
                spaceAfter=12,
                textColor=HexColor('#2E86AB')
            ),
            'Heading2': ParagraphStyle(
                'CustomHeading2',
                parent=styles['Heading2'],
                fontName=('CustomFont-Bold' if font_name == 'CustomFont' else font_name),
                fontSize=12,
                spaceAfter=8,
                textColor=HexColor('#A23B72')
            ),
            'BodyText': ParagraphStyle(
                'CustomBodyText',
                parent=styles['BodyText'],
                fontName=font_name,
                fontSize=10,
                spaceAfter=6
            )
        }

        elements: List[Any] = []

        # Заголовок и дата
        elements.append(Paragraph(f"💠 Финансово-Аналитический Отчёт по Крипто-Активу", custom_styles['Title']))
        elements.append(Paragraph(f"Дата отчёта: {analysis.get('timestamp', 'N/A')}", custom_styles['BodyText']))
        elements.append(Spacer(1, 16))

        # 0. Executive Summary
        elements.append(Paragraph("📑 0. Инвестиционное резюме (Executive Summary)", custom_styles['Heading1']))
        summary_data = [["Показатель", "Значение"]]
        summary_data += [
            ["Актив / Тикер", f"{analysis.get('symbol', 'N/A')}"],
            ["Текущая цена", f"{analysis.get('current_price', 'N/A')}",],
            ["Рыночная капитализация", f"{analysis.get('market_cap', 'N/A')}",],
            ["TVL", f"{analysis.get('tvl', 'N/A')}",],
            ["Изменение за 30д", f"{analysis.get('change_30d', 'N/A')}",],
            ["Оценка риска", f"{analysis.get('risk_level', 'N/A')}",],
            ["Фундаментальная сила", f"{analysis.get('fundamental_score', 'N/A')}",],
            ["Общий рейтинг", f"{analysis.get('total_score', analysis.get('overall_score', 0))}",],
        ]
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        # 1. Интегрированные метрики и визуализация
        elements.append(Paragraph("📊 1. Интегрированные метрики и визуализация", custom_styles['Heading1']))
        elements.append(Paragraph("1.1 📈 Цена и объёмы торгов", custom_styles['Heading2']))
        if charts:
            from reportlab.platypus import Image
            for ch in charts:
                try:
                    if any(k in ch.title for k in ["Цена", "Volume", "Волатильность"]):
                        img_buf = io.BytesIO(ch.image_bytes)
                        elements.append(Paragraph(ch.title, custom_styles['BodyText']))
                        elements.append(Image(img_buf, width=500, height=250))
                        elements.append(Spacer(1, 10))
                except Exception:
                    continue

        elements.append(Paragraph("1.2 🧠 Sentiment и новостная динамика", custom_styles['Heading2']))
        sent_block = analysis.get('sentiment', {})
        if sent_block:
            elements.append(Paragraph(
                f"Тональность: {sent_block.get('overall', {}).get('label', 'N/A')} ({sent_block.get('overall', {}).get('score', 0):.2f})",
                custom_styles['BodyText']
            ))
        elements.append(Spacer(1, 12))

        # 1.3 📡 On-chain данные
        elements.append(Paragraph("1.3 📡 On-chain данные", custom_styles['Heading2']))
        onchain = analysis.get('onchain', {})
        onchain_rows = [["Метрика", "Текущее значение", "Изменение (30д)"]]
        onchain_rows += [
            ["Активные адреса", f"{onchain.get('active_addresses','N/A')}", f"{onchain.get('change_addresses','N/A')}"] ,
            ["Транзакции / день", f"{onchain.get('tx_per_day','N/A')}", f"{onchain.get('change_tx','N/A')}"] ,
            ["Whale-транзакции", f"{onchain.get('whale_tx','N/A')}", f"{onchain.get('change_whale_tx','N/A')}"] ,
            ["Exchange Outflow", f"{onchain.get('exchange_outflow','N/A')}", f"{onchain.get('change_exchange_outflow','N/A')}"] ,
        ]
        elements.append(Table(onchain_rows))
        elements.append(Spacer(1, 8))

        # 1.4 ⚙️ Network Health
        elements.append(Paragraph("1.4 ⚙️ Network Health", custom_styles['Heading2']))
        nh = analysis.get('network_health', {})
        nh_rows = [["Показатель", "Значение", "Изменение"],
                   ["TVL", f"{analysis.get('tvl','N/A')}", f"{analysis.get('change_tvl','N/A')}"] ,
                   ["Активность Dev", f"{nh.get('dev_activity','N/A')}", f"{nh.get('dev_activity_change','N/A')}"] ,
                   ["DAU", f"{nh.get('dau','N/A')}", f"{nh.get('change_dau','N/A')}"] ]
        elements.append(Table(nh_rows))
        elements.append(Spacer(1, 8))

        # 1.5 📊 Сравнение с аналогами
        elements.append(Paragraph("1.5 📊 Сравнение с аналогами", custom_styles['Heading2']))
        comp_rows = [["Актив", "Капитализация", "TVL", "ROI (YTD)", "Dev Activity", "Sentiment"],
                     ["ETH", "$360B", "$95B", "+48%", "9.1", "0.73"],
                     ["SOL", "$75B", "$12B", "+210%", "8.7", "0.68"],
                     [analysis.get('symbol','N/A'), f"{analysis.get('market_cap','N/A')}", f"{analysis.get('tvl','N/A')}", f"{analysis.get('roi_ytd','N/A')}", f"{nh.get('dev_activity','N/A')}", f"{(analysis.get('sentiment',{}).get('overall',{}) or {}).get('score','N/A')}"]]
        elements.append(Table(comp_rows))
        elements.append(Spacer(1, 12))

        # 2. Фундаментальный анализ
        elements.append(Paragraph("🧠 2. Фундаментальный анализ", custom_styles['Heading1']))
        elements.append(Paragraph("2.1 Миссия и позиционирование", custom_styles['Heading2']))
        elements.append(Paragraph(f"{analysis.get('project_description', 'N/A')}", custom_styles['BodyText']))
        elements.append(Paragraph("2.2 Технологии", custom_styles['Heading2']))
        elements.append(Paragraph(f"Консенсус: {analysis.get('consensus','N/A')} | Масштабируемость: {analysis.get('scalability','N/A')} | Безопасность: {analysis.get('security_features','N/A')} | Инновации: {analysis.get('innovations','N/A')}", custom_styles['BodyText']))
        elements.append(Paragraph("2.3 Команда и инвесторы", custom_styles['Heading2']))
        elements.append(Paragraph(f"{analysis.get('team_investors', 'N/A')}", custom_styles['BodyText']))
        elements.append(Paragraph("2.4 Roadmap", custom_styles['Heading2']))
        rm = analysis.get('roadmap', [])
        rm_rows = [["Этап", "Состояние", "Дата"]]
        for item in rm[:3]:
            rm_rows.append([item.get('title','N/A'), item.get('status','N/A'), item.get('date','N/A')])
        if len(rm_rows) == 1:
            rm_rows.append(["N/A","N/A","N/A"])
        elements.append(Table(rm_rows))
        elements.append(Spacer(1, 12))

        # 3. Токеномика
        elements.append(Paragraph("💰 3. Токеномика", custom_styles['Heading1']))
        tokenomics_rows = [["Метрика", "Значение"]]
        tokenomics_rows += [
            ["Общий объём эмиссии", f"{analysis.get('max_supply', 'N/A')}"] ,
            ["Циркулирующее предложение", f"{analysis.get('circulating_supply', 'N/A')}"] ,
            ["Инфляция", f"{analysis.get('inflation', 'N/A')}"] ,
            ["Механизм", f"{analysis.get('token_mechanism', 'N/A')}"] ,
            ["Staking Yield", f"{analysis.get('staking_yield', 'N/A')}"] ,
        ]
        tokenomics_table = Table(tokenomics_rows)
        tokenomics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(tokenomics_table)
        elements.append(Spacer(1, 12))

        # 4. Финансовые показатели
        elements.append(Paragraph("📈 4. Финансовые показатели", custom_styles['Heading1']))
        fin_rows = [["Метрика", "Значение"]]
        fin_rows += [
            ["NVT", f"{analysis.get('nvt', 'N/A')}"] ,
            ["P/S", f"{analysis.get('ps_ratio', 'N/A')}"] ,
            ["Sharpe Ratio", f"{analysis.get('sharpe_ratio', 'N/A')}"] ,
            ["ROI (YTD)", f"{analysis.get('roi_ytd', 'N/A')}"] ,
            ["Волатильность", f"{analysis.get('volatility', 'N/A')}"] ,
        ]
        fin_table = Table(fin_rows)
        fin_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(fin_table)
        elements.append(Spacer(1, 12))

        # 5. Комьюнити и экосистема
        elements.append(Paragraph("🌐 5. Комьюнити и экосистема", custom_styles['Heading1']))
        elements.append(Paragraph(f"Метрики комьюнити: {analysis.get('community_metrics', 'N/A')}", custom_styles['BodyText']))
        elements.append(Spacer(1, 12))

        # 6. Анализ Santiment / Новостей
        elements.append(Paragraph("🧾 6. Анализ Santiment / Новостей", custom_styles['Heading1']))
        sentiment = analysis.get('sentiment', {})
        overall = sentiment.get('overall', {})
        # 6.1 Анализ новостного поля
        elements.append(Paragraph("6.1 Анализ новостного поля", custom_styles['Heading2']))
        articles = sentiment.get('articles', [])
        elements.append(Paragraph(f"Количество упоминаний: {len(articles)}", custom_styles['BodyText']))
        if articles:
            news_data = [["Заголовок", "Тональность", "Релевантность"]]
            for article in articles[:5]:
                title = article.get('title', 'N/A')
                news_data.append([title[:60] + ("..." if len(title) > 60 else ""), f"{article.get('sentiment_score', 0):.2f}", f"{article.get('relevance_score', 0):.2f}"])
            news_table = Table(news_data)
            news_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#A23B72')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            elements.append(news_table)
        # 6.2 Социальная активность
        elements.append(Paragraph("6.2 Социальная активность", custom_styles['Heading2']))
        social = analysis.get('social', {})
        social_rows = [["Платформа", "Активность", "Изменение", "Тональность"],
                       ["Twitter", f"{social.get('twitter_mentions','N/A')}", f"{social.get('twitter_change','N/A')}", f"{social.get('twitter_sentiment','N/A')}"] ,
                       ["Reddit", f"{social.get('reddit_posts','N/A')}", f"{social.get('reddit_change','N/A')}", f"{social.get('reddit_sentiment','N/A')}"] ,
                       ["Telegram", f"{social.get('telegram_activity','N/A')}", f"{social.get('telegram_change','N/A')}", f"{social.get('telegram_sentiment','N/A')}"] ]
        elements.append(Table(social_rows))
        # 6.3 Итог Santiment анализа
        elements.append(Paragraph("6.3 Итог Santiment анализа", custom_styles['Heading2']))
        elements.append(Paragraph(f"{analysis.get('santiment_summary', overall.get('label',''))}", custom_styles['BodyText']))
        elements.append(Spacer(1, 12))

        # 7. Риски и уязвимости
        elements.append(Paragraph("⚠️ 7. Риски и уязвимости", custom_styles['Heading1']))
        risks = analysis.get('risks', [])
        if risks:
            risk_rows = [["Категория", "Риск", "Вероятность", "Влияние"]]
            for r in risks[:5]:
                risk_rows.append([
                    r.get('category', 'N/A'), r.get('title', 'N/A'), r.get('probability', 'N/A'), r.get('impact', 'N/A')
                ])
            risk_table = Table(risk_rows)
            risk_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            elements.append(risk_table)
        elements.append(Spacer(1, 12))

        # 8. Прогноз и сценарный анализ
        elements.append(Paragraph("🔮 8. Прогноз и сценарный анализ", custom_styles['Heading1']))
        scenarios = analysis.get('scenarios', {})
        if scenarios:
            scen_rows = [["Сценарий", "Вероятность", "Цель цены"]]
            for name in ("Bullish", "Neutral", "Bearish"):
                s = scenarios.get(name.lower(), {})
                scen_rows.append([name, s.get('prob', 'N/A'), s.get('target', 'N/A')])
            scen_table = Table(scen_rows)
            scen_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            elements.append(scen_table)
        elements.append(Spacer(1, 12))

        # 9. Итоговая оценка
        elements.append(Paragraph("🧾 9. Итоговая оценка", custom_styles['Heading1']))
        eval_rows = [["Категория", "Балл (0–10)"],
                     ["Фундамент", f"{analysis.get('fundamental_score','N/A')}"] ,
                     ["Соц. метрики (Santiment)", f"{analysis.get('social_score','N/A')}"] ,
                     ["Ончейн активность", f"{analysis.get('onchain_score','N/A')}"] ,
                     ["Токеномика", f"{analysis.get('token_score','N/A')}"] ,
                     ["Потенциал роста", f"{analysis.get('growth_score','N/A')}"] ]
        elements.append(Table(eval_rows))
        elements.append(Paragraph(f"Итог: {analysis.get('total_score', analysis.get('overall_score', 'N/A'))} / 10", custom_styles['BodyText']))
        elements.append(Paragraph(f"Рекомендация: {analysis.get('final_recommendation', analysis.get('recommendation', 'N/A'))}", custom_styles['BodyText']))
        if analysis.get('buy_zone_low') or analysis.get('buy_zone_high'):
            elements.append(Paragraph(f"Инвест-зона: ${analysis.get('buy_zone_low','N/A')} – ${analysis.get('buy_zone_high','N/A')}", custom_styles['BodyText']))
        elements.append(Spacer(1, 12))

        # Источники данных
        data_sources = analysis.get('data_sources', [])
        if data_sources:
            elements.append(Paragraph("📚 Источники и материалы", custom_styles['Heading1']))
            elements.append(Paragraph(f"{', '.join(data_sources)}", custom_styles['BodyText']))
            elements.append(Spacer(1, 12))

        # Disclaimer
        elements.append(Paragraph("⚠️ ВАЖНАЯ ИНФОРМАЦИЯ", custom_styles['Heading1']))
        disclaimer_text = """
        • Анализ основан на дневных данных (1d) и актуальных новостях
        • Не является финансовой рекомендацией
        • Проводите собственное исследование перед инвестированием
        • Криптовалюты - высокорискованные активы
        • Возможны значительные потери капитала
        """
        elements.append(Paragraph(disclaimer_text, custom_styles['BodyText']))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    def generate_pdf_report_from_template(self, analysis: Dict[str, Any], market_data=None, charts: List[Chart] = None) -> bytes:
        """
        Генерирует PDF строго по шаблону templates/Расширенный отчет структура.md:
        - Заполняет плейсхолдеры через generate_readable_report_from_template
        - Парсит базовые элементы markdown (заголовки, цитаты, таблицы)
        - Игнорирует встроенные изображения в шаблоне и подставляет доступные charts
        - Очищает эмодзи для избежания проблем с кодировкой шрифта
        """
        charts = charts or []
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)

        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

        # Регистрируем шрифты с поддержкой кириллицы
        try:
            font_name = None
            candidates = [
                ('/usr/share/fonts/TTF/DejaVuSans.ttf', '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf'),
                ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
                ('/usr/share/fonts/noto/NotoSans-Regular.ttf', '/usr/share/fonts/noto/NotoSans-Bold.ttf'),
                ('/usr/share/fonts/TTF/NotoSans-Regular.ttf', '/usr/share/fonts/TTF/NotoSans-Bold.ttf'),
            ]
            for regular, bold in candidates:
                try:
                    pdfmetrics.registerFont(TTFont('TemplateFont', regular))
                    pdfmetrics.registerFont(TTFont('TemplateFont-Bold', bold))
                    font_name = 'TemplateFont'
                    break
                except Exception:
                    continue
            if not font_name:
                font_name = 'Helvetica'
        except Exception:
            font_name = 'Helvetica'

        styles = getSampleStyleSheet()
        styles['Normal'].fontName = font_name
        styles['BodyText'].fontName = font_name
        styles['Heading1'].fontName = 'TemplateFont-Bold' if font_name == 'TemplateFont' else font_name
        styles['Heading2'].fontName = 'TemplateFont-Bold' if font_name == 'TemplateFont' else font_name
        styles['Title'].fontName = 'TemplateFont-Bold' if font_name == 'TemplateFont' else font_name

        heading1 = ParagraphStyle('H1', parent=styles['Heading1'], textColor=HexColor('#2E86AB'), fontSize=16, spaceAfter=10)
        heading2 = ParagraphStyle('H2', parent=styles['Heading2'], textColor=HexColor('#A23B72'), fontSize=13, spaceAfter=8)
        body = ParagraphStyle('Body', parent=styles['BodyText'], fontSize=10, spaceAfter=6)
        quote = ParagraphStyle('Quote', parent=styles['BodyText'], fontSize=10, leftIndent=12, textColor=HexColor('#555555'))

        def strip_emojis(text: str) -> str:
            # Удаляем большинство эмодзи и не-BMP символов, сохраняя кириллицу/латиницу
            try:
                import re
                return re.sub(r"[\U00010000-\U0010FFFF]", "", text)
            except Exception:
                return text

        # Готовим текст отчёта
        md_text = self.generate_readable_report_from_template(analysis, market_data=market_data)
        md_text = strip_emojis(md_text)

        elements: List[Any] = []

        # Подстановка графиков вместо ![[...]]
        # (графики добавим в конце первого блока визуализации)

        lines = md_text.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i].rstrip()

            # Пропускаем пустые строки
            if not line:
                elements.append(Spacer(1, 6))
                i += 1
                continue

            # Игнорируем встроенные изображения из шаблона
            if line.strip().startswith('!['):
                i += 1
                continue

            # Заголовки
            if line.startswith('## '):
                elements.append(Paragraph(line[3:], heading1))
                i += 1
                continue
            if line.startswith('### '):
                elements.append(Paragraph(line[4:], heading2))
                i += 1
                continue

            # Цитаты
            if line.startswith('> '):
                quote_lines = [line[2:]]
                j = i + 1
                while j < len(lines) and lines[j].startswith('> '):
                    quote_lines.append(lines[j][2:])
                    j += 1
                elements.append(Paragraph(strip_emojis(" ".join(quote_lines)), quote))
                i = j
                continue

            # Таблицы markdown
            if line.startswith('|') and line.endswith('|'):
                table_rows: List[List[str]] = []
                j = i
                while j < len(lines) and lines[j].startswith('|') and lines[j].endswith('|'):
                    row = [c.strip() for c in lines[j][1:-1].split('|')]
                    # фильтруем разделитель '---'
                    if not all(cell.strip('- ') == '' for cell in row):
                        table_rows.append(row)
                    j += 1
                if table_rows:
                    tbl = Table(table_rows)
                    tbl.setStyle(TableStyle([
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                        ('FONTNAME', (0, 0), (-1, -1), font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ]))
                    elements.append(tbl)
                    elements.append(Spacer(1, 8))
                i = j
                continue

            # Обычный параграф
            elements.append(Paragraph(strip_emojis(line), body))
            i += 1

        # Вставляем доступные графики в конец документа (или можно найти место по заголовку)
        if charts:
            from reportlab.platypus import Image
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Графики", heading2))
            for ch in charts:
                try:
                    img_buf = io.BytesIO(ch.image_bytes)
                    elements.append(Paragraph(strip_emojis(ch.title), body))
                    elements.append(Image(img_buf, width=500, height=250))
                    elements.append(Spacer(1, 10))
                except Exception:
                    continue

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes


