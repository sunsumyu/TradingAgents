"""Tests for the backtesting module.

Tests the strategy adapter, engine, and report generation without
requiring akquant to be installed (mocks the Rust core).
"""

from __future__ import annotations

import copy
import unittest
from unittest import mock

import pytest

from tradingagents.backtesting.engine import BacktestEngine, BacktestResult
from tradingagents.backtesting.strategy import AgentDecisionStrategy, create_strategy_class
from tradingagents.backtesting.report import generate_backtest_report


# ---------------------------------------------------------------------------
# akquant-shaped result fakes (mirror the installed akquant public surface:
# metrics wrapper with __getattr__ delegation, trades_df DataFrame,
# equity_curve tz-aware Series; scalars in percent / decimal conventions)
# ---------------------------------------------------------------------------

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:  # pragma: no cover
    _HAS_PANDAS = False


class _RawMetrics:
    """Mirrors akquant PerformanceMetrics field names and conventions."""

    total_return = 0.12              # decimal
    annualized_return = 0.35         # decimal
    max_drawdown = -0.08             # decimal (negative)
    sharpe_ratio = 1.45
    win_rate = 60.0                  # percent
    initial_market_value = 100_000.0
    end_market_value = 112_000.0


class _MetricsWrapper:
    """Mirrors akquant's MetricsWrapper: __getattr__ delegates to raw."""

    def __init__(self, raw):
        self._raw = raw

    def __getattr__(self, name):
        return getattr(self._raw, name)


class _RawTradeMetrics:
    total_closed_trades = 3
    won_count = 2
    lost_count = 1
    win_rate = 66.6667               # percent
    avg_return_pct = 2.5             # percent


def _make_akquant_fake():
    """Build a result object shaped like akquant's BacktestResult wrapper."""
    assert _HAS_PANDAS, "pandas required for akquant-shaped fakes"

    idx = pd.to_datetime(
        ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"], utc=True
    )
    equity = pd.Series([100_000.0, 102_000.0, 101_000.0, 112_000.0], index=idx)

    trades_df = pd.DataFrame({
        "symbol": ["600519"] * 3,
        "pnl": [1500.0, -400.0, 900.0],
        "net_pnl": [1480.0, -420.0, 880.0],
        "return_pct": [0.015, -0.004, 0.009],
    })

    class _Fake:
        pass

    fake = _Fake()
    fake.metrics = _MetricsWrapper(_RawMetrics())
    fake.trade_metrics = _RawTradeMetrics()
    fake.equity_curve = equity
    fake.trades_df = trades_df
    fake.trades = object()  # non-iterable sentinel: must not crash extraction
    return fake


@pytest.mark.unit
class TestParseResultAkquantShape:
    """_parse_result must read the real akquant result shape."""

    @pytest.fixture(autouse=True)
    def _require_pandas(self):
        if not _HAS_PANDAS:
            pytest.skip("pandas not installed")

    def _parse(self, fake):
        engine = BacktestEngine()
        return engine._parse_result(
            fake,
            ticker="600519",
            strategy_class=type("AgentStrategy_BUY_600519", (), {}),
            initial_cash=100_000.0,
        )

    def test_metrics_extracted_from_wrapper(self):
        r = self._parse(_make_akquant_fake())
        assert r.total_return == pytest.approx(0.12)
        assert r.annual_return == pytest.approx(0.35)
        assert r.sharpe_ratio == pytest.approx(1.45)
        assert r.max_drawdown == pytest.approx(-0.08)
        assert r.final_value == pytest.approx(112_000.0)

    def test_win_rate_converted_from_percent(self):
        r = self._parse(_make_akquant_fake())
        # trade_metrics.win_rate=66.67% -> 0.6667 fraction
        assert r.win_rate == pytest.approx(0.666667, abs=1e-4)

    def test_trade_stats_from_trades_df(self):
        r = self._parse(_make_akquant_fake())
        assert r.total_trades == 3
        assert r.profit_trades == 2
        assert r.loss_trades == 1

    def test_equity_curve_daily_points(self):
        r = self._parse(_make_akquant_fake())
        curve = r.equity_curve
        assert isinstance(curve, list)
        assert len(curve) == 4
        assert curve[0] == {"date": "2026-01-05", "value": 100_000.0}
        assert curve[-1] == {"date": "2026-01-08", "value": 112_000.0}

    def test_equity_curve_derives_missing_final_value(self):
        fake = _make_akquant_fake()
        fake.metrics = _MetricsWrapper(type("M", (), {
            "total_return": 0.12,
        })())
        r = self._parse(fake)
        # end_market_value absent -> derive from curve
        assert r.final_value == pytest.approx(112_000.0)
        assert r.total_return == pytest.approx(0.12)

    def test_total_return_derived_from_curve(self):
        fake = _make_akquant_fake()
        fake.metrics = _MetricsWrapper(type("M", (), {})())
        r = self._parse(fake)
        # (112000-100000)/100000
        assert r.total_return == pytest.approx(0.12)

    def test_derived_total_return_from_end_market_value(self):
        fake = _make_akquant_fake()
        fake.equity_curve = pd.Series(dtype=float)  # empty curve
        raw = _RawMetrics()
        raw.total_return = 0.0  # engine treats 0.0 as missing sentinel
        fake.metrics = _MetricsWrapper(raw)
        r = self._parse(fake)
        assert r.total_return == pytest.approx(0.12)

    def test_flat_object_fallback(self):
        """Simple flat fakes (old-style) still work."""
        fake = _make_akquant_fake()
        fake.metrics = None
        fake.trade_metrics = None
        fake.trades_df = None
        fake.equity_curve = None
        # no metrics object: fields stay None, no crash
        r = self._parse(fake)
        assert r.final_value is None
        assert r.total_trades == 0
        assert r.equity_curve == []

    def test_naive_datetime_index_tolerated(self):
        fake = _make_akquant_fake()
        fake.equity_curve = pd.Series(
            [100_000.0, 105_000.0],
            index=pd.to_datetime(["2026-02-01", "2026-02-02"]),
        )
        r = self._parse(fake)
        assert r.equity_curve[0] == {"date": "2026-02-01", "value": 100_000.0}


# ---------------------------------------------------------------------------
# Strategy adapter tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAgentDecisionStrategy(unittest.TestCase):
    """Test the Agent decision → strategy adapter."""

    def test_buy_decision(self):
        s = AgentDecisionStrategy(decision="BUY", ticker="600519", holding_days=5)
        assert s.decision == "BUY"
        assert s.ticker == "600519"
        assert s.holding_days == 5

    def test_sell_decision(self):
        s = AgentDecisionStrategy(decision="SELL", ticker="NVDA")
        assert s.decision == "SELL"

    def test_hold_decision(self):
        s = AgentDecisionStrategy(decision="HOLD")
        assert s.decision == "HOLD"

    def test_case_insensitive(self):
        s = AgentDecisionStrategy(decision="buy")
        assert s.decision == "BUY"


# ---------------------------------------------------------------------------
# Engine tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBacktestEngineDecisionParsing(unittest.TestCase):
    """Test decision text parsing without akquant."""

    def test_parse_buy_chinese(self):
        assert BacktestEngine._parse_decision("建议买入，目标价50") == "BUY"

    def test_parse_buy_english(self):
        assert BacktestEngine._parse_decision("BUY signal confirmed") == "BUY"

    def test_parse_sell_chinese(self):
        assert BacktestEngine._parse_decision("建议卖出，止损45") == "SELL"

    def test_parse_sell_english(self):
        assert BacktestEngine._parse_decision("SELL recommendation") == "SELL"

    def test_parse_hold(self):
        assert BacktestEngine._parse_decision("建议持有观望") == "HOLD"

    def test_parse_bullish(self):
        assert BacktestEngine._parse_decision("BULLISH outlook") == "BUY"

    def test_parse_bearish(self):
        assert BacktestEngine._parse_decision("BEARISH, consider shorting") == "SELL"

    def test_parse_empty(self):
        assert BacktestEngine._parse_decision("") == "HOLD"


@pytest.mark.unit
class TestBacktestEngineRunFromDecision(unittest.TestCase):
    """Test run_from_decision with HOLD (no akquant needed)."""

    def test_hold_returns_zero(self):
        engine = BacktestEngine()
        result = engine.run_from_decision(
            final_state={"final_trade_decision": "建议持有", "trade_date": "2026-01-10"},
            ticker="600519",
        )
        assert result.decision == "HOLD"
        assert result.total_return == 0.0
        assert result.total_trades == 0


# ---------------------------------------------------------------------------
# BacktestResult tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBacktestResult(unittest.TestCase):

    def test_summary_basic(self):
        r = BacktestResult(ticker="600519", decision="BUY", total_return=0.05)
        s = r.summary()
        assert "600519" in s
        assert "BUY" in s
        assert "+5.00%" in s

    def test_to_dict(self):
        r = BacktestResult(ticker="NVDA", decision="SELL", total_return=-0.03)
        d = r.to_dict()
        assert d["ticker"] == "NVDA"
        assert d["decision"] == "SELL"
        assert d["total_return"] == -0.03


# ---------------------------------------------------------------------------
# Report tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestBacktestReport(unittest.TestCase):

    def test_generate_report(self):
        r = BacktestResult(
            ticker="600519", decision="BUY", total_return=0.08,
            sharpe_ratio=1.5, max_drawdown=-0.05, total_trades=1,
            profit_trades=1, loss_trades=0, win_rate=1.0,
        )
        report = generate_backtest_report(r)
        assert "# Backtest Report: 600519" in report
        assert "+8.00%" in report
        assert "Sharpe Ratio" in report

    def test_generate_report_hold(self):
        r = BacktestResult(ticker="NVDA", decision="HOLD")
        report = generate_backtest_report(r)
        assert "HOLD" in report
        assert "no position" in report


# ---------------------------------------------------------------------------
# create_strategy_class tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreateStrategyClass(unittest.TestCase):
    """Test the strategy factory (requires akquant)."""

    def _akquant_available(self):
        try:
            import akquant
            return True
        except ImportError:
            return False

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("akquant"),
        reason="akquant not installed"
    )
    def test_factory_returns_class(self):
        cls = create_strategy_class("BUY", "600519", holding_days=3)
        assert isinstance(cls, type)
        assert cls.__name__ == "AgentStrategy_BUY_600519"

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("akquant"),
        reason="akquant not installed"
    )
    def test_factory_sell(self):
        cls = create_strategy_class("SELL", "NVDA")
        assert "SELL" in cls.__name__


if __name__ == "__main__":
    unittest.main()
