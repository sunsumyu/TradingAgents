"""Bulk minute-data importer for ALL A-share stocks with resume support.

Downloads 1-min bars from Tencent (primary) or Sina (fallback) for every
A-share stock and stores them in PostgreSQL data_history.

Key features:
- Per-stock resume: tracks completed stocks, skips on restart
- Adaptive rate limiting: auto-adjusts delay based on API responses
- Multi-source: tries Tencent first, falls back to Sina for recent data
- Progress saved every 60 seconds
- Can run for days/weeks without manual intervention

Usage::

    # Import 10 years for all A-shares (resumable)
    python -m tradingagents.dataflows.a_stock.bulk_importer --years 10

    # Import specific stocks
    python -m tradingagents.dataflows.a_stock.bulk_importer \
        --tickers 001232,600519 --years 3

    # Resume interrupted import
    python -m tradingagents.dataflows.a_stock.bulk_importer --years 10

    # Show progress
    python -m tradingagents.dataflows.a_stock.bulk_importer --status

    # Reset and start fresh
    python -m tradingagents.dataflows.a_stock.bulk_importer --reset
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

# ── Data source configuration ────────────────────────────────────────────────

_TENCENT_URL = "http://web.ifzq.gtimg.cn/appstock/app/minute/query"
_TENCENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://finance.qq.com",
}

_SINA_URL = "https://quotes.sina.cn/cn/api/jsonp_v2.php"
_SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://finance.sina.com.cn",
}

# ── Rate limiting ─────────────────────────────────────────────────────────────

INITIAL_DELAY = 0.1   # seconds between requests
MIN_DELAY = 0.05
MAX_DELAY = 5.0
BACKOFF_FACTOR = 2.0
RECOVERY_FACTOR = 0.95
CONSECUTIVE_ERRORS_THRESHOLD = 5  # after this many errors, increase delay

# ── Progress tracking ─────────────────────────────────────────────────────────

PROGRESS_DIR = Path(__file__).parent / ".bulk_progress"
PROGRESS_FILE = PROGRESS_DIR / "import_state.json"


def get_all_astock_codes() -> list[str]:
    """Get all A-share stock codes from Sina HQ node data API."""
    import requests

    session = requests.Session()
    session.trust_env = False

    all_codes = []
    page_size = 100
    page = 1

    while True:
        try:
            url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            params = {
                "page": page,
                "num": page_size,
                "sort": "symbol",
                "asc": "1",
                "node": "hs_a",
                "symbol": "",
                "_s_r_a": "init",
            }
            r = session.get(url, params=params, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            if not data:
                break
            for item in data:
                code = item.get("code", "")
                if code and len(code) == 6 and code.isdigit():
                    if code[0] in ("0", "3", "6"):  # Shanghai + Shenzhen only
                        all_codes.append(code)
            if len(data) < page_size:
                break
            page += 1
            time.sleep(0.1)
        except Exception as exc:
            logger.warning("Failed to fetch stock list page %d: %s", page, exc)
            break

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in all_codes:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def load_progress() -> dict:
    """Load import state from progress file."""
    if not PROGRESS_FILE.exists():
        return {"completed_stocks": [], "current_stock": None, "total_bars": 0, "total_days": 0}
    try:
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"completed_stocks": [], "current_stock": None, "total_bars": 0, "total_days": 0}


def save_progress(state: dict) -> None:
    """Save import state to progress file."""
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PROGRESS_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(PROGRESS_FILE)


def get_existing_dates(pool, code: str) -> set[str]:
    """Get all already-imported dates for a stock."""
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT trade_date FROM data_history WHERE ticker = %s AND data_type = 'kline_1min'",
                (code,),
            )
            return {str(row[0]) for row in cur.fetchall()}
    finally:
        pool.putconn(conn)


def fetch_tencent_day(code: str, date_str: str) -> list[dict] | None:
    """Fetch 1-min bars for one stock on one day from Tencent."""
    import requests

    prefix = "sh" if code.startswith("6") else "sz"
    session = requests.Session()
    # 不要设置 trust_env = False，需要走系统代理访问腾讯 API

    params = {"code": f"{prefix}{code}", "date": date_str}

    try:
        r = session.get(_TENCENT_URL, params=params, headers=_TENCENT_HEADERS, timeout=15)
        if r.status_code != 200:
            return None

        data = r.json()
        if data.get("code") != 0:
            return None

        day_data = data.get("data", {}).get(f"{prefix}{code}", {}).get("data", {}).get("data", [])
        if not day_data:
            return None

        bars = []
        for bar_str in day_data:
            parts = bar_str.split()
            if len(parts) < 4:
                continue
            time_str = parts[0]
            price = float(parts[1])
            volume = int(float(parts[2]))

            if len(time_str) == 4:
                hh, mm = time_str[:2], time_str[2:]
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
    except Exception:
        return None


def fetch_sina_60min(code: str, datalen: int = 2000) -> list[dict] | None:
    """Fetch 60-min bars from Sina as fallback (~1 month of data)."""
    import re

    prefix = "sh" if code.startswith("6") else "sz"
    symbol = f"{prefix}{code}"
    url = f"{_SINA_URL}/var%20_{symbol}=/CN_MarketDataService.getKLineData"
    params = {"symbol": symbol, "scale": "60", "ma": "no", "datalen": str(datalen)}

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
    except Exception:
        return None


def get_trading_days(years: float) -> list[str]:
    """Get approximate trading days (weekdays) for the past N years."""
    today = datetime.now().date()
    days_back = int(years * 365.25)
    start = today - timedelta(days=days_back)
    days = []
    current = start
    while current <= today:
        if current.weekday() < 5:
            days.append(current.strftime("%Y%m%d"))
        current += timedelta(days=1)
    return days


def insert_bars(pool, code: str, trade_date: str, bars: list[dict]) -> bool:
    """Insert bars into PostgreSQL. Returns True on success."""
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                   VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                   ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                     result = EXCLUDED.result,
                     updated_at = EXCLUDED.updated_at
                   WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                (code, "kline_1min", trade_date, "1min", json.dumps(bars, ensure_ascii=False), time.time()),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        pool.putconn(conn)


def import_one_stock(
    code: str,
    trading_days: list[str],
    pool,
    delay: float,
    force: bool = False,
) -> tuple[int, int, float, str]:
    """Import one stock's minute data.

    Returns (imported_days, imported_bars, final_delay, source).
    """
    existing_dates = get_existing_dates(pool, code) if not force else set()

    imported_days = 0
    imported_bars = 0
    current_delay = delay
    consecutive_errors = 0
    source = "tencent"

    for day_str in trading_days:
        trade_date = f"{day_str[:4]}-{day_str[4:6]}-{day_str[6:8]}"
        if trade_date in existing_dates:
            continue

        # Try Tencent first
        bars = fetch_tencent_day(code, day_str)

        if bars is None:
            consecutive_errors += 1
            if consecutive_errors >= CONSECUTIVE_ERRORS_THRESHOLD:
                current_delay = min(current_delay * BACKOFF_FACTOR, MAX_DELAY)
                # If Tencent is blocked, try to detect and switch source
                if current_delay >= 1.0:
                    source = "blocked"
        else:
            consecutive_errors = 0
            current_delay = max(current_delay * RECOVERY_FACTOR, MIN_DELAY)
            if insert_bars(pool, code, trade_date, bars):
                imported_days += 1
                imported_bars += len(bars)
                existing_dates.add(trade_date)

        time.sleep(current_delay)

    return imported_days, imported_bars, current_delay, source


def main():
    parser = argparse.ArgumentParser(description="Bulk A-share minute data importer")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated codes (default: all)")
    parser.add_argument("--years", type=float, default=10, help="Years of history (default: 10)")
    parser.add_argument("--status", action="store_true", help="Show import progress and exit")
    parser.add_argument("--force", action="store_true", help="Re-import even if already exists")
    parser.add_argument("--reset", action="store_true", help="Reset progress and exit")
    parser.add_argument("--delay", type=float, default=INITIAL_DELAY, help="Initial delay between requests")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("bulk_import.log", mode="a"),
        ],
    )

    pool = _get_pg_pool()
    if pool is None:
        logger.error("PostgreSQL not available")
        sys.exit(1)

    state = load_progress()

    if args.reset:
        state = {"completed_stocks": [], "current_stock": None, "total_bars": 0, "total_days": 0}
        save_progress(state)
        logger.info("Progress reset")
        return

    if args.status:
        completed = state.get("completed_stocks", [])
        total_bars = state.get("total_bars", 0)
        total_days = state.get("total_days", 0)
        logger.info("Progress: %d stocks completed, %d days, %d bars", len(completed), total_days, total_bars)
        if completed:
            logger.info("Last 10: %s", completed[-10:])
        return

    # Get stock list
    if args.tickers:
        tickers = [t.strip().zfill(6) for t in args.tickers.split(",") if t.strip()]
    else:
        logger.info("Fetching all A-share stock codes...")
        tickers = get_all_astock_codes()
        logger.info("Found %d A-share stocks", len(tickers))

    if not tickers:
        logger.error("No tickers to import")
        sys.exit(1)

    trading_days = get_trading_days(args.years)
    logger.info(
        "Importing %d stocks × %d trading days = %d total requests",
        len(tickers), len(trading_days), len(tickers) * len(trading_days),
    )

    # Filter out completed stocks
    completed = set(state.get("completed_stocks", []))
    remaining = [t for t in tickers if t not in completed]
    logger.info("Already completed: %d, Remaining: %d", len(completed), len(remaining))

    # Import loop
    total_bars = state.get("total_bars", 0)
    total_days = state.get("total_days", 0)
    start_time = time.time()
    last_save = time.time()
    current_delay = args.delay
    tencent_blocked = False

    for i, code in enumerate(remaining):
        logger.info("Importing %s (%d/%d)...", code, i + 1, len(remaining))
        state["current_stock"] = code

        days, bars, current_delay, source = import_one_stock(code, trading_days, pool, current_delay, args.force)
        total_days += days
        total_bars += bars

        if source == "blocked" and not tencent_blocked:
            tencent_blocked = True
            logger.warning("Tencent API appears blocked (501). Will retry with backoff.")

        completed.add(code)
        state["completed_stocks"] = sorted(completed)
        state["total_bars"] = total_bars
        state["total_days"] = total_days
        state["current_stock"] = None

        # Save progress every 60 seconds
        if time.time() - last_save > 60:
            save_progress(state)
            last_save = time.time()

        # Progress report every 10 stocks
        if (i + 1) % 10 == 0 or i == 0:
            elapsed = time.time() - start_time
            stocks_done = len(completed)
            rate = stocks_done / elapsed if elapsed > 0 else 0
            remaining_count = len(tickers) - stocks_done
            eta = remaining_count / rate if rate > 0 else 0
            logger.info(
                "Progress: %d/%d stocks, %d days, %d bars, %.2fs delay, ETA: %s",
                stocks_done, len(tickers), total_days, total_bars,
                current_delay, timedelta(seconds=int(eta)),
            )

    save_progress(state)
    elapsed = time.time() - start_time
    logger.info("Done! %d bars for %d stocks in %s", total_bars, len(tickers), timedelta(seconds=int(elapsed)))


if __name__ == "__main__":
    main()
