"""Tencent daily K-line importer — full A-share market, 10+ years.

Tencent API: http://web.ifzq.gtimg.cn/appstock/app/kline/kline?param=<symbol>,day,<start>,<end>,<count>
Returns up to 2000 daily bars per request (covers ~10 years).

Usage::

    python -m tradingagents.dataflows.a_stock.tencent_daily_importer
    python -m tradingagents.dataflows.a_stock.tencent_daily_importer --status
    python -m tradingagents.dataflows.a_stock.tencent_daily_importer --reset
    python -m tradingagents.dataflows.a_stock.tencent_daily_importer --tickers 600519,000001
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

from tradingagents.cache.manager import _get_pg_pool

logger = logging.getLogger(__name__)

_TENCENT_URL = "http://web.ifzq.gtimg.cn/appstock/app/kline/kline"
PROGRESS_FILE = Path(__file__).parent / ".tencent_daily_progress" / "state.json"


def get_all_astock_codes() -> list[str]:
    """Get all A-share stock codes via Sina HQ API."""
    session = requests.Session()
    session.trust_env = False

    all_codes: list[str] = []
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

    seen: set[str] = set()
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


def fetch_tencent_daily(code: str, start: str = "", count: int = 2000) -> list[dict] | None:
    """Fetch daily K-line from Tencent API.

    Returns list of {date, open, high, low, close, volume} or None.
    """
    prefix = "sh" if code.startswith("6") else "sz"
    symbol = f"{prefix}{code}"

    params = {"param": f"{symbol},day,{start},,{count}"}
    session = requests.Session()
    session.trust_env = False

    try:
        resp = session.get(_TENCENT_URL, params=params, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("code") != 0:
            return None
        days = data.get("data", {}).get(symbol, {}).get("day", [])
        bars = []
        for item in days:
            bars.append({
                "date": str(item[0]),
                "open": float(item[1]),
                "high": float(item[3]),
                "low": float(item[2]),
                "close": float(item[4]),
                "volume": int(float(item[5])),
            })
        return bars
    except Exception as exc:
        logger.warning("Tencent fetch failed for %s: %s", code, exc)
        return None


def import_stock(code: str, pool) -> tuple[int, int]:
    """Import daily K-line for one stock into data_history."""
    bars = fetch_tencent_daily(code)
    if not bars:
        return 0, 0

    # Insert into PG
    conn = pool.getconn()
    inserted_days = 0
    inserted_bars = 0
    try:
        with conn.cursor() as cur:
            for bar in bars:
                cur.execute(
                    """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                       VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                       ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                         result = EXCLUDED.result,
                         updated_at = EXCLUDED.updated_at
                       WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                    (code, "kline_daily", bar["date"], "daily",
                     json.dumps(bar, ensure_ascii=False), time.time()),
                )
                inserted_days += 1
                inserted_bars += 1
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("PG write failed for %s: %s", code, exc)
    finally:
        pool.putconn(conn)

    return inserted_days, inserted_bars


def main():
    parser = argparse.ArgumentParser(description="Tencent daily K-line importer")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated codes")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("tencent_daily_import.log", mode="a"),
        ],
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
        logger.info(
            f"Progress: {len(completed)} stocks, "
            f"{state.get('total_days', 0)} days, "
            f"{state.get('total_bars', 0)} bars"
        )
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

    for i, code in enumerate(remaining):
        days, bars = import_stock(code, pool)
        total_days += days
        total_bars += bars

        completed.add(code)
        state["completed_stocks"] = sorted(completed)
        state["total_bars"] = total_bars
        state["total_days"] = total_days

        if time.time() - last_save > 60:
            save_progress(state)
            last_save = time.time()

        if (i + 1) % 100 == 0 or i == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(remaining) - i - 1) / rate if rate > 0 else 0
            logger.info(
                f"Progress: {i+1}/{len(remaining)}, {total_days} days, {total_bars} bars, "
                f"ETA: {timedelta(seconds=int(eta))}"
            )

        time.sleep(args.delay)

    save_progress(state)
    logger.info(f"Done! {total_bars} bars for {len(tickers)} stocks")


if __name__ == "__main__":
    main()
