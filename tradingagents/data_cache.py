"""PostgreSQL-backed shared cache for market data results.

Stores OHLCV, technical indicators, A-stock features, and fund flow results
so repeated chart loads and feature requests hit the central DB instead of
calling third-party APIs.  All tickers share a single PostgreSQL database
for better concurrency and reliability.

Falls back to SQLite if PostgreSQL is unreachable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from tradingagents.config import PG_DSN

logger = logging.getLogger(__name__)

# ── TTL defaults (seconds) ───────────────────────────────────────────────────

_TTL_TRADING_HOURS = 4 * 3600    # 4 hours during market hours
_TTL_AFTER_HOURS = 24 * 3600     # 24 hours after market close
_TTL_OHLCV = 24 * 3600           # OHLCV always 24h (daily bars change slowly)

_ASTOCK_OPEN_UTC = (1, 30)
_ASTOCK_CLOSE_UTC = (7, 0)
_US_OPEN_UTC = (13, 30)
_US_CLOSE_UTC = (20, 0)


def _is_market_hours() -> bool:
    now = datetime.now(timezone.utc)
    t = now.hour * 60 + now.minute
    a_open = _ASTOCK_OPEN_UTC[0] * 60 + _ASTOCK_OPEN_UTC[1]
    a_close = _ASTOCK_CLOSE_UTC[0] * 60 + _ASTOCK_CLOSE_UTC[1]
    if a_open <= t <= a_close:
        return True
    us_open = _US_OPEN_UTC[0] * 60 + _US_OPEN_UTC[1]
    us_close = _US_CLOSE_UTC[0] * 60 + _US_CLOSE_UTC[1]
    if us_open <= t <= us_close:
        return True
    return False


def _ttl_for_type(data_type: str) -> int:
    if data_type == "ohlcv":
        return _TTL_OHLCV
    if _is_market_hours():
        return _TTL_TRADING_HOURS
    return _TTL_AFTER_HOURS


def make_cache_key(data_type: str, **params: object) -> str:
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
    param_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"{data_type}:{param_hash}"


# ── PostgreSQL connection pool ────────────────────────────────────────────────

_pg_pool: Any = None
_pg_available: bool | None = None  # None = not checked yet

_PG_DSN = PG_DSN

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS data_cache (
    cache_key   VARCHAR(256) NOT NULL,
    ticker      VARCHAR(16)  NOT NULL DEFAULT '',
    data_type   VARCHAR(64)  NOT NULL,
    result      JSONB        NOT NULL,
    created_at  DOUBLE PRECISION NOT NULL,
    access_count INTEGER DEFAULT 1,
    PRIMARY KEY (cache_key, ticker)
);
CREATE INDEX IF NOT EXISTS idx_dc_data_type ON data_cache(data_type);
CREATE INDEX IF NOT EXISTS idx_dc_ticker ON data_cache(ticker);
CREATE INDEX IF NOT EXISTS idx_dc_created ON data_cache(created_at);
"""


def _get_pg_pool():
    """Lazy-init a psycopg2 connection pool."""
    global _pg_pool, _pg_available
    if _pg_available is False:
        return None
    if _pg_pool is not None:
        return _pg_pool
    try:
        import psycopg2
        from psycopg2 import pool
        _pg_pool = pool.ThreadedConnectionPool(1, 10, _PG_DSN)
        _pg_available = True
        # Ensure table exists
        conn = _pg_pool.getconn()
        try:
            with conn.cursor() as cur:
                # Bootstrap DDL only when the table is absent — the runtime
                # account holds no table ownership, so re-running it would
                # raise even with IF NOT EXISTS.
                cur.execute("SELECT to_regclass('public.data_cache')")
                if cur.fetchone()[0] is None:
                    cur.execute(_CREATE_TABLE_SQL)
            conn.commit()
        finally:
            _pg_pool.putconn(conn)
        logger.info("PostgreSQL cache pool connected (tradingagents)")
        return _pg_pool
    except Exception as exc:
        _pg_available = False
        logger.warning("PostgreSQL unavailable, falling back to SQLite: %s", exc)
        return None


class DataCache:
    """Shared PostgreSQL cache for market data results.

    Parameters
    ----------
    data_dir:
        Fallback SQLite directory (used when PostgreSQL is unreachable).
    ticker:
        Ticker symbol.
    """

    def __init__(self, data_dir: str, ticker: str) -> None:
        self._ticker = ticker.upper()
        self._hits = 0
        self._misses = 0
        self._pg = _get_pg_pool()

        # Fallback to SQLite if PostgreSQL unavailable
        self._sqlite = None
        if self._pg is None:
            self._init_sqlite(data_dir)

    def _init_sqlite(self, data_dir: str) -> None:
        import sqlite3
        from pathlib import Path
        db_path = Path(data_dir) / "data_cache"
        db_path.mkdir(parents=True, exist_ok=True)
        self._sqlite = sqlite3.connect(str(db_path / f"{self._ticker}.db"), check_same_thread=False)
        self._sqlite.execute("PRAGMA journal_mode=WAL")
        self._sqlite.execute("""
            CREATE TABLE IF NOT EXISTS data_cache (
                cache_key TEXT PRIMARY KEY, data_type TEXT NOT NULL,
                result TEXT NOT NULL, created_at REAL NOT NULL,
                access_count INTEGER DEFAULT 1
            )
        """)
        self._sqlite.execute("CREATE INDEX IF NOT EXISTS idx_data_type ON data_cache(data_type)")
        self._sqlite.commit()

    # ── Public API ────────────────────────────────────────────────────────

    def get(self, cache_key: str, ttl_seconds: int | None = None) -> dict | None:
        if self._pg:
            return self._get_pg(cache_key, ttl_seconds)
        if self._sqlite:
            return self._get_sqlite(cache_key, ttl_seconds)
        self._misses += 1
        return None

    def set(self, cache_key: str, result: dict, data_type: str = "unknown") -> None:
        if self._pg:
            self._set_pg(cache_key, result, data_type)
        elif self._sqlite:
            self._set_sqlite(cache_key, result, data_type)

    def has(self, cache_key: str, ttl_seconds: int | None = None) -> bool:
        return self.get(cache_key, ttl_seconds) is not None

    def clear(self, data_type: str | None = None) -> int:
        if self._pg:
            conn = self._pg.getconn()
            try:
                with conn.cursor() as cur:
                    if data_type:
                        cur.execute("DELETE FROM data_cache WHERE ticker = %s AND data_type = %s", (self._ticker, data_type))
                    else:
                        cur.execute("DELETE FROM data_cache WHERE ticker = %s", (self._ticker,))
                    n = cur.rowcount
                conn.commit()
                return n
            finally:
                self._pg.putconn(conn)
        elif self._sqlite:
            if data_type:
                cur = self._sqlite.execute("DELETE FROM data_cache WHERE data_type = ?", (data_type,))
            else:
                cur = self._sqlite.execute("DELETE FROM data_cache")
            self._sqlite.commit()
            return cur.rowcount
        return 0

    def prune_expired(self) -> int:
        cutoff = time.time() - _TTL_AFTER_HOURS
        if self._pg:
            conn = self._pg.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM data_cache WHERE created_at < %s", (cutoff,))
                    n = cur.rowcount
                conn.commit()
                return n
            finally:
                self._pg.putconn(conn)
        elif self._sqlite:
            cur = self._sqlite.execute("DELETE FROM data_cache WHERE created_at < ?", (cutoff,))
            self._sqlite.commit()
            return cur.rowcount
        return 0

    def stats(self) -> dict:
        total = 0
        by_type: dict = {}
        if self._pg:
            conn = self._pg.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM data_cache WHERE ticker = %s", (self._ticker,))
                    total = cur.fetchone()[0]
                    cur.execute("SELECT data_type, COUNT(*) FROM data_cache WHERE ticker = %s GROUP BY data_type", (self._ticker,))
                    for row in cur.fetchall():
                        by_type[row[0]] = row[1]
            finally:
                self._pg.putconn(conn)
        elif self._sqlite:
            total = self._sqlite.execute("SELECT COUNT(*) FROM data_cache").fetchone()[0]
            for row in self._sqlite.execute("SELECT data_type, COUNT(*) FROM data_cache GROUP BY data_type"):
                by_type[row[0]] = row[1]
        return {
            "ticker": self._ticker,
            "hits": self._hits,
            "misses": self._misses,
            "total_entries": total,
            "by_type": by_type,
            "hit_rate": (
                f"{self._hits / (self._hits + self._misses) * 100:.1f}%"
                if (self._hits + self._misses) > 0 else "n/a"
            ),
        }

    def close(self) -> None:
        if self._sqlite:
            try:
                self._sqlite.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ── PostgreSQL internals ──────────────────────────────────────────────

    def _get_pg(self, cache_key: str, ttl_seconds: int | None) -> dict | None:
        conn = self._pg.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT result, created_at, data_type FROM data_cache WHERE cache_key = %s AND ticker = %s",
                    (cache_key, self._ticker),
                )
                row = cur.fetchone()
                if row is None:
                    self._misses += 1
                    return None
                result_json, created_at, data_type = row
                effective_ttl = ttl_seconds if ttl_seconds is not None else _ttl_for_type(data_type)
                if time.time() - created_at > effective_ttl:
                    cur.execute("DELETE FROM data_cache WHERE cache_key = %s AND ticker = %s", (cache_key, self._ticker))
                    conn.commit()
                    self._misses += 1
                    return None
                cur.execute(
                    "UPDATE data_cache SET access_count = access_count + 1 WHERE cache_key = %s AND ticker = %s",
                    (cache_key, self._ticker),
                )
            conn.commit()
            self._hits += 1
            if isinstance(result_json, str):
                return json.loads(result_json)
            return result_json  # already dict (jsonb)
        except Exception as exc:
            conn.rollback()
            logger.warning("PG cache read failed: %s", exc)
            self._misses += 1
            return None
        finally:
            self._pg.putconn(conn)

    def _set_pg(self, cache_key: str, result: dict, data_type: str) -> None:
        conn = self._pg.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO data_cache (cache_key, ticker, data_type, result, created_at, access_count)
                       VALUES (%s, %s, %s, %s, %s, 1)
                       ON CONFLICT (cache_key, ticker) DO UPDATE SET
                         result = EXCLUDED.result,
                         data_type = EXCLUDED.data_type,
                         created_at = EXCLUDED.created_at,
                         access_count = data_cache.access_count + 1""",
                    (cache_key, self._ticker, data_type,
                     json.dumps(result, ensure_ascii=False), time.time()),
                )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.warning("PG cache write failed: %s", exc)
        finally:
            self._pg.putconn(conn)

    # ── SQLite fallback internals ─────────────────────────────────────────

    def _get_sqlite(self, cache_key: str, ttl_seconds: int | None) -> dict | None:
        import json as _json
        row = self._sqlite.execute(
            "SELECT result, created_at, data_type FROM data_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if row is None:
            self._misses += 1
            return None
        result_json, created_at, data_type = row
        effective_ttl = ttl_seconds if ttl_seconds is not None else _ttl_for_type(data_type)
        if time.time() - created_at > effective_ttl:
            self._sqlite.execute("DELETE FROM data_cache WHERE cache_key = ?", (cache_key,))
            self._sqlite.commit()
            self._misses += 1
            return None
        try:
            self._sqlite.execute("UPDATE data_cache SET access_count = access_count + 1 WHERE cache_key = ?", (cache_key,))
            self._sqlite.commit()
        except Exception:
            pass
        self._hits += 1
        return _json.loads(result_json)

    def _set_sqlite(self, cache_key: str, result: dict, data_type: str) -> None:
        import json as _json
        try:
            self._sqlite.execute(
                "INSERT OR REPLACE INTO data_cache (cache_key, data_type, result, created_at, access_count) VALUES (?, ?, ?, ?, 1)",
                (cache_key, data_type, _json.dumps(result, ensure_ascii=False), time.time()),
            )
            self._sqlite.commit()
        except Exception as exc:
            logger.warning("SQLite cache write failed: %s", exc)


# ── Module-level helper ───────────────────────────────────────────────────────

_default_cache_enabled: bool | None = None
_default_cache_dir: str | None = None


def _get_config() -> tuple[bool, str]:
    """Lazy-load config to avoid circular imports."""
    global _default_cache_enabled, _default_cache_dir
    if _default_cache_enabled is None:
        try:
            from tradingagents.dataflows.config import get_config
            cfg = get_config()
            _default_cache_enabled = cfg.get("data_cache_enabled", True)
            _default_cache_dir = cfg.get("data_cache_dir", "")
        except Exception:
            _default_cache_enabled = False
            _default_cache_dir = ""
    return _default_cache_enabled, _default_cache_dir or ""


def get_data_cache(ticker: str) -> DataCache | None:
    """Return a DataCache for *ticker*, or ``None`` if caching is disabled.

    This is the main entry point for callers — it respects the global
    ``data_cache_enabled`` config flag.
    """
    enabled, data_dir = _get_config()
    if not enabled or not data_dir:
        return None
    try:
        return DataCache(data_dir, ticker)
    except Exception as exc:
        logger.warning("Failed to open data cache for %s: %s", ticker, exc)
        return None


# ── cached_fetch context manager ────────────────────────────────────────────────

from contextlib import contextmanager
from typing import Any, Callable


@contextmanager
def cached_fetch(
    symbol: str,
    data_type: str,
    **key_params: Any,
):
    """Context manager that eliminates the repetitive cache boilerplate.

    **Before** (repeated 7 times across 3 files)::

        cache = get_data_cache(symbol)
        cache_key = make_cache_key("ohlcv", ticker=symbol, start=start, end=end)
        if cache is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached.get("result")
            cache.close()
        result = fetch_from_vendor(...)
        c2 = get_data_cache(symbol)       # ← second handle!
        if c2 is not None:
            c2.set(cache_key, {"result": result}, "ohlcv")
            c2.close()
        return result

    **After**::

        with cached_fetch(symbol, "ohlcv", start=start, end=end) as ctx:
            if ctx.hit:
                return ctx.value
            result = fetch_from_vendor(...)
            ctx.store(result)
            return result

    Design: *one* DataCache handle for the full lifecycle.  The old code
    opened a second handle for writes — unnecessary since SQLite WAL mode
    supports read-write on a single connection.

    The caller's ``with`` block always closes the handle, even on early
    return (cache hit).  This fixes the previous pattern where cache
    handles leaked on hits.
    """

    class _Ctx:
        """Internal context object passed to the with-block."""
        __slots__ = ("hit", "value", "_cache", "_key", "_type")

        def __init__(self, hit: bool, value: Any, cache: DataCache | None, key: str, dtype: str):
            self.hit = hit
            self.value = value
            self._cache = cache
            self._key = key
            self._type = dtype

        def store(self, result: Any) -> None:
            """Write *result* to cache (no-op if cache is disabled)."""
            if self._cache is not None:
                self._cache.set(self._key, {"result": result}, self._type)

        def store_raw(self, result: Any) -> None:
            """Write *result* directly (not wrapped in ``{"result": ...}``)."""
            if self._cache is not None:
                self._cache.set(self._key, result, self._type)

    cache_key = make_cache_key(data_type, **key_params)
    cache = get_data_cache(symbol)

    try:
        if cache is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                yield _Ctx(hit=True, value=cached.get("result"), cache=cache, key=cache_key, dtype=data_type)
                return
        yield _Ctx(hit=False, value=None, cache=cache, key=cache_key, dtype=data_type)
    finally:
        if cache is not None:
            cache.close()


@contextmanager
def cached_fetch_raw(
    symbol: str,
    data_type: str,
    **key_params: Any,
):
    """Like :func:`cached_fetch` but yields the raw cached dict (not ``.get("result")``).

    Use when the cached value is a dict with multiple keys, not a single
    ``{"result": ...}`` wrapper.
    """

    class _Ctx:
        __slots__ = ("hit", "value", "_cache", "_key", "_type")

        def __init__(self, hit: bool, value: Any, cache: DataCache | None, key: str, dtype: str):
            self.hit = hit
            self.value = value
            self._cache = cache
            self._key = key
            self._type = dtype

        def store(self, result: dict) -> None:
            if self._cache is not None:
                self._cache.set(self._key, result, self._type)

    cache_key = make_cache_key(data_type, **key_params)
    cache = get_data_cache(symbol)

    try:
        if cache is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                yield _Ctx(hit=True, value=cached, cache=cache, key=cache_key, dtype=data_type)
                return
        yield _Ctx(hit=False, value=None, cache=cache, key=cache_key, dtype=data_type)
    finally:
        if cache is not None:
            cache.close()
