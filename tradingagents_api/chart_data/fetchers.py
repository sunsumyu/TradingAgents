"""Vendor API fetchers for chart data.

All functions are I/O-bound (HTTP / TCP) and may block.  Caching is handled
via the ``data_cache`` layer.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from tradingagents.data_cache import cached_fetch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_astock_symbol(symbol: str) -> bool:
    """Return True if the symbol looks like a 6-digit A-share code."""
    code = symbol.strip().split(".")[0]
    return code.isdigit() and len(code) == 6


# ---------------------------------------------------------------------------
# OHLCV fetching
# ---------------------------------------------------------------------------

def fetch_ohlcv(
    symbol: str, start_date: str, end_date: str
) -> str | None:
    """Fetch OHLCV CSV via the vendor routing layer.

    For A-stock tickers (6-digit codes), the a_stock vendor is tried first
    directly, bypassing the user's ``data_vendors`` config.

    Returns the CSV text on success, or ``None`` if no data is available.
    """
    with cached_fetch(symbol, "ohlcv", ticker=symbol, start=start_date, end=end_date) as ctx:
        if ctx.hit:
            return ctx.value

        if _is_astock_symbol(symbol):
            try:
                from tradingagents.dataflows.a_stock import get_stock_data as astock_get
                result = astock_get(symbol, start_date, end_date)
                if isinstance(result, str):
                    _is_error = (
                        not result.startswith("#")
                        or "失败" in result
                        or "不可用" in result
                        or "NO_DATA" in result
                        or "No data found" in result
                    )
                    if _is_error:
                        logger.warning("A-stock OHLCV error for %s: %s", symbol, result[:120])
                    else:
                        ctx.store(result)
                        return result
            except Exception as exc:
                logger.warning("A-stock vendor failed for %s: %s, trying generic route", symbol, exc)

        try:
            from tradingagents.dataflows.interface import route_to_vendor
            result = route_to_vendor("get_stock_data", symbol, start_date, end_date)
            if isinstance(result, str) and (
                result.startswith("NO_DATA_AVAILABLE") or result.startswith("DATA_UNAVAILABLE")
            ):
                logger.warning("OHLCV unavailable for %s: %s", symbol, result[:120])
                return None
            ctx.store(result)
            return result
        except Exception as exc:
            logger.warning("Failed to fetch OHLCV for %s: %s", symbol, exc)
            return None


# ---------------------------------------------------------------------------
# Indicator fetching
# ---------------------------------------------------------------------------

def fetch_indicator(
    symbol: str, indicator: str, curr_date: str, look_back_days: int = 30
) -> str | None:
    """Fetch a single technical indicator via the vendor routing layer."""
    with cached_fetch(symbol, "indicator", ticker=symbol, indicator=indicator,
                      date=curr_date, look_back=look_back_days) as ctx:
        if ctx.hit:
            return ctx.value

        try:
            from tradingagents.dataflows.interface import route_to_vendor
            result = route_to_vendor("get_indicators", symbol, indicator, curr_date, look_back_days)
            ctx.store(result)
            return result
        except Exception as exc:
            logger.warning("Failed to fetch indicator %s for %s: %s", indicator, symbol, exc)
            return None


# ---------------------------------------------------------------------------
# Minute-bar fetching
# ---------------------------------------------------------------------------

MINUTE_TDX_FREQUENCY = {"1m": 8, "5m": 0, "15m": 1, "30m": 2, "60m": 3}

_YF_MINUTE_PERIOD_CAP = {
    "1m": "7d",
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
}

MINUTE_BAR_LIMIT = 800


def is_minute_interval(interval: str | None) -> bool:
    """Return True if ``interval`` names a supported minute granularity."""
    return interval in MINUTE_TDX_FREQUENCY


def fetch_minute_astock(
    symbol: str,
    frequency_code: int,
    bar_count: int,
) -> list[dict[str, Any]]:
    """Fetch minute OHLCV bars for an A-share symbol via mootdx (TDX)."""
    from mootdx.quotes import Quotes

    client = Quotes.factory(market="std")
    seen: dict[str, dict[str, Any]] = {}
    page_size = 240

    for start in range(0, 4000, page_size):
        df = client.bars(
            symbol=symbol.split(".")[0],
            frequency=frequency_code,
            start=start,
            offset=page_size,
        )
        if df is None or len(df) == 0:
            break

        new_rows = 0
        for _, row in df.iterrows():
            dt_val = row.get("datetime")
            if dt_val is None or pd.isna(dt_val):
                continue
            key = str(dt_val)[:16]
            if key in seen:
                continue
            try:
                seen[key] = {
                    "date": key,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0) or 0),
                }
                new_rows += 1
            except (KeyError, TypeError, ValueError):
                continue

        if len(seen) >= bar_count or new_rows == 0:
            break

    records = [seen[k] for k in sorted(seen)]
    return list(reversed(records))[:bar_count]


def fetch_minute_global(
    symbol: str,
    interval: str,
    days: int,
) -> list[dict[str, Any]]:
    """Fetch minute OHLCV bars for a global symbol via yfinance."""
    import yfinance as yf
    from tradingagents.dataflows.stockstats_utils import yf_retry

    canonical = symbol.upper().split(".")[0]
    period = _YF_MINUTE_PERIOD_CAP.get(interval, "5d")
    data = yf_retry(lambda: yf.Ticker(canonical).history(period=period, interval=interval))

    if data is None or data.empty:
        return []

    if data.index.tz is not None:
        data.index = data.index.tz_localize(None)

    records: list[dict[str, Any]] = []
    for idx, row in data.iterrows():
        ts = pd.Timestamp(idx)
        records.append(
            {
                "date": ts.strftime("%Y-%m-%d %H:%M"),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": float(row["Volume"]),
            }
        )

    return list(reversed(records))[:MINUTE_BAR_LIMIT]


# ---------------------------------------------------------------------------
# Fund flow fetching
# ---------------------------------------------------------------------------

def fetch_fund_flow_data(
    ticker: str, date: str
) -> dict[str, list] | None:
    """Fetch and parse fund flow + northbound data for an A-share ticker.

    Returns merged data dict or None on failure.
    """
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        from .parsers import parse_fund_flow_text, parse_northbound_text

        ff_text = route_to_vendor("get_fund_flow", ticker, date, True)
        ff_parsed = parse_fund_flow_text(ff_text) if ff_text else {}

        nb_text = route_to_vendor("get_northbound_flow", date, True)
        nb_parsed = parse_northbound_text(nb_text) if nb_text else {}

        if not ff_parsed.get("dates"):
            return None

        ff_map = dict(zip(ff_parsed["dates"], zip(
            ff_parsed["mainForce"], ff_parsed["retail"]
        )))
        nb_map = dict(zip(nb_parsed.get("dates", []),
                          nb_parsed.get("values", [])))
        common = sorted(d for d in ff_map if d in nb_map)
        if not common:
            common = sorted(ff_parsed["dates"])

        return {
            "dates": common,
            "northbound": [nb_map.get(d, 0.0) for d in common],
            "mainForce": [ff_map[d][0] for d in common],
            "retail": [ff_map[d][1] for d in common],
        }
    except Exception as exc:
        logger.warning("Fund flow fetch failed for %s: %s", ticker, exc)
        return None
