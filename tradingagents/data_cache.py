"""SQLite-backed per-ticker cache for market data results.

Stores OHLCV, technical indicators, A-stock features, and fund flow results
so repeated chart loads and feature requests hit the local DB instead of
calling third-party APIs.  Realtime prices and LLM results are excluded
(realtime must be live; LLM has its own cache in ``llm_cache.py``).

Design mirrors ``LLMCache`` — each ticker gets its own ``.db`` file so
concurrent requests never contend on locks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ── TTL defaults (seconds) ───────────────────────────────────────────────────

_TTL_TRADING_HOURS = 4 * 3600    # 4 hours during market hours
_TTL_AFTER_HOURS = 24 * 3600     # 24 hours after market close
_TTL_OHLCV = 24 * 3600           # OHLCV always 24h (daily bars change slowly)

# A-share market hours in UTC: 01:30–07:00 (09:30–15:00 CST)
_ASTOCK_OPEN_UTC = (1, 30)   # 01:30 UTC = 09:30 CST
_ASTOCK_CLOSE_UTC = (7, 0)   # 07:00 UTC = 15:00 CST

# US market hours in UTC: 13:30–20:00 (09:30–16:00 ET)
_US_OPEN_UTC = (13, 30)
_US_CLOSE_UTC = (20, 0)


def _is_market_hours() -> bool:
    """Check if any major market is currently open (rough heuristic)."""
    now = datetime.now(timezone.utc)
    h, m = now.hour, now.minute
    t = h * 60 + m

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
    """Return TTL in seconds for a given data type."""
    if data_type == "ohlcv":
        return _TTL_OHLCV
    if _is_market_hours():
        return _TTL_TRADING_HOURS
    return _TTL_AFTER_HOURS


# ── Cache key construction ────────────────────────────────────────────────────

def make_cache_key(data_type: str, **params: object) -> str:
    """Build a deterministic cache key from data type and parameters.

    Example::

        make_cache_key("ohlcv", ticker="600519", start="2026-01-01", end="2026-08-28")
        # -> "ohlcv:a1b2c3d4e5f6..."
    """
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
    param_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"{data_type}:{param_hash}"


# ── DataCache class ───────────────────────────────────────────────────────────

class DataCache:
    """Per-ticker SQLite cache for market data results.

    Parameters
    ----------
    data_dir:
        Root cache directory (typically ``config["data_cache_dir"]``).
    ticker:
        Ticker symbol — determines the DB file name.
    """

    def __init__(self, data_dir: str | Path, ticker: str) -> None:
        self._db_path = Path(data_dir) / "data_cache"
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._db_file = self._db_path / f"{ticker.upper()}.db"
        self._conn = sqlite3.connect(str(self._db_file), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS data_cache (
                cache_key   TEXT PRIMARY KEY,
                data_type   TEXT NOT NULL,
                result      TEXT NOT NULL,
                created_at  REAL NOT NULL,
                access_count INTEGER DEFAULT 1
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_data_type ON data_cache(data_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_created ON data_cache(created_at)"
        )
        self._conn.commit()

        self._hits = 0
        self._misses = 0

    # ── Public API ────────────────────────────────────────────────────────

    def get(self, cache_key: str, ttl_seconds: int | None = None) -> dict | None:
        """Return the cached result dict, or ``None`` on miss / expiry.

        If *ttl_seconds* is ``None``, the TTL is computed automatically from
        the data type stored in the row.
        """
        row = self._conn.execute(
            "SELECT result, created_at, data_type FROM data_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()

        if row is None:
            self._misses += 1
            return None

        result_json, created_at, data_type = row
        effective_ttl = ttl_seconds if ttl_seconds is not None else _ttl_for_type(data_type)

        if time.time() - created_at > effective_ttl:
            self._conn.execute(
                "DELETE FROM data_cache WHERE cache_key = ?", (cache_key,)
            )
            self._conn.commit()
            self._misses += 1
            return None

        try:
            self._conn.execute(
                "UPDATE data_cache SET access_count = access_count + 1 "
                "WHERE cache_key = ?",
                (cache_key,),
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass

        self._hits += 1
        return json.loads(result_json)

    def set(self, cache_key: str, result: dict, data_type: str = "unknown") -> None:
        """Store a serialised result."""
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO data_cache
                    (cache_key, data_type, result, created_at, access_count)
                VALUES (?, ?, ?, ?, 1)
                """,
                (cache_key, data_type, json.dumps(result, ensure_ascii=False), time.time()),
            )
            self._conn.commit()
        except sqlite3.OperationalError as exc:
            logger.warning("Data cache write failed: %s", exc)

    def has(self, cache_key: str, ttl_seconds: int | None = None) -> bool:
        """Check if a valid (non-expired) entry exists."""
        return self.get(cache_key, ttl_seconds) is not None

    def clear(self, data_type: str | None = None) -> int:
        """Delete all entries, or only those matching *data_type*."""
        if data_type:
            cur = self._conn.execute(
                "DELETE FROM data_cache WHERE data_type = ?", (data_type,)
            )
        else:
            cur = self._conn.execute("DELETE FROM data_cache")
        self._conn.commit()
        return cur.rowcount

    def prune_expired(self) -> int:
        """Remove all expired entries across all types.  Returns row count."""
        now = time.time()
        # OHLCV uses 24h; others use dynamic TTL.  Prune conservatively at 24h.
        cutoff = now - _TTL_AFTER_HOURS
        cur = self._conn.execute(
            "DELETE FROM data_cache WHERE created_at < ?", (cutoff,)
        )
        self._conn.commit()
        return cur.rowcount

    def stats(self) -> dict:
        """Return session hit/miss counts and total stored entries."""
        total = self._conn.execute(
            "SELECT COUNT(*) FROM data_cache"
        ).fetchone()[0]
        by_type = {}
        for row in self._conn.execute(
            "SELECT data_type, COUNT(*) FROM data_cache GROUP BY data_type"
        ):
            by_type[row[0]] = row[1]
        return {
            "ticker": self._db_file.stem,
            "hits": self._hits,
            "misses": self._misses,
            "total_entries": total,
            "by_type": by_type,
            "hit_rate": (
                f"{self._hits / (self._hits + self._misses) * 100:.1f}%"
                if (self._hits + self._misses) > 0
                else "n/a"
            ),
        }

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ── Module-level helper ───────────────────────────────────────────────────────

_default_cache_enabled: bool | None = None
_default_cache_dir: str | None = None


def _get_config() -> tuple[bool, str]:
    """Lazy-load config to avoid circular imports."""
    global _default_cache_enabled, _default_cache_dir
    if _default_cache_enabled is None:
        try:
            from tradingagents.default_config import get_config
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
