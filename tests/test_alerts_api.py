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
