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
