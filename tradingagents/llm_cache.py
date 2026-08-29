"""SQLite-backed per-ticker cache for LLM results.

Stores successful ``llm.invoke()`` outputs keyed by a deterministic hash of
the normalised input messages plus model identity.  Entries expire after a
configurable TTL so stale results from a previous run don't linger forever.

The design mirrors the existing per-ticker checkpoint pattern
(``tradingagents.graph.checkpointer``) — each ticker gets its own ``.db``
file so concurrent runs never contend on locks.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class LLMCache:
    """Per-ticker SQLite cache for LLM call results.

    Parameters
    ----------
    data_dir:
        Root cache directory (typically ``config["data_cache_dir"]``).
    ticker:
        Ticker symbol — determines the DB file name.
    ttl_hours:
        Entries older than this are treated as missing and eventually pruned.
    """

    def __init__(self, data_dir: str | Path, ticker: str, *, ttl_hours: float = 24.0) -> None:
        self._ttl_seconds = ttl_hours * 3600
        self._db_path = Path(data_dir) / "llm_cache"
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._db_file = self._db_path / f"{ticker.upper()}.db"
        self._conn = sqlite3.connect(str(self._db_file), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key   TEXT PRIMARY KEY,
                result      TEXT NOT NULL,
                model       TEXT NOT NULL,
                created_at  REAL NOT NULL,
                access_count INTEGER DEFAULT 1
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_created ON llm_cache(created_at)"
        )
        self._conn.commit()

        # Per-session counters for diagnostics.
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, cache_key: str) -> dict | None:
        """Return the cached result dict, or ``None`` on miss / expiry."""
        row = self._conn.execute(
            "SELECT result, created_at FROM llm_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()

        if row is None:
            self._misses += 1
            return None

        result_json, created_at = row
        if time.time() - created_at > self._ttl_seconds:
            # Expired — treat as miss and prune lazily.
            self._conn.execute(
                "DELETE FROM llm_cache WHERE cache_key = ?", (cache_key,)
            )
            self._conn.commit()
            self._misses += 1
            return None

        # Touch access count (best-effort, don't fail on lock contention).
        try:
            self._conn.execute(
                "UPDATE llm_cache SET access_count = access_count + 1 "
                "WHERE cache_key = ?",
                (cache_key,),
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # concurrent writer — harmless

        self._hits += 1
        return json.loads(result_json)

    def set(self, cache_key: str, result: dict, *, model: str = "unknown") -> None:
        """Store a serialised LLM result."""
        try:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO llm_cache
                    (cache_key, result, model, created_at, access_count)
                VALUES (?, ?, ?, ?, 1)
                """,
                (cache_key, json.dumps(result, ensure_ascii=False), model, time.time()),
            )
            self._conn.commit()
        except sqlite3.OperationalError as exc:
            logger.warning("LLM cache write failed: %s", exc)

    def clear(self) -> int:
        """Delete all entries for this ticker.  Returns the row count."""
        cur = self._conn.execute("DELETE FROM llm_cache")
        self._conn.commit()
        return cur.rowcount

    def prune_expired(self) -> int:
        """Remove all expired entries.  Returns the row count."""
        cutoff = time.time() - self._ttl_seconds
        cur = self._conn.execute(
            "DELETE FROM llm_cache WHERE created_at < ?", (cutoff,)
        )
        self._conn.commit()
        return cur.rowcount

    def stats(self) -> dict:
        """Return session hit/miss counts and total stored entries."""
        total = self._conn.execute(
            "SELECT COUNT(*) FROM llm_cache"
        ).fetchone()[0]
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total_entries": total,
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
