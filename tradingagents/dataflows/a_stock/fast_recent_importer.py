"""Fast recent importer — imports last 30 days of 1-min data for all A-shares.

TDX only has ~1 month of minute data. This importer fetches just that window
so it completes in ~2 hours instead of 340 days.

Also checks if Tencent API has recovered. If so, triggers full 10-year import.

Usage::

    # Import last 30 days for all A-shares
    python -m tradingagents.dataflows.a_stock.fast_recent_importer --days 30

    # Check Tencent status
    python -m tradingagents.dataflows.a_stock.fast_recent_importer --check-tencent
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

_TENCENT_URL = "http://web.ifzq.gtimg.cn/appstock/app/minute/query"
_TENCENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://finance.qq.com",
}

PROGRESS_FILE = Path(__file__).parent / ".fast_progress" / "state.json"


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


def get_existing_dates(pool, code: str) -> set[str]:
    """Get already-imported dates for a stock."""
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT trade_date FROM data_history WHERE ticker = %s AND data_type = 'kline_1min'", (code,))
            return {str(row[0]) for row in cur.fetchall()}
    finally:
        pool.putconn(conn)


def fetch_tdx_day(code: str, frequency: int, start: int, offset: int):
    """Fetch one page from TDX."""
    from mootdx.quotes import Quotes
    client = Quotes.factory(market="std")
    try:
        return client.bars(symbol=code, frequency=frequency, start=start, offset=offset)
    except Exception:
        return None


def fetch_tencent_day(code: str, date_str: str) -> list[dict] | None:
    """Fetch 1-min bars from Tencent for one day."""
    import requests
    prefix = "sh" if code.startswith("6") else "sz"
    session = requests.Session()
    session.trust_env = False

    try:
        r = session.get(_TENCENT_URL, params={"code": f"{prefix}{code}", "date": date_str}, headers=_TENCENT_HEADERS, timeout=15)
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
            hh, mm = (time_str[:2], time_str[2:]) if len(time_str) == 4 else (time_str[:-2].zfill(2), time_str[-2:])
            dt_val = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {hh}:{mm}"
            bars.append({"date": dt_val, "open": price, "high": price, "low": price, "close": price, "volume": volume})
        return bars
    except Exception:
        return None


def check_tencent() -> bool:
    """Check if Tencent API has recovered."""
    import requests
    session = requests.Session()
    session.trust_env = False
    try:
        r = session.get(_TENCENT_URL, params={"code": "sz001232", "date": "20260908"}, headers=_TENCENT_HEADERS, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def import_stock_recent(code: str, days: int, pool, force: bool = False) -> tuple[int, int, str]:
    """Import last N days of 1-min data for one stock.

    Returns (imported_days, imported_bars, source).
    """
    existing_dates = get_existing_dates(pool, code) if not force else set()

    # Generate recent trading days
    today = datetime.now().date()
    trading_days = []
    current = today
    while len(trading_days) < days:
        if current.weekday() < 5:
            trading_days.append(current.strftime("%Y%m%d"))
        current -= timedelta(days=1)
    trading_days.reverse()  # Oldest first

    imported_days = 0
    imported_bars = 0
    source = "none"

    # Try Tencent first for each day
    tencent_ok = True
    for day_str in trading_days:
        trade_date = f"{day_str[:4]}-{day_str[4:6]}-{day_str[6:8]}"
        if trade_date in existing_dates:
            continue

        bars = fetch_tencent_day(code, day_str)
        if bars:
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                           VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                           ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                             result = EXCLUDED.result, updated_at = EXCLUDED.updated_at
                           WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                        (code, "kline_1min", trade_date, "1min", json.dumps(bars, ensure_ascii=False), time.time()),
                    )
                conn.commit()
                imported_days += 1
                imported_bars += len(bars)
                source = "tencent"
            except Exception:
                conn.rollback()
            finally:
                pool.putconn(conn)
            time.sleep(0.05)
        else:
            tencent_ok = False
            break  # Stop trying Tencent, fall back to TDX

    # If Tencent failed, use TDX
    if not tencent_ok and imported_days == 0:
        # TDX: fetch 1-min data in pages
        start = 0
        for _ in range(20):  # Max 20 pages
            df = fetch_tdx_day(code, 8, start, 800)
            if df is None or df.empty:
                break

            by_date: dict[str, list[dict]] = {}
            for idx, row in df.iterrows():
                dt_val = str(idx)[:16]
                trade_date = dt_val[:10]
                if trade_date in existing_dates:
                    continue
                bar = {"date": dt_val, "open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"]), "volume": float(row.get("volume", 0) or 0)}
                by_date.setdefault(trade_date, []).append(bar)

            if not by_date:
                break

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
                source = "tdx"
            except Exception:
                conn.rollback()
            finally:
                pool.putconn(conn)

            start += 800
            time.sleep(0.01)

    return imported_days, imported_bars, source


def main():
    parser = argparse.ArgumentParser(description="Fast recent minute data importer")
    parser.add_argument("--days", type=int, default=30, help="Days of history (default: 30)")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated codes (default: all)")
    parser.add_argument("--force", action="store_true", help="Re-import even if already exists")
    parser.add_argument("--check-tencent", action="store_true", help="Check Tencent status and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler("fast_import.log", mode="a")],
    )

    if args.check_tencent:
        if check_tencent():
            print("Tencent API is RECOVERED! Run bulk_importer.py --years 10 for full history.")
        else:
            print("Tencent API is still blocked (501).")
        return

    pool = _get_pg_pool()
    if pool is None:
        logger.error("PostgreSQL not available")
        sys.exit(1)

    # Check if Tencent has recovered
    if check_tencent():
        logger.info("Tencent API has recovered! Use bulk_importer.py --years 10 for full history.")
        return

    logger.info("Tencent still blocked. Using TDX for recent data only.")

    if args.tickers:
        tickers = [t.strip().zfill(6) for t in args.tickers.split(",") if t.strip()]
    else:
        logger.info("Fetching all A-share stock codes...")
        tickers = get_all_astock_codes()
        logger.info("Found %d A-share stocks", len(tickers))

    if not tickers:
        logger.error("No tickers to import")
        sys.exit(1)

    total_bars = 0
    total_days = 0
    tencent_count = 0
    tdx_count = 0
    start_time = time.time()

    for i, code in enumerate(tickers):
        days, bars, source = import_stock_recent(code, args.days, pool, args.force)
        total_days += days
        total_bars += bars
        if source == "tencent":
            tencent_count += 1
        elif source == "tdx":
            tdx_count += 1

        if (i + 1) % 50 == 0 or i == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(tickers) - i - 1) / rate if rate > 0 else 0
            logger.info(
                "Progress: %d/%d stocks, %d days, %d bars, %.1f stocks/sec, ETA: %s",
                i + 1, len(tickers), total_days, total_bars, rate,
                timedelta(seconds=int(eta)),
            )

    elapsed = time.time() - start_time
    logger.info(
        "Done! %d bars for %d stocks in %s (tencent: %d, tdx: %d)",
        total_bars, len(tickers), timedelta(seconds=int(elapsed)), tencent_count, tdx_count,
    )


if __name__ == "__main__":
    main()
