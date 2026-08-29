"""Tests for simulated portfolio (Phase 6, ticket 6.04).

Tests CRUD operations, P&L calculation, and edge cases.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tradingagents_api.portfolio import (
    PortfolioSnapshot,
    execute_trade,
    get_nav_history,
    get_portfolio,
    get_trade_history,
    reset_portfolio,
)


@pytest.fixture(autouse=True)
def isolated_portfolio(tmp_path):
    """Redirect portfolio storage to a temp directory for test isolation."""
    fake_file = tmp_path / "portfolio.json"
    with patch("tradingagents_api.portfolio.PORTFOLIO_FILE", fake_file):
        # Reset to clean state before each test
        reset_portfolio(1_000_000.0)
        yield


class TestGetPortfolio:
    def test_empty_portfolio(self):
        p = get_portfolio()
        assert p.positions == []
        assert p.cash == 1_000_000.0
        assert p.total_value == 1_000_000.0
        assert p.total_pnl == 0.0

    def test_initial_cash_default(self):
        p = get_portfolio()
        assert p.cash == 1_000_000.0


class TestBuyTrade:
    def test_buy_creates_position(self):
        p = execute_trade("600519", "buy", 100, 1500.0, name="贵州茅台")
        assert len(p.positions) == 1
        assert p.positions[0].ticker == "600519"
        assert p.positions[0].quantity == 100
        assert p.positions[0].avg_cost == 1500.0
        assert p.cash == 850_000.0

    def test_buy_multiple_same_ticker_averages_cost(self):
        execute_trade("600519", "buy", 100, 1500.0)
        p = execute_trade("600519", "buy", 100, 1600.0)
        assert len(p.positions) == 1
        assert p.positions[0].quantity == 200
        assert p.positions[0].avg_cost == 1550.0

    def test_buy_different_tickers(self):
        execute_trade("600519", "buy", 100, 1500.0)
        p = execute_trade("000858", "buy", 200, 160.0)
        assert len(p.positions) == 2
        assert p.cash == 1_000_000 - 150_000 - 32_000

    def test_buy_insufficient_cash(self):
        with pytest.raises(ValueError, match="现金不足"):
            execute_trade("600519", "buy", 1000, 1500.0)  # needs 1.5M, only has 1M


class TestSellTrade:
    def test_sell_reduces_position(self):
        execute_trade("600519", "buy", 100, 1500.0)
        p = execute_trade("600519", "sell", 50, 1550.0)
        assert p.positions[0].quantity == 50
        assert p.cash == 850_000 + 50 * 1550.0

    def test_sell_all_removes_position(self):
        execute_trade("600519", "buy", 100, 1500.0)  # cost 150000
        p = execute_trade("600519", "sell", 100, 1550.0)  # revenue 155000
        assert len(p.positions) == 0
        # cash = 1M - 150K (buy) + 155K (sell) = 1,005,000
        assert p.cash == 1_005_000.0

    def test_sell_insufficient_shares(self):
        execute_trade("600519", "buy", 100, 1500.0)
        with pytest.raises(ValueError, match="持仓不足"):
            execute_trade("600519", "sell", 200, 1550.0)

    def test_sell_nonexistent_ticker(self):
        with pytest.raises(ValueError, match="持仓不足"):
            execute_trade("600519", "sell", 100, 1550.0)


class TestPnL:
    def test_pnl_after_buy(self):
        p = execute_trade("600519", "buy", 100, 1500.0)
        # No current_price set, so P&L uses avg_cost → 0
        assert p.total_pnl == 0.0

    def test_total_value_calculation(self):
        execute_trade("600519", "buy", 100, 1500.0)
        p = get_portfolio()
        assert p.total_value == p.cash + 100 * 1500.0


class TestTradeHistory:
    def test_history_records_trades(self):
        execute_trade("600519", "buy", 100, 1500.0)
        execute_trade("000858", "buy", 200, 160.0)
        history = get_trade_history()
        assert len(history) == 2
        # Newest first
        assert history[0].ticker == "000858"
        assert history[1].ticker == "600519"

    def test_history_includes_reason(self):
        execute_trade("600519", "buy", 100, 1500.0, reason="AI信号")
        history = get_trade_history()
        assert history[0].reason == "AI信号"


class TestNavHistory:
    def test_nav_records_snapshots(self):
        execute_trade("600519", "buy", 100, 1500.0)
        nav = get_nav_history()
        assert len(nav) == 1
        assert nav[0]["nav"] == 1_000_000.0


class TestReset:
    def test_reset_clears_everything(self):
        execute_trade("600519", "buy", 100, 1500.0)
        p = reset_portfolio(500_000.0)
        assert p.positions == []
        assert p.cash == 500_000.0
        assert get_trade_history() == []
        assert get_nav_history() == []


class TestInvalidInput:
    def test_unknown_action(self):
        with pytest.raises(ValueError, match="未知操作"):
            execute_trade("600519", "hold", 100, 1500.0)
