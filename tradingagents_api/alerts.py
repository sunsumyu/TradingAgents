"""Price/indicator alert service (ticket #4).

SQLite-backed alert rules with full trigger history. Alert evaluation is
delegated to the signal engine (the single evaluation authority); this
module owns persistence and the HTTP contract.

Storage: ~/.tradingagents/alerts.db (WAL) — tables ``alerts`` and
``alert_events`` (trigger history).
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


class AlertEvent(BaseModel):
    """One recorded trigger of an alert."""

    alert_id: str
    ticker: str
    condition: str
    value: float | None = None
    message: str = ""
    triggered_at: float


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
            last_indicator_value REAL
        )
        """
    )
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
    conn.commit()
    return conn


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
            " message, enabled, triggered, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?)",
            (alert_id, ticker, condition, threshold, indicator, message, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        return _row_to_out(row)
    finally:
        conn.close()


def delete_alert(alert_id: str) -> bool:
    """Delete an alert rule and its history. Returns True if it existed."""
    conn = _connect()
    try:
        cur = conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        conn.execute("DELETE FROM alert_events WHERE alert_id = ?", (alert_id,))
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
            "UPDATE alerts SET enabled = ?, triggered = 0, triggered_at = NULL"
            " WHERE id = ?",
            (1 if enabled else 0, alert_id),
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
            conn.execute(
                "UPDATE alerts SET last_price = ?, last_indicator_value = ?,"
                " triggered = ?, triggered_at = COALESCE(?, triggered_at)"
                " WHERE id = ?",
                (
                    alert.last_price,
                    alert.last_indicator_value,
                    1 if alert.triggered else 0,
                    alert.triggered_at,
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
