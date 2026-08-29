"""DataCenter — unified data access facade.

Wraps the existing ``tradingagents.dataflows`` vendor routing system
with a clean interface, adds SQLite caching, and provides batch
real-time quote fetching.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .cache import CacheManager
from .models import OHLCVBar, Quote, NewsItem, FundamentalData

logger = logging.getLogger(__name__)


class DataCenter:
    """Unified data access layer — deep module with small interface.

    Wraps the existing vendor routing system and adds SQLite caching.
    The chart engine and signal engine both consume this interface.

    Usage::

        dc = DataCenter(cache_dir="~/.tradingagents/cache")
        df = dc.get_ohlcv("600519", "1D", "2025-01-01", "2025-06-01")
        quotes = dc.get_realtime(["600519", "000001"])
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        cache_ttl: int = 86400,
    ) -> None:
        if cache_dir is None:
            from tradingagents.dataflows.config import get_config
            config = get_config()
            cache_dir = config.get("data_cache_dir", "~/.tradingagents/cache")

        self._cache = CacheManager(cache_dir, default_ttl=cache_ttl)
        self._config_cache: dict[str, Any] | None = None

    def _get_config(self) -> dict[str, Any]:
        """Lazy-load config."""
        if self._config_cache is None:
            from tradingagents.dataflows.config import get_config
            self._config_cache = get_config()
        return self._config_cache

    # ── OHLCV data ────────────────────────────────────────────────────────

    def get_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Get OHLCV data with automatic caching.

        Args:
            ticker: Stock ticker (e.g., "600519", "AAPL").
            timeframe: Chart timeframe ("1D", "1W", "1m", etc.).
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            adjust: Price adjustment ("qfq"=forward, "hfq"=backward, "none").
            force_refresh: Skip cache and fetch fresh data.

        Returns:
            DataFrame with columns: date, open, high, low, close, volume.
        """
        # Try cache first
        if not force_refresh:
            cached = self._cache.get_ohlcv(ticker, timeframe, start_date, end_date)
            if cached is not None and not cached.empty:
                return cached

        # Fetch from vendor
        df = self._fetch_ohlcv_from_vendor(ticker, timeframe, start_date, end_date)

        if df is not None and not df.empty:
            self._cache.set_ohlcv(ticker, timeframe, df)
            return df

        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    def _fetch_ohlcv_from_vendor(
        self,
        ticker: str,
        timeframe: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """Fetch OHLCV from the vendor routing system."""
        try:
            from tradingagents.dataflows.stockstats_utils import load_ohlcv

            # load_ohlcv expects (symbol, curr_date) and returns 5 years of data
            # We'll use it for daily data and filter by date range
            df = load_ohlcv(ticker, end_date)

            if df is None or df.empty:
                return None

            # Ensure date column exists
            if "date" not in df.columns:
                if isinstance(df.index, pd.DatetimeIndex):
                    df = df.reset_index()
                    df = df.rename(columns={df.columns[0]: "date"})
                else:
                    df["date"] = pd.to_datetime(df.index)

            # Filter by date range
            df["date"] = pd.to_datetime(df["date"])
            mask = (df["date"] >= start_date) & (df["date"] <= end_date)
            df = df[mask].copy()

            # Ensure required columns
            for col in ["open", "high", "low", "close", "volume"]:
                if col not in df.columns:
                    return None

            return df[["date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)

        except Exception as exc:
            logger.warning("Failed to fetch OHLCV for %s: %s", ticker, exc)
            return None

    # ── Real-time quotes ──────────────────────────────────────────────────

    def get_realtime(
        self,
        tickers: list[str],
    ) -> dict[str, Quote]:
        """Batch fetch real-time quotes.

        Args:
            tickers: List of ticker symbols.

        Returns:
            Dict mapping ticker → Quote. Failed tickers are omitted.
        """
        if not tickers:
            return {}

        # Separate A-share and global tickers
        astock_tickers = [t for t in tickers if self._is_astock(ticker=t)]
        global_tickers = [t for t in tickers if not self._is_astock(ticker=t)]

        quotes: dict[str, Quote] = {}

        # Fetch A-share quotes via Tencent batch API
        if astock_tickers:
            try:
                from tradingagents.dataflows.a_stock.tencent_quote import get_realtime_quotes
                raw_quotes = get_realtime_quotes(astock_tickers)
                if isinstance(raw_quotes, pd.DataFrame):
                    for _, row in raw_quotes.iterrows():
                        ticker = str(row.get("symbol", row.get("code", "")))
                        if ticker:
                            quotes[ticker] = Quote(
                                ticker=ticker,
                                name=str(row.get("name", "")),
                                price=float(row.get("price", row.get("current_price", 0))),
                                change=float(row.get("change", 0)),
                                change_pct=float(row.get("change_pct", row.get("pct_change", 0))),
                                open=float(row.get("open", 0)),
                                high=float(row.get("high", 0)),
                                low=float(row.get("low", 0)),
                                volume=int(row.get("volume", 0)),
                                amount=float(row.get("amount", row.get("turnover", 0))),
                            )
            except Exception as exc:
                logger.warning("Failed to fetch A-share quotes: %s", exc)

        # Fetch global quotes via yfinance
        for ticker in global_tickers:
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                info = stock.fast_info
                price = float(info.get("lastPrice", info.get("last_price", 0)))
                prev_close = float(info.get("previousClose", info.get("previous_close", price)))
                change = price - prev_close
                change_pct = (change / prev_close * 100) if prev_close else 0

                quotes[ticker] = Quote(
                    ticker=ticker,
                    name=ticker,
                    price=price,
                    change=change,
                    change_pct=change_pct,
                    open=float(info.get("open", 0)),
                    high=float(info.get("dayHigh", info.get("day_high", 0))),
                    low=float(info.get("dayLow", info.get("day_low", 0))),
                    volume=int(info.get("lastVolume", info.get("last_volume", 0))),
                    amount=0.0,
                )
            except Exception as exc:
                logger.warning("Failed to fetch quote for %s: %s", ticker, exc)

        return quotes

    def _is_astock(self, ticker: str) -> bool:
        """Check if a ticker is an A-share code."""
        # A-share codes are 6-digit numbers, optionally with .SS/.SZ suffix
        import re
        clean = ticker.split(".")[0]
        return bool(re.match(r"^[0-9]{6}$", clean))

    # ── News ──────────────────────────────────────────────────────────────

    def get_news(
        self,
        ticker: str,
        days: int = 7,
    ) -> list[NewsItem]:
        """Get recent news for a ticker.

        Args:
            ticker: Stock ticker.
            days: Number of days to look back.

        Returns:
            List of NewsItem objects.
        """
        try:
            from tradingagents.dataflows.interface import route_to_vendor
            from datetime import datetime, timedelta

            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = datetime.now().strftime("%Y-%m-%d")

            result = route_to_vendor("get_news", ticker, start_date, end_date)

            if not result or result in ("NO_DATA_AVAILABLE", "DATA_UNAVAILABLE"):
                return []

            # Parse the result text into NewsItem objects
            items = []
            if isinstance(result, str):
                for line in result.split("\n"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 1 and parts[0]:
                        items.append(NewsItem(
                            title=parts[0],
                            publisher=parts[1] if len(parts) > 1 else None,
                            summary=parts[2] if len(parts) > 2 else None,
                            link=parts[3] if len(parts) > 3 else None,
                        ))
            elif isinstance(result, list):
                for item in result:
                    if isinstance(item, dict):
                        items.append(NewsItem(
                            title=item.get("title", ""),
                            publisher=item.get("publisher"),
                            summary=item.get("summary"),
                            link=item.get("link"),
                        ))

            return items[:20]  # Limit to 20 articles

        except Exception as exc:
            logger.warning("Failed to fetch news for %s: %s", ticker, exc)
            return []

    # ── Fundamentals ──────────────────────────────────────────────────────

    def get_fundamental(
        self,
        ticker: str,
    ) -> FundamentalData | None:
        """Get fundamental data for a ticker.

        Args:
            ticker: Stock ticker.

        Returns:
            FundamentalData object, or None if unavailable.
        """
        try:
            from tradingagents.dataflows.interface import route_to_vendor

            result = route_to_vendor("get_fundamentals", ticker, "2025-01-01")

            if not result or result in ("NO_DATA_AVAILABLE", "DATA_UNAVAILABLE"):
                return None

            # Parse key-value pairs from text
            data: dict[str, Any] = {}
            if isinstance(result, str):
                for line in result.split("\n"):
                    line = line.strip()
                    if ":" in line:
                        key, _, value = line.partition(":")
                        data[key.strip()] = value.strip()

            # Map common field names
            def _parse_float(val: Any) -> float | None:
                if val is None:
                    return None
                try:
                    s = str(val).replace(",", "").replace("%", "").strip()
                    return float(s) if s else None
                except (ValueError, TypeError):
                    return None

            return FundamentalData(
                ticker=ticker,
                pe_ratio=_parse_float(data.get("PE Ratio", data.get("市盈率"))),
                pb_ratio=_parse_float(data.get("PB Ratio", data.get("市净率"))),
                ps_ratio=_parse_float(data.get("PS Ratio", data.get("市销率"))),
                market_cap=_parse_float(data.get("Market Cap", data.get("总市值"))),
                dividend_yield=_parse_float(data.get("Dividend Yield", data.get("股息率"))),
                roe=_parse_float(data.get("ROE", data.get("净资产收益率"))),
                extra=data,
            )

        except Exception as exc:
            logger.warning("Failed to fetch fundamentals for %s: %s", ticker, exc)
            return None

    # ── Cache management ──────────────────────────────────────────────────

    def clear_cache(
        self,
        ticker: str | None = None,
        older_than_days: int | None = None,
    ) -> int:
        """Clear cache entries. Returns count of deleted rows."""
        return self._cache.clear(ticker, older_than_days)

    def cache_stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        return self._cache.stats()

    def close(self) -> None:
        """Close all connections."""
        self._cache.close()
