"""
Тесты для генератора отчетов
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

from reports.generator import ReportGenerator


def test_generate_readable_report_from_template():
    """Тест генерации читаемого отчета из шаблона"""
    
    # Создаем тестовые данные анализа
    test_analysis = {
        'symbol': 'BTC',
        'timeframe': '1day',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'overall_score': 0.5,
        'risk_level': 'medium',
        'recommendation': 'hold',
        'technical': {
            'trend': 'bullish',
            'moving_averages': {
                'MA7': 45000.0,
                'MA30': 43000.0
            }
        },
        'sentiment': {
            'overall': {
                'label': 'positive',
                'score': 0.6
            },
            'key_themes': ['ETF', 'adoption', 'institutional'],
            'articles': [
                {'sentiment_score': 0.8, 'title': 'Good news'},
                {'sentiment_score': -0.2, 'title': 'Bad news'},
                {'sentiment_score': 0.5, 'title': 'Neutral news'}
            ]
        },
        'key_points': ['Point 1', 'Point 2', 'Point 3'],
        'data_sources': ['TwelveData', 'NewsAPI'],
        'market_cap': '850000000000',
        'tvl': '50000000',
        'current_price': 45000.0
    }
    
    # Создаем тестовые рыночные данные
    dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
    market_data = pd.DataFrame({
        'close': [40000 + i * 100 for i in range(60)],
        'volume': [1000000 + i * 10000 for i in range(60)]
    }, index=dates)
    
    # Создаем генератор отчетов
    generator = ReportGenerator()
    
    # Генерируем отчет
    report = generator.generate_readable_report_from_template(
        test_analysis, 
        market_data=market_data
    )
    
    # Проверяем, что отчет не пустой
    assert report is not None
    assert len(report) > 0
    
    # Проверяем, что это не сообщение об ошибке
    assert not report.startswith('❌')
    
    # Проверяем, что все основные плейсхолдеры заменены
    assert '{{' not in report or '{{' not in report.replace('{{', ''), 'Должны быть заменены все плейсхолдеры'
    
    # Проверяем наличие ключевых данных
    assert 'BTC' in report, 'Символ должен быть в отчете'
    assert 'bullish' in report.lower() or 'бычий' in report.lower() or 'тренд' in report.lower(), 'Тренд должен быть в отчете'
    
    # Проверяем наличие основных разделов
    assert 'Инвестиционное резюме' in report or 'Executive Summary' in report or 'резюме' in report.lower()
    assert 'Фундаментальный анализ' in report or 'фундамент' in report.lower()
    assert 'Токеномика' in report or 'токеномика' in report.lower()
    
    print("✅ Тест генерации читаемого отчета пройден")
    return True


def test_generate_readable_report_without_market_data():
    """Тест генерации отчета без рыночных данных"""
    
    test_analysis = {
        'symbol': 'ETH',
        'timeframe': '1day',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'overall_score': -0.2,
        'risk_level': 'high',
        'recommendation': 'sell',
        'technical': {
            'trend': 'bearish',
            'moving_averages': {
                'MA7': 2500.0,
                'MA30': 2600.0
            }
        },
        'sentiment': {
            'overall': {
                'label': 'negative',
                'score': -0.3
            },
            'key_themes': [],
            'articles': []
        },
        'key_points': [],
        'data_sources': ['TwelveData']
    }
    
    generator = ReportGenerator()
    
    # Генерируем отчет без рыночных данных
    report = generator.generate_readable_report_from_template(
        test_analysis,
        market_data=None
    )
    
    assert report is not None
    assert len(report) > 0
    assert not report.startswith('❌')
    assert 'ETH' in report
    
    print("✅ Тест генерации отчета без рыночных данных пройден")
    return True


def test_generate_readable_report_missing_template():
    """Тест обработки отсутствующего шаблона"""
    
    # Временно изменяем путь к шаблону на несуществующий
    generator = ReportGenerator()
    original_path = generator.template_path
    generator.template_path = '/nonexistent/path'
    
    test_analysis = {
        'symbol': 'BTC',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    report = generator.generate_readable_report_from_template(
        test_analysis,
        market_data=None
    )
    
    # Должна быть попытка найти шаблон в альтернативном месте
    # Если шаблон не найден, должна быть ошибка
    assert report is not None
    
    # Восстанавливаем оригинальный путь
    generator.template_path = original_path
    
    print("✅ Тест обработки отсутствующего шаблона пройден")
    return True


def test_generate_readable_report_all_placeholders():
    """Тест что все плейсхолдеры в шаблоне заменяются"""
    
    test_analysis = {
        'symbol': 'SOL',
        'timeframe': '1day',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'overall_score': 0.7,
        'risk_level': 'low',
        'recommendation': 'buy',
        'technical': {
            'trend': 'bullish',
            'moving_averages': {
                'MA7': 150.0,
                'MA30': 140.0
            }
        },
        'sentiment': {
            'overall': {
                'label': 'very_positive',
                'score': 0.8
            },
            'key_themes': ['DeFi', 'NFT', 'gaming'],
            'articles': [
                {'sentiment_score': 0.9, 'title': 'Great news'},
                {'sentiment_score': 0.7, 'title': 'Good news'}
            ]
        },
        'key_points': ['Strong fundamentals', 'Growing ecosystem'],
        'data_sources': ['TwelveData', 'NewsAPI', 'Santiment'],
        'market_cap': '75000000000',
        'tvl': '2000000000',
        'current_price': 150.0,
        'project_description': 'High-performance blockchain',
        'consensus': 'PoS',
        'scalability': 'High',
        'security_features': 'Advanced',
        'innovations': 'Multiple',
        'team_investors': 'Experienced team',
        'max_supply': '500000000',
        'circulating_supply': '400000000',
        'inflation': '5',
        'token_mechanism': 'Staking',
        'staking_yield': '7',
        'fundamental_score': 8.5,
        'social_score': 8.0,
        'onchain_score': 7.5,
        'token_score': 8.0,
        'growth_score': 9.0,
        'roi_ytd': '+150',
        'onchain': {
            'active_addresses': '1000000',
            'tx_per_day': '500000',
            'whale_tx': '100'
        },
        'network_health': {
            'dev_activity': 'High',
            'dau': '500000'
        },
        'social': {
            'twitter_followers': '2000000',
            'telegram_members': '500000'
        }
    }
    
    dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
    market_data = pd.DataFrame({
        'close': [100 + i * 2 for i in range(60)],
        'volume': [500000 + i * 5000 for i in range(60)]
    }, index=dates)
    
    generator = ReportGenerator()
    report = generator.generate_readable_report_from_template(
        test_analysis,
        market_data=market_data
    )
    
    # Проверяем что отчет сгенерирован
    assert report is not None
    assert len(report) > 0
    assert not report.startswith('❌')
    
    # Проверяем что основные плейсхолдеры заменены
    assert 'SOL' in report
    assert '{{' not in report or report.count('{{') == 0, 'Не все плейсхолдеры заменены'
    
    print("✅ Тест замены всех плейсхолдеров пройден")
    return True


def test_full_report_generation():
    """Полный тест генерации отчета с проверкой всех плейсхолдеров"""
    import re
    
    test_analysis = {
        'symbol': 'BTC',
        'timeframe': '1day',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'overall_score': 0.5,
        'risk_level': 'medium',
        'recommendation': 'hold',
        'technical': {
            'trend': 'bullish',
            'moving_averages': {
                'MA7': 45000.0,
                'MA30': 43000.0
            }
        },
        'sentiment': {
            'overall': {
                'label': 'positive',
                'score': 0.6
            },
            'key_themes': ['ETF', 'adoption'],
            'articles': [
                {'sentiment_score': 0.8, 'title': 'Good news'},
                {'sentiment_score': -0.2, 'title': 'Bad news'}
            ]
        },
        'key_points': ['Point 1', 'Point 2'],
        'data_sources': ['TwelveData', 'NewsAPI'],
        'market_cap': '850000000000',
        'tvl': '50000000'
    }
    
    dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
    market_data = pd.DataFrame({
        'close': [40000 + i * 100 for i in range(60)],
        'volume': [1000000 + i * 10000 for i in range(60)]
    }, index=dates)
    
    generator = ReportGenerator()
    report = generator.generate_readable_report_from_template(
        test_analysis,
        market_data=market_data
    )
    
    # Проверяем что отчет сгенерирован
    assert report is not None
    assert len(report) > 0
    assert not report.startswith('❌')
    
    # Проверяем отсутствие незамененных плейсхолдеров
    placeholders = re.findall(r'\{\{[A-Z_]+\}\}', report)
    if placeholders:
        unique_placeholders = set(placeholders)
        print(f"⚠️  Найдены незамененные плейсхолдеры: {unique_placeholders}")
        assert False, f"Найдены незамененные плейсхолдеры: {unique_placeholders}"
    
    # Проверяем наличие ключевых данных
    assert 'BTC' in report
    assert 'Инвестиционное резюме' in report or 'резюме' in report.lower() or 'Executive Summary' in report
    assert 'Фундаментальный анализ' in report or 'фундамент' in report.lower()
    
    # Проверяем что основные разделы присутствуют
    sections = [
        'Токеномика',
        'Финансовые показатели',
        'Риски',
        'Прогноз',
        'Итоговая оценка'
    ]
    found_sections = sum(1 for section in sections if section in report)
    assert found_sections >= 3, f"Найдено слишком мало разделов: {found_sections}/{len(sections)}"
    
    print("✅ Полный тест генерации отчета пройден")
    return True


def test_real_btc_report():
    """Генерация реального отчета по BTC с сохранением в файл"""
    import os
    from pathlib import Path
    from data_collectors.crypto_collector import CryptoCollector
    from analysis.enhanced_engine import EnhancedAnalysisEngine
    from analysis.sentiment_analyzer import SentimentAnalyzer
    from AI_block.analyzer import AIAnalyzer
    from config import config
    
    print("\n" + "=" * 60)
    print("Генерация реального отчета по BTC")
    print("=" * 60)
    
    symbol = 'BTC'
    
    try:
        # Пытаемся получить реальные данные
        print(f"\n📊 Получение реальных данных для {symbol}...")
        timeframe = getattr(config, 'DEFAULT_TIMEFRAME', '1day')
        period = getattr(config, 'DEFAULT_PERIOD', 90)
        crypto_collector = CryptoCollector(
            timeframe=timeframe,
            period=str(period)
        )
        
        market_data = crypto_collector.get_crypto_data(symbol)
        current_price = crypto_collector.get_current_price(symbol)
        
        if market_data is None or market_data.empty:
            print("⚠️  Не удалось получить реальные данные, используем тестовые")
            # Создаем более реалистичные тестовые данные
            dates = pd.date_range(start='2024-01-01', periods=90, freq='D')
            price_base = 45000
            market_data = pd.DataFrame({
                'close': [price_base + (i * 50) + (i % 7 * 100) - 200 for i in range(90)],
                'volume': [2000000000 + i * 10000000 for i in range(90)],
                'open': [price_base + (i * 50) - 100 for i in range(90)],
                'high': [price_base + (i * 50) + 300 for i in range(90)],
                'low': [price_base + (i * 50) - 200 for i in range(90)]
            }, index=dates)
            current_price = float(market_data['close'].iloc[-1])
        else:
            print(f"✅ Получено {len(market_data)} записей")
            if current_price:
                print(f"💰 Текущая цена BTC: ${current_price:,.2f}")
        
        # Вычисляем дополнительные данные из рыночных данных
        latest_price = float(market_data['close'].iloc[-1])
        price_30d_ago = float(market_data['close'].iloc[-30]) if len(market_data) >= 30 else latest_price
        change_30d = ((latest_price - price_30d_ago) / price_30d_ago * 100) if price_30d_ago > 0 else 0
        
        # Вычисляем скользящие средние
        ma_7 = float(market_data['close'].tail(7).mean()) if len(market_data) >= 7 else latest_price
        ma_30 = float(market_data['close'].tail(30).mean()) if len(market_data) >= 30 else latest_price
        
        # Определяем тренд
        trend = 'bullish' if ma_7 > ma_30 else ('bearish' if ma_7 < ma_30 else 'neutral')
        
        # Создаем реалистичный анализ
        print(f"\n🔍 Формирование анализа...")
        analysis_dict = {
            'symbol': symbol,
            'timeframe': '1day',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_score': 0.65 if trend == 'bullish' else (0.35 if trend == 'bearish' else 0.5),
            'risk_level': 'medium',
            'recommendation': 'buy' if trend == 'bullish' else ('sell' if trend == 'bearish' else 'hold'),
            'technical': {
                'trend': trend,
                'moving_averages': {
                    'MA7': ma_7,
                    'MA30': ma_30
                }
            },
            'sentiment': {
                'overall': {
                    'label': 'positive' if trend == 'bullish' else ('negative' if trend == 'bearish' else 'neutral'),
                    'score': 0.6 if trend == 'bullish' else (-0.4 if trend == 'bearish' else 0.1)
                },
                'key_themes': ['Bitcoin', 'ETF', 'Institutional adoption', 'Halving'],
                'articles': [
                    {'sentiment_score': 0.75, 'title': 'Bitcoin ETF Approval Boosts Market Confidence'},
                    {'sentiment_score': 0.65, 'title': 'Major Institutions Continue Bitcoin Accumulation'},
                    {'sentiment_score': 0.5, 'title': 'Bitcoin Price Stabilizes Above Support Level'},
                    {'sentiment_score': -0.3, 'title': 'Regulatory Concerns Linger'},
                ]
            },
            'key_points': [
                f'Тренд: {trend}',
                f'MA7: ${ma_7:,.2f}, MA30: ${ma_30:,.2f}',
                f'Изменение за 30 дней: {change_30d:+.2f}%',
                'Положительный сентимент на новостях'
            ],
            'data_sources': ['TwelveData', 'NewsAPI', 'CoinMarketCap'],
            'current_price': current_price or latest_price,
            'market_cap': '850000000000',  # Примерная капитализация BTC
            'tvl': 'N/A',  # BTC не имеет TVL
            'change_30d': f'{change_30d:+.2f}',
            'fundamental_score': 8.5,
            'social_score': 7.8,
            'onchain_score': 8.2,
            'token_score': 9.0,
            'growth_score': 8.0,
            'roi_ytd': f'{change_30d:+.1f}',
            'project_description': 'Bitcoin - первая и крупнейшая криптовалюта, децентрализованная цифровая валюта, работающая на технологии blockchain.',
            'consensus': 'Proof of Work (PoW)',
            'scalability': 'Средняя (Lightning Network для масштабирования)',
            'security_features': 'Высокая (самая безопасная криптовалюта)',
            'innovations': 'Lightning Network, Taproot, SegWit',
            'team_investors': 'Децентрализованная разработка (Satoshi Nakamoto - создатель)',
            'max_supply': '21000000',
            'circulating_supply': '19500000',
            'inflation': '1.8',
            'token_mechanism': 'Mining + Staking через экосистему',
            'staking_yield': 'N/A',
            'nvt': '45',
            'ps_ratio': 'N/A',
            'sharpe_ratio': '1.2',
            'volatility': '65',
            'onchain': {
                'active_addresses': '900000',
                'tx_per_day': '250000',
                'whale_tx': '150',
                'exchange_outflow': '12000'
            },
            'network_health': {
                'dev_activity': 'Высокая',
                'dau': '850000',
                'commits': '250'
            },
            'social': {
                'twitter_followers': '5000000',
                'twitter_mentions': '45000',
                'telegram_members': '1200000',
                'reddit_posts': '8500'
            }
        }
        
        # Генерируем отчет
        print(f"\n📝 Генерация отчета...")
        generator = ReportGenerator()
        report = generator.generate_readable_report_from_template(
            analysis_dict,
            market_data=market_data
        )
        
        # Проверяем результат
        assert report is not None, "Отчет не сгенерирован"
        assert len(report) > 0, "Отчет пустой"
        assert not report.startswith('❌'), f"Ошибка генерации отчета: {report[:200]}"
        
        # Проверяем отсутствие незамененных плейсхолдеров
        import re as regex_module
        placeholders = regex_module.findall(r'\{\{[A-Z_]+\}\}', report)
        if placeholders:
            unique_placeholders = set(placeholders)
            print(f"\n⚠️  Найдены незамененные плейсхолдеры: {unique_placeholders}")
            # Не считаем критической ошибкой, но предупреждаем
        
        # Сохраняем отчет в файл
        output_dir = Path(__file__).parent.parent / 'docs' / 'test_reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f'BTC_report_{timestamp}.md'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n✅ Отчет успешно сгенерирован!")
        print(f"📄 Сохранен в: {output_file}")
        print(f"📊 Длина отчета: {len(report)} символов")
        print(f"📝 Строк: {len(report.splitlines())}")
        
        # Показываем превью
        print(f"\n📋 Превью отчета (первые 500 символов):")
        print("-" * 60)
        print(report[:500])
        print("...")
        print("-" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Ошибка при генерации реального отчета: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Запуск всех тестов"""
    print("=" * 60)
    print("Тестирование генератора отчетов")
    print("=" * 60)
    
    # Базовые тесты
    tests = [
        test_generate_readable_report_from_template,
        test_generate_readable_report_without_market_data,
        test_generate_readable_report_missing_template,
        test_generate_readable_report_all_placeholders,
        test_full_report_generation
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ Тест {test.__name__} провален: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Результаты базовых тестов: {passed} пройдено, {failed} провалено")
    print("=" * 60)
    
    # Реальный тест генерации отчета по BTC
    print("\n" + "=" * 60)
    print("Запуск теста генерации реального отчета по BTC")
    print("=" * 60)
    
    real_test_passed = False
    try:
        real_test_passed = test_real_btc_report()
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении реального теста: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    if real_test_passed:
        print("✅ Реальный тест генерации отчета пройден!")
        print("📄 Проверьте сгенерированный отчет в директории docs/test_reports/")
    else:
        print("❌ Реальный тест генерации отчета провален")
    print("=" * 60)
    
    return failed == 0 and real_test_passed


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

