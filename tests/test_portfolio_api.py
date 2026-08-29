"""HTTP contract tests for the portfolio router (ticket #2 migration).

Pins the legacy API contract (zero-commission arithmetic, Chinese error
messages, response shapes) while the service is migrated onto the
portfolio engine, plus the new optional fields (commission, performance).
"""

import pytest
from unittest.mock import patch

from fastapi.testclient import TestClient

from tradingagents_api.server import app
from tradingagents_api import portfolio as portfolio_service


@pytest.fixture()
def client(tmp_path):
    """Test client with portfolio storage isolated to a temp file."""
    fake_file = tmp_path / "portfolio.json"
    with patch.object(portfolio_service, "PORTFOLIO_FILE", fake_file):
        portfolio_service.reset_portfolio(1_000_000.0)
        yield TestClient(app)


class TestLegacyContract:
    def test_empty_portfolio(self, client):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert data["positions"] == []
        assert data["cash"] == 1_000_000.0
        assert data["total_value"] == 1_000_000.0
        assert data["total_pnl"] == 0.0

    def test_buy_exact_cash_arithmetic_no_commission(self, client):
        resp = client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 100,
            "price": 1500.0, "name": "贵州茅台",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["cash"] == 850_000.0  # No commission by default
        assert data["positions"][0]["avg_cost"] == 1500.0
        assert data["positions"][0]["quantity"] == 100

    def test_buy_insufficient_cash_chinese_error(self, client):
        resp = client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 1000, "price": 1500.0,
        })
        assert resp.status_code == 400
        assert "现金不足" in resp.json()["detail"]

    def test_sell_insufficient_chinese_error(self, client):
        client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 100, "price": 1500.0,
        })
        resp = client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "sell", "quantity": 200, "price": 1550.0,
        })
        assert resp.status_code == 400
        assert "持仓不足" in resp.json()["detail"]

    def test_unknown_action_chinese_error(self, client):
        resp = client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "hold", "quantity": 100, "price": 1500.0,
        })
        assert resp.status_code == 400
        assert "未知操作" in resp.json()["detail"]

    def test_sell_all_cash_exact(self, client):
        client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 100, "price": 1500.0,
        })
        resp = client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "sell", "quantity": 100, "price": 1550.0,
        })
        assert resp.json()["cash"] == 1_005_000.0

    def test_history_newest_first(self, client):
        client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 100, "price": 1500.0,
        })
        client.post("/api/portfolio/trade", json={
            "ticker": "000858", "action": "buy", "quantity": 200, "price": 160.0,
        })
        resp = client.get("/api/portfolio/history")
        tickers = [t["ticker"] for t in resp.json()]
        assert tickers == ["000858", "600519"]

    def test_nav_history(self, client):
        client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 100, "price": 1500.0,
        })
        resp = client.get("/api/portfolio/nav")
        nav = resp.json()["nav_history"]
        assert len(nav) == 1
        assert nav[0]["nav"] == 1_000_000.0

    def test_reset(self, client):
        client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 100, "price": 1500.0,
        })
        resp = client.post("/api/portfolio/reset?initial_cash=500000")
        assert resp.json()["cash"] == 500_000.0
        assert client.get("/api/portfolio/history").json() == []


class TestNewOptionalFields:
    def test_trade_record_has_commission_field(self, client):
        client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 100, "price": 1500.0,
        })
        record = client.get("/api/portfolio/history").json()[0]
        assert "commission" in record
        assert record["commission"] == 0.0  # Zero-rate default preserves legacy

    def test_portfolio_response_has_performance(self, client):
        client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 100, "price": 1500.0,
        })
        client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "sell", "quantity": 100, "price": 1650.0,
        })
        data = client.get("/api/portfolio").json()
        assert "performance" in data
        perf = data["performance"]
        assert perf["total_trades"] == 1
        assert perf["winning_trades"] == 1
        assert "sharpe_ratio" in perf
        assert "max_drawdown" in perf
        assert "win_rate" in perf

    def test_commission_charged_when_configured(self, client, monkeypatch):
        monkeypatch.setattr(portfolio_service, "COMMISSION_RATE", 0.001)
        monkeypatch.setattr(portfolio_service, "MIN_COMMISSION", 5.0)
        resp = client.post("/api/portfolio/trade", json={
            "ticker": "600519", "action": "buy", "quantity": 100, "price": 1500.0,
        })
        data = resp.json()
        expected_commission = max(150_000 * 0.001, 5.0)
        assert data["cash"] == pytest.approx(1_000_000 - 150_000 - expected_commission)
        record = client.get("/api/portfolio/history").json()[0]
        assert record["commission"] == pytest.approx(expected_commission)
