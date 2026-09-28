"""Hourly (60-min) kline collector — accumulates local history in PostgreSQL.

A-share free data sources (TDX/Sina) only provide ~1 month of 60-min bars.
This collector runs periodically during/after trading hours, fetching the latest
60-min bars from Sina and appending new ones to ``data_history``.

Over time the local archive grows, so older hourly data becomes queryable even
though the upstream source only keeps a shallow window.

Usage::

    # One-shot collection for a list of tickers
    python -m tradingagents.dataflows.a_stock.hourly_collector --tickers 001232,600519

    # Start the scheduler (collects every trading day at 15:30)
    python -m tradingagents.dataflows.a_stock.hourly_collector --daemon
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timedelta

import requests

from tradingagents.cache.manager import _get_pg_pool

logger = logging.getLogger(__name__)

_SINA_URL = "https://quotes.sina.cn/cn/api/jsonp_v2.php"
_SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
}


def _sina_60min_bars(symbol: str, datalen: int = 200) -> list[dict] | None:
    """Fetch 60-min bars from Sina for a single A-share symbol.

    Returns list of {date, open, high, low, close, volume} dicts, or None on failure.
    """
    prefix = "sh" if symbol.startswith("6") else "sz"
    url = f"{_SINA_URL}/var%20_{prefix}{symbol}=/CN_MarketDataService.getKLineData"
    params = {"symbol": f"{prefix}{symbol}", "scale": "60", "ma": "no", "datalen": str(datalen)}

    session = requests.Session()
    session.trust_env = False
    try:
        resp = session.get(url, params=params, headers=_SINA_HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
        match = re.search(r"=\((\[.*?\])\)", resp.text, re.DOTALL)
        if not match:
            return None
        raw = json.loads(match.group(1))
        bars = []
        for item in raw:
            bars.append({
                "date": str(item.get("day", "")),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": int(float(item.get("volume", 0))),
            })
        return bars
    except Exception as exc:
        logger.warning("Sina 60min fetch failed for %s: %s", symbol, exc)
        return None


def collect_for_ticker(symbol: str, datalen: int = 200) -> int:
    """Collect 60-min bars for one ticker into data_history.

    Groups bars by trade_date and stores as a JSON array so all 4 intraday
    bars per day are preserved (no primary-key collision).

    Returns the number of new/updated day-rows inserted.
    """
    bars = _sina_60min_bars(symbol, datalen=datalen)
    if not bars:
        logger.info("No 60min data for %s", symbol)
        return 0

    pool = _get_pg_pool()
    if pool is None:
        logger.warning("PostgreSQL not available, cannot archive %s", symbol)
        return 0

    # Normalize ticker: ensure 6-digit code
    code = symbol.strip().split(".")[0]
    ticker = code.zfill(6)

    # Group bars by trade_date
    by_date: dict[str, list[dict]] = {}
    for bar in bars:
        trade_date = bar["date"][:10]  # YYYY-MM-DD
        by_date.setdefault(trade_date, []).append(bar)

    inserted = 0
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            for trade_date, day_bars in by_date.items():
                cur.execute(
                    """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                       VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                       ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                         result = EXCLUDED.result,
                         updated_at = EXCLUDED.updated_at
                       WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                    (ticker, "kline_60min", trade_date, "60min",
                     json.dumps(day_bars, ensure_ascii=False), time.time()),
                )
                inserted += 1
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("Archive write failed for %s: %s", ticker, exc)
    finally:
        pool.putconn(conn)

    total_bars = sum(len(v) for v in by_date.values())
    if inserted:
        logger.info("Collected %d day-rows (%d bars total) for %s", inserted, total_bars, ticker)
    return inserted


def collect_batch(tickers: list[str], datalen: int = 200) -> dict[str, int]:
    """Collect 60-min bars for multiple tickers."""
    results = {}
    for t in tickers:
        results[t] = collect_for_ticker(t, datalen=datalen)
    return results


def _daemon_loop(tickers: list[str], interval_hours: int = 1):
    """Run collection every `interval_hours` hours."""
    logger.info("Hourly collector daemon started for %d tickers, interval=%dh", len(tickers), interval_hours)
    while True:
        try:
            now = datetime.now()
            # Only collect during/after trading hours (9:30-15:30)
            t_minutes = now.hour * 60 + now.minute
            if 9 * 60 + 30 <= t_minutes <= 15 * 60 + 30:
                logger.info("Running collection at %s", now.strftime("%Y-%m-%d %H:%M:%S"))
                results = collect_batch(tickers)
                total = sum(results.values())
                logger.info("Collected %d new bars total", total)
            else:
                logger.debug("Outside trading hours, skipping")
        except Exception as exc:
            logger.warning("Collection cycle failed: %s", exc)
        time.sleep(interval_hours * 3600)


def _get_all_tickers_from_pg() -> list[str]:
    """Fetch all distinct tickers from data_history (kline_60min)."""
    pool = _get_pg_pool()
    if pool is None:
        logger.error("PostgreSQL not available, cannot fetch ticker list")
        return []
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT ticker FROM data_history WHERE data_type='kline_60min' ORDER BY ticker")
            tickers = [r[0] for r in cur.fetchall()]
        return tickers
    finally:
        pool.putconn(conn)


def main():
    parser = argparse.ArgumentParser(description="60-min kline collector")
    parser.add_argument("--tickers", help="Comma-separated stock codes")
    parser.add_argument("--all", action="store_true", help="Fetch all tickers from PostgreSQL")
    parser.add_argument("--datalen", type=int, default=200, help="Bars to fetch per ticker")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--interval", type=int, default=1, help="Daemon interval in hours")
    args = parser.parse_args()

    if args.all:
        tickers = _get_all_tickers_from_pg()
        logger.info("Fetched %d tickers from PostgreSQL", len(tickers))
    elif args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    else:
        parser.error("Either --tickers or --all is required")

    if not tickers:
        logger.error("No tickers to collect")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    if args.daemon:
        _daemon_loop(tickers, interval_hours=args.interval)
    else:
        results = collect_batch(tickers, datalen=args.datalen)
        for t, n in results.items():
            print(f"{t}: {n} new bars")


if __name__ == "__main__":
    main()
