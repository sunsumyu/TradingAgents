"""A-share Level 1 snapshot recorder.

Records full-market snapshots (Plan A) plus high-frequency snapshots for
focus stocks (Plan B) from Tencent's free realtime quote API (qt.gtimg.cn),
into TDengine for time-series accumulation.

Plan A: all ~5,200 stocks, one full sweep every ~30s (60 codes per batch).
Plan B: focus list, swept every ~3s (Level 1 physical push limit is 3s SZ / 5s SH).

Snapshot payload per stock: price, cumulative volume/amount, five-level
order book, outer/inner disc. History accumulates from the moment recording
starts.

Usage::

    python -m tradingagents.dataflows.a_stock.snapshot_recorder          # A+B
    python -m tradingagents.dataflows.a_stock.snapshot_recorder --plan a
    python -m tradingagents.dataflows.a_stock.snapshot_recorder --plan b
    python -m tradingagents.dataflows.a_stock.snapshot_recorder --status
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from tradingagents.config import PG_DSN as _PG_DSN, TD_DSN as _TD_DSN
from tradingagents.dataflows.a_stock.worker_runtime import (
    AlreadyRunning,
    InstanceLock,
    log_handlers,
)

_PG_CONN = None

logger = logging.getLogger(__name__)

# Tencent realtime quote endpoint (Level 1, free). One request carries ~60 codes.
# HTTP + explicit no-proxy: the system proxy (127.0.0.1:7897) intercepts HTTPS
# handshakes and breaks batch fetches intermittently.
_QUOTE_URL = "http://qt.gtimg.cn/q="
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

try:
    import requests as _requests

    _SESSION = _requests.Session()
    _SESSION.trust_env = False  # bypass the system proxy
    _SESSION.headers.update(_HEADERS)
except ImportError:  # pragma: no cover
    _SESSION = None
    _OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# Plan A: whole market, batched sweeps.
MARKET_SWEEP_INTERVAL = 30.0   # seconds between full-market sweeps
BATCH_SIZE = 60                # codes per HTTP request
BATCH_PAUSE = 0.15             # seconds between batches (politeness)

# Plan B: focus list, high frequency.
FOCUS_SWEEP_INTERVAL = 3.0
DEFAULT_FOCUS_FILE = Path(__file__).parent / ".snapshot_focus.txt"

# Field offsets in Tencent's `~`-separated payload (GBK encoded).
_F_NAME = 1
_F_PRICE = 3
_F_LAST_CLOSE = 4
_F_VOLUME = 6                  # hands (手)
_F_OUTER = 7
_F_INNER = 8
_F_BID_PRICE = 9               # bid1..bid5 prices at 9,11,13,15,17; vols at 10,12,14,16,18
_F_ASK_PRICE = 19              # ask1..ask5 prices at 19,21,23,25,27; vols at 20,22,24,26,28

_STOCK_LIST_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
    "/Market_Center.getHQNodeData"
)
_LIST_CACHE = Path(__file__).parent / ".snapshot_stock_list.json"
_LIST_CACHE_TTL = 24 * 3600  # refresh daily

LOG_FILE = "snapshot_recorder.log"


def _http_get(url: str, timeout: float = 10.0) -> bytes:
    if _SESSION is not None:
        resp = _SESSION.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    req = urllib.request.Request(url, headers=_HEADERS)
    return _OPENER.open(req, timeout=timeout).read()


def get_all_astock_codes() -> list[str]:
    """All A-share codes, cached for a day."""
    if _LIST_CACHE.exists():
        age = time.time() - _LIST_CACHE.stat().st_mtime
        if age < _LIST_CACHE_TTL:
            codes = json.loads(_LIST_CACHE.read_text())
            if codes:
                return codes

    codes: list[str] = []
    page = 1
    while True:
        params = (
            f"?page={page}&num=100&sort=symbol&asc=1&node=hs_a"
            f"&symbol=&_s_r_a=init"
        )
        data = None
        for attempt in range(3):
            try:
                raw = _http_get(_STOCK_LIST_URL + params).decode("utf-8")
                data = json.loads(raw)
                break
            except Exception as exc:
                if attempt < 2:
                    time.sleep(2)
                else:
                    logger.warning("stock list page %d failed after 3 attempts: %s", page, exc)
        if data is None:
            break
        if not data:
            break
        for item in data:
            code = item.get("code", "")
            if len(code) == 6 and code.isdigit() and code[0] in ("0", "3", "6"):
                codes.append(code)
        if len(data) < 100:
            break
        page += 1
        time.sleep(0.1)

    codes = sorted(set(codes))
    if codes:
        _LIST_CACHE.write_text(json.dumps(codes))
    return codes


def load_focus_codes() -> list[str]:
    """Focus list for Plan B; defaults to a few liquid names if file missing."""
    if DEFAULT_FOCUS_FILE.exists():
        codes = [
            ln.strip().zfill(6)
            for ln in DEFAULT_FOCUS_FILE.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if codes:
            return codes
    return ["600000", "000001", "300750", "600519", "000858"]


def parse_quote_payload(raw: str) -> dict[str, dict]:
    """Parse the GBK `v_sh600000="..."` payload into {code: snapshot}."""
    out: dict[str, dict] = {}
    for line in raw.strip().split(";"):
        line = line.strip()
        if "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 46 or not key[2:].isdigit():
            continue
        code = key[2:]
        try:
            out[code] = {
                "price": float(vals[_F_PRICE]),
                "last_close": float(vals[_F_LAST_CLOSE]),
                "volume": int(vals[_F_VOLUME]),
                "outer_disc": int(vals[_F_OUTER]),
                "inner_disc": int(vals[_F_INNER]),
                "bid1_price": float(vals[9]), "bid1_vol": int(vals[10]),
                "bid2_price": float(vals[11]), "bid2_vol": int(vals[12]),
                "bid3_price": float(vals[13]), "bid3_vol": int(vals[14]),
                "bid4_price": float(vals[15]), "bid4_vol": int(vals[16]),
                "bid5_price": float(vals[17]), "bid5_vol": int(vals[18]),
                "ask1_price": float(vals[19]), "ask1_vol": int(vals[20]),
                "ask2_price": float(vals[21]), "ask2_vol": int(vals[22]),
                "ask3_price": float(vals[23]), "ask3_vol": int(vals[24]),
                "ask4_price": float(vals[25]), "ask4_vol": int(vals[26]),
                "ask5_price": float(vals[27]), "ask5_vol": int(vals[28]),
            }
        except (ValueError, IndexError):
            continue
    return out


def fetch_batch(prefixed: list[str], retries: int = 1) -> dict[str, dict]:
    """One HTTP request for up to ~60 prefixed codes (e.g. sh600000)."""
    url = _QUOTE_URL + ",".join(prefixed)
    for attempt in range(retries + 1):
        try:
            raw = _http_get(url).decode("gbk", errors="replace")
            return parse_quote_payload(raw)
        except Exception as exc:
            if attempt < retries:
                time.sleep(0.5)
                continue
            logger.warning("batch fetch failed (%s...): %s", prefixed[0], exc)
            return {}


def td_connect():
    import taosws
    return taosws.connect(_TD_DSN)


def pg_connect():
    """Get or create a PostgreSQL connection for snapshot archival."""
    global _PG_CONN
    if _PG_CONN is None:
        import psycopg2
        _PG_CONN = psycopg2.connect(_PG_DSN)
    return _PG_CONN


def ensure_schema(td) -> None:
    """Create the snapshot supertable if absent."""
    td.execute("""
        CREATE STABLE IF NOT EXISTS st_stock_snapshot (
            ts TIMESTAMP,
            price DOUBLE,
            last_close DOUBLE,
            volume BIGINT,
            outer_disc BIGINT,
            inner_disc BIGINT,
            bid1_price DOUBLE, bid1_vol BIGINT,
            bid2_price DOUBLE, bid2_vol BIGINT,
            bid3_price DOUBLE, bid3_vol BIGINT,
            bid4_price DOUBLE, bid4_vol BIGINT,
            bid5_price DOUBLE, bid5_vol BIGINT,
            ask1_price DOUBLE, ask1_vol BIGINT,
            ask2_price DOUBLE, ask2_vol BIGINT,
            ask3_price DOUBLE, ask3_vol BIGINT,
            ask4_price DOUBLE, ask4_vol BIGINT,
            ask5_price DOUBLE, ask5_vol BIGINT
        ) TAGS (ticker BINARY(8), market BINARY(4))
    """)
    # Plan B's tighter-grained stream goes to its own supertable so it
    # doesn't drown out Plan A's 30s sweeps in queries.
    td.execute("""
        CREATE STABLE IF NOT EXISTS st_stock_snapshot_hf (
            ts TIMESTAMP,
            price DOUBLE,
            last_close DOUBLE,
            volume BIGINT,
            outer_disc BIGINT,
            inner_disc BIGINT,
            bid1_price DOUBLE, bid1_vol BIGINT,
            bid2_price DOUBLE, bid2_vol BIGINT,
            bid3_price DOUBLE, bid3_vol BIGINT,
            bid4_price DOUBLE, bid4_vol BIGINT,
            bid5_price DOUBLE, bid5_vol BIGINT,
            ask1_price DOUBLE, ask1_vol BIGINT,
            ask2_price DOUBLE, ask2_vol BIGINT,
            ask3_price DOUBLE, ask3_vol BIGINT,
            ask4_price DOUBLE, ask4_vol BIGINT,
            ask5_price DOUBLE, ask5_vol BIGINT
        ) TAGS (ticker BINARY(8), market BINARY(4))
    """)
    
    # Create PostgreSQL archival table
    pg = pg_connect()
    with pg.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stock_snapshot_archive (
                ts TIMESTAMPTZ NOT NULL,
                ticker VARCHAR(8) NOT NULL,
                market VARCHAR(4) NOT NULL,
                stream VARCHAR(2) NOT NULL,
                price DOUBLE PRECISION,
                last_close DOUBLE PRECISION,
                volume BIGINT,
                outer_disc BIGINT,
                inner_disc BIGINT,
                bid1_price DOUBLE PRECISION, bid1_vol BIGINT,
                bid2_price DOUBLE PRECISION, bid2_vol BIGINT,
                bid3_price DOUBLE PRECISION, bid3_vol BIGINT,
                bid4_price DOUBLE PRECISION, bid4_vol BIGINT,
                bid5_price DOUBLE PRECISION, bid5_vol BIGINT,
                ask1_price DOUBLE PRECISION, ask1_vol BIGINT,
                ask2_price DOUBLE PRECISION, ask2_vol BIGINT,
                ask3_price DOUBLE PRECISION, ask3_vol BIGINT,
                ask4_price DOUBLE PRECISION, ask4_vol BIGINT,
                ask5_price DOUBLE PRECISION, ask5_vol BIGINT,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (ts, ticker, stream)
            );
            CREATE INDEX IF NOT EXISTS idx_snapshot_ticker ON stock_snapshot_archive(ticker);
            CREATE INDEX IF NOT EXISTS idx_snapshot_ts ON stock_snapshot_archive(ts);
        """)
    pg.commit()


def _insert_values_line(snap: dict) -> str:
    return (
        f"NOW, {snap['price']}, {snap['last_close']}, {snap['volume']}, "
        f"{snap['outer_disc']}, {snap['inner_disc']}, "
        f"{snap['bid1_price']}, {snap['bid1_vol']}, "
        f"{snap['bid2_price']}, {snap['bid2_vol']}, "
        f"{snap['bid3_price']}, {snap['bid3_vol']}, "
        f"{snap['bid4_price']}, {snap['bid4_vol']}, "
        f"{snap['bid5_price']}, {snap['bid5_vol']}, "
        f"{snap['ask1_price']}, {snap['ask1_vol']}, "
        f"{snap['ask2_price']}, {snap['ask2_vol']}, "
        f"{snap['ask3_price']}, {snap['ask3_vol']}, "
        f"{snap['ask4_price']}, {snap['ask4_vol']}, "
        f"{snap['ask5_price']}, {snap['ask5_vol']} "
    )


_PG_COLS = (
    "ticker", "market", "stream",
    "price", "last_close", "volume", "outer_disc", "inner_disc",
    "bid1_price", "bid1_vol", "bid2_price", "bid2_vol", "bid3_price", "bid3_vol",
    "bid4_price", "bid4_vol", "bid5_price", "bid5_vol", "ask1_price", "ask1_vol",
    "ask2_price", "ask2_vol", "ask3_price", "ask3_vol", "ask4_price", "ask4_vol",
    "ask5_price", "ask5_vol",
)
_PG_VALUE_KEYS = (
    "price", "last_close", "volume", "outer_disc", "inner_disc",
    "bid1_price", "bid1_vol", "bid2_price", "bid2_vol", "bid3_price", "bid3_vol",
    "bid4_price", "bid4_vol", "bid5_price", "bid5_vol", "ask1_price", "ask1_vol",
    "ask2_price", "ask2_vol", "ask3_price", "ask3_vol", "ask4_price", "ask4_vol",
    "ask5_price", "ask5_vol",
)


def archive_snapshots_pg(snaps: dict[str, dict], stable: str) -> int:
    """Append the same batch to PostgreSQL as a durable second copy."""
    if not snaps:
        return 0
    from psycopg2.extras import execute_values
    pg = pg_connect()
    stream = "HF" if stable.endswith("_hf") else "A"
    rows = []
    for code, snap in snaps.items():
        market = "SH" if code.startswith("6") else "SZ"
        rows.append((code, market, stream, *[snap[k] for k in _PG_VALUE_KEYS]))
    # execute_values canonical form: statement carries `VALUES %s`; NOW() lives in
    # the row template so every row of a page shares the transaction timestamp.
    template = "(NOW()," + ",".join(["%s"] * len(_PG_COLS)) + ")"
    sql = (
        "INSERT INTO stock_snapshot_archive (ts, "
        + ",".join(_PG_COLS)
        + ") VALUES %s ON CONFLICT (ts, ticker, stream) DO NOTHING"
    )
    try:
        with pg.cursor() as cur:
            execute_values(cur, sql, rows, template=template, page_size=100)
        pg.commit()
        return len(rows)
    except Exception:
        pg.rollback()
        logger.exception("PostgreSQL snapshot archive failed")
        return 0


def write_snapshots(td, snaps: dict[str, dict], stable: str) -> int:
    """Auto-create child tables and insert, then archive to PostgreSQL."""
    if not snaps:
        return 0
    written = 0
    # Chunk the multi-insert so one bad code can't kill the whole sweep.
    # TDengine syntax: one INSERT INTO, then repeated `tbl USING st TAGS(...) VALUES (...)`.
    items = list(snaps.items())
    for i in range(0, len(items), 100):
        chunk = items[i:i + 100]
        parts = []
        for code, snap in chunk:
            market = "SH" if code.startswith("6") else "SZ"
            table = f"snap_{stable[-2:]}_{code}"
            parts.append(
                f'{table} USING {stable} TAGS ("{code}", "{market}") VALUES ({_insert_values_line(snap)})'
            )
        sql = "INSERT INTO " + " ".join(parts)
        try:
            td.execute(sql)
            written += len(chunk)
        except Exception as exc:
            logger.warning("TDengine write failed (%d rows): %s", len(chunk), exc)
    archived = archive_snapshots_pg(snaps, stable)
    if archived != len(snaps):
        logger.warning("snapshot dual-write gap: TDengine=%d PostgreSQL=%d", written, archived)
    return written


def in_trading_hours(now: datetime | None = None) -> bool:
    """A-share continuous+call auction sessions, Mon-Fri."""
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return (915 <= t <= 1131) or (1257 <= t <= 1501)


def sweep_market(td, codes: list[str]) -> tuple[int, float]:
    """Plan A: one full-market sweep. Returns (rows, seconds)."""
    start = time.time()
    rows = 0
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i:i + BATCH_SIZE]
        prefixed = [("sh" if c.startswith("6") else "sz") + c for c in batch]
        snaps = fetch_batch(prefixed)
        rows += write_snapshots(td, snaps, "st_stock_snapshot")
        time.sleep(BATCH_PAUSE)
    return rows, time.time() - start


def sweep_focus(td, codes: list[str]) -> int:
    """Plan B: one focus-list sweep (fast, single batch)."""
    prefixed = [("sh" if c.startswith("6") else "sz") + c for c in codes]
    snaps = fetch_batch(prefixed[:BATCH_SIZE])
    return write_snapshots(td, snaps, "st_stock_snapshot_hf")


def run(plan: str, focus_codes: list[str] | None = None) -> None:
    td = td_connect()
    ensure_schema(td)

    codes = get_all_astock_codes()
    codes_loaded_at = time.time()
    logger.info("Plan %s: %d market codes loaded", plan.upper(), len(codes))

    focus = focus_codes or load_focus_codes()
    if plan in ("a", "ab"):
        logger.info("Plan A active: full sweep every %.0fs", MARKET_SWEEP_INTERVAL)
    if plan in ("b", "ab"):
        logger.info("Plan B active: %d focus codes every %.0fs", len(focus), FOCUS_SWEEP_INTERVAL)

    run_a = plan in ("a", "ab")
    run_b = plan in ("b", "ab")

    last_market_sweep = 0.0
    sweeps_done = 0
    total_rows = 0

    while True:
        now = datetime.now()
        if not in_trading_hours(now):
            # Sleep until next session starts; check every minute.
            time.sleep(60)
            continue

        # Plan B: high-frequency focus sweeps.
        if run_b:
            rows = sweep_focus(td, focus)
            total_rows += rows

        # Plan A: refresh the stock list daily (retry hourly if startup fetch failed).
        if run_a:
            refresh_due = (
                (not codes and time.time() - codes_loaded_at >= 3600)
                or (codes and time.time() - codes_loaded_at >= _LIST_CACHE_TTL)
            )
            if refresh_due:
                refreshed = get_all_astock_codes()
                codes_loaded_at = time.time()
                # A partial refetch must never shrink coverage.
                if len(refreshed) > len(codes):
                    codes = refreshed
                    logger.info("stock list refreshed: %d codes", len(codes))

        # Plan A: market sweep when due.
        if run_a and time.time() - last_market_sweep >= MARKET_SWEEP_INTERVAL:
            rows, elapsed = sweep_market(td, codes)
            total_rows += rows
            sweeps_done += 1
            last_market_sweep = time.time()
            if sweeps_done % 10 == 1:
                logger.info(
                    "market sweep #%d: %d rows in %.1fs, total rows %d",
                    sweeps_done, rows, elapsed, total_rows,
                )

        time.sleep(FOCUS_SWEEP_INTERVAL if run_b else 5.0)


def status() -> None:
    import taosws
    td = taosws.connect(_TD_DSN)
    for stable in ("st_stock_snapshot", "st_stock_snapshot_hf"):
        try:
            r = td.query(f"SELECT COUNT(*) FROM {stable}")
            n = list(r)[0][0]
            r2 = td.query(f"SELECT COUNT(DISTINCT tbname) FROM {stable}")
            tables = list(r2)[0][0]
            r3 = td.query(f"SELECT FIRST(ts), LAST(ts) FROM {stable}")
            first, last = list(r3)[0]
            print(f"{stable}: {n} rows, {tables} stocks, {first} ~ {last}")
        except Exception as exc:
            print(f"{stable}: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Level 1 snapshot recorder")
    parser.add_argument("--plan", choices=["a", "b", "ab"], default="ab",
                        help="a=full market 30s, b=focus 3s, ab=both (default)")
    parser.add_argument("--focus", type=str, default=None,
                        help="Comma-separated focus codes for plan B")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=log_handlers(LOG_FILE),
    )

    if args.status:
        status()
        return

    focus = None
    if args.focus:
        focus = [t.strip().zfill(6) for t in args.focus.split(",") if t.strip()]

    try:
        with InstanceLock("snapshot_recorder"):
            try:
                run(args.plan, focus)
            except KeyboardInterrupt:
                logger.info("stopped")
    except AlreadyRunning as exc:
        logger.error("%s — refusing to start a second recorder", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
