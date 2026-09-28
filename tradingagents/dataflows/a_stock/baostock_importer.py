"""BaoStock minute-data importer — imports 5/15/30/60min for all A-shares.

BaoStock provides free historical minute data going back to 2020-01-01 (~6 years).

Hardened against the three failure modes observed in production:
  1. Proxy TUN fake-IP DNS blackholes the server host → resolve real IP via DoH.
  2. baostock's send_msg() swallows exceptions and busy-loops on dead sockets
     → patched send_msg with size cap, deadline, and raising behavior.
  3. Connection death mid-run silently marked stocks complete with 0 bars
     → failed fetches are retried with reconnect and never marked complete;
     ``--rebuild`` recovers state from PG ground truth.

Usage::

    python -m tradingagents.dataflows.a_stock.baostock_importer
    python -m tradingagents.dataflows.a_stock.baostock_importer --intervals 5,15
    python -m tradingagents.dataflows.a_stock.baostock_importer --status
    python -m tradingagents.dataflows.a_stock.baostock_importer --rebuild
"""

from __future__ import annotations

import argparse
import atexit
import errno
import json
import logging
import os
import select as _select
import signal
import socket
import sys
import threading
import time
import zlib
from datetime import datetime
from pathlib import Path

import baostock as bs
from tradingagents.cache.manager import _get_pg_pool
from tradingagents.dataflows.a_stock.worker_runtime import (
    AlreadyRunning,
    InstanceLock,
    log_handlers,
)

logger = logging.getLogger(__name__)

# BaoStock's sockets have NO timeout — a dead server blocks forever (the
# historical "process alive, progress frozen" stalls). Force a global timeout
# so hangs surface as exceptions that the reconnect logic can handle. This also
# bounds baostock's internal login() connect() call.
socket.setdefaulttimeout(20)

# BaoStock frequency → (PG data_type, param_hash, tdengine stable, tdengine prefix, baostock name)
INTERVAL_MAP = {
    "5":  ("kline_5min",  "5min",  "st_stock_5min",  "st_5min",  "5min"),
    "15": ("kline_15min", "15min", "st_stock_15min", "st_15min", "15min"),
    "30": ("kline_30min", "30min", "st_stock_30min", "st_30min", "30min"),
    "60": ("kline_60min", "60min", "st_stock_60min", "st_60min", "60min"),
}

# 2020-01-01 to present = 6+ years of data
START_DATE = "2020-01-01"
END_DATE = "2026-09-10"

# Minute series are expected from this year onward. kline_daily goes back to
# 2014, so a 2016-listed stock still has daily history from 2016 — capping at
# 2020 keeps "complete" meaning "has the full minute window we asked for"
# instead of demanding minute bars from before this import ever ran.
MINUTE_HISTORY_START = int(START_DATE[:4])

PROGRESS_DIR = Path(__file__).parent / ".baostock_progress"

# The proxy environment (TUN fake-IP DNS) breaks plain DNS for
# public-api.baostock.com; resolve the real IP over DoH at startup.
BAOSTOCK_HOST = "public-api.baostock.com"
BAOSTOCK_FALLBACK_IP = "114.94.20.42"  # last known-good A record


def _progress_file(interval: str) -> Path:
    return PROGRESS_DIR / f"bs_{interval}min_state.json"


def get_all_tickers_bs() -> list[str]:
    """Get all A-share tickers from BaoStock (format: sh.600519)."""
    import baostock as bs

    rs = bs.query_all_stock(day=END_DATE)
    tickers = []
    while rs.error_code == '0' and rs.next():
        row = rs.get_row_data()
        code = row[0]  # e.g. "sh.600519"
        # Filter: only A-shares (sh.6xxxxx, sz.0xxxxx, sz.3xxxxx);
        # exclude sz.399xxx market indexes
        if code.startswith("sz.399"):
            continue
        if (code.startswith("sh.6") or code.startswith("sz.0") or code.startswith("sz.3")):
            tickers.append(code)

    if not tickers:
        # Fallback: read from PG
        logger.info("BaoStock query_all_stock returned 0, using PG stock list")
        pool = _get_pg_pool()
        if pool:
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT DISTINCT ticker FROM data_history WHERE data_type='kline_daily' ORDER BY ticker")
                    for row in cur.fetchall():
                        t = row[0]
                        bs_ticker = f"sh.{t}" if t.startswith("6") else f"sz.{t}"
                        tickers.append(bs_ticker)
            finally:
                pool.putconn(conn)
    return tickers


def load_progress(interval: str) -> dict:
    f = _progress_file(interval)
    if not f.exists():
        return {"completed": [], "total_bars": 0}
    try:
        return json.loads(f.read_text())
    except Exception:
        return {"completed": [], "total_bars": 0}


def save_progress(interval: str, state: dict) -> None:
    """Persist the run state for an interval ("30" -> bs_30min_state.json)."""
    _write_progress_file(_progress_file(interval), state)


def save_named_progress(name: str, state: dict) -> None:
    """Write ``bs_<name>_state.json`` verbatim.

    Unlike save_progress this does not route through the ``<interval>min``
    naming helper, so callers can persist auxiliary baselines such as
    ``30min_full`` / ``30min_shallow`` without "min" being appended twice.
    """
    _write_progress_file(PROGRESS_DIR / f"bs_{name}_state.json", state)


def _write_progress_file(f: Path, state: dict) -> None:
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(f)
    except PermissionError:
        try:
            import shutil
            shutil.copy2(str(tmp), str(f))
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def bs_code_to_ticker(bs_code: str) -> str:
    """Convert BaoStock code (sh.600519) to plain ticker (600519)."""
    return bs_code.split(".")[1]


# ── Proxy-safe connection layer ──────────────────────────────────────────────

def resolve_baostock_ip() -> str:
    """Resolve the real BaoStock IP via DNS-over-HTTPS.

    The proxy TUN returns a fake IP (198.18.0.x) for every domain via plain
    DNS, which blackholes the TCP session. DoH responses over HTTPS survive.
    """
    import json as _json
    import urllib.request
    for server in ("223.5.5.5", "1.12.12.12"):
        try:
            url = f"https://{server}/resolve?name={BAOSTOCK_HOST}&type=A"
            req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                answers = _json.loads(r.read()).get("Answer", [])
            ips = [a["data"] for a in answers if a.get("type") == 1]
            if ips:
                return ips[0]
        except Exception as exc:
            logger.warning("DoH resolve via %s failed: %r", server, exc)
    return BAOSTOCK_FALLBACK_IP


class _BaostockSocketGuard:
    """Wraps the baostock socket so EOF raises instead of letting
    send_msg() busy-loop forever on empty recv (the freeze mechanism).

    Also forces an explicit socket timeout: baostock creates sockets without
    one, and a timeoutless recv blocks forever even inside our deadline
    loop (the deadline check only runs between recv calls)."""

    RECV_TIMEOUT = 30  # seconds per recv chunk — fail fast on dead connections (was 15s; bumped for flaky BaoStock link)

    def __init__(self, sock):
        self._sock = sock

    def _recv_bounded(self, bufsize):
        """recv with a hard, interruptible deadline via select.select.

        Windows socket.settimeout() proved unreliable for the
        'connect succeeds but stream never fills' case — select.select
        enforces a true wall.
        """
        import select as _select
        sock = self._sock
        rlist, _, _ = _select.select([sock], [], [], self.RECV_TIMEOUT)
        if not rlist:
            raise TimeoutError(f"recv exceeded {self.RECV_TIMEOUT}s")
        return sock.recv(bufsize)

    def send(self, data):
        return self._sock.send(data)

    def recv(self, bufsize):
        chunk = self._recv_bounded(bufsize)
        if not chunk:
            raise ConnectionError("BaoStock closed the connection (EOF)")
        return chunk

    def close(self):
        return self._sock.close()

    def __getattr__(self, name):
        return getattr(self._sock, name)


# Receive bounds for one baostock message (a full page of rows is ~1MB)
_BS_MAX_RECV = 64 * 1024 * 1024
_BS_MSG_DEADLINE = 60  # seconds per request/response cycle
_BS_STOCK_TIMEOUT = 180  # hard wall per stock (3min — enough for 7-year fetches with network variance)

_TIMEOUT_SENTINEL = object()  # module-level singleton for _run_with_timeout


def _install_patched_send_msg() -> None:
    """Replace baostock's send_msg with a hardened version.

    The original swallows every exception (returns None) and loops on recv
    forever — no size cap, no deadline — which combined with a proxy-mangled
    connection produces silent infinite busy-loops. This version raises so
    callers (and our retry logic) can see failures, and bounds every cycle.
    """
    import baostock.util.socketutil as sockutil
    import baostock.common.contants as cons
    import baostock.common.context as bctx
    import zlib

    if getattr(sockutil, "_ta_patched", False):
        return

    def _send_msg(msg):
        if not hasattr(bctx, "default_socket"):
            raise ConnectionError("BaoStock socket not initialized (not logged in)")
        sock_ = getattr(bctx, "default_socket")
        msg = msg + "\n"
        sock_.send(bytes(msg, encoding="utf-8"))
        receive = b""
        deadline = time.monotonic() + _BS_MSG_DEADLINE
        while True:
            try:
                chunk = sock_.recv(8192)
            except (TimeoutError, ConnectionError, OSError):
                raise  # _BaostockSocketGuard / _recv_bounded already classified these
            receive += chunk
            if len(receive) > _BS_MAX_RECV:
                raise ConnectionError(f"BaoStock response exceeds {_BS_MAX_RECV} bytes")
            if time.monotonic() > deadline:
                raise TimeoutError(f"BaoStock response not complete within {_BS_MSG_DEADLINE}s")
            if receive[-13:] == b"<![CDATA[]]>\n":
                break
        head_str = bytes.decode(receive[0:cons.MESSAGE_HEADER_LENGTH])
        head_arr = head_str.split(cons.MESSAGE_SPLIT)
        if head_arr[1] in cons.COMPRESSED_MESSAGE_TYPE_TUPLE:
            head_inner_length = int(head_arr[2])
            try:
                decompressed = zlib.decompress(
                    receive[cons.MESSAGE_HEADER_LENGTH:cons.MESSAGE_HEADER_LENGTH + head_inner_length]
                )
            except zlib.error as exc:
                raise ConnectionError(f"BaoStock gzip decompress failed: {exc}") from exc
            try:
                body_str = bytes.decode(decompressed)
            except UnicodeDecodeError as exc:
                raise ConnectionError(f"BaoStock body decode failed: {exc}") from exc
            return head_str + body_str
        try:
            return bytes.decode(receive)
        except UnicodeDecodeError as exc:
            raise ConnectionError(f"BaoStock response decode failed: {exc}") from exc

    sockutil.send_msg = _send_msg
    sockutil._ta_patched = True


def _apply_socket_guard() -> None:
    import baostock.common.context as _ctx
    sock = getattr(_ctx, "default_socket", None)
    if sock is not None and not isinstance(sock, _BaostockSocketGuard):
        _ctx.default_socket = _BaostockSocketGuard(sock)


def _bs_login_guarded(timeout: float = 60) -> "object":
    """Call bs.login() with a hard time wall.

    baostock's login() creates a raw socket via get_default_socket() that
    inherits no timeout and isn't guarded by _BaostockSocketGuard until
    *after* login succeeds — so a frozen login blocks forever. We run it
    in a worker thread and abandon it past ``timeout``.
    """
    import baostock as bs
    import threading

    box: dict = {}

    def _worker():
        try:
            box["result"] = bs.login()
        except Exception as exc:
            box["error"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"BaoStock login exceeded {timeout}s")
    if "error" in box:
        raise box["error"]
    return box.get("result")


def bs_login() -> bool:
    """Login to BaoStock through the proxy-safe path (real IP + guards)."""
    import baostock.common.contants as _contants

    _install_patched_send_msg()

    real_ip = resolve_baostock_ip()
    _contants.BAOSTOCK_SERVER_IP = real_ip
    logger.info("BaoStock server: %s -> %s", BAOSTOCK_HOST, real_ip)

    try:
        lg = _bs_login_guarded(timeout=60)
    except Exception as exc:
        logger.error("BaoStock login failed: %r", exc)
        return False
    if lg.error_code != '0':
        logger.error("BaoStock login failed: %s", lg.error_msg)
        return False
    _apply_socket_guard()
    return True


def _cleanup_baostock_session() -> None:
    """Force-clean a stale baostock session before reconnecting.

    A timed-out worker thread leaves default_socket open + a stale user_id in
    context — subsequent login() either reuses the dead socket or errors with
    "用户未登录". Tear everything down cleanly.
    """
    import baostock as bs
    import baostock.common.context as _ctx
    try:
        bs.logout()
    except Exception:
        pass
    # Clear the stale socket/user_id so next login creates a fresh one
    for attr in ("default_socket", "user_id"):
        if hasattr(_ctx, attr):
            try:
                delattr(_ctx, attr)
            except Exception:
                setattr(_ctx, attr, None)
    # Best-effort force-close the old socket
    sock = getattr(_ctx, "default_socket", None)
    if sock is not None:
        try:
            sock.close()
        except Exception:
            pass


def bs_reconnect(max_attempts: int = 5) -> bool:
    """Force-reconnect the BaoStock session. Returns True on success."""
    import baostock as bs

    for attempt in range(1, max_attempts + 1):
        _cleanup_baostock_session()
        try:
            lg = bs_login()
        except Exception as exc:
            logger.warning("BaoStock reconnect attempt %d failed: %r", attempt, exc)
            time.sleep(5 * attempt)
            continue
        if lg:
            logger.info("BaoStock reconnected (attempt %d)", attempt)
            return True
        logger.warning("BaoStock reconnect attempt %d failed: login refused", attempt)
        time.sleep(5 * attempt)
    return False


def rebuild_state_from_pg(interval: str, min_days: int = 100) -> dict:
    """Rebuild progress state from PG ground truth.

    A stock counts as completed only if it has >= min_days of daily bar-batches
    in data_history. Protects against state files corrupted by connection-death
    runs that marked stocks complete with 0 bars.
    """
    data_type, param_hash, _, _, _ = INTERVAL_MAP[interval]
    pool = _get_pg_pool()
    if pool is None:
        raise RuntimeError("PostgreSQL not available")
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT ticker, COUNT(*) FROM data_history
                   WHERE data_type = %s AND param_hash = %s
                   GROUP BY ticker HAVING COUNT(*) >= %s""",
                (data_type, param_hash, min_days),
            )
            tickers = {row[0] for row in cur.fetchall()}
    finally:
        pool.putconn(conn)

    bs_codes = sorted(f"sh.{t}" if t.startswith("6") else f"sz.{t}" for t in tickers)
    return {"completed": bs_codes, "total_bars": 0}


def coverage_from_pg(interval: str) -> dict:
    """Classify every ticker by the year-span of history actually stored in PG.

    Row counts lie: a stock whose 2021-2022 fetches never landed still has
    thousands of rows from the other years, so ``>= min_days`` marks it complete
    even though a chunk of its history is missing. What matters is where the
    data starts, whether the years present form an unbroken run, and whether
    that run reaches the current year.

    "Where it starts" cannot be judged against a fixed year: a stock listed in
    2023 has no 2020 bars and must not be re-crawled forever. ``kline_daily``
    spans 2014+ and is the reference for each ticker's true first year — a
    minute series is only expected from max(that year, MINUTE_HISTORY_START).

    Returns {"full": [bs_codes], "shallow": [bs_codes],
             "gaps": {code: (first, last, years, expected_first)}}.
    """
    data_type, param_hash, _, _, _ = INTERVAL_MAP[interval]
    pool = _get_pg_pool()
    if pool is None:
        raise RuntimeError("PostgreSQL not available")
    current_year = int(END_DATE[:4])
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            # Listing-year reference: kline_daily reaches back to 2014, so its
            # first year per ticker approximates when the stock started trading.
            cur.execute(
                """SELECT ticker, min(extract(year from trade_date))::int
                   FROM data_history
                   WHERE data_type = 'kline_daily'
                   GROUP BY ticker"""
            )
            ref_first = {t: y for t, y in cur.fetchall()}
            cur.execute(
                """SELECT ticker,
                          min(extract(year from trade_date))::int,
                          max(extract(year from trade_date))::int,
                          count(DISTINCT extract(year from trade_date))::int
                   FROM data_history
                   WHERE data_type = %s AND param_hash = %s
                   GROUP BY ticker""",
                (data_type, param_hash),
            )
            rows = cur.fetchall()
    finally:
        pool.putconn(conn)

    def to_bs(t: str) -> str:
        return f"sh.{t}" if t.startswith("6") else f"sz.{t}"

    full, shallow, gaps = [], [], {}
    for ticker, first_year, last_year, n_years in rows:
        code = to_bs(ticker)
        expected_first = max(ref_first.get(ticker, MINUTE_HISTORY_START), MINUTE_HISTORY_START)
        complete = (
            n_years == last_year - first_year + 1
            and last_year >= current_year
            and first_year <= expected_first
        )
        if complete:
            full.append(code)
        else:
            shallow.append(code)
            gaps[code] = (first_year, last_year, n_years, expected_first)
    return {"full": sorted(full), "shallow": sorted(shallow), "gaps": gaps}


def _fetch_bars_chunked(bs_code: str, freq: str) -> tuple[list[dict], bool]:
    """Fetch all bars for one stock, querying year-by-year.

    BaoStock's deep pagination is pathologically slow (~8 pages for a 6-year
    5min range = 190s); year chunks stay within 1-2 pages each (~16s total).

    Returns (bars, partial):
      - bars: collected bars (may be partial if some years failed)
      - partial: True if any year failed (data is incomplete, needs retry)
    """
    import baostock as bs

    bars: list[dict] = []
    partial = False
    start_year = int(START_DATE[:4])
    end_year = int(END_DATE[:4])
    for year in range(start_year, end_year + 1):
        sd = START_DATE if year == start_year else f"{year}-01-01"
        ed = END_DATE if year == end_year else f"{year}-12-31"

        # Retry the year-chunk per BaoStock's intermittent throttling
        rs = None
        for _yr_attempt in range(4):
            try:
                rs = bs.query_history_k_data_plus(
                    bs_code,
                    "date,open,high,low,close,volume,amount",
                    start_date=sd,
                    end_date=ed,
                    frequency=freq,
                    adjustflag="3",
                )
                if rs.error_code == '0':
                    break
                logger.warning("BaoStock %s %s %s~%s error: %s (attempt %d/4)",
                               bs_code, freq, sd, ed, rs.error_msg, _yr_attempt + 1)
            except (TimeoutError, ConnectionError, OSError) as exc:
                logger.warning("BaoStock %s %s %s~%s recv fail: %r (attempt %d/4)",
                               bs_code, freq, sd, ed, exc, _yr_attempt + 1)
                rs = None
            time.sleep(10 * (_yr_attempt + 1))
        if rs is None or rs.error_code != '0':
            # This year failed — keep bars collected so far, mark as partial
            logger.warning("BaoStock year %d failed for %s %s after 4 attempts (keeping %d bars so far)",
                           year, bs_code, freq, len(bars))
            partial = True
            break

        year_bars = 0
        while rs.error_code == '0' and rs.next():
            row = rs.get_row_data()
            try:
                date_str = row[0]  # "2023-09-01"
                o = float(row[1]) if row[1] else 0
                h = float(row[2]) if row[2] else 0
                l = float(row[3]) if row[3] else 0
                c = float(row[4]) if row[4] else 0
                v = int(float(row[5])) if row[5] else 0
                a = float(row[6]) if len(row) > 6 and row[6] else 0
                if o == 0 and c == 0:
                    continue  # skip empty rows
                bars.append({"date": date_str, "open": o, "high": h, "low": l, "close": c, "volume": v, "amount": a})
                year_bars += 1
            except (ValueError, IndexError):
                continue
        logger.info("BaoStock %s %s %s~%s: %d bars", bs_code, freq, sd, ed, year_bars)
        # After finishing the year-chunk, verify the connection is still healthy
        if rs.error_code != '0':
            logger.warning("BaoStock query broke for %s %s: %s (keeping %d bars so far)",
                           bs_code, freq, rs.error_msg, len(bars))
            partial = True
            break
    if not bars:
        return [], False
    # BaoStock's minute `date` field is date-only; stamp HH:MM:SS from the
    # session grid so intra-day bars keep distinct timestamps everywhere downstream
    from .utils import resolve_dateonly_bars as _resolve
    bars, _ = _resolve(bars, f"kline_{freq}min")
    return bars, partial


# Backwards-compat alias (callers built their own object())


def _run_with_timeout(func, arg, timeout: float) -> object:
    """Run a blocking BaoStock call in a worker thread with timeout.

    On timeout, abandons the daemon thread (it will die when process exits).
    The next call to baostock will create a fresh socket via bs_reconnect().

    DO NOT close the socket here — that causes 10038 WSAENOTSOCK errors
    when the daemon thread continues using it.
    """
    box: dict = {}

    def _worker():
        try:
            box["result"] = func(arg)
        except BaseException as exc:
            box["error"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        # Timeout: abandon the thread, don't touch the socket
        # The daemon thread will die when the process exits
        # Next bs_reconnect() will create a fresh socket
        return _TIMEOUT_SENTINEL
    if "error" in box:
        raise box["error"]
    return box.get("result")


# Backwards-compat alias (callers built their own object())


def import_stock_bs(bs_code: str, freq: str, pool, bs_session) -> tuple[str, int]:
    """Import one stock for one frequency from BaoStock.

    Returns (status, bars_count) where status is:
      - "ok":      data fetched and written to PG (complete)
      - "partial": some years fetched and written, but incomplete — caller should retry
      - "empty":   query succeeded but stock has no minute data (legitimately)
      - "failed":  connection/query error — caller must NOT mark as complete
    """
    import baostock as bs

    data_type, param_hash, _, _, bs_name = INTERVAL_MAP[freq]
    ticker = bs_code_to_ticker(bs_code)

    try:
        result = _run_with_timeout(lambda _: _fetch_bars_chunked(bs_code, freq), None, _BS_STOCK_TIMEOUT)
        if result is _TIMEOUT_SENTINEL:
            logger.warning("BaoStock fetch timeout (> %ds) for %s %s — abandoning stock", _BS_STOCK_TIMEOUT, bs_code, freq)
            return "failed", 0
        bars, partial = result  # type: ignore[misc]
    except Exception as exc:
        logger.warning("BaoStock exception %s/%s: %r", ticker, freq, exc)
        return "failed", 0

    if not bars:
        return "empty", 0

    # Group by trade_date
    by_date: dict[str, list[dict]] = {}
    for bar in bars:
        td = bar["date"][:10]
        by_date.setdefault(td, []).append(bar)

    # Insert into PG (single batched statement — per-row execute was ~140s/stock)
    conn = pool.getconn()
    inserted = 0
    bars_count = 0
    written = False
    try:
        with conn.cursor() as cur:
            from psycopg2.extras import execute_values
            rows = [
                (ticker, data_type, td, param_hash,
                 json.dumps(day_bars, ensure_ascii=False), time.time())
                for td, day_bars in sorted(by_date.items())
            ]
            execute_values(
                cur,
                """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                   VALUES %s
                   ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                     result = EXCLUDED.result,
                     updated_at = EXCLUDED.updated_at""",
                rows,
                template="(%s, %s, %s, %s, %s, to_timestamp(%s))",
                page_size=200,
            )
            inserted = len(rows)
            bars_count = len(bars)
        conn.commit()
        written = True
    except Exception as exc:
        conn.rollback()
        logger.error("PG write failed %s/%s: %s", ticker, freq, exc)
    finally:
        pool.putconn(conn)

    # Critical: a PG write failure must NOT be reported as success — otherwise the
    # stock is marked complete with zero rows persisted (silent data loss).
    if not written:
        return "failed", 0
    if partial:
        logger.info("%s/%s: PARTIAL — %d bars saved, %d dates, needs retry for remaining years",
                     ticker, freq, bars_count, len(by_date))
        return "partial", bars_count
    return "ok", bars_count


def main():
    parser = argparse.ArgumentParser(description="BaoStock minute-data importer")
    parser.add_argument("--intervals", type=str, default="5,15,30,60",
                        help="Comma-separated frequencies (5,15,30,60)")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated bs_codes (sh.600519)")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--rebuild", action="store_true",
                        help="Rebuild progress state from PG ground truth (repairs corrupted state files)")
    parser.add_argument("--min-days", type=int, default=100,
                        help="Min PG day-rows for a stock to count as complete during --rebuild "
                             "(use 800 to force re-import of partial data)")
    parser.add_argument("--coverage", action="store_true",
                        help="Report how many years of history each stock actually has in PG "
                             "(year-contiguity, not just row count) and write two state "
                             "baselines: '_full' = skip these, '_shallow' = re-import these")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=log_handlers("baostock_import.log"),
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
            logger.info("%smin: %d stocks, %d bars", iv, c, state.get("total_bars", 0))
        return

    if args.coverage:
        # Baseline a run without guessing: stocks with an unbroken year span are
        # already in PG and must not be re-fetched (a full 30min re-crawl is ~65h
        # of BaoStock calls for data we already have); stocks with holes go last.
        for iv in intervals:
            cov = coverage_from_pg(iv)
            total = len(cov["full"]) + len(cov["shallow"])
            logger.info(
                "%smin: %d/%d stocks have an unbroken year span in PG; %d have gaps",
                iv, len(cov["full"]), total, len(cov["shallow"]),
            )
            for code, (fy, ly, ny) in sorted(cov["gaps"].items())[:10]:
                logger.info("  gap %s: years %d-%d but only %d present", code, fy, ly, ny)
            if cov["gaps"]:
                logger.info("  (+%d more)", max(0, len(cov["gaps"]) - 10))
            save_named_progress(f"{iv}min_full", {"completed": cov["full"], "total_bars": 0})
            save_named_progress(f"{iv}min_shallow", {"completed": cov["shallow"], "total_bars": 0})
            logger.info(
                "  wrote baselines: bs_%smin_full_state.json (%d) / bs_%smin_shallow_state.json (%d)",
                iv, len(cov["full"]), iv, len(cov["shallow"]),
            )
        return

    if args.rebuild:
        for iv in intervals:
            state = rebuild_state_from_pg(iv, min_days=args.min_days)
            save_progress(iv, state)
            logger.info("%smin: rebuilt from PG — %d stocks verified complete", iv, len(state["completed"]))
        return

    if args.reset:
        for iv in intervals:
            save_progress(iv, {"completed": [], "total_bars": 0})
        logger.info("Progress reset")
        return

    # Two importers would share the same progress files and double BaoStock's
    # request rate, which is what extended the IP ban. The admin commands above
    # return before this point so they stay usable while an import is running.
    # The lock is released by its atexit hook on every exit path.
    try:
        InstanceLock("baostock_importer").acquire()
    except AlreadyRunning as exc:
        logger.error("%s — refusing to start a second importer", exc)
        sys.exit(1)

    if not bs_login():
        sys.exit(1)

    # Register emergency progress save on SIGTERM/SIGINT so forced kills (taskkill)
    # don't lose the state accumulated during the current interval loop.
    _emergency_state = {"freq": None, "state": None}

    def _save_on_signal(signum: int, _frame):
        logger.warning("Received signal %d — saving emergency progress before exit", signum)
        if freq_obj := _emergency_state["freq"]:
            if st := _emergency_state["state"]:
                try:
                    save_progress(freq_obj, st)
                except Exception as e:
                    logger.error("Emergency save failed: %s", e)
        sys.exit(2)

    signal.signal(signal.SIGTERM, _save_on_signal)
    signal.signal(signal.SIGINT, _save_on_signal)
    atexit.register(lambda: _save_on_signal(0, None) if _emergency_state["freq"] else None)

    # Mark start time per interval so slow runs can log wall-clock
    _batch_start = time.time()

    # Get ticker list (needs bs session active)
    if args.tickers:
        tickers = [t.strip() for t in args.tickers.split(",")]
    else:
        logger.info("Fetching all A-share tickers...")
        for _fetch_attempt in range(4):
            try:
                tickers = get_all_tickers_bs()
            except Exception as exc:
                logger.warning("get_all_tickers attempt %d failed: %r", _fetch_attempt + 1, exc)
                if not bs_reconnect():
                    logger.error("BaoStock unreachable; aborting ticker fetch")
                    bs.logout(); sys.exit(1)
                continue
            if tickers:
                break
            logger.warning("get_all_tickers returned empty (attempt %d); retrying", _fetch_attempt + 1)
            time.sleep(5 * (_fetch_attempt + 1))
        if not tickers:
            logger.error("No tickers obtained from BaoStock; aborting")
            bs.logout()
            sys.exit(1)
        logger.info(f"Found {len(tickers)} tickers")

    if not tickers:
        bs.logout()
        sys.exit(1)

    for freq in intervals:
        data_type, param_hash, td_stable, td_prefix, bs_name = INTERVAL_MAP[freq]
        logger.info(f"\n{'='*60}\nBaoStock {bs_name} import ({data_type})\n{'='*60}")

        state = load_progress(freq)
        _emergency_state["freq"] = freq
        _emergency_state["state"] = state
        completed = set(state.get("completed", []))
        # Previously-failed stocks go last: don't let server-throttled
        # stragglers block broad progress across the other 5,000 stocks.
        failed_prev = set(state.get("failed", []))
        remaining = [t for t in tickers if t not in completed and t not in failed_prev]
        remaining += sorted(failed_prev & set(tickers))
        logger.info(f"Already: {len(completed)}, Failed(skipped): {len(failed_prev)}, Remaining: {len(remaining)}")

        total_bars = state.get("total_bars", 0)
        start_time = time.time()
        last_save = time.time()
        consecutive_failures = 0
        circuit_breaker_open = False  # True when BaoStock is down — stop hammering
        circuit_breaker_until = 0  # Unix timestamp when we can retry

        for i, bs_code in enumerate(remaining):
            # Retry with reconnect — never mark a failed fetch as complete
            status = "failed"
            for attempt in range(1, 3):  # reduced from 3 to 2 — 3rd attempt rarely succeeds for throttled stocks
                status, bars = import_stock_bs(bs_code, freq, pool, bs)
                if status != "failed":
                    break
                logger.warning(
                    "%s %s attempt %d/2 failed — reconnecting", bs_name, bs_code, attempt
                )
            if not bs_reconnect():
                # Reconnect failed → server is down, not a per-stock issue.
                consecutive_failures += 1
                save_progress(freq, state)
                logger.error(
                    "BaoStock reconnect failed for %s (consecutive=%d)",
                    bs_code, consecutive_failures,
                )
                # Circuit breaker: after 5 consecutive failures, back off for 10 minutes
                if consecutive_failures >= 5 and not circuit_breaker_open:
                    circuit_breaker_open = True
                    circuit_breaker_until = time.time() + 600  # 10 minutes
                    logger.error(
                        "Circuit breaker OPEN — BaoStock appears down. Backing off 10 minutes.",
                    )
                if circuit_breaker_open:
                    if time.time() < circuit_breaker_until:
                        logger.info(
                            "Circuit breaker open, waiting %d seconds...",
                            int(circuit_breaker_until - time.time()),
                        )
                        save_progress(freq, state)
                        bs.logout()
                        sys.exit(0)  # Clean exit — watchdog will restart after delay
                    else:
                        # Cooldown expired, try again
                        circuit_breaker_open = False
                        consecutive_failures = 0
                        logger.info("Circuit breaker CLOSED — retrying BaoStock connection.")
                time.sleep(30)
                continue
            time.sleep(8)

            if status == "failed":
                # One stubborn stock must not block the whole run — record and skip
                failed = state.setdefault("failed", [])
                if bs_code not in failed:
                    failed.append(bs_code)
                state["failed"] = sorted(failed)
                consecutive_failures += 1
                logger.error(
                    "Stock %s failed after 2 attempts; skipping (%d failed so far).", bs_code, len(failed),
                )
                # Circuit breaker: after 10 consecutive stock failures, back off
                if consecutive_failures >= 10 and not circuit_breaker_open:
                    circuit_breaker_open = True
                    circuit_breaker_until = time.time() + 300  # 5 minutes
                    logger.error(
                        "Circuit breaker OPEN — too many stock failures. Backing off 5 minutes.",
                    )
                if circuit_breaker_open:
                    if time.time() < circuit_breaker_until:
                        save_progress(freq, state)
                        bs.logout()
                        sys.exit(0)  # Clean exit — watchdog will restart after delay
                    else:
                        circuit_breaker_open = False
                        consecutive_failures = 0
                        logger.info("Circuit breaker CLOSED — retrying.")
                continue

            if status == "partial":
                # Partial data saved to PG; count bars but don't mark complete — needs retry
                consecutive_failures = 0
                total_bars += bars
                failed = state.setdefault("failed", [])
                if bs_code not in failed:
                    failed.append(bs_code)
                state["failed"] = sorted(failed)
                logger.info(
                    "Stock %s partial (%d bars saved); will retry remaining years (%d failed total).",
                    bs_code, bars, len(failed),
                )
            else:  # "ok"
                consecutive_failures = 0
                total_bars += bars
                completed.add(bs_code)
                state["completed"] = sorted(completed)
            state["total_bars"] = total_bars

            if time.time() - last_save > 60:
                save_progress(freq, state)
                last_save = time.time()

            if (i + 1) % 200 == 0 or i == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (len(remaining) - i - 1) / rate if rate > 0 else 0
                logger.info(
                    "%s: %d/%d, %d bars (%d failed), ETA: %dh %dm",
                    bs_name, i+1, len(remaining), total_bars, len(state.get("failed",[])),
                    int(eta // 3600), int((eta % 3600) // 60)
                )

            time.sleep(0.02)

        save_progress(freq, state)
        failed = state.get("failed", [])
        if failed:
            logger.info(f"Done! {bs_name}: {total_bars} bars; {len(failed)} stocks FAILED: {failed}")
        else:
            logger.info(f"Done! {bs_name}: {total_bars} bars for {len(tickers)} stocks")

    bs.logout()
    logger.info("All intervals complete!")


if __name__ == "__main__":
    main()
