"""TDX minute-data importer with rate-limit handling.

Features:
- Auto-detects TDX rate limiting and backs off
- Exponential backoff on empty results
- Per-stock progress tracking (resume support)
- Reconnects on connection errors

Usage::

    python -m tradingagents.dataflows.a_stock.tdx_importer --years 1
    python -m tradingagents.dataflows.a_stock.tdx_importer --status
    python -m tradingagents.dataflows.a_stock.tdx_importer --reset
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from tradingagents.cache.manager import _get_pg_pool

logger = logging.getLogger(__name__)

TDX_FREQUENCY = {"1m": 8, "5m": 0, "15m": 1, "30m": 2, "60m": 3}
PROGRESS_FILE = Path(__file__).parent / ".tdx_progress" / "state.json"

# Rate limiting
INITIAL_DELAY = 0.5      # Start with 0.5s between requests
MAX_DELAY = 30.0         # Max 30s backoff
BACKOFF_FACTOR = 2.0     # Double delay on empty results
RECOVERY_FACTOR = 0.9    # Slowly reduce delay on success
EMPTY_THRESHOLD = 5      # After this many empty results, back off hard


def get_all_astock_codes() -> list[str]:
    """Get all A-share stock codes."""
    import requests
    session = requests.Session()
    session.trust_env = False

    all_codes = []
    page_size = 100
    page = 1

    while True:
        try:
            url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            params = {"page": page, "num": page_size, "sort": "symbol", "asc": "1", "node": "hs_a", "symbol": "", "_s_r_a": "init"}
            r = session.get(url, params=params, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            for item in data:
                code = item.get("code", "")
                if code and len(code) == 6 and code.isdigit() and code[0] in ("0", "3", "6"):
                    all_codes.append(code)
            if len(data) < page_size:
                break
            page += 1
            time.sleep(0.1)
        except Exception as exc:
            logger.warning("Failed to fetch stock list page %d: %s", page, exc)
            break

    seen = set()
    return [c for c in all_codes if not (c in seen or seen.add(c))]


def load_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return {"completed_stocks": [], "total_bars": 0, "total_days": 0}
    try:
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"completed_stocks": [], "total_bars": 0, "total_days": 0}


def save_progress(state: dict) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(PROGRESS_FILE)


def get_existing_dates(pool, code: str) -> set[str]:
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT trade_date FROM data_history WHERE ticker = %s AND data_type = 'kline_1min'", (code,))
            return {str(row[0]) for row in cur.fetchall()}
    finally:
        pool.putconn(conn)


def import_stock(code: str, years: float, pool, delay: float) -> tuple[int, int, float]:
    """Import 1-min data for one stock with adaptive rate limiting."""
    from mootdx.quotes import Quotes

    existing_dates = get_existing_dates(pool, code)
    imported_days = 0
    imported_bars = 0
    current_delay = delay
    empty_count = 0
    start = 0
    max_requests = int(years * 365.25 * 4)

    client = None

    for _ in range(max_requests):
        try:
            if client is None:
                client = Quotes.factory(market='std')

            df = client.bars(symbol=code, frequency=8, start=start, offset=800)

            if df is None or df.empty:
                empty_count += 1
                if empty_count >= 3:
                    # Back off
                    current_delay = min(current_delay * BACKOFF_FACTOR, MAX_DELAY)
                    logger.debug(f"{code}: empty result, backing off to {current_delay:.1f}s")
                    time.sleep(current_delay)
                    # Recreate client
                    try:
                        client = Quotes.factory(market='std')
                    except Exception:
                        pass
                    if empty_count >= 10:
                        # Give up on this stock
                        logger.info(f"{code}: too many empty results, skipping")
                        break
                continue

            # Reset empty count on success
            empty_count = 0
            current_delay = max(current_delay * RECOVERY_FACTOR, INITIAL_DELAY)

            # Group by date
            by_date: dict[str, list[dict]] = {}
            for idx, row in df.iterrows():
                dt_val = str(idx)[:16]
                trade_date = dt_val[:10]
                if trade_date in existing_dates:
                    continue
                bar = {
                    "date": dt_val,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0) or 0),
                }
                by_date.setdefault(trade_date, []).append(bar)

            if not by_date:
                # No new data
                break

            # Insert
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    for td, bars in sorted(by_date.items()):
                        cur.execute(
                            """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                               VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                               ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                                 result = EXCLUDED.result, updated_at = EXCLUDED.updated_at
                               WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                            (code, "kline_1min", td, "1min", json.dumps(bars, ensure_ascii=False), time.time()),
                        )
                        imported_bars += len(bars)
                        if td not in existing_dates:
                            existing_dates.add(td)
                            imported_days += 1
                conn.commit()
            except Exception:
                conn.rollback()
            finally:
                pool.putconn(conn)

            start += 800
            time.sleep(current_delay)

        except Exception as exc:
            logger.debug(f"{code}: error - {exc}")
            empty_count += 1
            current_delay = min(current_delay * BACKOFF_FACTOR, MAX_DELAY)
            time.sleep(current_delay)
            client = None  # Force reconnect

    return imported_days, imported_bars, current_delay


def main():
    parser = argparse.ArgumentParser(description="TDX minute data importer")
    parser.add_argument("--tickers", type=str, default=None)
    parser.add_argument("--years", type=float, default=1)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--delay", type=float, default=INITIAL_DELAY)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("tdx_import.log", mode="a")],
    )

    pool = _get_pg_pool()
    if pool is None:
        logger.error("PostgreSQL not available")
        sys.exit(1)

    state = load_progress()

    if args.reset:
        state = {"completed_stocks": [], "total_bars": 0, "total_days": 0}
        save_progress(state)
        logger.info("Progress reset")
        return

    if args.status:
        completed = state.get("completed_stocks", [])
        logger.info(f"Progress: {len(completed)} stocks, {state.get('total_days', 0)} days, {state.get('total_bars', 0)} bars")
        return

    if args.tickers:
        tickers = [t.strip().zfill(6) for t in args.tickers.split(",") if t.strip()]
    else:
        logger.info("Fetching all A-share stock codes...")
        tickers = get_all_astock_codes()
        logger.info(f"Found {len(tickers)} A-share stocks")

    if not tickers:
        logger.error("No tickers to import")
        sys.exit(1)

    completed = set(state.get("completed_stocks", []))
    remaining = [t for t in tickers if t not in completed]
    logger.info(f"Already completed: {len(completed)}, Remaining: {len(remaining)}")

    total_bars = state.get("total_bars", 0)
    total_days = state.get("total_days", 0)
    start_time = time.time()
    last_save = time.time()
    current_delay = args.delay

    for i, code in enumerate(remaining):
        logger.info(f"Importing {code} ({i+1}/{len(remaining)})...")
        days, bars, current_delay = import_stock(code, args.years, pool, current_delay)
        total_days += days
        total_bars += bars

        completed.add(code)
        state["completed_stocks"] = sorted(completed)
        state["total_bars"] = total_bars
        state["total_days"] = total_days

        if time.time() - last_save > 60:
            save_progress(state)
            last_save = time.time()

        if (i + 1) % 10 == 0 or i == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(remaining) - i - 1) / rate if rate > 0 else 0
            logger.info(
                f"Progress: {i+1}/{len(remaining)}, {total_days} days, {total_bars} bars, "
                f"delay={current_delay:.1f}s, ETA: {timedelta(seconds=int(eta))}"
            )

    save_progress(state)
    logger.info(f"Done! {total_bars} bars for {len(tickers)} stocks")


if __name__ == "__main__":
    main()
