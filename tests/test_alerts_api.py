"""HTTP contract tests for the alerts router (ticket #4).

Covers the full alert lifecycle over the API: create (all 7 condition
types validated), list/filter, enable/disable, delete, trigger history,
and quote-driven checks. Storage is isolated to a temp SQLite file.
"""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tradingagents_api import alerts as alerts_service
from tradingagents_api.server import app


@pytest.fixture()
def client(tmp_path):
    fake_db = tmp_path / "alerts.db"
    with patch.object(alerts_service, "ALERTS_DB", fake_db):
        yield TestClient(app)


class TestAlertLifecycle:
    def test_create_and_list(self, client):
        resp = client.post("/api/alerts", json={
            "ticker": "600519", "condition": "price_above",
            "threshold": 1800.0, "message": "突破",
        })
        assert resp.status_code == 200
        alert = resp.json()
        assert alert["ticker"] == "600519"
        assert alert["enabled"] is True
        assert alert["triggered"] is False

        listing = client.get("/api/alerts").json()
        assert len(listing) == 1
        assert listing[0]["id"] == alert["id"]

    def test_list_filter_by_ticker(self, client):
        client.post("/api/alerts", json={
            "ticker": "600519", "condition": "price_above", "threshold": 1,
        })
        client.post("/api/alerts", json={
            "ticker": "000858", "condition": "price_below", "threshold": 2,
        })
        only = client.get("/api/alerts", params={"ticker": "600519"}).json()
        assert len(only) == 1
        assert only[0]["ticker"] == "600519"

    def test_invalid_condition_rejected(self, client):
        resp = client.post("/api/alerts", json={
            "ticker": "600519", "condition": "moon_alignment", "threshold": 1,
        })
        assert resp.status_code == 400
        assert "未知预警条件" in resp.json()["detail"]

    def test_empty_ticker_rejected(self, client):
        resp = client.post("/api/alerts", json={
            "ticker": "", "condition": "price_above", "threshold": 1,
        })
        assert resp.status_code == 400

    def test_delete(self, client):
        alert = client.post("/api/alerts", json={
            "ticker": "600519", "condition": "price_above", "threshold": 1,
        }).json()
        resp = client.delete(f"/api/alerts/{alert['id']}")
        assert resp.json() == {"deleted": True}
        assert client.get("/api/alerts").json() == []
        # History rows are cleaned up too
        assert client.get(f"/api/alerts/{alert['id']}/history").json() == []

    def test_enable_disable_rearms(self, client):
        alert = client.post("/api/alerts", json={
            "ticker": "600519", "condition": "price_above", "threshold": 1800.0,
        }).json()
        # Trigger it
        client.post("/api/alerts/check", json={"ticker": "600519", "price": 1900.0})
        # Disable -> re-enable re-arms
        off = client.post(f"/api/alerts/{alert['id']}/enabled",
                          json={"enabled": False}).json()
        assert off["enabled"] is False
        on = client.post(f"/api/alerts/{alert['id']}/enabled",
                         json={"enabled": True}).json()
        assert on["enabled"] is True and on["triggered"] is False

    def test_enable_unknown_alert_404(self, client):
        resp = client.post("/api/alerts/nonexistent/enabled",
                           json={"enabled": True})
        assert resp.status_code == 404


class TestAlertChecking:
    def test_price_above_triggers_and_records_history(self, client):
        alert = client.post("/api/alerts", json={
            "ticker": "600519", "condition": "price_above",
            "threshold": 1800.0, "message": "突破压力位",
        }).json()

        miss = client.post("/api/alerts/check",
                           json={"ticker": "600519", "price": 1750.0}).json()
        assert miss["triggered"] == []

        hit = client.post("/api/alerts/check",
                          json={"ticker": "600519", "price": 1850.0}).json()
        assert len(hit["triggered"]) == 1
        assert hit["triggered"][0]["id"] == alert["id"]

        # Triggered once — repeated checks don't re-fire
        again = client.post("/api/alerts/check",
                            json={"ticker": "600519", "price": 1900.0}).json()
        assert again["triggered"] == []

        history = client.get(f"/api/alerts/{alert['id']}/history").json()
        assert len(history) == 1
        assert history[0]["condition"] == "price_above"
        assert history[0]["value"] == 1850.0

    def test_indicator_below_with_values(self, client):
        alert = client.post("/api/alerts", json={
            "ticker": "600519", "condition": "indicator_below",
            "threshold": 30.0, "indicator": "RSI", "message": "超卖",
        }).json()

        # No indicator values -> stays armed
        miss = client.post("/api/alerts/check",
                           json={"ticker": "600519", "price": 1800.0}).json()
        assert miss["triggered"] == []

        hit = client.post("/api/alerts/check", json={
            "ticker": "600519", "price": 1800.0,
            "indicator_values": {"RSI": 25.0},
        }).json()
        assert len(hit["triggered"]) == 1
        assert hit["triggered"][0]["indicator"] == "RSI"

    def test_missing_indicator_values_reported_explicitly(self, client):
        """Indicator conditions without values are surfaced as
        'unevaluated' (explicit) instead of failing silently."""
        client.post("/api/alerts", json={
            "ticker": "600519", "condition": "indicator_below",
            "threshold": 30.0, "indicator": "RSI",
        })
        result = client.post("/api/alerts/check",
                             json={"ticker": "600519", "price": 1800.0}).json()
        assert result["triggered"] == []
        assert len(result["unevaluated"]) == 1

        # Once values arrive, the alert evaluates normally
        result = client.post("/api/alerts/check", json={
            "ticker": "600519", "price": 1800.0,
            "indicator_values": {"RSI": 25.0},
        }).json()
        assert len(result["triggered"]) == 1
        assert result["unevaluated"] == []

    def test_cross_above_arms_then_triggers_across_calls(self, client):
        """Cross detection works across separate stateless check calls —
        baselines round-trip through the store."""
        alert = client.post("/api/alerts", json={
            "ticker": "600519", "condition": "cross_above",
            "indicator": "MA20",
        }).json()

        client.post("/api/alerts/check", json={
            "ticker": "600519", "price": 1750.0,
            "indicator_values": {"MA20": 1800.0},
        })
        hit = client.post("/api/alerts/check", json={
            "ticker": "600519", "price": 1815.0,
            "indicator_values": {"MA20": 1800.0},
        }).json()
        assert len(hit["triggered"]) == 1

    def test_other_ticker_unaffected(self, client):
        client.post("/api/alerts", json={
            "ticker": "600519", "condition": "price_above", "threshold": 1800.0,
        })
        result = client.post("/api/alerts/check",
                             json={"ticker": "000858", "price": 9999.0}).json()
        assert result["triggered"] == []


# ── Ticket #12: GUI sync (local-first + server merge) ───────────────────────


class TestAlertSync:
    """PUT /api/alerts/sync - the GUI's one idempotent round-trip.

    The server is the merge authority: client pushes its full alert
    state plus explicit deletion tombstones; the server applies
    newer-wins-by-updated_at merging and returns the merged state.
    """

    def _payload(self, **overrides):
        base = {
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "price_above",
                "threshold": 1800.0, "message": "", "enabled": True,
                "triggered": False, "created_at": 100.0,
                "triggered_at": None, "updated_at": 100.0,
            }],
            "deleted": [],
        }
        base.update(overrides)
        return base

    def test_sync_roundtrip_returns_merged_state(self, client):
        resp = client.put("/api/alerts/sync", json=self._payload())
        assert resp.status_code == 200
        state = resp.json()
        assert len(state["alerts"]) == 1
        alert = state["alerts"][0]
        assert alert["id"] == "a1"
        assert alert["condition"] == "price_above"
        assert alert["updated_at"] == 100.0

        # Empty sync (fresh device pull) returns server state unchanged
        again = client.put("/api/alerts/sync", json={
            "alerts": [], "deleted": [],
        }).json()
        assert len(again["alerts"]) == 1
        assert again["alerts"][0]["id"] == "a1"

    def test_client_wins_when_newer(self, client):
        client.put("/api/alerts/sync", json=self._payload())
        resp = client.put("/api/alerts/sync", json={
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "price_above",
                "threshold": 1900.0, "message": "新阈值", "enabled": True,
                "triggered": False, "created_at": 100.0,
                "triggered_at": None, "updated_at": 200.0,
            }],
            "deleted": [],
        })
        alert = resp.json()["alerts"][0]
        assert alert["threshold"] == 1900.0
        assert alert["message"] == "新阈值"

    def test_server_wins_when_newer(self, client):
        client.put("/api/alerts/sync", json={
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "price_above",
                "threshold": 1900.0, "message": "服务端版本", "enabled": True,
                "triggered": False, "created_at": 100.0,
                "triggered_at": None, "updated_at": 300.0,
            }],
            "deleted": [],
        })
        resp = client.put("/api/alerts/sync", json={
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "price_above",
                "threshold": 1700.0, "message": "过期客户端", "enabled": True,
                "triggered": False, "created_at": 100.0,
                "triggered_at": None, "updated_at": 100.0,
            }],
            "deleted": [],
        })
        alert = resp.json()["alerts"][0]
        assert alert["threshold"] == 1900.0

    def test_tombstone_blocks_stale_push(self, client):
        client.put("/api/alerts/sync", json=self._payload())
        # Client deletes a1 on device 1
        client.put("/api/alerts/sync", json={
            "alerts": [], "deleted": [{"id": "a1", "deleted_at": 200.0}],
        })
        state = client.put("/api/alerts/sync", json=self._payload()).json()
        assert state["alerts"] == []

    def test_newer_push_resurrects_after_tombstone(self, client):
        client.put("/api/alerts/sync", json=self._payload())
        client.put("/api/alerts/sync", json={
            "alerts": [], "deleted": [{"id": "a1", "deleted_at": 200.0}],
        })
        # Device 2 pushes a version newer than the tombstone
        state = client.put("/api/alerts/sync", json={
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "price_below",
                "threshold": 1600.0, "message": "", "enabled": True,
                "triggered": False, "created_at": 100.0,
                "triggered_at": None, "updated_at": 300.0,
            }],
            "deleted": [],
        }).json()
        assert len(state["alerts"]) == 1
        assert state["alerts"][0]["condition"] == "price_below"

    def test_triggering_sync_records_event_once(self, client):
        client.put("/api/alerts/sync", json=self._payload())
        # Local trigger -> client pushes triggered=True
        resp = client.put("/api/alerts/sync", json={
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "price_above",
                "threshold": 1800.0, "message": "", "enabled": True,
                "triggered": True, "created_at": 100.0,
                "triggered_at": 200.0, "updated_at": 200.0,
            }],
            "deleted": [],
        })
        alert = resp.json()["alerts"][0]
        assert alert["triggered"] is True

        # The false->true transition is recorded in history exactly once
        history = client.get("/api/alerts/a1/history").json()
        assert len(history) == 1
        assert history[0]["value"] == 1800.0

        # Pushing triggered=True again does not duplicate the event
        client.put("/api/alerts/sync", json={
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "price_above",
                "threshold": 1850.0, "message": "", "enabled": True,
                "triggered": True, "created_at": 100.0,
                "triggered_at": 250.0, "updated_at": 250.0,
            }],
            "deleted": [],
        })
        assert len(client.get("/api/alerts/a1/history").json()) == 1

    def test_sync_preserves_cross_baselines(self, client):
        # Cross-condition alert: baselines only establish with indicator values
        client.put("/api/alerts/sync", json={
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "cross_above",
                "threshold": 0, "indicator": "MA20", "message": "", "enabled": True,
                "triggered": False, "created_at": 100.0,
                "triggered_at": None, "updated_at": 100.0,
            }],
            "deleted": [],
        })
        # Server-side check establishes baselines (price 1750 / MA20 1800)
        client.post("/api/alerts/check", json={
            "ticker": "600519", "price": 1750.0,
            "indicator_values": {"MA20": 1800.0},
        })
        # Client pushes an unrelated edit - baselines must survive
        client.put("/api/alerts/sync", json={
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "cross_above",
                "threshold": 0, "indicator": "MA20", "message": "编辑",
                "enabled": True, "triggered": False, "created_at": 100.0,
                "triggered_at": None, "updated_at": 300.0,
            }],
            "deleted": [],
        })
        row = alerts_service._connect().execute(
            "SELECT last_price, last_indicator_value FROM alerts WHERE id = 'a1'"
        ).fetchone()
        assert row["last_price"] == 1750.0
        assert row["last_indicator_value"] == 1800.0

    def test_sync_pulls_api_created_alerts(self, client):
        created = client.post("/api/alerts", json={
            "ticker": "000858", "condition": "price_above", "threshold": 150.0,
        }).json()
        state = client.put("/api/alerts/sync", json={
            "alerts": [], "deleted": [],
        }).json()
        assert any(a["id"] == created["id"] for a in state["alerts"])

    def test_legacy_db_gains_updated_at_column(self, tmp_path):
        """Alerts DBs created before ticket #12 gain updated_at on open."""
        import sqlite3
        legacy_db = tmp_path / "legacy.db"
        conn = sqlite3.connect(legacy_db)
        conn.execute(
            "CREATE TABLE alerts (id TEXT PRIMARY KEY, ticker TEXT NOT NULL,"
            " condition TEXT NOT NULL, threshold REAL NOT NULL DEFAULT 0,"
            " indicator TEXT, message TEXT DEFAULT '',"
            " enabled INTEGER NOT NULL DEFAULT 1,"
            " triggered INTEGER NOT NULL DEFAULT 0,"
            " created_at REAL NOT NULL DEFAULT 0, triggered_at REAL,"
            " last_price REAL, last_indicator_value REAL)"
        )
        conn.execute(
            "INSERT INTO alerts (id, ticker, condition, threshold, created_at)"
            " VALUES ('old1', '600519', 'price_above', 1.0, 50.0)"
        )
        conn.commit()
        conn.close()

        with patch.object(alerts_service, "ALERTS_DB", legacy_db):
            state = alerts_service.get_sync_state()
            alert = next(a for a in state.alerts if a.id == "old1")
            assert alert.updated_at == 50.0  # backfilled from created_at

    def test_enable_disable_via_sync(self, client):
        client.put("/api/alerts/sync", json=self._payload())
        resp = client.put("/api/alerts/sync", json={
            "alerts": [{
                "id": "a1", "ticker": "600519", "condition": "price_above",
                "threshold": 1800.0, "message": "", "enabled": False,
                "triggered": True, "created_at": 100.0,
                "triggered_at": 150.0, "updated_at": 200.0,
            }],
            "deleted": [],
        })
        alert = resp.json()["alerts"][0]
        assert alert["enabled"] is False
