"""Price/indicator alert service (ticket #4 + #12).

SQLite-backed alert rules with full trigger history. Alert evaluation is
delegated to the signal engine (the single evaluation authority); this
module owns persistence and the HTTP contract.

Storage: ~/.tradingagents/alerts.db (WAL) - tables ``alerts`` and
``alert_events`` (trigger history), plus ``alert_deletions`` tombstones
for ticket #12 GUI sync. ``alerts.updated_at`` drives newer-wins merge
with offline clients (legacy rows backfill from created_at).
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from tradingagents.signal_engine import AlertCondition, SignalEngine
from tradingagents.signal_engine.models import Alert

logger = logging.getLogger(__name__)

ALERTS_DIR = Path.home() / ".tradingagents"
ALERTS_DB = ALERTS_DIR / "alerts.db"

_VALID_CONDITIONS = {c.value for c in AlertCondition}

# ── Models ───────────────────────────────────────────────────────────────────


class AlertOut(BaseModel):
    """One alert rule as returned by the API."""

    id: str
    ticker: str
    condition: str
    threshold: float = 0
    indicator: str | None = None
    message: str = ""
    enabled: bool = True
    triggered: bool = False
    created_at: float = 0
    triggered_at: float | None = None
    updated_at: float = 0


class AlertEvent(BaseModel):
    """One recorded trigger of an alert."""

    alert_id: str
    ticker: str
    condition: str
    value: float | None = None
    message: str = ""
    triggered_at: float


class AlertSyncItem(BaseModel):
    """One client-side alert pushed during a sync (partial - merge,
    not replace). ``triggered``/``triggered_at`` mirror the client's
    view; a false->true transition is recorded as a trigger event."""

    id: str
    ticker: str
    condition: str
    threshold: float = 0
    indicator: str | None = None
    message: str = ""
    enabled: bool = True
    triggered: bool = False
    created_at: float = 0
    triggered_at: float | None = None
    updated_at: float = 0


class AlertDeleteMark(BaseModel):
    """A deletion tombstone: the alert was removed client-side at
    ``deleted_at``; stale pushes older than this are dropped."""

    id: str
    deleted_at: float = 0


class AlertSyncRequest(BaseModel):
    alerts: list[AlertSyncItem] = Field(default_factory=list)
    deleted: list[AlertDeleteMark] = Field(default_factory=list)


class AlertSyncResult(BaseModel):
    alerts: list[AlertOut] = Field(default_factory=list)


# ── Storage ──────────────────────────────────────────────────────────────────


def _connect() -> sqlite3.Connection:
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ALERTS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            condition TEXT NOT NULL,
            threshold REAL NOT NULL DEFAULT 0,
            indicator TEXT,
            message TEXT DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            triggered INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL DEFAULT 0,
            triggered_at REAL,
            last_price REAL,
            last_indicator_value REAL,
            updated_at REAL NOT NULL DEFAULT 0
        )
        """
    )
    # Ticket #12: pre-sync DBs lack updated_at / the tombstone table
    _ensure_schema(conn)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            condition TEXT NOT NULL,
            value REAL,
            message TEXT DEFAULT '',
            triggered_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_deletions (
            id TEXT PRIMARY KEY,
            deleted_at REAL NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Bring pre-ticket-#12 databases up to the current schema.

    Adds the ``updated_at`` column (backfilled from ``created_at``) and
    the ``alert_deletions`` tombstone table. Safe to run repeatedly.
    """
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(alerts)")}
    if "updated_at" not in columns:
        conn.execute("ALTER TABLE alerts ADD COLUMN updated_at REAL DEFAULT 0")
        conn.execute(
            "UPDATE alerts SET updated_at = created_at WHERE updated_at = 0"
        )
        conn.commit()


def _row_to_out(row: sqlite3.Row) -> AlertOut:
    return AlertOut(
        id=row["id"],
        ticker=row["ticker"],
        condition=row["condition"],
        threshold=row["threshold"],
        indicator=row["indicator"],
        message=row["message"],
        enabled=bool(row["enabled"]),
        triggered=bool(row["triggered"]),
        created_at=row["created_at"],
        triggered_at=row["triggered_at"],
        updated_at=row["updated_at"],
    )


def _alert_to_out(alert: Alert) -> AlertOut:
    return AlertOut(
        id=alert.id,
        ticker=alert.ticker,
        condition=alert.condition.value,
        threshold=alert.threshold,
        indicator=alert.indicator,
        message=alert.message,
        enabled=alert.enabled,
        triggered=alert.triggered,
        created_at=alert.created_at,
        triggered_at=alert.triggered_at,
        updated_at=alert.created_at,
    )


def _row_to_alert(row: sqlite3.Row) -> Alert:
    """Rehydrate an engine Alert (including cross-detection baselines)."""
    return Alert(
        id=row["id"],
        ticker=row["ticker"],
        condition=AlertCondition(row["condition"]),
        threshold=row["threshold"],
        indicator=row["indicator"],
        message=row["message"],
        triggered=bool(row["triggered"]),
        created_at=row["created_at"],
        triggered_at=row["triggered_at"],
        enabled=bool(row["enabled"]),
        last_price=row["last_price"],
        last_indicator_value=row["last_indicator_value"],
    )


# ── Public API ───────────────────────────────────────────────────────────────


def list_alerts(ticker: str | None = None) -> list[AlertOut]:
    """List alert rules, optionally filtered by ticker."""
    conn = _connect()
    try:
        if ticker:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE ticker = ? ORDER BY created_at DESC",
                (ticker,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_out(r) for r in rows]
    finally:
        conn.close()


def create_alert(
    ticker: str,
    condition: str,
    threshold: float = 0,
    indicator: str | None = None,
    message: str = "",
) -> AlertOut:
    """Create an alert rule. Raises ValueError on an unknown condition."""
    if condition not in _VALID_CONDITIONS:
        raise ValueError(
            f"未知预警条件: {condition}（支持: {', '.join(sorted(_VALID_CONDITIONS))}）"
        )
    if not ticker:
        raise ValueError("ticker 不能为空")

    conn = _connect()
    try:
        alert_id = uuid.uuid4().hex[:8]
        now = time.time()
        conn.execute(
            "INSERT INTO alerts (id, ticker, condition, threshold, indicator,"
            " message, enabled, triggered, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?)",
            (alert_id, ticker, condition, threshold, indicator, message,
             now, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return _row_to_out(row)
    finally:
        conn.close()


def delete_alert(alert_id: str) -> bool:
    """Delete an alert rule and its history. Returns True if it existed.

    A deletion tombstone is written so offline clients pushing the same
    alert later don't resurrect it (unless their push is newer).
    """
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        conn.execute("DELETE FROM alert_events WHERE alert_id = ?", (alert_id,))
        conn.execute(
            "INSERT OR REPLACE INTO alert_deletions (id, deleted_at)"
            " VALUES (?, ?)",
            (alert_id, time.time()),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def set_alert_enabled(alert_id: str, enabled: bool) -> AlertOut | None:
    """Enable/disable an alert without deleting it (re-enable re-arms)."""
    conn = _connect()
    try:
        # Re-enabling re-arms the alert: clear the triggered state so it
        # can fire again (disable+enable is the documented re-arm path).
        conn.execute(
            "UPDATE alerts SET enabled = ?, triggered = 0, triggered_at = NULL,"
            " updated_at = ? WHERE id = ?",
            (1 if enabled else 0, time.time(), alert_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return _row_to_out(row) if row else None
    finally:
        conn.close()


def get_alert_history(alert_id: str) -> list[AlertEvent]:
    """Get the trigger history for one alert, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM alert_events WHERE alert_id = ? ORDER BY triggered_at DESC",
            (alert_id,),
        ).fetchall()
        return [
            AlertEvent(
                alert_id=r["alert_id"],
                ticker=r["ticker"],
                condition=r["condition"],
                value=r["value"],
                message=r["message"],
                triggered_at=r["triggered_at"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def check_alerts(
    ticker: str,
    price: float,
    volume: float = 0,
    indicator_values: dict[str, float] | None = None,
) -> tuple[list[AlertOut], list[str]]:
    """Evaluate all armed alerts for *ticker* against the latest quote.

    Alert evaluation runs through the signal engine; baselines
    (last_price / last_indicator_value) round-trip through the store so
    cross detection survives process restarts and stateless workers.

    Returns:
        (triggered alerts, ids of indicator-condition alerts that could not
        be evaluated because their indicator value was not supplied — they
        stay armed, but the caller is told explicitly).
    """
    indicator_values = indicator_values or {}
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE ticker = ?", (ticker,)
        ).fetchall()
        if not rows:
            return [], []

        engine = SignalEngine()
        engine.restore_alerts([_row_to_alert(row) for row in rows])

        triggered = engine.check_alerts(
            ticker, price, volume=volume, indicator_values=indicator_values
        )

        now = time.time()
        for alert in engine._alerts.values():
            row = conn.execute(
                "SELECT triggered FROM alerts WHERE id = ?", (alert.id,)
            ).fetchone()
            became_triggered = alert.triggered and not bool(row["triggered"])
            conn.execute(
                "UPDATE alerts SET last_price = ?, last_indicator_value = ?,"
                " triggered = ?, triggered_at = COALESCE(?, triggered_at),"
                " updated_at = CASE WHEN ? THEN ? ELSE updated_at END"
                " WHERE id = ?",
                (
                    alert.last_price,
                    alert.last_indicator_value,
                    1 if alert.triggered else 0,
                    alert.triggered_at,
                    1 if became_triggered else 0,
                    now,
                    alert.id,
                ),
            )
        for alert in triggered:
            conn.execute(
                "INSERT INTO alert_events (alert_id, ticker, condition, value,"
                " message, triggered_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    alert.id,
                    alert.ticker,
                    alert.condition.value,
                    alert.last_indicator_value
                    if alert.condition in (AlertCondition.INDICATOR_ABOVE,
                                           AlertCondition.INDICATOR_BELOW)
                    else price,
                    alert.message,
                    now,
                ),
            )
        conn.commit()

        unevaluated = [
            alert.id
            for alert in engine._alerts.values()
            if alert.enabled and not alert.triggered
            and alert.condition in (AlertCondition.INDICATOR_ABOVE,
                                    AlertCondition.INDICATOR_BELOW,
                                    AlertCondition.CROSS_ABOVE,
                                    AlertCondition.CROSS_BELOW)
            and indicator_values.get(alert.indicator) is None
        ]
        return [_alert_to_out(a) for a in triggered], unevaluated
    finally:
        conn.close()


# ── Ticket #12: GUI sync (local-first + server merge) ───────────────────────


def get_sync_state() -> AlertSyncResult:
    """Full server-side alert state (used by the sync round-trip)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC"
        ).fetchall()
        return AlertSyncResult(alerts=[_row_to_out(r) for r in rows])
    finally:
        conn.close()


def sync_alerts(request: AlertSyncRequest) -> AlertSyncResult:
    """Merge the client's alert state into the server store and return it.

    Merge rules (mirrors the watchlist sync design):
    - ``deleted`` tombstones remove alerts and record the deletion time;
      a later push for the same id only resurrects it when its
      ``updated_at`` is newer than the tombstone.
    - Each pushed alert upserts when its ``updated_at`` >= the stored
      one (ties -> client wins; the client is the active editor). The
      upsert writes user fields + trigger state but never touches
      ``last_price`` / ``last_indicator_value`` (server-side cross
      detection baselines survive client edits).
    - A false->true trigger transition records one ``alert_events`` row
      (repeat triggered=True pushes don't duplicate history).
    """
    conn = _connect()
    try:
        now = time.time()
        tombstones: dict[str, float] = {
            r["id"]: r["deleted_at"]
            for r in conn.execute("SELECT * FROM alert_deletions").fetchall()
        }

        # 1. Apply client deletions (newest tombstone wins)
        for mark in request.deleted:
            conn.execute("DELETE FROM alerts WHERE id = ?", (mark.id,))
            conn.execute("DELETE FROM alert_events WHERE alert_id = ?", (mark.id,))
            current = tombstones.get(mark.id, 0.0)
            if mark.deleted_at >= current:
                tombstones[mark.id] = mark.deleted_at
            conn.execute(
                "INSERT OR REPLACE INTO alert_deletions (id, deleted_at)"
                " VALUES (?, ?)",
                (mark.id, tombstones[mark.id]),
            )

        # 2. Upsert pushed alerts
        for item in request.alerts:
            if item.condition not in _VALID_CONDITIONS:
                logger.warning("Sync dropped unknown condition: %s", item.condition)
                continue

            # A tombstone newer than this push means the deletion is the
            # more recent truth - drop the stale push.
            tombstone_ts = tombstones.get(item.id)
            if tombstone_ts is not None and tombstone_ts >= item.updated_at:
                continue

            row = conn.execute(
                "SELECT * FROM alerts WHERE id = ?", (item.id,)
            ).fetchone()
            if row is not None and row["updated_at"] > item.updated_at:
                continue  # server version is newer - client push is stale

            became_triggered = bool(item.triggered) and (
                row is None or not bool(row["triggered"])
            )
            conn.execute(
                """
                INSERT INTO alerts (id, ticker, condition, threshold, indicator,
                    message, enabled, triggered, created_at, triggered_at,
                    last_price, last_indicator_value, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    ticker = excluded.ticker,
                    condition = excluded.condition,
                    threshold = excluded.threshold,
                    indicator = excluded.indicator,
                    message = excluded.message,
                    enabled = excluded.enabled,
                    triggered = excluded.triggered,
                    triggered_at = excluded.triggered_at,
                    updated_at = excluded.updated_at
                """,
                (
                    item.id, item.ticker, item.condition, item.threshold,
                    item.indicator, item.message,
                    1 if item.enabled else 0,
                    1 if item.triggered else 0,
                    item.created_at or now,
                    item.triggered_at,
                    None if row is None else row["last_price"],
                    None if row is None else row["last_indicator_value"],
                    item.updated_at or now,
                ),
            )
            # The push resurrected/re-created the alert - clear tombstone
            conn.execute("DELETE FROM alert_deletions WHERE id = ?", (item.id,))
            tombstones.pop(item.id, None)

            if became_triggered:
                conn.execute(
                    "INSERT INTO alert_events (alert_id, ticker, condition,"
                    " value, message, triggered_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        item.id, item.ticker, item.condition, item.threshold,
                        item.message, item.triggered_at or now,
                    ),
                )

        conn.commit()
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC"
        ).fetchall()
        return AlertSyncResult(alerts=[_row_to_out(r) for r in rows])
    finally:
        conn.close()
