"""SQLite-based offline data cache for OHLCV and indicator data.

Provides per-ticker SQLite databases with TTL-based expiration,
avoiding lock contention between concurrent requests.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import pandas as pd


class CacheManager:
    """SQLite-backed data cache with per-ticker databases.

    Each ticker gets its own ``.db`` file under ``cache_dir/data_cache/``,
    avoiding lock contention. Entries have a configurable TTL with lazy
    expiration (expired rows are deleted on read).

    Usage::

        cache = CacheManager(cache_dir)
        cached = cache.get_ohlcv("600519", "1D", "2025-01-01", "2025-06-01")
        if cached is None:
            data = fetch_from_network(...)
            cache.set_ohlcv("600519", "1D", data)
    """

    def __init__(
        self,
        cache_dir: str | Path,
        default_ttl: int = 86400,  # 24 hours
        max_size_mb: int = 500,
    ) -> None:
        self.cache_dir = Path(cache_dir) / "data_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self.max_size_mb = max_size_mb
        self._connections: dict[str, sqlite3.Connection] = {}

    def _get_db(self, ticker: str) -> sqlite3.Connection:
        """Get or create a SQLite connection for a ticker."""
        ticker = ticker.upper().replace(".", "_")
        if ticker not in self._connections:
            db_path = self.cache_dir / f"{ticker}.db"
            conn = sqlite3.connect(str(db_path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ohlcv (
                    ticker TEXT,
                    timeframe TEXT,
                    date TEXT,
                    data TEXT,
                    cached_at REAL,
                    PRIMARY KEY (ticker, timeframe, date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS indicator (
                    ticker TEXT,
                    indicator TEXT,
                    params TEXT,
                    date TEXT,
                    data TEXT,
                    cached_at REAL,
                    PRIMARY KEY (ticker, indicator, params, date)
                )
            """)
            conn.commit()
            self._connections[ticker] = conn
        return self._connections[ticker]

    def get_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """Get cached OHLCV data, or None if not cached/expired."""
        conn = self._get_db(ticker)
        now = time.time()
        cutoff = now - self.default_ttl

        rows = conn.execute(
            "SELECT date, data, cached_at FROM ohlcv "
            "WHERE ticker=? AND timeframe=? AND date>=? AND date<=? AND cached_at>?",
            (ticker, timeframe, start_date, end_date, cutoff),
        ).fetchall()

        if not rows:
            return None

        records = []
        for date_str, data_json, _ in rows:
            try:
                record = json.loads(data_json)
                record["date"] = date_str
                records.append(record)
            except json.JSONDecodeError:
                continue

        if not records:
            return None

        df = pd.DataFrame(records)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
        return df

    def set_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        data: pd.DataFrame,
    ) -> None:
        """Store OHLCV data in cache."""
        if data.empty:
            return

        conn = self._get_db(ticker)
        now = time.time()

        # Use "date" column if present, otherwise use index
        if "date" in data.columns:
            dates = data["date"].astype(str).tolist()
        else:
            dates = data.index.astype(str).tolist()

        for i, (_, row) in enumerate(data.iterrows()):
            date_str = dates[i] if i < len(dates) else str(i)
            record = {
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": int(row.get("volume", 0)),
            }
            if "amount" in row:
                record["amount"] = float(row["amount"])
            if "turnover" in row:
                record["turnover"] = float(row["turnover"])

            conn.execute(
                "INSERT OR REPLACE INTO ohlcv (ticker, timeframe, date, data, cached_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (ticker, timeframe, date_str, json.dumps(record), now),
            )

        conn.commit()

    def get_indicator(
        self,
        ticker: str,
        indicator: str,
        params: dict[str, Any],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """Get cached indicator data, or None if not cached/expired."""
        conn = self._get_db(ticker)
        now = time.time()
        cutoff = now - self.default_ttl
        params_key = json.dumps(params, sort_keys=True)

        rows = conn.execute(
            "SELECT date, data, cached_at FROM indicator "
            "WHERE ticker=? AND indicator=? AND params=? AND date>=? AND date<=? AND cached_at>?",
            (ticker, indicator, params_key, start_date, end_date, cutoff),
        ).fetchall()

        if not rows:
            return None

        records = []
        for date_str, data_json, _ in rows:
            try:
                record = json.loads(data_json)
                record["date"] = date_str
                records.append(record)
            except json.JSONDecodeError:
                continue

        if not records:
            return None

        return pd.DataFrame(records)

    def set_indicator(
        self,
        ticker: str,
        indicator: str,
        params: dict[str, Any],
        data: pd.DataFrame,
    ) -> None:
        """Store indicator data in cache."""
        if data.empty:
            return

        conn = self._get_db(ticker)
        now = time.time()
        params_key = json.dumps(params, sort_keys=True)

        if "date" in data.columns:
            dates = data["date"].astype(str).tolist()
        else:
            dates = data.index.astype(str).tolist()

        for i, (_, row) in enumerate(data.iterrows()):
            date_str = dates[i] if i < len(dates) else str(i)
            record = row.to_dict()
            # Convert non-serializable types
            for k, v in record.items():
                if hasattr(v, "item"):
                    record[k] = v.item()
                elif hasattr(v, "isoformat"):
                    record[k] = v.isoformat()
                elif pd.isna(v):
                    record[k] = None

            conn.execute(
                "INSERT OR REPLACE INTO indicator "
                "(ticker, indicator, params, date, data, cached_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ticker, indicator, params_key, date_str, json.dumps(record), now),
            )

        conn.commit()

    def clear(
        self,
        ticker: str | None = None,
        older_than_days: int | None = None,
    ) -> int:
        """Clear cache entries. Returns count of deleted rows."""
        total_deleted = 0

        if ticker:
            db_files = [self.cache_dir / f"{ticker.upper()}.db"]
        else:
            db_files = list(self.cache_dir.glob("*.db"))

        for db_path in db_files:
            if not db_path.exists():
                continue
            try:
                conn = sqlite3.connect(str(db_path))
                if older_than_days:
                    cutoff = time.time() - (older_than_days * 86400)
                    for table in ("ohlcv", "indicator"):
                        cursor = conn.execute(
                            f"DELETE FROM {table} WHERE cached_at < ?", (cutoff,)
                        )
                        total_deleted += cursor.rowcount
                else:
                    for table in ("ohlcv", "indicator"):
                        cursor = conn.execute(f"DELETE FROM {table}")
                        total_deleted += cursor.rowcount
                conn.commit()
                conn.close()
            except Exception:
                continue

        return total_deleted

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        total_entries = 0
        total_size_kb = 0
        tickers = []

        for db_path in self.cache_dir.glob("*.db"):
            ticker = db_path.stem
            size_kb = db_path.stat().st_size / 1024
            total_size_kb += size_kb

            try:
                conn = sqlite3.connect(str(db_path))
                ohlcv_count = conn.execute("SELECT COUNT(*) FROM ohlcv").fetchone()[0]
                indicator_count = conn.execute("SELECT COUNT(*) FROM indicator").fetchone()[0]
                conn.close()
                total_entries += ohlcv_count + indicator_count
                tickers.append({
                    "ticker": ticker,
                    "ohlcv_rows": ohlcv_count,
                    "indicator_rows": indicator_count,
                    "size_kb": round(size_kb, 1),
                })
            except Exception:
                continue

        return {
            "enabled": True,
            "cache_dir": str(self.cache_dir),
            "total_entries": total_entries,
            "total_size_kb": round(total_size_kb, 1),
            "tickers": tickers,
        }

    def close(self) -> None:
        """Close all database connections."""
        for conn in self._connections.values():
            try:
                conn.close()
            except Exception:
                pass
        self._connections.clear()
