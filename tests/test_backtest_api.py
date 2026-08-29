"""HTTP contract tests for the backtest router (ticket #6).

The engine is replaced with a fake (akquant-shaped result object), so no
real akquant / akshare / network is required.  Covers: full metric +
equity-curve roundtrip, akquant metric-shape extraction, ImportError ->
503 with install guidance, ValueError -> 400, and decision passthrough.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tradingagents.backtesting.engine import BacktestResult
from tradingagents_api.server import app


try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:  # pragma: no cover
    _HAS_PANDAS = False


class _RawMetrics:
    total_return = 0.12
    annualized_return = 0.35
    max_drawdown = -0.08
    sharpe_ratio = 1.45
    end_market_value = 112_000.0


class _MetricsWrapper:
    def __init__(self, raw):
        self._raw = raw

    def __getattr__(self, name):
        return getattr(self._raw, name)


class _RawTradeMetrics:
    total_closed_trades = 3
    won_count = 2
    lost_count = 1
    win_rate = 66.6667


@pytest.fixture()
def client():
    return TestClient(app)


def _akquant_shaped_run_result():
    """akquant-shaped fake: wrapper metrics + trades_df + tz-aware curve."""
    assert _HAS_PANDAS, "pandas required"
    idx = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-08"], utc=True)
    equity = pd.Series([100_000.0, 102_000.0, 112_000.0], index=idx)
    trades_df = pd.DataFrame({"pnl": [1500.0, -400.0, 900.0]})

    class _FakeResult:
        pass

    fake = _FakeResult()
    fake.metrics = _MetricsWrapper(_RawMetrics())
    fake.trade_metrics = _RawTradeMetrics()
    fake.equity_curve = equity
    fake.trades_df = trades_df
    return fake


def _flat_run_result():
    """Simple BacktestResult, as returned by run_from_decision(HOLD)."""
    return BacktestResult(
        ticker="600519",
        decision="AgentStrategy_HOLD_600519",
        total_return=0.0,
        total_trades=0,
        initial_cash=100_000.0,
        final_value=100_000.0,
        holding_days=5,
        equity_curve=[],
    )


class _FakeEngine:
    def __init__(self, run_result=None, run_error=None):
        self.run_result = run_result
        self.run_error = run_error
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.run_error is not None:
            raise self.run_error
        return self.run_result


class TestBacktestHTTPContract:

    def test_full_roundtrip_with_curve(self, client):
        result = BacktestResult(
            ticker="600519",
            decision="AgentStrategy_BUY_600519",
            total_return=0.12,
            annual_return=0.35,
            sharpe_ratio=1.45,
            max_drawdown=-0.08,
            win_rate=2 / 3,
            total_trades=3,
            profit_trades=2,
            loss_trades=1,
            initial_cash=100_000.0,
            final_value=112_000.0,
            holding_days=5,
            equity_curve=[
                {"date": "2026-01-05", "value": 100_000.0},
                {"date": "2026-01-06", "value": 102_000.0},
                {"date": "2026-01-08", "value": 112_000.0},
            ],
        )
        fake = _FakeEngine(run_result=result)
        with patch(
            "tradingagents_api.routers.backtest._load_engine",
            return_value=lambda: fake,
        ):
            resp = client.post("/api/backtest", json={
                "ticker": "600519",
                "start_date": "2025-12-01",
                "end_date": "2026-01-10",
                "decision": "BUY",
                "holding_days": 5,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["ticker"] == "600519"
        assert body["total_return"] == pytest.approx(0.12)
        assert body["annual_return"] == pytest.approx(0.35)
        assert body["sharpe_ratio"] == pytest.approx(1.45)
        assert body["max_drawdown"] == pytest.approx(-0.08)
        assert body["win_rate"] == pytest.approx(2 / 3)
        assert body["total_trades"] == 3
        assert body["final_value"] == pytest.approx(112_000.0)
        assert body["holding_days"] == 5
        assert body["equity_curve"] == [
            {"date": "2026-01-05", "value": 100_000.0},
            {"date": "2026-01-06", "value": 102_000.0},
            {"date": "2026-01-08", "value": 112_000.0},
        ]
        assert "# Backtest Report" in (body["report_markdown"] or "")
        # Engine received the request verbatim
        call = fake.calls[0]
        assert call["ticker"] == "600519"
        assert call["start_date"] == "2025-12-01"
        assert call["holding_days"] == 5

    @pytest.mark.skipif(not _HAS_PANDAS, reason="pandas not installed")
    def test_akquant_shaped_result_extracted(self, client):
        """Raw akquant result flows through _parse_result inside engine.run."""
        raw = _akquant_shaped_run_result()

        class _EngineWithParse:
            """Mimics the real engine: run() -> _parse_result -> BacktestResult."""

            def run(self, **kwargs):
                from tradingagents.backtesting.engine import BacktestEngine

                return BacktestEngine()._parse_result(
                    raw,
                    ticker=kwargs["ticker"],
                    strategy_class=kwargs.get("strategy_class")
                    or type("AgentStrategy_BUY_600519", (), {}),
                    initial_cash=kwargs.get("initial_cash", 100_000.0),
                )

        fake = _EngineWithParse()
        with patch(
            "tradingagents_api.routers.backtest._load_engine",
            return_value=lambda: fake,
        ):
            resp = client.post("/api/backtest", json={
                "ticker": "600519",
                "start_date": "2025-12-01",
                "end_date": "2026-01-10",
                "decision": "BUY",
                "holding_days": 3,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_return"] == pytest.approx(0.12)
        assert body["annual_return"] == pytest.approx(0.35)
        assert body["sharpe_ratio"] == pytest.approx(1.45)
        assert body["max_drawdown"] == pytest.approx(-0.08)
        assert body["win_rate"] == pytest.approx(2 / 3)
        assert body["final_value"] == pytest.approx(112_000.0)
        assert body["equity_curve"] == [
            {"date": "2026-01-05", "value": 100_000.0},
            {"date": "2026-01-06", "value": 102_000.0},
            {"date": "2026-01-08", "value": 112_000.0},
        ]

    def test_import_error_returns_503_with_guidance(self, client):
        def _boom(**kwargs):
            raise ImportError("akquant is not installed")

        fake = type("E", (), {"run": staticmethod(_boom)})()
        with patch(
            "tradingagents_api.routers.backtest._load_engine",
            return_value=lambda: fake,
        ):
            resp = client.post("/api/backtest", json={
                "ticker": "600519",
                "start_date": "2025-12-01",
                "end_date": "2026-01-10",
                "decision": "BUY",
            })
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert "akquant" in detail
        assert "pip install" in detail

    def test_value_error_returns_400(self, client):
        def _boom(**kwargs):
            raise ValueError("No data available for 600519")

        fake = type("E", (), {"run": staticmethod(_boom)})()
        with patch(
            "tradingagents_api.routers.backtest._load_engine",
            return_value=lambda: fake,
        ):
            resp = client.post("/api/backtest", json={
                "ticker": "600519",
                "start_date": "2099-01-01",
                "end_date": "2099-02-01",
                "decision": "BUY",
            })
        assert resp.status_code == 400
        assert "No data available" in resp.json()["detail"]

    def test_hold_decision_returns_zero_trade_result(self, client):
        fake = _FakeEngine(run_result=_flat_run_result())
        with patch(
            "tradingagents_api.routers.backtest._load_engine",
            return_value=lambda: fake,
        ):
            resp = client.post("/api/backtest", json={
                "ticker": "600519",
                "start_date": "2025-12-01",
                "end_date": "2026-01-10",
                "decision": "HOLD",
                "holding_days": 10,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "AgentStrategy_HOLD_600519"
        assert body["total_trades"] == 0
        assert body["equity_curve"] == []

    def test_holding_days_passthrough(self, client):
        fake = _FakeEngine(run_result=_flat_run_result())
        with patch(
            "tradingagents_api.routers.backtest._load_engine",
            return_value=lambda: fake,
        ):
            resp = client.post("/api/backtest", json={
                "ticker": "600519",
                "start_date": "2025-12-01",
                "end_date": "2026-01-10",
                "decision": "BUY",
                "holding_days": 10,
            })
        assert resp.status_code == 200
        assert fake.calls[0]["holding_days"] == 10
