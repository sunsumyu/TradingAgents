"""Sina multi-interval minute data importer.

Fetches all available minute intervals (1m, 5m, 15m, 30m, 60m) from Sina API
for all A-shares. Sina provides up to 1000 bars per interval per request.

Depth per interval:
  1min:  ~1 week
  5min:  ~1 month
  15min: ~3 months
  30min: ~6 months
  60min: ~1 year

Usage::

    python -m tradingagents.dataflows.a_stock.sina_minute_importer
    python -m tradingagents.dataflows.a_stock.sina_minute_importer --intervals 1m,5m
    python -m tradingagents.dataflows.a_stock.sina_minute_importer --status
"""

from __future__ import annotations

import argparse
import hashlib
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

# Interval config: sina_scale → (pg_data_type, param_hash, tdengine_stable, tdengine_prefix)
INTERVAL_MAP = {
    "1m":  ("kline_1min",  "1min",  "st_stock_1min",  "st_1min"),
    "5m":  ("kline_5min",  "5min",  "st_stock_5min",  "st_5min"),
    "15m": ("kline_15min", "15min", "st_stock_15min", "st_15min"),
    "30m": ("kline_30min", "30min", "st_stock_30min", "st_30min"),
    "60m": ("kline_60min", "60min", "st_stock_60min", "st_60min"),
}

# Sina API expects scale as numeric string: "1", "5", "15", "30", "60"
SINA_SCALE_MAP = {k: k.rstrip("m") for k in INTERVAL_MAP}

PROGRESS_DIR = Path(__file__).parent / ".sina_minute_progress"


def _progress_file(interval: str) -> Path:
    return PROGRESS_DIR / f"{interval}_state.json"


def get_all_astock_codes() -> list[str]:
    session = requests.Session()
    session.trust_env = False
    all_codes: list[str] = []
    page = 1
    while True:
        try:
            url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
            params = {"page": page, "num": 100, "sort": "symbol", "asc": "1", "node": "hs_a", "symbol": "", "_s_r_a": "init"}
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
            if len(data) < 100:
                break
            page += 1
            time.sleep(0.1)
        except Exception:
            break
    seen: set[str] = set()
    return [c for c in all_codes if not (c in seen or seen.add(c))]


def load_progress(interval: str) -> dict:
    f = _progress_file(interval)
    if not f.exists():
        return {"completed": [], "total_bars": 0, "total_days": 0}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {"completed": [], "total_bars": 0, "total_days": 0}


def save_progress(interval: str, state: dict) -> None:
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    f = _progress_file(interval)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(f)


def fetch_sina_bars(code: str, scale: str, datalen: int = 1000) -> list[dict] | None:
    """Fetch minute bars from Sina. Returns list of {date, open, high, low, close, volume}."""
    prefix = "sh" if code.startswith("6") else "sz"
    url = f"{_SINA_URL}/var%20_{prefix}{code}=/CN_MarketDataService.getKLineData"
    params = {"symbol": f"{prefix}{code}", "scale": scale, "ma": "no", "datalen": str(datalen)}

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
        if not raw:
            return None
        bars = []
        for item in raw:
            bars.append({
                "date": str(item.get("day", item.get("date", ""))),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": int(float(item.get("volume", 0))),
            })
        return bars
    except Exception:
        return None


def import_stock(code: str, scale: str, pool) -> tuple[int, int]:
    """Import bars for one stock and one interval into PG data_history."""
    data_type, param_hash, _, _ = INTERVAL_MAP[scale]
    sina_scale = SINA_SCALE_MAP[scale]  # "1m" → "1" for Sina API
    bars = fetch_sina_bars(code, sina_scale)
    if not bars:
        return 0, 0

    by_date: dict[str, list[dict]] = {}
    for bar in bars:
        td = bar["date"][:10]
        by_date.setdefault(td, []).append(bar)

    if not by_date:
        return 0, 0

    conn = pool.getconn()
    inserted = 0
    bars_count = 0
    try:
        with conn.cursor() as cur:
            for td, day_bars in sorted(by_date.items()):
                cur.execute(
                    """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                       VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                       ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                         result = EXCLUDED.result, updated_at = EXCLUDED.updated_at
                       WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                    (code, data_type, td, param_hash,
                     json.dumps(day_bars, ensure_ascii=False), time.time()),
                )
                inserted += 1
                bars_count += len(day_bars)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("PG write failed %s/%s: %s", code, scale, exc)
    finally:
        pool.putconn(conn)

    return inserted, bars_count


def main():
    parser = argparse.ArgumentParser(description="Sina multi-interval minute importer")
    parser.add_argument("--intervals", type=str, default="1m,5m,15m,30m,60m",
                        help="Comma-separated intervals to import")
    parser.add_argument("--tickers", type=str, default=None)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--delay", type=float, default=0.05)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("sina_minute_import.log", mode="a")],
    )

    intervals = [i.strip() for i in args.intervals.split(",") if i.strip() in INTERVAL_MAP]
    if not intervals:
        logger.error("No valid intervals. Supported: %s", list(INTERVAL_MAP.keys()))
        sys.exit(1)

    pool = _get_pg_pool()
    if pool is None:
        logger.error("PostgreSQL not available")
        sys.exit(1)

    if args.status:
        for iv in intervals:
            state = load_progress(iv)
            c = len(state.get("completed", []))
            logger.info("%s: %d stocks, %d days, %d bars",
                        iv, c, state.get("total_days", 0), state.get("total_bars", 0))
        return

    if args.reset:
        for iv in intervals:
            save_progress(iv, {"completed": [], "total_bars": 0, "total_days": 0})
        logger.info("Progress reset for: %s", intervals)
        return

    if args.tickers:
        tickers = [t.strip().zfill(6) for t in args.tickers.split(",") if t.strip()]
    else:
        logger.info("Fetching stock list...")
        tickers = get_all_astock_codes()
        logger.info(f"Found {len(tickers)} stocks")

    if not tickers:
        logger.error("No tickers")
        sys.exit(1)

    for iv in intervals:
        data_type, param_hash, td_stable, td_prefix = INTERVAL_MAP[iv]
        logger.info(f"\n{'='*60}\nImporting interval: {iv} ({data_type})\n{'='*60}")

        state = load_progress(iv)
        completed = set(state.get("completed", []))
        remaining = [t for t in tickers if t not in completed]
        logger.info(f"Already: {len(completed)}, Remaining: {len(remaining)}")

        total_bars = state.get("total_bars", 0)
        total_days = state.get("total_days", 0)
        start_time = time.time()
        last_save = time.time()

        for i, code in enumerate(remaining):
            days, bars = import_stock(code, iv, pool)
            total_days += days
            total_bars += bars

            completed.add(code)
            state["completed"] = sorted(completed)
            state["total_bars"] = total_bars
            state["total_days"] = total_days

            if time.time() - last_save > 60:
                save_progress(iv, state)
                last_save = time.time()

            if (i + 1) % 200 == 0 or i == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(remaining) - i - 1) / rate if rate > 0 else 0
                logger.info(
                    "%s %d/%d, %d days, %d bars, ETA: %dh %dm",
                    iv, i+1, len(remaining), total_days, total_bars,
                    int(eta // 3600), int((eta % 3600) // 60)
                )

            time.sleep(args.delay)

        save_progress(iv, state)
        logger.info(f"Done! {iv}: {total_bars} bars for {len(tickers)} stocks")

    logger.info("All intervals complete!")


if __name__ == "__main__":
    main()
