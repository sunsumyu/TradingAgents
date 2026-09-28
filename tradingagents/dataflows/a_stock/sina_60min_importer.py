"""Sina 60-minute kline importer — full A-share market import.

Sina provides ~1 month of 60-min bars (200 bars ≈ 50 trading days).
This importer fetches all A-shares and stores them in PostgreSQL data_history.

Usage::

    python -m tradingagents.dataflows.a_stock.sina_60min_importer
    python -m tradingagents.dataflows.a_stock.sina_60min_importer --status
    python -m tradingagents.dataflows.a_stock.sina_60min_importer --reset
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import timedelta
from pathlib import Path

import requests

from tradingagents.cache.manager import _get_pg_pool

logger = logging.getLogger(__name__)

_SINA_URL = "https://quotes.sina.cn/cn/api/jsonp_v2.php"
_SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
}

PROGRESS_FILE = Path(__file__).parent / ".sina_60min_progress" / "state.json"


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


def fetch_sina_60min(code: str, datalen: int = 200) -> list[dict] | None:
    """Fetch 60-min bars from Sina for one A-share code.

    Returns list of {date, open, high, low, close, volume} or None.
    """
    prefix = "sh" if code.startswith("6") else "sz"
    url = f"{_SINA_URL}/var%20_{prefix}{code}=/CN_MarketDataService.getKLineData"
    params = {"symbol": f"{prefix}{code}", "scale": "60", "ma": "no", "datalen": str(datalen)}

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
        logger.warning("Sina 60min fetch failed for %s: %s", code, exc)
        return None


def import_stock(code: str, pool, datalen: int = 200) -> tuple[int, int]:
    """Import 60-min bars for one stock into data_history.

    Groups bars by trade_date, stores as JSON array.
    Returns (days_inserted, bars_inserted).
    """
    bars = fetch_sina_60min(code, datalen=datalen)
    if not bars:
        return 0, 0

    # Group by trade_date
    by_date: dict[str, list[dict]] = {}
    for bar in bars:
        trade_date = bar["date"][:10]
        by_date.setdefault(trade_date, []).append(bar)

    if not by_date:
        return 0, 0

    # Insert into PG
    conn = pool.getconn()
    inserted_days = 0
    inserted_bars = 0
    try:
        with conn.cursor() as cur:
            for trade_date, day_bars in sorted(by_date.items()):
                cur.execute(
                    """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                       VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                       ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                         result = EXCLUDED.result,
                         updated_at = EXCLUDED.updated_at
                       WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                    (code, "kline_60min", trade_date, "60min",
                     json.dumps(day_bars, ensure_ascii=False), time.time()),
                )
                inserted_days += 1
                inserted_bars += len(day_bars)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("PG write failed for %s: %s", code, exc)
    finally:
        pool.putconn(conn)

    return inserted_days, inserted_bars


def main():
    parser = argparse.ArgumentParser(description="Sina 60-min kline importer")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated codes")
    parser.add_argument("--datalen", type=int, default=200, help="Bars per request")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("sina_60min_import.log", mode="a"),
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
        days, bars = import_stock(code, pool, datalen=args.datalen)
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
