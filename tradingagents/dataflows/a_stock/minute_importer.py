"""A-share minute-data importer — downloads historical minute bars from Tencent
and bulk-loads them into PostgreSQL ``data_history``.

Tencent's free API (web.ifzq.gtimg.cn) provides 1-minute bars for any trading
day going back several years.  Each request returns one full day of minute data
(~240 bars for A-shares).  We iterate over trading days and insert into PG.

Usage::

    # Import 3 years of 1-min data for one stock
    python -m tradingagents.dataflows.a_stock.minute_importer \
        --tickers 001232 --interval 1m --years 3

    # Import from already-downloaded CSV files
    python -m tradingagents.dataflows.a_stock.minute_importer \
        --csv-dir ./data/minute_csv --interval 1m

    # Batch import for multiple stocks
    python -m tradingagents.dataflows.a_stock.minute_importer \
        --tickers 001232,600519,000001 --interval 1m --years 2

Intervals: 1m, 5m, 15m, 30m, 60m
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

from tradingagents.cache.manager import _get_pg_pool

logger = logging.getLogger(__name__)

# Interval → (data_type label, param_hash)
_INTERVAL_MAP = {
    "1m":  ("kline_1min",  "1min"),
    "5m":  ("kline_5min",  "5min"),
    "15m": ("kline_15min", "15min"),
    "30m": ("kline_30min", "30min"),
    "60m": ("kline_60min", "60min"),
}

_TENCENT_URL = "http://web.ifzq.gtimg.cn/appstock/app/minute/query"
_TENCENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://finance.qq.com",
}


def _fetch_tencent_minute(code: str, date_str: str) -> list[dict]:
    """Fetch 1-minute bars from Tencent for a specific trading day.

    Args:
        code: 6-digit stock code (e.g. "001232")
        date_str: Date in YYYYMMDD format (e.g. "20260908")

    Returns:
        List of {date, open, high, low, close, volume} dicts.
    """
    import requests

    session = requests.Session()
    session.trust_env = False

    params = {"code": f"sz{code}", "date": date_str}

    try:
        r = session.get(_TENCENT_URL, params=params, headers=_TENCENT_HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        data = r.json()
        if data.get("code") != 0:
            return []

        day_data = data.get("data", {}).get(f"sz{code}", {}).get("data", {}).get("data", [])
        if not day_data:
            return []

        bars = []
        for bar_str in day_data:
            parts = bar_str.split()
            if len(parts) < 4:
                continue
            # Format: "HHMM price volume amount"
            time_str = parts[0]
            price = float(parts[1])
            volume = int(float(parts[2]))

            # Convert time to HH:MM format
            if len(time_str) == 4:
                hh = time_str[:2]
                mm = time_str[2:]
            else:
                hh = time_str[:-2].zfill(2)
                mm = time_str[-2:]

            dt_val = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {hh}:{mm}"

            bars.append({
                "date": dt_val,
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            })

        return bars
    except Exception as exc:
        logger.debug("Tencent fetch failed for %s %s: %s", code, date_str, exc)
        return []


def _fetch_tencent_5min(code: str, date_str: str) -> list[dict]:
    """Fetch 5-minute bars from Tencent for a specific trading day."""
    import requests

    session = requests.Session()
    session.trust_env = False

    # Tencent 5min uses mkline API
    url = "http://web.ifzq.gtimg.cn/appstock/app/kline/mkline"
    params = {"param": f"sz{code},m5,,600"}

    try:
        r = session.get(url, params=params, headers=_TENCENT_HEADERS, timeout=15)
        if r.status_code != 200:
            return []

        data = r.json()
        if data.get("code") != 0:
            return []

        day_data = data.get("data", {}).get(f"sz{code}", {}).get("m5", [])
        if not day_data:
            return []

        bars = []
        for item in day_data:
            # Format: ["2026-09-08 09:35", "168.75", "167.00", "165.22", "165.80", "380"]
            dt_val = item[0]  # "2026-09-08 09:35"
            bars.append({
                "date": dt_val,
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": int(float(item[5])),
            })

        return bars
    except Exception as exc:
        logger.debug("Tencent 5min fetch failed for %s %s: %s", code, date_str, exc)
        return []


def _trading_days_in_range(start_date: datetime, end_date: datetime) -> list[str]:
    """Generate list of trading days (YYYYMMDD) between start and end.

    This is approximate — it skips weekends.  Actual trading holidays are
    handled gracefully (no data returned for non-trading days).
    """
    days = []
    current = start_date
    # Normalize to date for comparison
    end = end_date if isinstance(end_date, datetime) else datetime(end_date.year, end_date.month, end_date.day)
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            days.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return days


def import_minute_data(
    tickers: list[str],
    interval: str = "1m",
    years: int = 3,
    csv_dir: str | None = None,
) -> dict[str, int]:
    """Import minute data for multiple tickers into data_history.

    Returns dict of {ticker: bars_imported}.
    """
    if interval not in _INTERVAL_MAP:
        logger.error("Unsupported interval: %s (choose from %s)", interval, list(_INTERVAL_MAP.keys()))
        return {}

    data_type, param_hash = _INTERVAL_MAP[interval]
    pool = _get_pg_pool()
    if pool is None:
        logger.error("PostgreSQL not available")
        return {}

    results: dict[str, int] = {}

    for ticker in tickers:
        code = ticker.strip().split(".")[0].zfill(6)
        logger.info("Importing %s %s (%d years)...", code, interval, years)

        total_bars = 0
        conn = pool.getconn()
        try:
            if csv_dir:
                total_bars = _import_from_csv(conn, code, data_type, param_hash, csv_dir, interval)
            else:
                total_bars = _import_from_api(conn, code, data_type, param_hash, interval, years)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error("Import failed for %s: %s", code, exc)
        finally:
            pool.putconn(conn)

        results[code] = total_bars
        logger.info("Done: %s — %d bars imported", code, total_bars)

    return results


def _import_from_api(
    conn,
    code: str,
    data_type: str,
    param_hash: str,
    interval: str,
    years: int,
) -> int:
    """Download from Tencent and insert into PG."""
    today = datetime.now()
    start_date = today.replace(year=today.year - years)
    trading_days = _trading_days_in_range(start_date, today)

    total_bars = 0
    fetched_days = 0

    for day_str in trading_days:
        if interval == "1m":
            bars = _fetch_tencent_minute(code, day_str)
        elif interval == "5m":
            bars = _fetch_tencent_5min(code, day_str)
        else:
            # For other intervals, aggregate from 1min
            bars = _aggregate_from_1min(code, day_str, interval)

        if not bars:
            continue

        # Group by trade_date
        by_date: dict[str, list[dict]] = {}
        for bar in bars:
            trade_date = bar["date"][:10]
            by_date.setdefault(trade_date, []).append(bar)

        # Insert each day
        with conn.cursor() as cur:
            for trade_date, day_bars in by_date.items():
                cur.execute(
                    """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                       VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                       ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                         result = EXCLUDED.result,
                         updated_at = EXCLUDED.updated_at
                       WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                    (code, data_type, trade_date, param_hash,
                     json.dumps(day_bars, ensure_ascii=False), time.time()),
                )
                total_bars += len(day_bars)

        fetched_days += 1
        if fetched_days % 50 == 0:
            logger.info("  Progress: %d/%d days, %d bars", fetched_days, len(trading_days), total_bars)

        # Rate limit: be gentle on Tencent's API
        time.sleep(0.05)

    return total_bars


def _aggregate_from_1min(code: str, day_str: str, interval: str) -> list[dict]:
    """Aggregate 1-minute bars into larger intervals (15m, 30m, 60m)."""
    bars_1m = _fetch_tencent_minute(code, day_str)
    if not bars_1m:
        return []

    interval_min = int(interval.replace("m", ""))
    if interval_min not in (15, 30, 60):
        return bars_1m

    aggregated = []
    current_chunk = []

    for bar in bars_1m:
        current_chunk.append(bar)
        if len(current_chunk) == interval_min:
            # Aggregate
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


def _import_from_csv(
    conn,
    code: str,
    data_type: str,
    param_hash: str,
    csv_dir: str,
    interval: str,
) -> int:
    """Import from pre-downloaded CSV files."""
    csv_path = Path(csv_dir)
    if not csv_path.exists():
        logger.error("CSV directory not found: %s", csv_dir)
        return 0

    # Look for files matching the code
    patterns = [
        csv_path / f"{code}.csv",
        csv_path / f"{code}_{interval}.csv",
    ]

    total_bars = 0
    for pattern in patterns:
        if not pattern.exists():
            continue

        logger.info("  Importing from %s", pattern.name)
        try:
            import pandas as pd
            df = pd.read_csv(pattern)
            if df.empty:
                continue

            # Normalize column names
            df.columns = [c.strip().lower() for c in df.columns]

            # Find datetime column
            dt_col = None
            for candidate in ["day", "时间", "datetime", "date", "timestamp"]:
                if candidate in df.columns:
                    dt_col = candidate
                    break
            if dt_col is None:
                logger.warning("  No datetime column in %s, skipping", pattern.name)
                continue

            bars = []
            for _, row in df.iterrows():
                dt_val = str(row.get(dt_col, ""))
                if not dt_val or dt_val == "nan":
                    continue
                bars.append({
                    "date": dt_val[:16],
                    "open": float(row.get("open", 0) or 0),
                    "high": float(row.get("high", 0) or 0),
                    "low": float(row.get("low", 0) or 0),
                    "close": float(row.get("close", 0) or 0),
                    "volume": int(float(row.get("volume", 0) or 0)),
                })

            # Group by trade_date
            by_date: dict[str, list[dict]] = {}
            for bar in bars:
                trade_date = bar["date"][:10]
                by_date.setdefault(trade_date, []).append(bar)

            with conn.cursor() as cur:
                for trade_date, day_bars in by_date.items():
                    cur.execute(
                        """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                           VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                           ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                             result = EXCLUDED.result,
                             updated_at = EXCLUDED.updated_at
                           WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                        (code, data_type, trade_date, param_hash,
                         json.dumps(day_bars, ensure_ascii=False), time.time()),
                    )
                    total_bars += len(day_bars)

        except Exception as exc:
            logger.warning("  Failed to import %s: %s", pattern.name, exc)

    return total_bars


def main():
    parser = argparse.ArgumentParser(description="A-share minute data importer (Tencent source)")
    parser.add_argument("--tickers", required=True, help="Comma-separated stock codes")
    parser.add_argument("--interval", default="1m", choices=list(_INTERVAL_MAP.keys()),
                        help="Minute interval (1m, 5m, 15m, 30m, 60m)")
    parser.add_argument("--years", type=int, default=3, help="Years of history to import")
    parser.add_argument("--csv-dir", type=str, default=None,
                        help="Import from CSV files instead of downloading")
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    results = import_minute_data(tickers, args.interval, args.years, args.csv_dir)
    for t, n in results.items():
        print(f"{t}: {n} bars imported")


if __name__ == "__main__":
    main()
