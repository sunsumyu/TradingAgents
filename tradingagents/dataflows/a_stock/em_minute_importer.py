"""Eastmoney minute-data importer — fast, reliable alternative to BaoStock.

BaoStock's server has become unstable (persistent timeouts + corrupted gzip),
stalling the 5/15/30min backfill for days. Eastmoney's kline API is stable and
fast (~0.2s/stock), providing roughly:
  - 5min:  ~1,500 bars (~1.5 months)
  - 15min: ~3 months
  - 30min: ~6 months
  - 60min: ~1.5 years
Deep 6-year history still requires BaoStock (run separately); this importer
fills the recent window reliably in under an hour per interval.

Data flow: Eastmoney → PostgreSQL data_history (same rows as BaoStock importer)
→ TDengine via pg_to_tdengine. Progress resumes from JSON state files.

Usage::

    python -m tradingagents.dataflows.a_stock.em_minute_importer
    python -m tradingagents.dataflows.a_stock.em_minute_importer --intervals 5
    python -m tradingagents.dataflows.a_stock.em_minute_importer --status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

import requests

from tradingagents.cache.manager import _get_pg_pool

logger = logging.getLogger(__name__)

_EM_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}

# freq → (data_type, param_hash) — matches baostock_importer.INTERVAL_MAP
INTERVAL_MAP = {
    "5": ("kline_5min", "5min"),
    "15": ("kline_15min", "15min"),
    "30": ("kline_30min", "30min"),
    "60": ("kline_60min", "60min"),
}

PROGRESS_DIR = Path(__file__).parent / ".em_progress"
REQUEST_PAUSE = 0.5   # seconds between stocks (~2 req/s, sustainable)
MAX_RETRIES = 2
THROTTLE_COOLDOWN = 120  # consecutive-failure cooldown: rate limit clears in ~90s
# 深度停牌股 (如 000029) 会让东财直接断连；连续失败则多为限流，
# 冷却 2 分钟等限制解除，而不是持续撞墙加重封锁。


def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False  # bypass system proxy (breaks eastmoney TLS)
    s.headers.update(_HEADERS)
    return s


def _secid(code: str) -> str:
    """Map 6-digit code to Eastmoney secid (market.code)."""
    if code.startswith(("6", "9")):
        return f"1.{code}"   # Shanghai
    return f"0.{code}"        # Shenzhen / Beijing


def fetch_em_bars(s: requests.Session, code: str, klt: str) -> list[dict] | None:
    """Fetch minute bars for one stock. Returns None on failure."""
    params = {
        "secid": _secid(code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": klt,
        "fqt": "1",
        "lmt": "100000",
        "end": "20500101",
    }
    try:
        r = s.get(_EM_URL, params=params, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json().get("data") or {}
        klines = data.get("klines") or []
    except Exception as exc:
        logger.debug("EM fetch %s klt=%s failed: %s", code, klt, exc)
        return None

    bars: list[dict] = []
    for line in klines:
        # CSV: date,open,close,high,low,volume(手),amount(元)
        parts = line.split(",")
        if len(parts) < 7:
            continue
        try:
            bars.append({
                "date": parts[0],
                "open": float(parts[1]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "close": float(parts[2]),
                "volume": int(float(parts[5])) * 100,  # 手 → 股 (matches BaoStock unit)
                "amount": float(parts[6]),
            })
        except (ValueError, IndexError):
            continue
    return bars


def get_all_tickers() -> list[str]:
    """All A-share tickers from PG (data_history already covers 5,218 stocks)."""
    pool = _get_pg_pool()
    if pool is None:
        logger.error("PostgreSQL not available")
        return []
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ticker FROM data_history "
                "WHERE data_type IN ('kline_60min','kline_daily') ORDER BY ticker"
            )
            return [r[0] for r in cur.fetchall()]
    finally:
        pool.putconn(conn)


def load_progress(freq: str) -> dict:
    PROGRESS_DIR.mkdir(exist_ok=True)
    f = PROGRESS_DIR / f"em_{freq}min_state.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"completed": [], "total_bars": 0}


def save_progress(freq: str, state: dict) -> None:
    f = PROGRESS_DIR / f"em_{freq}min_state.json"
    tmp = f.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, f)
    except PermissionError:
        shutil.copy2(tmp, f)


def import_stock(s: requests.Session, code: str, freq: str, pool) -> tuple[str, int]:
    """Import one stock. Returns (status, bars_count)."""
    data_type, param_hash = INTERVAL_MAP[freq]
    klt = freq

    bars = None
    for attempt in range(1, MAX_RETRIES + 1):
        bars = fetch_em_bars(s, code, klt)
        if bars is not None:
            break
        logger.warning("EM %s klt=%s attempt %d failed", code, klt, attempt)
        time.sleep(0.5)
    if bars is None:
        return "failed", 0
    if not bars:
        return "empty", 0

    # Group by trade_date
    by_date: dict[str, list[dict]] = {}
    for bar in bars:
        by_date.setdefault(bar["date"][:10], []).append(bar)

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            from psycopg2.extras import execute_values
            rows = [
                (code, data_type, td, param_hash,
                 json.dumps(day_bars, ensure_ascii=False), time.time())
                for td, day_bars in sorted(by_date.items())
            ]
            execute_values(
                cur,
                """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                   VALUES %s
                   ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                     result = EXCLUDED.result, updated_at = EXCLUDED.updated_at
                   WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                rows,
                template="(%s, %s, %s, %s, %s, to_timestamp(%s))",
                page_size=200,
            )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning("PG write failed %s/%s: %s", code, freq, exc)
        return "failed", 0
    finally:
        pool.putconn(conn)

    return "ok", len(bars)


def main():
    parser = argparse.ArgumentParser(description="Eastmoney minute-data importer")
    parser.add_argument("--intervals", type=str, default="5,15,30,60")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated 6-digit codes")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    if args.status:
        for freq in args.intervals.split(","):
            state = load_progress(freq)
            logger.info("%smin: %d stocks, %s bars",
                        freq, len(state.get("completed", [])),
                        f"{state.get('total_bars', 0):,}")
        return

    if args.reset:
        for freq in args.intervals.split(","):
            save_progress(freq, {"completed": [], "total_bars": 0})
        logger.info("Progress reset")
        return

    pool = _get_pg_pool()
    if pool is None:
        sys.exit(1)

    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    else:
        tickers = get_all_tickers()
    logger.info("Tickers: %d", len(tickers))

    s = _session()

    for freq in args.intervals.split(","):
        if freq not in INTERVAL_MAP:
            continue
        logger.info("=" * 60)
        logger.info("EM %smin import", freq)
        logger.info("=" * 60)

        state = load_progress(freq)
        completed = set(state.get("completed", []))
        remaining = [t for t in tickers if t not in completed]
        logger.info("Already: %d, Remaining: %d", len(completed), len(remaining))

        total_bars = state.get("total_bars", 0)
        start_time = time.time()
        last_save = time.time()
        consecutive_failures = 0

        for i, code in enumerate(remaining):
            status, bars = import_stock(s, code, freq, pool)
            time.sleep(REQUEST_PAUSE)

            if status == "failed":
                consecutive_failures += 1
                failed = state.setdefault("failed", [])
                if code not in failed:
                    failed.append(code)
                if consecutive_failures >= 5:
                    save_progress(freq, state)
                    if consecutive_failures >= 50:
                        logger.error("50 consecutive failures even after cooldowns — aborting %smin", freq)
                        sys.exit(2)
                    logger.warning(
                        "%d consecutive failures — rate-limited? cooling down %ds",
                        consecutive_failures, THROTTLE_COOLDOWN,
                    )
                    time.sleep(THROTTLE_COOLDOWN)
                continue

            consecutive_failures = 0
            if status == "ok":
                total_bars += bars
                completed.add(code)
                state["completed"] = sorted(completed)
                state["total_bars"] = total_bars

            if time.time() - last_save > 30:
                save_progress(freq, state)
                last_save = time.time()

            if (i + 1) % 100 == 0 or i == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(remaining) - i - 1) / rate if rate > 0 else 0
                logger.info("%smin: %d/%d, %s bars, ETA: %dm",
                            freq, i + 1, len(remaining), f"{total_bars:,}", int(eta / 60))

        save_progress(freq, state)
        logger.info("Done! %smin: %s bars", freq, f"{total_bars:,}")

    logger.info("All intervals complete!")


if __name__ == "__main__":
    main()
