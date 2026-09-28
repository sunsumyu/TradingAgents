"""Vendor API fetchers for chart data.

All functions are I/O-bound (HTTP / TCP) and may block.  Caching is handled
via the ``data_cache`` layer.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

import pandas as pd

from tradingagents.cache import get_cache
from tradingagents.cache.manager import _get_pg_pool
from tradingagents.config import TD_DSN

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
    def _source():
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
                        return None
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
            return result
        except Exception as exc:
            logger.warning("Failed to fetch OHLCV for %s: %s", symbol, exc)
            return None

    mgr = get_cache(symbol)
    with mgr.fetch("ohlcv", start_date, source_fn=_source) as (data, hit):
        return data


# ---------------------------------------------------------------------------
# Indicator fetching
# ---------------------------------------------------------------------------

def fetch_indicator(
    symbol: str, indicator: str, curr_date: str, look_back_days: int = 30
) -> str | None:
    """Fetch a single technical indicator via the vendor routing layer."""
    def _source():
        try:
            from tradingagents.dataflows.interface import route_to_vendor
            result = route_to_vendor("get_indicators", symbol, indicator, curr_date, look_back_days)
            return result
        except Exception as exc:
            logger.warning("Failed to fetch indicator %s for %s: %s", indicator, symbol, exc)
            return None

    mgr = get_cache(symbol)
    with mgr.fetch("indicator", curr_date, source_fn=_source) as (data, hit):
        return data


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

MINUTE_BAR_LIMIT = 2000  # A 股分钟线上限（60min: ~2 年，30min: ~1 年，15min: ~6 个月）


def is_minute_interval(interval: str | None) -> bool:
    """Return True if ``interval`` names a supported minute granularity."""
    return interval in MINUTE_TDX_FREQUENCY


def fetch_minute_astock(
    symbol: str,
    frequency_code: int,
    bar_count: int,
) -> list[dict[str, Any]]:
    """Fetch minute OHLCV bars for an A-share symbol.

    Strategy:
      1. Query local PG archive (data_history) for the exact interval
      2. If not enough, aggregate from 1min data in PG
      3. For 60m: supplement with fresh Sina data
      4. Fall back to mootdx if local archive is empty
    """
    code = symbol.split(".")[0].zfill(6)
    interval_label = _frequency_to_label(frequency_code)
    interval_min = _label_to_minutes(interval_label)

    # Try local archive for the exact interval
    local_bars = _fetch_local_minute(code, interval_label, bar_count)
    if len(local_bars) >= bar_count:
        return local_bars[:bar_count]

    # If we have 1min data in PG, aggregate to target interval
    if interval_min > 1:
        aggregated = _aggregate_local_minutes(code, interval_min, bar_count)
        if len(aggregated) >= bar_count:
            return aggregated[:bar_count]
        local_bars = aggregated

    # For 60m: supplement with fresh Sina data
    if frequency_code == MINUTE_TDX_FREQUENCY.get("60m"):
        fresh = _fetch_fresh_60min(code, bar_count - len(local_bars))
        seen = {b["date"] for b in local_bars}
        for b in fresh:
            if b["date"] not in seen:
                local_bars.append(b)
                seen.add(b["date"])
        local_bars.sort(key=lambda b: b["date"])
        return local_bars[-bar_count:]

    # Non-60-min: mootdx direct
    return _fetch_mootdx_minute(symbol, frequency_code, bar_count)


# TDX interval suffix → data_type label stored by minute_importer.
# Must match _INTERVAL_MAP in minute_importer.py exactly:
#   "1m":  ("kline_1min",  "1min"),
#   "5m":  ("kline_5min",  "5min"),
#   "15m": ("kline_15min", "15min"),
#   "30m": ("kline_30min", "30min"),
#   "60m": ("kline_60min", "60min"),
_INTERVAL_LABEL_MAP = {
    "1m": "kline_1min",
    "5m": "kline_5min",
    "15m": "kline_15min",
    "30m": "kline_30min",
    "60m": "kline_60min",
}


def _frequency_to_label(frequency_code: int) -> str:
    """Convert TDX frequency code to data_history label."""
    for interval, code in MINUTE_TDX_FREQUENCY.items():
        if code == frequency_code:
            return _INTERVAL_LABEL_MAP.get(interval, f"kline_{interval}min")
    return "kline_60min"


def _label_to_minutes(label: str) -> int:
    """Convert data_type label to minutes (e.g. 'kline_5min' -> 5)."""
    if "60min" in label:
        return 60
    if "30min" in label:
        return 30
    if "15min" in label:
        return 15
    if "5min" in label:
        return 5
    if "1min" in label:
        return 1
    return 1


def _aggregate_local_minutes(code: str, target_minutes: int, bar_count: int) -> list[dict[str, Any]]:
    """Aggregate 1min bars from PG into larger intervals."""
    # Fetch enough 1min bars (with multiplier for aggregation)
    bars_1m = _fetch_local_minute(code, "kline_1min", bar_count * target_minutes)
    if not bars_1m:
        return []

    # Ensure chronological order (oldest first)
    bars_1m.sort(key=lambda b: b["date"])

    aggregated = []
    current_chunk: list[dict] = []

    for bar in bars_1m:
        current_chunk.append(bar)
        if len(current_chunk) == target_minutes:
            aggregated.append({
                "date": current_chunk[0]["date"],
                "open": current_chunk[0]["open"],
                "high": max(b["high"] for b in current_chunk),
                "low": min(b["low"] for b in current_chunk),
                "close": current_chunk[-1]["close"],
                "volume": sum(b["volume"] for b in current_chunk),
            })
            current_chunk = []

    # Handle remaining bars
    if current_chunk:
        aggregated.append({
            "date": current_chunk[0]["date"],
            "open": current_chunk[0]["open"],
            "high": max(b["high"] for b in current_chunk),
            "low": min(b["low"] for b in current_chunk),
            "close": current_chunk[-1]["close"],
            "volume": sum(b["volume"] for b in current_chunk),
        })

    return aggregated


_TD_TABLE_MAP = {
    "kline_1min":  ("st_stock_1min",  "st_1min"),
    "kline_5min":  ("st_stock_5min",  "st_5min"),
    "kline_15min": ("st_stock_15min", "st_15min"),
    "kline_30min": ("st_stock_30min", "st_30min"),
    "kline_60min": ("st_stock_60min", "st_60min"),
}


def _fetch_tdengine_minute(code: str, data_type: str, bar_count: int) -> list[dict[str, Any]]:
    """Query TDengine for minute bars. Returns empty list if TDengine unavailable.

    TDengine stores each stock as a child table under a supertable.
    Child table naming: st_<interval>_<code> (e.g. st_60min_600519).
    """
    mapping = _TD_TABLE_MAP.get(data_type)
    if not mapping:
        return []
    stable, prefix = mapping
    child = f"{prefix}_{code}"

    try:
        import taosws
        conn = taosws.connect(TD_DSN)
        cursor = conn.cursor()

        cursor.execute(f"SELECT ts, open, high, low, close, volume, amount FROM {child} ORDER BY ts DESC LIMIT {bar_count}")
        rows = cursor.fetchall()

        bars = []
        for row in rows:
            ts = row[0]
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else str(ts)
            bars.append({
                "date": ts_str[:16],  # "YYYY-MM-DD HH:MM"
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": int(row[5]) if row[5] else 0,
            })
        bars = bars[:bar_count]
        bars.reverse()  # DESC → ascending
        cursor.close()
        conn.close()
        return bars
    except Exception as exc:
        logger.debug("TDengine fetch failed for %s: %s", code, exc)
        return []

    try:
        import taosws
        conn = taosws.connect(TD_DSN)
        cursor = conn.cursor()

        # Get most recent bar_count bars from the child table
        cursor.execute(f"SELECT ts, open, high, low, close, volume, amount FROM {child} ORDER BY ts DESC LIMIT {bar_count}")
        rows = cursor.fetchall()

        bars = []
        for row in rows:
            ts = row[0]
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if hasattr(ts, "strftime") else str(ts)
            bars.append({
                "date": ts_str[:16],  # "YYYY-MM-DD HH:MM"
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": int(row[5]) if row[5] else 0,
            })
        # TDengine returns DESC (newest first). Return newest bar_count bars in ascending order.
        bars = bars[:bar_count]  # Take newest bar_count (already DESC)
        bars.reverse()  # Flip to ascending (oldest first)
        cursor.close()
        conn.close()
        return bars
    except Exception as exc:
        logger.debug("TDengine fetch failed for %s: %s", code, exc)
        return []


def _fetch_local_minute(code: str, data_type: str, bar_count: int) -> list[dict[str, Any]]:
    """Query local archive for minute bars. Tries TDengine first (faster), then PG."""
    td_bars = []
    # Try TDengine first for supported intervals
    if data_type in _TD_TABLE_MAP:
        td_bars = _fetch_tdengine_minute(code, data_type, bar_count)
        if len(td_bars) >= bar_count:
            return td_bars[:bar_count]

    # Fall back to PG
    pool = _get_pg_pool()
    if pool is None:
        return td_bars

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            # For aggregated intervals (60m), need extra rows since multiple bars per day
            multiplier = 4 if "60" in data_type else (2 if "30" in data_type else 1)
            cur.execute(
                """SELECT trade_date, result FROM data_history
                   WHERE ticker = %s AND data_type = %s
                   ORDER BY trade_date DESC LIMIT %s""",
                (code, data_type, bar_count * multiplier),
            )
            rows = cur.fetchall()
    except Exception:
        conn.rollback()
        return td_bars if data_type in ("kline_60min", "kline_1min") else []
    finally:
        pool.putconn(conn)

    bars = []
    for trade_date, result_json in rows:
        data = result_json if isinstance(result_json, (dict, list)) else json.loads(result_json)
        items = data if isinstance(data, list) else [data]
        for bar in items:
            bars.append({
                "date": bar.get("date", str(trade_date)),
                "open": bar.get("open", 0),
                "high": bar.get("high", 0),
                "low": bar.get("low", 0),
                "close": bar.get("close", 0),
                "volume": bar.get("volume", 0),
            })
    bars.sort(key=lambda b: b["date"])
    return bars


def _fetch_local_60min(code: str, bar_count: int) -> list[dict[str, Any]]:
    """Query local PG archive for 60-min bars."""
    pool = _get_pg_pool()
    if pool is None:
        return []

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT trade_date, result FROM data_history
                   WHERE ticker = %s AND data_type = 'kline_60min'
                   ORDER BY trade_date DESC LIMIT %s""",
                (code, bar_count * 4),  # fetch extra to account for multiple bars per day
            )
            rows = cur.fetchall()
    except Exception:
        conn.rollback()
        return []
    finally:
        pool.putconn(conn)

    bars = []
    for trade_date, result_json in rows:
        data = result_json if isinstance(result_json, (dict, list)) else json.loads(result_json)
        items = data if isinstance(data, list) else [data]
        for bar in items:
            bars.append({
                "date": bar.get("date", str(trade_date)),
                "open": bar.get("open", 0),
                "high": bar.get("high", 0),
                "low": bar.get("low", 0),
                "close": bar.get("close", 0),
                "volume": bar.get("volume", 0),
            })
    bars.sort(key=lambda b: b["date"])
    return bars


def _fetch_fresh_60min(code: str, bar_count: int) -> list[dict[str, Any]]:
    """Fetch fresh 60-min bars from Sina (fallback when local archive is shallow)."""
    if bar_count <= 0:
        return []

    import re as _re
    session = requests.Session()
    session.trust_env = False

    prefix = "sh" if code.startswith("6") else "sz"
    url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_{prefix}{code}=/CN_MarketDataService.getKLineData"
    params = {"symbol": f"{prefix}{code}", "scale": "60", "ma": "no", "datalen": str(bar_count)}

    try:
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return []
        match = _re.search(r"=\((\[.*?\])\)", resp.text, re.DOTALL)
        if not match:
            return []
        raw = json.loads(match.group(1))
        return [
            {
                "date": str(item.get("day", "")),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": int(float(item.get("volume", 0))),
            }
            for item in raw
        ]
    except Exception:
        return []


def _fetch_mootdx_minute(
    symbol: str, frequency_code: int, bar_count: int,
) -> list[dict[str, Any]]:
    """Original mootdx-based minute bar fetcher."""
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
