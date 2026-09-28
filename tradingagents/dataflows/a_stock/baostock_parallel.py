"""BaoStock parallel importer — 4 threads × BaoStock connections.

Each thread has its own BaoStock login session, processing a chunk of tickers.
Estimated: 5216 stocks / 4 threads / ~3min per stock ≈ 65 hours for 5min alone.

Usage::

    python -m tradingagents.dataflows.a_stock.baostock_parallel
    python -m tradingagents.dataflows.a_stock.baostock_parallel --threads 8
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock

from tradingagents.cache.manager import _get_pg_pool

logger = logging.getLogger(__name__)

START_DATE = "2020-01-01"
END_DATE = "2026-09-10"

INTERVAL_MAP = {
    "5":  ("kline_5min",  "5min",  "st_stock_5min",  "st_5min"),
    "15": ("kline_15min", "15min", "st_stock_15min", "st_15min"),
    "30": ("kline_30min", "30min", "st_stock_30min", "st_30min"),
    "60": ("kline_60min", "60min", "st_stock_60min", "st_60min"),
}

PROGRESS_DIR = Path(__file__).parent / ".baostock_progress"
_lock = Lock()


def _progress_file(interval: str) -> Path:
    return PROGRESS_DIR / f"bs_{interval}min_parallel.json"


def load_progress(interval: str) -> dict:
    f = _progress_file(interval)
    if not f.exists():
        return {"completed": [], "total_bars": 0}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {"completed": [], "total_bars": 0}


def save_progress(interval: str, state: dict) -> None:
    with _lock:
        PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
        f = _progress_file(interval)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(f)


def get_all_tickers() -> list[str]:
    """Get A-share tickers from PG data."""
    pool = _get_pg_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT ticker FROM data_history WHERE data_type='kline_daily' ORDER BY ticker")
            tickers = []
            for row in cur.fetchall():
                t = row[0]
                bs_ticker = f"sh.{t}" if t.startswith("6") else f"sz.{t}"
                tickers.append(bs_ticker)
            return tickers
    finally:
        pool.putconn(conn)


def import_stock(bs_code: str, freq: str, pool) -> tuple[int, int]:
    """Import one stock for one frequency. Each call creates its own BS session."""
    import baostock as bs

    data_type, param_hash, _, _ = INTERVAL_MAP[freq]
    ticker = bs_code.split(".")[1]

    lg = bs.login()
    if lg.error_code != '0':
        return 0, 0

    try:
        rs = bs.query_history_k_data_plus(
            bs_code, "date,open,high,low,close,volume,amount",
            start_date=START_DATE, end_date=END_DATE,
            frequency=freq, adjustflag="3",
        )

        bars = []
        while rs.error_code == '0' and rs.next():
            row = rs.get_row_data()
            try:
                o = float(row[1]) if row[1] else 0
                h = float(row[2]) if row[2] else 0
                l = float(row[3]) if row[3] else 0
                c = float(row[4]) if row[4] else 0
                v = int(float(row[5])) if row[5] else 0
                a = float(row[6]) if len(row) > 6 and row[6] else 0
                if o == 0 and c == 0:
                    continue
                bars.append({"date": row[0], "open": o, "high": h, "low": l, "close": c, "volume": v, "amount": a})
            except (ValueError, IndexError):
                continue

        if not bars:
            return 0, 0

        by_date: dict[str, list[dict]] = {}
        for bar in bars:
            by_date.setdefault(bar["date"][:10], []).append(bar)

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
                        (ticker, data_type, td, param_hash,
                         json.dumps(day_bars, ensure_ascii=False), time.time()),
                    )
                    inserted += 1
                    bars_count += len(day_bars)
            conn.commit()
        except Exception as exc:
            conn.rollback()
        finally:
            pool.putconn(conn)

        return inserted, bars_count
    finally:
        bs.logout()


def worker(thread_id: int, tickers: list[str], freq: str, pool, state: dict):
    """Worker thread: process a chunk of tickers."""
    completed = set(state.get("completed", []))
    total_bars = state.get("total_bars", 0)

    for i, bs_code in enumerate(tickers):
        if bs_code in completed:
            continue

        ticker = bs_code.split(".")[1]
        days, bars = import_stock(bs_code, freq, pool)

        with _lock:
            completed.add(bs_code)
            total_bars += bars
            state["completed"] = sorted(completed)
            state["total_bars"] = total_bars

            if len(completed) % 100 == 0:
                save_progress(freq, state)
                logger.info("T%d: %d stocks done, %d bars", thread_id, len(completed), total_bars)


def main():
    parser = argparse.ArgumentParser(description="BaoStock parallel importer")
    parser.add_argument("--intervals", type=str, default="5,15,30,60")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("baostock_parallel.log", mode="a")],
    )

    intervals = [i.strip() for i in args.intervals.split(",") if i.strip() in INTERVAL_MAP]
    pool = _get_pg_pool()
    if pool is None:
        logger.error("PostgreSQL not available")
        sys.exit(1)

    if args.status:
        for iv in intervals:
            s = load_progress(iv)
            logger.info("%smin: %d done, %d bars", iv, len(s.get("completed", [])), s.get("total_bars", 0))
        return

    if args.reset:
        for iv in intervals:
            save_progress(iv, {"completed": [], "total_bars": 0})
        return

    tickers = get_all_tickers()
    logger.info("Found %d tickers", len(tickers))

    for freq in intervals:
        data_type, param_hash, _, _ = INTERVAL_MAP[freq]
        logger.info(f"\n{'='*60}\n{freq}min import\n{'='*60}")

        state = load_progress(freq)
        completed = set(state.get("completed", []))
        remaining = [t for t in tickers if t not in completed]
        logger.info("Already: %d, Remaining: %d", len(completed), len(remaining))

        if not remaining:
            continue

        # Split tickers into chunks for parallel processing
        chunk_size = (len(remaining) + args.threads - 1) // args.threads
        chunks = [remaining[i:i+chunk_size] for i in range(0, len(remaining), chunk_size)]

        start_time = time.time()
        threads = []
        for tid, chunk in enumerate(chunks):
            t = Thread(target=worker, args=(tid, chunk, freq, pool, state), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        elapsed = time.time() - start_time
        save_progress(freq, state)
        logger.info("Done! %smin: %d bars in %.0fs (%.1fh)",
                     freq, state.get("total_bars", 0), elapsed, elapsed/3600)

    logger.info("All intervals complete!")


if __name__ == "__main__":
    main()
