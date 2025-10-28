import time
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from config import config as AppConfig
from .rate_limiter import RateLimiter


logger = logging.getLogger(__name__)


class NewsCollectorError(Exception):
    """Ошибка уровня интеграции NewsCollector."""


@dataclass
class NewsCollectorConfig:
    api_key: str
    base_url: str = "https://newsapi.org/v2"
    timeout_seconds: float = 10.0
    max_retries: int = 3
    backoff_seconds: float = 1.0


class NewsCollector:
    """Клиент интеграции с NewsAPI с ретраями и обработкой ошибок.

    Клиент изолирован от БД и кэшей. Ограничение запросов и кэширование
    реализуются отдельными компонентами.
    """

    def __init__(self, cfg: Optional[NewsCollectorConfig] = None, session: Optional[requests.Session] = None, rate_limiter: Optional[RateLimiter] = None) -> None:
        if cfg is None:
            if not AppConfig.NEWSAPI_KEY:
                raise NewsCollectorError("NEWSAPI_KEY отсутствует в конфигурации")
            cfg = NewsCollectorConfig(
                api_key=AppConfig.NEWSAPI_KEY or "",
                base_url=AppConfig.NEWSAPI_BASE_URL,
                timeout_seconds=AppConfig.NEWSAPI_TIMEOUT_SECONDS,
                max_retries=AppConfig.NEWSAPI_MAX_RETRIES,
                backoff_seconds=AppConfig.NEWSAPI_BACKOFF_SECONDS,
            )
        self._cfg = cfg
        self._session = session or requests.Session()
        self._headers = {"Authorization": f"Bearer {self._cfg.api_key}"}
        self._rate_limiter = rate_limiter or RateLimiter()

    def get_top_headlines(self, q: Optional[str] = None, category: Optional[str] = None,
                           language: str = "en", page_size: int = 20, symbol: Optional[str] = None,
                           is_user_requested: bool = False) -> Dict[str, Any]:
        if not self._rate_limiter.can_make_request(is_user_requested=is_user_requested):
            # TODO: фолбэк на кэш (будет реализован в задачах 8.x)
            raise NewsCollectorError("NewsAPI quota exceeded or not available today")
        params: Dict[str, Any] = {
            "language": language,
            "pageSize": page_size,
        }
        if q:
            params["q"] = q
        if category:
            params["category"] = category
        data = self._request("/top-headlines", params)
        self._rate_limiter.record_request(symbol=symbol)
        return data

    def search_everything(self, query: str, from_param: Optional[str] = None,
                           to: Optional[str] = None, language: str = "en",
                           sort_by: str = "publishedAt", page_size: int = 50,
                           symbol: Optional[str] = None, is_user_requested: bool = False) -> Dict[str, Any]:
        if not self._rate_limiter.can_make_request(is_user_requested=is_user_requested):
            # TODO: фолбэк на кэш (будет реализован в задачах 8.x)
            raise NewsCollectorError("NewsAPI quota exceeded or not available today")
        params: Dict[str, Any] = {
            "q": query,
            "language": language,
            "sortBy": sort_by,
            "pageSize": page_size,
        }
        if from_param:
            params["from"] = from_param
        if to:
            params["to"] = to
        data = self._request("/everything", params)
        self._rate_limiter.record_request(symbol=symbol)
        return data

    def get_crypto_headlines(self, language: str = "en", page_size: int = 20,
                             is_user_requested: bool = False) -> Dict[str, Any]:
        return self.get_top_headlines(q="(crypto OR bitcoin OR ethereum)", language=language,
                                      page_size=page_size, is_user_requested=is_user_requested)

    def _request(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._cfg.base_url}{path}"
        attempt = 0
        last_error: Optional[Exception] = None
        merged_params = {**params, "apiKey": self._cfg.api_key}

        while attempt <= self._cfg.max_retries:
            try:
                response = self._session.get(
                    url,
                    params=merged_params,
                    headers=self._headers,
                    timeout=self._cfg.timeout_seconds,
                )
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", self._cfg.backoff_seconds))
                    logger.warning("NewsAPI 429 Too Many Requests, retry after %s s", retry_after)
                    time.sleep(retry_after)
                    attempt += 1
                    continue
                response.raise_for_status()
                data = response.json()
                status = data.get("status")
                if status != "ok":
                    raise NewsCollectorError(f"NewsAPI error status='{status}' message={data}")
                return data
            except (requests.Timeout, requests.ConnectionError) as net_err:
                last_error = net_err
                if attempt >= self._cfg.max_retries:
                    break
                backoff = self._cfg.backoff_seconds * (2 ** attempt)
                logger.warning("NewsAPI network error: %s. Retry in %.1fs", net_err, backoff)
                time.sleep(backoff)
                attempt += 1
            except requests.HTTPError as http_err:
                code = getattr(http_err.response, "status_code", None)
                if code and 400 <= code < 500 and code != 429:
                    raise NewsCollectorError(f"HTTP {code}: {http_err}") from http_err
                last_error = http_err
                if attempt >= self._cfg.max_retries:
                    break
                backoff = self._cfg.backoff_seconds * (2 ** attempt)
                logger.warning("NewsAPI HTTP error: %s. Retry in %.1fs", http_err, backoff)
                time.sleep(backoff)
                attempt += 1
            except ValueError as json_err:
                raise NewsCollectorError(f"Invalid JSON response: {json_err}") from json_err
            except Exception as unexpected:
                raise NewsCollectorError(f"Unexpected error: {unexpected}") from unexpected

        raise NewsCollectorError(f"Failed to fetch from NewsAPI after {self._cfg.max_retries} retries: {last_error}")


