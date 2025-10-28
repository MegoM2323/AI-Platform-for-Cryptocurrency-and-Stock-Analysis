from analysis.sentiment_analyzer import SentimentAnalyzer


def test_article_sentiment_positive():
    sa = SentimentAnalyzer()
    s = sa.analyze_article_sentiment("ETF approved for Bitcoin", None, None)
    assert s.score > 0
    assert s.label in ("positive", "neutral")


def test_overall_sentiment_average():
    sa = SentimentAnalyzer()
    scores = [sa.analyze_article_sentiment("rise", None, None), sa.analyze_article_sentiment("drop", None, None)]
    overall = sa.calculate_overall_sentiment(scores)
    assert -1 <= overall.score <= 1


