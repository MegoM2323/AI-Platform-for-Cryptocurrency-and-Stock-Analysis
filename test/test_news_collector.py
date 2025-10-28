import types
from data_collectors.news_collector import NewsCollector, NewsCollectorConfig


class DummyResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP error")


class DummySession:
    def __init__(self, response):
        self._response = response

    def get(self, *args, **kwargs):
        return self._response


def test_news_collector_top_headlines_success():
    cfg = NewsCollectorConfig(api_key="x")
    response = DummyResponse({"status": "ok", "articles": [{"title": "A"}]})
    session = DummySession(response)
    nc = NewsCollector(cfg=cfg, session=session)
    data = nc.get_top_headlines(q="bitcoin")
    assert data.get("status") == "ok"
    assert isinstance(data.get("articles"), list)


