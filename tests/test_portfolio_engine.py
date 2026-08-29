"""Tests for PortfolioEngine — Phase 5 of TDX-style platform."""

import pytest
import numpy as np
from tradingagents.portfolio_engine import (
    PortfolioEngine,
    Position,
    TradeRecord,
    PortfolioSummary,
    PerformanceResult,
    TradeAction,
)


class TestExecuteTrade:
    def test_buy_stock(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        trade = engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台", "技术突破")

        assert trade.ticker == "600519"
        assert trade.side == "buy"
        assert trade.quantity == 100
        assert trade.price == 1800.0
        assert trade.amount == 180_000.0
        assert trade.commission > 0
        assert engine._cash < 1_000_000

    def test_sell_stock(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        trade = engine.execute_trade("600519", "sell", 50, 1850.0, "贵州茅台", "获利了结")

        assert trade.side == "sell"
        assert trade.quantity == 50
        assert engine._positions["600519"]["quantity"] == 50

    def test_sell_all_position(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        engine.execute_trade("600519", "sell", 100, 1850.0)

        assert "600519" not in engine._positions
        assert len(engine._trades) == 2

    def test_insufficient_cash(self):
        engine = PortfolioEngine(initial_capital=10_000)
        with pytest.raises(ValueError, match="Insufficient cash"):
            engine.execute_trade("600519", "buy", 100, 1800.0)

    def test_insufficient_position(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        with pytest.raises(ValueError, match="Insufficient position"):
            engine.execute_trade("600519", "sell", 100, 1800.0)

    def test_invalid_side(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        with pytest.raises(ValueError, match="Invalid side"):
            engine.execute_trade("600519", "short", 100, 1800.0)

    def test_invalid_quantity(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        with pytest.raises(ValueError, match="Invalid quantity"):
            engine.execute_trade("600519", "buy", -10, 1800.0)

    def test_commission_deduction(self):
        engine = PortfolioEngine(initial_capital=1_000_000, commission_rate=0.001)
        trade = engine.execute_trade("600519", "buy", 100, 1800.0)

        expected_commission = max(180_000 * 0.001, 5.0)
        assert trade.commission == pytest.approx(expected_commission, rel=1e-3)
        assert engine._cash == pytest.approx(1_000_000 - 180_000 - expected_commission, rel=1e-3)

    def test_min_commission(self):
        engine = PortfolioEngine(initial_capital=1_000_000, commission_rate=0.0001)
        trade = engine.execute_trade("600519", "buy", 1, 10.0)

        assert trade.commission == 5.0  # Minimum commission

    def test_multiple_buys_average_cost(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        engine.execute_trade("600519", "buy", 100, 1900.0, "贵州茅台")

        pos = engine._positions["600519"]
        assert pos["quantity"] == 200
        assert pos["avg_cost"] == pytest.approx(1850.0, rel=1e-3)


class TestGetPositions:
    def test_empty_portfolio(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        summary = engine.get_positions()

        assert summary.total_value == 1_000_000
        assert summary.cash == 1_000_000
        assert summary.market_value == 0
        assert len(summary.positions) == 0

    def test_with_positions(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")

        summary = engine.get_positions(current_prices={"600519": 1850.0})

        assert len(summary.positions) == 1
        pos = summary.positions[0]
        assert pos.ticker == "600519"
        assert pos.quantity == 100
        assert pos.current_price == 1850.0
        assert pos.market_value == 185_000.0
        assert pos.unrealized_pnl > 0

    def test_pnl_calculation(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")

        summary = engine.get_positions(current_prices={"600519": 2000.0})

        assert summary.total_pnl > 0
        assert summary.total_pnl_pct > 0

    def test_weight_calculation(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        engine.execute_trade("000858", "buy", 200, 150.0, "五粮液")

        summary = engine.get_positions(current_prices={
            "600519": 1800.0,
            "000858": 150.0,
        })

        # Weights are % of total portfolio value (including cash)
        # 600519: ~180k / 1M = ~18%, 000858: ~30k / 1M = ~3%
        total_weight = sum(p.weight for p in summary.positions)
        assert total_weight < 100  # Cash makes up the rest
        assert total_weight > 0
        # 600519 has more weight
        assert summary.positions[0].weight > summary.positions[1].weight

    def test_unrealized_pnl_pct(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 100.0, "贵州茅台")

        summary = engine.get_positions(current_prices={"600519": 110.0})
        assert summary.positions[0].unrealized_pnl_pct == pytest.approx(10.0, rel=1e-1)


class TestGetPerformance:
    def test_no_trades(self):
        engine = PortfolioEngine()
        perf = engine.get_performance()
        assert perf.total_return == 0
        assert perf.total_trades == 0

    def test_with_trades(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        engine.execute_trade("600519", "sell", 100, 1900.0, "贵州茅台", "获利了结")

        perf = engine.get_performance()

        assert perf.total_trades >= 1
        assert perf.winning_trades >= 0
        assert perf.win_rate >= 0

    def test_max_drawdown(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        engine.execute_trade("600519", "sell", 100, 1700.0, "贵州茅台")  # Loss
        engine.execute_trade("600519", "buy", 100, 1700.0, "贵州茅台")
        engine.execute_trade("600519", "sell", 100, 1800.0, "贵州茅台")  # Recovery

        perf = engine.get_performance()
        assert perf.max_drawdown >= 0

    def test_sharpe_ratio(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        # Create some trades to generate NAV history
        for i in range(5):
            engine.execute_trade("600519", "buy", 10, 1800 + i * 10, "贵州茅台")
            engine.execute_trade("600519", "sell", 10, 1810 + i * 10, "贵州茅台")

        perf = engine.get_performance()
        assert isinstance(perf.sharpe_ratio, float)

    def test_profit_factor(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        engine.execute_trade("600519", "sell", 100, 1900.0, "贵州茅台")

        perf = engine.get_performance()
        assert perf.profit_factor > 0

    def test_benchmark_comparison(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        engine.execute_trade("600519", "sell", 100, 1900.0, "贵州茅台")

        perf = engine.get_performance(benchmark_return=5.0)
        assert perf.benchmark_return == 5.0
        assert perf.alpha != 0


class TestGetHistory:
    def test_empty_history(self):
        engine = PortfolioEngine()
        history = engine.get_history()
        assert len(history) == 0

    def test_trade_history(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        engine.execute_trade("000858", "buy", 200, 150.0, "五粮液")

        history = engine.get_history()
        assert len(history) == 2
        assert history[0].ticker == "600519"
        assert history[1].ticker == "000858"

    def test_history_is_copy(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")

        history = engine.get_history()
        history.clear()  # Modify the returned list

        assert len(engine.get_history()) == 1  # Original unchanged


class TestReset:
    def test_reset(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")
        engine.reset()

        assert engine._cash == 1_000_000
        assert len(engine._positions) == 0
        assert len(engine._trades) == 0
        assert len(engine._nav_history) == 0


class TestTradeRecord:
    def test_trade_record_fields(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        trade = engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台", "技术突破")

        assert trade.id is not None
        assert len(trade.id) == 8
        assert trade.timestamp is not None
        assert trade.reason == "技术突破"

    def test_trade_to_dict(self):
        engine = PortfolioEngine(initial_capital=1_000_000)
        trade = engine.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台")

        d = trade.to_dict()
        assert d["ticker"] == "600519"
        assert d["side"] == "buy"
        assert "timestamp" in d


class TestPositionModel:
    def test_position_to_dict(self):
        pos = Position(
            ticker="600519",
            name="贵州茅台",
            quantity=100,
            avg_cost=1800.0,
            current_price=1850.0,
            market_value=185_000.0,
            unrealized_pnl=5_000.0,
            unrealized_pnl_pct=2.78,
            weight=18.5,
        )
        d = pos.to_dict()
        assert d["ticker"] == "600519"
        assert d["weight"] == 18.5


class TestRestore:
    """PortfolioEngine.restore — rebuild state from a persisted snapshot."""

    def test_restore_roundtrip(self):
        source = PortfolioEngine(initial_capital=1_000_000)
        source.execute_trade("600519", "buy", 100, 1800.0, "贵州茅台", "测试")
        source.execute_trade("000858", "buy", 200, 150.0, "五粮液")
        source.execute_trade("000858", "sell", 50, 160.0)

        restored = PortfolioEngine(initial_capital=1_000_000)
        restored.restore(
            cash=source._cash,
            positions={t: dict(p) for t, p in source._positions.items()},
            trades=list(source._trades),
        )

        assert restored._cash == source._cash
        assert set(restored._positions) == set(source._positions)
        assert restored._positions["600519"]["quantity"] == 100
        assert restored._positions["600519"]["avg_cost"] == 1800.0
        assert restored._positions["000858"]["quantity"] == 150
        assert len(restored.get_history()) == 3

    def test_restore_enables_performance(self):
        source = PortfolioEngine(initial_capital=1_000_000)
        source.execute_trade("600519", "buy", 100, 1800.0)
        source.execute_trade("600519", "sell", 100, 1900.0)

        restored = PortfolioEngine(initial_capital=1_000_000)
        restored.restore(
            cash=source._cash,
            positions={},
            trades=list(source.get_history()),
        )
        perf = restored.get_performance()
        assert perf.total_trades == 1
        assert perf.winning_trades == 1

    def test_restore_empty(self):
        engine = PortfolioEngine(initial_capital=500_000)
        engine.restore(cash=500_000, positions={}, trades=[])
        summary = engine.get_positions()
        assert summary.cash == 500_000
        assert summary.positions == []
