"""Unified HTTP client for financial data sources.

Provides:
- Proxy bypass (for Chinese vendor APIs)
- Automatic retry with exponential backoff
- Consistent error handling
- Request/response logging
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional

import requests

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_DEFAULT_TIMEOUT = 15


class HttpClient:
    """HTTP client with retry, proxy bypass, and error handling.

    Usage::

        client = HttpClient()
        data = client.get_json(url, params={"key": "value"})
    """

    def __init__(
        self,
        timeout: int = _DEFAULT_TIMEOUT,
        retries: int = 3,
        backoff: float = 1.0,
        bypass_proxy: bool = True,
        headers: Optional[dict] = None,
    ):
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.bypass_proxy = bypass_proxy
        self.headers = {**(headers or {}), "User-Agent": _UA}

    def get(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> requests.Response:
        """Make a GET request with retry and proxy bypass."""
        merged_headers = {**self.headers, **(headers or {})}
        merged_timeout = timeout or self.timeout

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                if self.bypass_proxy:
                    with requests.Session() as s:
                        s.trust_env = False
                        return s.get(
                            url,
                            params=params,
                            headers=merged_headers,
                            timeout=merged_timeout,
                        )
                else:
                    return requests.get(
                        url,
                        params=params,
                        headers=merged_headers,
                        timeout=merged_timeout,
                    )
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                if attempt < self.retries:
                    wait = self.backoff * (2 ** (attempt - 1))
                    logger.debug(
                        "HTTP attempt %d/%d failed (%s), retrying in %.1fs...",
                        attempt, self.retries, exc, wait,
                    )
                    time.sleep(wait)
                else:
                    break

        raise last_exc  # type: ignore[misc]

    def get_json(
        self,
        url: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
    ) -> dict:
        """Make a GET request and return JSON response."""
        resp = self.get(url, params=params, headers=headers, timeout=timeout)
        return resp.json()


# Module-level default client instances
default_client = HttpClient()
em_client = HttpClient(  # eastmoney-specific
    retries=3,
    backoff=1.5,
    bypass_proxy=True,
)
sina_client = HttpClient(  # sina-specific
    retries=2,
    backoff=1.0,
    bypass_proxy=True,
)
