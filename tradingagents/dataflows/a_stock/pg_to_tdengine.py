"""PostgreSQL → TDengine data migration script.

Migrates kline data from PG data_history to TDengine supertables.
Supports 1min, 60min, and daily intervals with separate progress tracking.

Supertables:
  st_stock_1min   ← kline_1min
  st_stock_60min  ← kline_60min
  st_stock_daily  ← kline_daily

Usage::

    python -m tradingagents.dataflows.a_stock.pg_to_tdengine --type daily
    python -m tradingagents.dataflows.a_stock.pg_to_tdengine --type 60min
    python -m tradingagents.dataflows.a_stock.pg_to_tdengine --type 1min
    python -m tradingagents.dataflows.a_stock.pg_to_tdengine --status
    python -m tradingagents.dataflows.a_stock.pg_to_tdengine --reset
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tradingagents.cache.manager import _get_pg_pool
from tradingagents.config import TD_DSN as _TD_DSN

logger = logging.getLogger(__name__)

# Map PG data_type → TDengine supertable + child table prefix
_TYPE_MAP = {
    "kline_1min":  ("st_stock_1min",  "st_1min"),
    "kline_5min":  ("st_stock_5min",  "st_5min"),
    "kline_15min": ("st_stock_15min", "st_15min"),
    "kline_30min": ("st_stock_30min", "st_30min"),
    "kline_60min": ("st_stock_60min", "st_60min"),
    "kline_daily": ("st_stock_daily", "st_daily"),
}

PROGRESS_DIR = Path(__file__).parent / ".tdengine_migration"


def _progress_file(data_type: str) -> Path:
    return PROGRESS_DIR / f"{data_type}_state.json"


def _get_td_conn():
    try:
        import taosws
        return taosws.connect(_TD_DSN)
    except ImportError:
        logger.error("taosws not installed. Run: pip install taos-ws-py")
        return None


def load_progress(data_type: str) -> dict:
    f = _progress_file(data_type)
    if not f.exists():
        return {"completed_tickers": [], "total_bars": 0, "total_days": 0}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {"completed_tickers": [], "total_bars": 0, "total_days": 0}


def save_progress(data_type: str, state: dict) -> None:
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    f = _progress_file(data_type)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(f)


def get_all_tickers(pool, data_type: str) -> list[str]:
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ticker FROM data_history
                WHERE data_type = %s ORDER BY ticker
            """, (data_type,))
            return [row[0] for row in cur.fetchall()]
    finally:
        pool.putconn(conn)


def read_ticker_data(pool, ticker: str, data_type: str) -> list[tuple[str, any]]:
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT trade_date, result FROM data_history
                WHERE ticker = %s AND data_type = %s
                ORDER BY trade_date
            """, (ticker, data_type))
            return cur.fetchall()
    finally:
        pool.putconn(conn)


def write_to_tdengine(td_conn, ticker: str, market: str, bars: list[dict], data_type: str) -> int:
    if not td_conn or not bars:
        return 0

    # BaoStock-stored bars carry date-only timestamps — reconstruct HH:MM:SS
    # from the A-share session grid so intra-day bars don't collapse in TDengine
    try:
        from .utils import resolve_dateonly_bars
    except ImportError:  # run as a plain script
        from tradingagents.dataflows.a_stock.utils import resolve_dateonly_bars
    bars, _n_resolved = resolve_dateonly_bars(bars, data_type)

    stable, prefix = _TYPE_MAP[data_type]
    child = f"{prefix}_{ticker}"
    cursor = td_conn.cursor()
    inserted = 0

    values_list = []
    for bar in bars:
        ts_str = bar.get("date", "")
        if not ts_str:
            continue
        try:
            if len(ts_str) == 10:  # "YYYY-MM-DD"
                ts = datetime.strptime(ts_str, "%Y-%m-%d")
            elif len(ts_str) == 16:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
            elif len(ts_str) == 19:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            else:
                continue
            ts_ms = int(ts.timestamp() * 1000)
        except Exception:
            continue

        o = float(bar.get("open", 0))
        h = float(bar.get("high", 0))
        l = float(bar.get("low", 0))
        c = float(bar.get("close", 0))
        v = int(float(bar.get("volume", 0)))
        a = float(bar.get("amount", o * v))
        values_list.append(f"({ts_ms}, {o}, {h}, {l}, {c}, {v}, {a})")

    if not values_list:
        return 0

    batch_size = 1000
    for i in range(0, len(values_list), batch_size):
        batch = values_list[i:i + batch_size]
        values_str = ",".join(batch)
        sql = f"INSERT INTO {child} USING {stable} TAGS ('{ticker}', '{market}') VALUES {values_str}"
        try:
            cursor.execute(sql)
            inserted += len(batch)
        except Exception as exc:
            logger.warning("TDengine batch %s failed for %s: %s", data_type, ticker, exc)
            for val in batch:
                try:
                    cursor.execute(f"INSERT INTO {child} USING {stable} TAGS ('{ticker}', '{market}') VALUES {val}")
                    inserted += 1
                except Exception:
                    pass

    return inserted


def migrate(data_type: str):
    if data_type not in _TYPE_MAP:
        logger.error("Unknown type: %s. Supported: %s", data_type, list(_TYPE_MAP.keys()))
        sys.exit(1)

    pool = _get_pg_pool()
    if pool is None:
        logger.error("PostgreSQL not available")
        sys.exit(1)

    td_conn = _get_td_conn()
    if td_conn is None:
        logger.error("TDengine not available")
        sys.exit(1)

    state = load_progress(data_type)
    tickers = get_all_tickers(pool, data_type)
    if not tickers:
        logger.error("No tickers found for %s", data_type)
        sys.exit(1)

    completed = set(state.get("completed_tickers", []))
    remaining = [t for t in tickers if t not in completed]
    logger.info("Migrating %s: %d total, %d remaining", data_type, len(tickers), len(remaining))

    total_bars = state.get("total_bars", 0)
    total_days = state.get("total_days", 0)
    start_time = time.time()
    last_save = time.time()

    for i, ticker in enumerate(remaining):
        market = "sh" if ticker.startswith("6") else "sz"
        rows = read_ticker_data(pool, ticker, data_type)

        if not rows:
            completed.add(ticker)
            continue

        all_bars = []
        for trade_date, result_json in rows:
            if isinstance(result_json, str):
                day_bars = json.loads(result_json)
            else:
                day_bars = result_json
            if isinstance(day_bars, list):
                all_bars.extend(day_bars)
            else:
                all_bars.append(day_bars)

        inserted = write_to_tdengine(td_conn, ticker, market, all_bars, data_type)
        total_bars += inserted
        total_days += len(rows)

        completed.add(ticker)
        state["completed_tickers"] = sorted(completed)
        state["total_bars"] = total_bars
        state["total_days"] = total_days

        if time.time() - last_save > 60:
            save_progress(data_type, state)
            last_save = time.time()

        if (i + 1) % 100 == 0 or i == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(remaining) - i - 1) / rate if rate > 0 else 0
            logger.info(
                "%s: %d/%d, %d days, %d bars, ETA: %dh %dm",
                data_type, i+1, len(remaining), total_days, total_bars,
                int(eta // 3600), int((eta % 3600) // 60)
            )

        time.sleep(0.01)

    save_progress(data_type, state)
    td_conn.close()
    logger.info("Done! %s: %d bars for %d tickers", data_type, total_bars, len(tickers))


def main():
    parser = argparse.ArgumentParser(description="PG → TDengine migration")
    parser.add_argument("--type", type=str, default="daily", choices=list(_TYPE_MAP.keys()),
                        help="Data type to migrate (PG data_type label)")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("tdengine_migration.log", mode="a")],
    )

    if args.reset:
        for dt in _TYPE_MAP:
            save_progress(dt, {"completed_tickers": [], "total_bars": 0, "total_days": 0})
        logger.info("All progress reset")
        return

    if args.status:
        for dt in _TYPE_MAP:
            state = load_progress(dt)
            c = len(state.get("completed_tickers", []))
            logger.info("%s: %d tickers, %d days, %d bars", dt, c,
                        state.get("total_days", 0), state.get("total_bars", 0))
        return

    migrate(args.type)


if __name__ == "__main__":
    main()
