"""Watchlist sync service (ticket #5).

User-level SQLite store (WAL) for watchlist groups and their tickers.
The server is the merge authority: PUT applies the client's state with
newer-wins-by-updated_at and explicit tombstone deletions, then returns
the merged full state — one idempotent round-trip per sync.

Storage: ~/.tradingagents/watchlist.db — tables ``watch_groups`` and
``watch_items`` (item identity = (group_id, ticker)).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

WATCHLIST_DIR = Path.home() / ".tradingagents"
WATCHLIST_DB = WATCHLIST_DIR / "watchlist.db"

# ── Models ───────────────────────────────────────────────────────────────────


class WatchlistItemIn(BaseModel):
    ticker: str
    name: str = ""
    position: int = 0
    updated_at: float = 0


class WatchlistItemDelete(BaseModel):
    group_id: str
    ticker: str
    updated_at: float = 0


class WatchlistGroupIn(BaseModel):
    id: str
    name: str = ""
    position: int = 0
    collapsed: bool = False
    updated_at: float = 0
    items: list[WatchlistItemIn] = Field(default_factory=list)


class WatchlistSyncRequest(BaseModel):
    """Client state pushed during a sync (partial — merge, not replace)."""

    groups: list[WatchlistGroupIn] = Field(default_factory=list)
    deleted_group_ids: list[str] = Field(default_factory=list)
    deleted_items: list[WatchlistItemDelete] = Field(default_factory=list)


class WatchlistItemOut(BaseModel):
    ticker: str
    name: str = ""
    position: int = 0
    updated_at: float = 0


class WatchlistGroupOut(BaseModel):
    id: str
    name: str = ""
    position: int = 0
    collapsed: bool = False
    updated_at: float = 0
    items: list[WatchlistItemOut] = Field(default_factory=list)


class WatchlistState(BaseModel):
    groups: list[WatchlistGroupOut] = Field(default_factory=list)


# ── Storage ──────────────────────────────────────────────────────────────────


def _connect() -> sqlite3.Connection:
    WATCHLIST_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(WATCHLIST_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watch_groups (
            id TEXT PRIMARY KEY,
            name TEXT DEFAULT '',
            position INTEGER DEFAULT 0,
            collapsed INTEGER DEFAULT 0,
            updated_at REAL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS watch_items (
            group_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT DEFAULT '',
            position INTEGER DEFAULT 0,
            updated_at REAL DEFAULT 0,
            PRIMARY KEY (group_id, ticker)
        )
        """
    )
    conn.commit()
    return conn


def _load_state(conn: sqlite3.Connection) -> WatchlistState:
    group_rows = conn.execute(
        "SELECT * FROM watch_groups ORDER BY position, updated_at"
    ).fetchall()
    item_rows = conn.execute(
        "SELECT * FROM watch_items ORDER BY position, updated_at"
    ).fetchall()

    items_by_group: dict[str, list[WatchlistItemOut]] = {}
    for r in item_rows:
        items_by_group.setdefault(r["group_id"], []).append(
            WatchlistItemOut(
                ticker=r["ticker"],
                name=r["name"],
                position=r["position"],
                updated_at=r["updated_at"],
            )
        )

    return WatchlistState(groups=[
        WatchlistGroupOut(
            id=r["id"],
            name=r["name"],
            position=r["position"],
            collapsed=bool(r["collapsed"]),
            updated_at=r["updated_at"],
            items=items_by_group.get(r["id"], []),
        )
        for r in group_rows
    ])


# ── Public API ───────────────────────────────────────────────────────────────


def get_watchlist() -> WatchlistState:
    """Return the full server-side watchlist state."""
    conn = _connect()
    try:
        return _load_state(conn)
    finally:
        conn.close()


def sync_watchlist(request: WatchlistSyncRequest) -> WatchlistState:
    """Merge the client's state into the server store and return the result.

    Merge rules:
    - Groups/items are upserted only when the incoming ``updated_at`` is
      newer than or equal to the stored one (ties → incoming wins; the
      client is the active editor).
    - ``deleted_items`` tombstones remove (group_id, ticker) pairs.
    - ``deleted_group_ids`` tombstones remove groups and their items.
    """
    now = time.time()
    conn = _connect()
    try:
        for tombstone in request.deleted_items:
            conn.execute(
                "DELETE FROM watch_items WHERE group_id = ? AND ticker = ?",
                (tombstone.group_id, tombstone.ticker),
            )
        for group_id in request.deleted_group_ids:
            conn.execute("DELETE FROM watch_groups WHERE id = ?", (group_id,))
            conn.execute("DELETE FROM watch_items WHERE group_id = ?", (group_id,))

        for g in request.groups:
            stored = conn.execute(
                "SELECT updated_at FROM watch_groups WHERE id = ?", (g.id,)
            ).fetchone()
            if stored is None or g.updated_at >= stored["updated_at"]:
                conn.execute(
                    "INSERT INTO watch_groups (id, name, position, collapsed, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)"
                    " ON CONFLICT(id) DO UPDATE SET name=excluded.name,"
                    " position=excluded.position, collapsed=excluded.collapsed,"
                    " updated_at=excluded.updated_at",
                    (g.id, g.name, g.position, 1 if g.collapsed else 0,
                     g.updated_at or now),
                )
            for item in g.items:
                stored_item = conn.execute(
                    "SELECT updated_at FROM watch_items WHERE group_id = ? AND ticker = ?",
                    (g.id, item.ticker),
                ).fetchone()
                if stored_item is None or item.updated_at >= stored_item["updated_at"]:
                    conn.execute(
                        "INSERT INTO watch_items (group_id, ticker, name, position, updated_at)"
                        " VALUES (?, ?, ?, ?, ?)"
                        " ON CONFLICT(group_id, ticker) DO UPDATE SET name=excluded.name,"
                        " position=excluded.position, updated_at=excluded.updated_at",
                        (g.id, item.ticker, item.name, item.position,
                         item.updated_at or now),
                    )

        conn.commit()
        return _load_state(conn)
    finally:
        conn.close()
