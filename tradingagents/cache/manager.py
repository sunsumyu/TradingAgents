"""Unified cache manager for TradingAgents.

Replaces the old DataCache + cached_fetch_raw dual-path system.
All features go through one interface: `fetch()`.

Key format: {ticker}:{feature}:{date}:{version}:{params_hash}
Version bumping automatically invalidates stale cache entries.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Generator, Optional

from tradingagents.config import PG_DSN, DATA_CACHE_DIR

logger = logging.getLogger(__name__)

# ── PostgreSQL connection pool (lazy) ─────────────────────────────────────────

_pg_pool: Any = None
_pg_available: Optional[bool] = None  # None = not yet attempted

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS data_cache (
    cache_key   VARCHAR(256) NOT NULL,
    ticker      VARCHAR(16)  NOT NULL DEFAULT '',
    data_type   VARCHAR(64)  NOT NULL,
    result      JSONB        NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMPTZ,
    access_count INTEGER DEFAULT 1,
    PRIMARY KEY (cache_key, ticker)
);
CREATE INDEX IF NOT EXISTS idx_dc_data_type ON data_cache(data_type);
CREATE INDEX IF NOT EXISTS idx_dc_ticker  ON data_cache(ticker);
CREATE INDEX IF NOT EXISTS idx_dc_created ON data_cache(created_at);
CREATE INDEX IF NOT EXISTS idx_dc_expires_at ON data_cache(expires_at) WHERE expires_at IS NOT NULL;
CREATE TABLE IF NOT EXISTS data_history (
    ticker      VARCHAR(16)  NOT NULL DEFAULT '',
    data_type   VARCHAR(64)  NOT NULL,
    trade_date  DATE         NOT NULL,
    param_hash  VARCHAR(16)  NOT NULL DEFAULT '',
    result      JSONB        NOT NULL,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, data_type, trade_date, param_hash)
);
CREATE INDEX IF NOT EXISTS idx_dh_trade_date ON data_history(trade_date);
CREATE INDEX IF NOT EXISTS idx_dh_ticker_type_date ON data_history(ticker, data_type, trade_date);
"""


def _get_pg_pool():
    global _pg_pool, _pg_available
    if _pg_available is False:
        return None
    if _pg_pool is not None:
        return _pg_pool
    try:
        import psycopg2
        from psycopg2 import pool
        _pg_pool = pool.ThreadedConnectionPool(1, 10, PG_DSN)
        _pg_available = True
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


# ── Cache key builder ─────────────────────────────────────────────────────────

def _make_cache_key(
    ticker: str,
    feature: str,
    date: str,
    version: str,
    **params: Any,
) -> str:
    """Build a deterministic, versioned cache key.

    Format: {ticker}:{feature}:{date}:{version}:{params_hash}
    Changing `version` invalidates all prior cache entries for this feature.
    """
    payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
    param_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{ticker}:{feature}:{date}:{version}:{param_hash}"


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Box-drawing → markdown table converter ────────────────────────────────────

def _box_table_to_markdown(text: str) -> str:
    """Convert box-drawing tables (│ ┌ ─ etc) to standard markdown pipes.

    Handles U+2502 (│), U+FF5C (｜), and all standard box-drawing chars.
    """
    lines = text.split("\n")
    result: list[str] = []
    in_table = False

    for line in lines:
        has_vline = bool(re.search(r"[│｜|]", line))
        has_border = bool(re.search(r"[┌┬┐├┼┤└┴┘─]", line))

        # Pure border line → skip
        if has_border and not has_vline:
            stripped = re.sub(r"[─┌┬┐├┼┤└┴┘│｜\s]", "", line)
            if not stripped.strip():
                continue

        # Data line with vertical separators → convert
        if has_vline:
            cells = re.split(r"[│｜]", line)
            cleaned = [c.strip() for c in cells if c.strip()]
            if cleaned:
                row_str = " | ".join(cleaned)
                if not in_table or (result and result[-1] != row_str):
                    result.append(row_str)
                    in_table = True
                continue

        in_table = False
        result.append(line)

    return "\n".join(result)


# ── TTL management ────────────────────────────────────────────────────────────

_TTL_TRADING_HOURS = 4 * 3600
_TTL_AFTER_HOURS = 24 * 3600
_TTL_OHLCV = 24 * 3600
_ASTOCK_OPEN_UTC = (1, 30)
_ASTOCK_CLOSE_UTC = (7, 0)
_US_OPEN_UTC = (13, 30)
_US_CLOSE_UTC = (20, 0)


def _is_market_hours() -> bool:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    t = now.hour * 60 + now.minute
    a_open = _ASTOCK_OPEN_UTC[0] * 60 + _ASTOCK_OPEN_UTC[1]
    a_close = _ASTOCK_CLOSE_UTC[0] * 60 + _ASTOCK_CLOSE_UTC[1]
    if a_open <= t <= a_close:
        return True
    us_open = _US_OPEN_UTC[0] * 60 + _US_OPEN_UTC[1]
    us_close = _US_CLOSE_UTC[0] * 60 + _US_CLOSE_UTC[1]
    return us_open <= t <= us_close


def _ttl_for_type(data_type: str) -> int:
    # Ticket 11: an explicit per-feature declaration always wins. Everything
    # without one keeps the historical behaviour (ohlcv 24h, otherwise
    # 4h during market hours / 24h after close) — no entry, no change.
    override = _FEATURE_TTL_OVERRIDES.get(data_type)
    if override is not None:
        return override
    if data_type == "ohlcv":
        return _TTL_OHLCV
    return _TTL_TRADING_HOURS if _is_market_hours() else _TTL_AFTER_HOURS


# ── Per-feature TTL declarations (ticket 11) ─────────────────────────────────
#
# Phase 9 spec §6 assigns each data type its own freshness (e.g. institutional
# holdings are quarterly → 72h; analyst ratings move fast → 6h), but only ohlcv
# had a special case. Feature registries declare their TTLs here at import time;
# unregistered features fall through to the defaults above.

_FEATURE_TTL_OVERRIDES: dict[str, int] = {}


def register_feature_ttl(feature: str, ttl_seconds: int) -> None:
    """Declare the cache TTL (seconds) for one feature.

    Later registrations overwrite earlier ones; non-positive values are ignored
    so a misconfigured declaration can never disable caching entirely.
    """
    if ttl_seconds and int(ttl_seconds) > 0:
        _FEATURE_TTL_OVERRIDES[feature] = int(ttl_seconds)


def feature_ttl(feature: str) -> int:
    """Effective TTL for a feature (declaration if present, default otherwise)."""
    return _ttl_for_type(feature)


# ── CacheManager ──────────────────────────────────────────────────────────────

class CacheManager:
    """Unified cache for all TradingAgents data.

    Replaces both DataCache and cached_fetch_raw.

    Usage::

        mgr = CacheManager(data_dir, "001232", version="1.0")

        # Simple get/set
        cached = mgr.get("balance_sheet", "2026-09-01")
        if cached is None:
            data = fetch_from_api(...)
            mgr.set("balance_sheet", "2026-09-01", data)

        # Context-manager style (replaces cached_fetch_raw)
        with mgr.fetch("hot_stocks", "2026-09-01", source_fn=api_fn) as (data, hit):
            process(data)
    """

    SCHEMA_VERSIONS: dict[str, str] = {
        "ohlcv": "1.0",
        "technical_indicators": "1.0",
        "balance_sheet": "2.0",
        "income_statement": "2.0",
        "cashflow": "2.0",
        "insider_transactions": "2.0",
        "hot_stocks": "1.0",
        "northbound_flow": "1.0",
        "dragon_tiger": "1.0",
        "chip_distribution": "1.0",
        "concept_blocks": "1.0",
        "lockup_expiry": "1.0",
        "profit_forecast": "1.0",
        "industry_comparison": "1.0",
        # Phase 10: TongDaXin data menu — 2.0 invalidated the old dict cache;
        # Phase 13 bumped to 2.1 for the structured fund parsers.
        "fund_purchase": "2.1",
        "fund_announcement": "2.1",
        "fund_scale": "2.1",
        "fund_open_info": "2.1",
        "industry_chain_categories": "2.1",
        "industry_chain_chains": "2.1",
        "industry_chain_overview": "2.2",
        "industry_list": "2.1",
        "industry_commodity": "2.1",
        "industry_data_overview": "2.1",
        # Phase 13 batch: macro features now emit structured payloads
        # (parsers changed) — bumped to invalidate the passthrough-era cache
        "macro_gdp": "2.2",
        "macro_cpi": "2.1",
        "macro_pmi": "2.1",
        "macro_overview": "2.0",
        # Stock info panel (Phase 11)
        "stock_info_panel": "1.0",
        # Phase 13 batch: ipo features now emit structured payloads
        "ipo_declaration": "2.1",
        "ipo_listing": "2.1",
        # Phase 13 batch: margin features now emit structured payloads
        "margin_detail": "2.1",
        "margin_market_stat": "2.1",
        # Phase 13 batch: calendar / dragon-tiger activity structured payloads
        "investment_calendar": "2.2",
        "seat_activity": "2.1",
        "stock_activity": "2.1",
        # Phase 13 batch: survey / market-stats / futures structured payloads
        "survey_interaction": "2.1",
        "market_statistics": "2.1",
        "futures_position": "2.1",
        # Ticket 09: SZSE-backed name changes / derived ST changes
        "company_name_changes": "2.1",
        "st_changes": "2.1",
        # 2026-09-28: holder_num switched to RPT_HOLDERNUM_DET (history, not latest-only)
        "holder_num": "2.2",
        # Ticket 08: hk_ipo re-sourced to aastocks (was mislabeled A-share data)
        "hk_ipo": "2.1",
    }

    def __init__(self, data_dir: str | Path, ticker: str, version: str | None = None):
        self._data_dir = Path(data_dir)
        self._ticker = ticker.upper()
        self._pg = _get_pg_pool()
        self._sqlite: Any = None
        self._hits = 0
        self._misses = 0
        self._default_version = version or "1.0"

        if self._pg is None:
            self._init_sqlite()

    # ── SQLite fallback ─────────────────────────────────────────────────

    def _init_sqlite(self):
        import sqlite3
        cache_dir = self._data_dir / "data_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._sqlite = sqlite3.connect(
            str(cache_dir / f"{self._ticker}.db"), check_same_thread=False
        )
        self._sqlite.execute("PRAGMA journal_mode=WAL")
        self._sqlite.execute("""
            CREATE TABLE IF NOT EXISTS data_cache (
                cache_key TEXT PRIMARY KEY,
                data_type TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at REAL NOT NULL,
                access_count INTEGER DEFAULT 1
            )
        """)
        self._sqlite.execute(
            "CREATE INDEX IF NOT EXISTS idx_data_type ON data_cache(data_type)"
        )
        self._sqlite.commit()

    # ── Public API ────────────────────────────────────────────────────────

    def get(self, feature: str, date: str, **params: Any) -> dict | None:
        """Get cached data, or None on miss/expiry."""
        version = self.SCHEMA_VERSIONS.get(feature, self._default_version)
        key = _make_cache_key(self._ticker, feature, date, version, **params)

        if self._pg:
            return self._pg_get(key, feature)
        if self._sqlite:
            return self._sqlite_get(key)
        self._misses += 1
        return None

    def set(self, feature: str, date: str, data: Any, **params: Any) -> None:
        """Store data in cache and archive a permanent daily snapshot to PG."""
        version = self.SCHEMA_VERSIONS.get(feature, self._default_version)
        key = _make_cache_key(self._ticker, feature, date, version, **params)

        if self._pg:
            self._pg_set(key, feature, data)
            self._pg_archive(feature, date, data, **params)
        elif self._sqlite:
            self._sqlite_set(key, feature, data)

    def clear(self, feature: str | None = None) -> int:
        """Delete cache entries. If feature is None, clear all."""
        if self._pg:
            conn = self._pg.getconn()
            try:
                with conn.cursor() as cur:
                    if feature:
                        cur.execute(
                            "DELETE FROM data_cache WHERE ticker = %s AND data_type = %s",
                            (self._ticker, feature),
                        )
                    else:
                        cur.execute("DELETE FROM data_cache WHERE ticker = %s", (self._ticker,))
                    n = cur.rowcount
                conn.commit()
                return n
            finally:
                self._pg.putconn(conn)
        elif self._sqlite:
            if feature:
                cur = self._sqlite.execute(
                    "DELETE FROM data_cache WHERE data_type = ?", (feature,)
                )
            else:
                cur = self._sqlite.execute("DELETE FROM data_cache")
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
                    cur.execute(
                        "SELECT COUNT(*) FROM data_cache WHERE ticker = %s",
                        (self._ticker,),
                    )
                    total = cur.fetchone()[0]
                    cur.execute(
                        "SELECT data_type, COUNT(*) FROM data_cache WHERE ticker = %s GROUP BY data_type",
                        (self._ticker,),
                    )
                    for row in cur.fetchall():
                        by_type[row[0]] = row[1]
            finally:
                self._pg.putconn(conn)
        elif self._sqlite:
            total = self._sqlite.execute(
                "SELECT COUNT(*) FROM data_cache"
            ).fetchone()[0]
            for row in self._sqlite.execute(
                "SELECT data_type, COUNT(*) FROM data_cache GROUP BY data_type"
            ):
                by_type[row[0]] = row[1]
        return {
            "ticker": self._ticker,
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

    def close(self):
        if self._sqlite:
            try:
                self._sqlite.close()
            except Exception:
                pass

    # ── PostgreSQL internals ──────────────────────────────────────────────

    def _pg_get(self, key: str, feature: str) -> dict | None:
        conn = self._pg.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT result, EXTRACT(EPOCH FROM created_at)::float AS created_at, data_type FROM data_cache WHERE cache_key = %s AND ticker = %s",
                    (key, self._ticker),
                )
                row = cur.fetchone()
                if row is None:
                    self._misses += 1
                    return None
                result_json, created_at, _ = row
                effective_ttl = _ttl_for_type(feature)
                if time.time() - created_at > effective_ttl:
                    cur.execute(
                        "DELETE FROM data_cache WHERE cache_key = %s AND ticker = %s",
                        (key, self._ticker),
                    )
                    conn.commit()
                    self._misses += 1
                    return None
                cur.execute(
                    "UPDATE data_cache SET access_count = access_count + 1 WHERE cache_key = %s AND ticker = %s",
                    (key, self._ticker),
                )
            conn.commit()
            self._hits += 1
            return result_json if isinstance(result_json, dict) else json.loads(result_json)
        except Exception as exc:
            conn.rollback()
            logger.warning("PG cache read failed: %s", exc)
            self._misses += 1
            return None
        finally:
            self._pg.putconn(conn)

    def _pg_set(self, key: str, feature: str, data: Any) -> None:
        conn = self._pg.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO data_cache (cache_key, ticker, data_type, result, created_at, access_count)
                       VALUES (%s, %s, %s, %s, to_timestamp(%s), 1)
                       ON CONFLICT (cache_key, ticker) DO UPDATE SET
                         result = EXCLUDED.result,
                         data_type = EXCLUDED.data_type,
                         created_at = EXCLUDED.created_at,
                         access_count = data_cache.access_count + 1""",
                    (key, self._ticker, feature,
                     json.dumps(data, ensure_ascii=False), time.time()),
                )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.warning("PG cache write failed: %s", exc)
        finally:
            self._pg.putconn(conn)

    # (archive: see _pg_archive below)

    def _pg_archive(self, feature: str, date: str, data: Any, **params: Any) -> None:
        """永久归档每日快照到 data_history（不随 TTL/清缓存删除）。

        主键 (ticker, data_type, trade_date, param_hash)：
        同日重复写入仅更新结果（保留当日最终快照），不同参数变体各自保留。
        date 非日期格式（如 "latest"）时按当天归档。
        """
        trade_date = date if _DATE_RE.match(date or "") else time.strftime("%Y-%m-%d")
        payload = json.dumps(params, sort_keys=True, ensure_ascii=False)
        param_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        conn = self._pg.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO data_history (ticker, data_type, trade_date, param_hash, result, updated_at)
                       VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                       ON CONFLICT (ticker, data_type, trade_date, param_hash) DO UPDATE SET
                         result = EXCLUDED.result,
                         updated_at = EXCLUDED.updated_at
                       WHERE data_history.result IS DISTINCT FROM EXCLUDED.result""",
                    (self._ticker, feature, trade_date, param_hash,
                     json.dumps(data, ensure_ascii=False), time.time()),
                )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.warning("PG archive write failed (%s/%s): %s", self._ticker, feature, exc)
        finally:
            self._pg.putconn(conn)

    # ── SQLite internals ──────────────────────────────────────────────────

    def _sqlite_get(self, key: str) -> dict | None:
        row = self._sqlite.execute(
            "SELECT result, created_at, data_type FROM data_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            self._misses += 1
            return None
        result_json, created_at, data_type = row
        effective_ttl = _ttl_for_type(data_type)
        if time.time() - created_at > effective_ttl:
            self._sqlite.execute("DELETE FROM data_cache WHERE cache_key = ?", (key,))
            self._sqlite.commit()
            self._misses += 1
            return None
        try:
            self._sqlite.execute(
                "UPDATE data_cache SET access_count = access_count + 1 WHERE cache_key = ?",
                (key,),
            )
            self._sqlite.commit()
        except Exception:
            pass
        self._hits += 1
        return json.loads(result_json)

    def _sqlite_set(self, key: str, feature: str, data: Any) -> None:
        try:
            self._sqlite.execute(
                """INSERT OR REPLACE INTO data_cache
                   (cache_key, data_type, result, created_at, access_count)
                   VALUES (?, ?, ?, ?, 1)""",
                (key, feature, json.dumps(data, ensure_ascii=False), time.time()),
            )
            self._sqlite.commit()
        except Exception as exc:
            logger.warning("SQLite cache write failed: %s", exc)

    # ── High-level fetch (replaces cached_fetch_raw) ──────────────────────

    @contextmanager
    def fetch(
        self,
        feature: str,
        date: str,
        source_fn: Callable[[], Any],
        convert_box: bool = False,
        **params: Any,
    ) -> Generator:
        """Unified cache-aware data fetch.

        Usage::

            with mgr.fetch("hot_stocks", "2026-09-01", source_fn=api_fn) as (data, hit):
                process(data)

        On cache hit: yields (cached_data, True) without calling source_fn.
        On cache miss: calls source_fn(), caches result, yields (data, False).
        """
        cached = self.get(feature, date, **params)
        if cached is not None:
            yield cached, True
            return

        raw = source_fn()

        # Optional: convert box-drawing tables to markdown
        if convert_box and isinstance(raw, str):
            raw = _box_table_to_markdown(raw)

        self.set(feature, date, raw, **params)
        yield raw, False


# ── Backward-compatible helpers ──────────────────────────────────────────────

# Singleton cache directory
_CACHE_DIR = DATA_CACHE_DIR.parent

_instances: dict[str, CacheManager] = {}


def get_cache(ticker: str) -> CacheManager:
    """Get or create a CacheManager for a ticker. Returns singleton per ticker."""
    key = ticker.upper()
    if key not in _instances:
        _instances[key] = CacheManager(_CACHE_DIR, ticker)
    return _instances[key]


def clear_cache(ticker: str | None = None, feature: str | None = None):
    """Clear cache entries (both PostgreSQL and SQLite backends)."""
    if ticker:
        get_cache(ticker).clear(feature)
        return

    # No ticker: clear every known cache namespace.
    # 1. Live CacheManager instances (covers the PG backend — SQLite files
    #    may not exist for PG-backed managers, so globbing alone misses them)
    for t, mgr in list(_instances.items()):
        mgr.clear(feature)
    # 2. Remaining PG rows (e.g. "MARKET" namespace not yet instantiated)
    pool = _get_pg_pool()
    if pool is not None:
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                if feature:
                    cur.execute("DELETE FROM data_cache WHERE data_type = %s", (feature,))
                else:
                    cur.execute("DELETE FROM data_cache")
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.warning("PG cache clear-all failed: %s", exc)
        finally:
            pool.putconn(conn)
    # 3. SQLite files on disk
    import glob as _glob
    for db_path in _glob.glob(str(_CACHE_DIR / "data_cache" / "*.db")):
        t = Path(db_path).stem
        get_cache(t).clear(feature)
