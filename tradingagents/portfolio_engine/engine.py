"""PortfolioEngine — position tracking, order management, performance analysis.

This is the deep module's main class. It provides four methods:

1. execute_trade() — buy/sell with position tracking
2. get_positions() — portfolio summary with P&L
3. get_performance() — detailed performance metrics
4. get_history() — trade history
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import numpy as np

from tradingagents.data_center import DataCenter

from .models import (
    PerformanceResult,
    PortfolioSummary,
    Position,
    TradeAction,
    TradeRecord,
)


class PortfolioEngine:
    """Portfolio Engine — deep module with small interface.

    Interface (4 methods)::

        engine = PortfolioEngine(initial_capital=1_000_000)
        engine.execute_trade("600519", "buy", 100, 1800.0, "技术突破")
        summary = engine.get_positions()
        perf = engine.get_performance(benchmark="000300")
        history = engine.get_history()

    Implementation hides: position tracking, P&L calculation, risk metrics,
    and trade history management.
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000,
        commission_rate: float = 0.0003,  # 0.03% commission
        min_commission: float = 5.0,  # Minimum commission
    ) -> None:
        self._initial_capital = initial_capital
        self._cash = initial_capital
        self._positions: dict[str, dict] = {}
        self._trades: list[TradeRecord] = []
        self._nav_history: list[dict[str, Any]] = []
        self._commission_rate = commission_rate
        self._min_commission = min_commission

    # ── Public interface ──────────────────────────────────────────────────

    def execute_trade(
        self,
        ticker: str,
        side: str,  # "buy" | "sell"
        quantity: int,
        price: float,
        name: str = "",
        reason: str = "",
    ) -> TradeRecord:
        """Execute a trade and update positions.

        Args:
            ticker: Stock ticker.
            side: "buy" or "sell".
            quantity: Number of shares.
            price: Trade price.
            name: Stock name (optional).
            reason: Trade reason (optional).

        Returns:
            TradeRecord with trade details.

        Raises:
            ValueError: If invalid trade (insufficient cash/position).
        """
        side = side.lower()
        if side not in ("buy", "sell"):
            raise ValueError(f"Invalid side: {side}. Must be 'buy' or 'sell'")

        if quantity <= 0:
            raise ValueError(f"Invalid quantity: {quantity}")

        amount = quantity * price
        commission = max(amount * self._commission_rate, self._min_commission)

        if side == "buy":
            total_cost = amount + commission
            if total_cost > self._cash:
                raise ValueError(
                    f"Insufficient cash: need {total_cost:.2f}, have {self._cash:.2f}"
                )
            self._cash -= total_cost
            self._update_position_buy(ticker, name, quantity, price)

        else:  # sell
            pos = self._positions.get(ticker)
            if not pos or pos["quantity"] < quantity:
                available = pos["quantity"] if pos else 0
                raise ValueError(
                    f"Insufficient position: need {quantity}, have {available}"
                )
            self._cash += amount - commission
            self._update_position_sell(ticker, quantity, price)

        trade = TradeRecord(
            id=uuid.uuid4().hex[:8],
            ticker=ticker,
            name=name or ticker,
            side=side,
            quantity=quantity,
            price=price,
            amount=amount,
            commission=commission,
            timestamp=datetime.now(),
            reason=reason,
        )
        self._trades.append(trade)

        # Record NAV
        self._record_nav()

        return trade

    def get_positions(
        self,
        current_prices: dict[str, float] | None = None,
    ) -> PortfolioSummary:
        """Get portfolio summary with current positions.

        Args:
            current_prices: Optional dict of ticker → current price.
                           If not provided, uses last trade price.

        Returns:
            PortfolioSummary with positions and metrics.
        """
        positions: list[Position] = []
        total_market_value = 0.0

        for ticker, pos in self._positions.items():
            current_price = (current_prices or {}).get(ticker, pos["current_price"])
            market_value = pos["quantity"] * current_price
            avg_cost = pos["avg_cost"]
            unrealized_pnl = (current_price - avg_cost) * pos["quantity"]
            unrealized_pnl_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0

            total_market_value += market_value

            positions.append(Position(
                ticker=ticker,
                name=pos.get("name", ticker),
                quantity=pos["quantity"],
                avg_cost=avg_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
                weight=0,  # Calculated below
            ))

        # Calculate weights
        total_value = self._cash + total_market_value
        for pos in positions:
            pos.weight = (pos.market_value / total_value * 100) if total_value > 0 else 0
            pos.weight = round(pos.weight, 2)

        # Calculate P&L
        total_pnl = total_value - self._initial_capital
        total_pnl_pct = (total_pnl / self._initial_capital * 100) if self._initial_capital > 0 else 0

        # Today's P&L (simplified: use last trade as reference)
        today_pnl = 0.0
        today_pnl_pct = 0.0
        if self._nav_history and len(self._nav_history) >= 2:
            today_pnl = self._nav_history[-1]["nav"] - self._nav_history[-2]["nav"]
            today_pnl_pct = (today_pnl / self._nav_history[-2]["nav"] * 100) if self._nav_history[-2]["nav"] > 0 else 0

        return PortfolioSummary(
            total_value=round(total_value, 2),
            cash=round(self._cash, 2),
            market_value=round(total_market_value, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_pct=round(total_pnl_pct, 2),
            today_pnl=round(today_pnl, 2),
            today_pnl_pct=round(today_pnl_pct, 2),
            positions=positions,
        )

    def get_performance(
        self,
        benchmark: str = "000300",
        benchmark_return: float | None = None,
    ) -> PerformanceResult:
        """Get detailed performance analysis.

        Args:
            benchmark: Benchmark ticker (e.g., "000300" for CSI 300).
            benchmark_return: Optional benchmark return % (if not fetching).

        Returns:
            PerformanceResult with comprehensive metrics.
        """
        if not self._trades:
            return PerformanceResult(
                total_return=0,
                annual_return=0,
                sharpe_ratio=0,
                max_drawdown=0,
                win_rate=0,
                profit_factor=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win=0,
                avg_loss=0,
                best_trade=0,
                worst_trade=0,
            )

        # Calculate returns from NAV history
        nav_values = [h["nav"] for h in self._nav_history] if self._nav_history else [self._initial_capital]

        total_return = ((nav_values[-1] - nav_values[0]) / nav_values[0] * 100) if nav_values[0] > 0 else 0

        # Annualized return (assume 252 trading days)
        n_days = len(nav_values)
        annual_return = ((1 + total_return / 100) ** (252 / max(n_days, 1)) - 1) * 100

        # Sharpe ratio
        if len(nav_values) > 1:
            returns = np.diff(nav_values) / nav_values[:-1]
            sharpe = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252)
        else:
            sharpe = 0.0

        # Max drawdown
        peak = nav_values[0]
        max_dd = 0.0
        for nav in nav_values:
            if nav > peak:
                peak = nav
            dd = (peak - nav) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # Trade analysis
        buy_trades = [t for t in self._trades if t.side == "buy"]
        sell_trades = [t for t in self._trades if t.side == "sell"]

        # Match buy/sell pairs
        trade_returns: list[float] = []
        buy_map: dict[str, list[TradeRecord]] = {}
        for t in buy_trades:
            buy_map.setdefault(t.ticker, []).append(t)

        for sell in sell_trades:
            buys = buy_map.get(sell.ticker, [])
            if buys:
                buy = buys[-1]
                ret = (sell.price - buy.price) / buy.price * 100
                trade_returns.append(ret)
                buys.pop()

        winning = [r for r in trade_returns if r > 0]
        losing = [r for r in trade_returns if r <= 0]

        total_trades = len(trade_returns)
        win_rate = (len(winning) / total_trades * 100) if total_trades > 0 else 0

        avg_win = np.mean(winning) if winning else 0
        avg_loss = np.mean(losing) if losing else 0

        # Profit factor
        total_win = sum(winning) if winning else 0
        total_loss = abs(sum(losing)) if losing else 0
        profit_factor = (total_win / total_loss) if total_loss > 0 else float("inf") if total_win > 0 else 0

        best_trade = max(trade_returns) if trade_returns else 0
        worst_trade = min(trade_returns) if trade_returns else 0

        # Benchmark comparison
        bm_return = benchmark_return if benchmark_return is not None else 0.0
        alpha = total_return - bm_return

        return PerformanceResult(
            total_return=round(total_return, 2),
            annual_return=round(annual_return, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown=round(max_dd, 2),
            win_rate=round(win_rate, 2),
            profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
            total_trades=total_trades,
            winning_trades=len(winning),
            losing_trades=len(losing),
            avg_win=round(float(avg_win), 2),
            avg_loss=round(float(avg_loss), 2),
            best_trade=round(best_trade, 2),
            worst_trade=round(worst_trade, 2),
            benchmark_return=round(bm_return, 2),
            alpha=round(alpha, 2),
            trades=self._trades,
        )

    def get_history(self) -> list[TradeRecord]:
        """Get complete trade history."""
        return list(self._trades)

    def restore(
        self,
        cash: float,
        positions: dict[str, dict],
        trades: list[TradeRecord],
    ) -> None:
        """Restore engine state from a persisted snapshot.

        Args:
            cash: Current cash balance.
            positions: {ticker: {"name", "quantity", "avg_cost", "current_price"}}.
            trades: Previously executed trade records (chronological order).
        """
        self.reset()
        self._cash = cash
        for ticker, pos in positions.items():
            self._positions[ticker] = {
                "name": pos.get("name", ticker),
                "quantity": pos["quantity"],
                "avg_cost": pos["avg_cost"],
                "current_price": pos["current_price"] if pos.get("current_price") is not None else pos["avg_cost"],
            }
        self._trades = list(trades)

    def reset(self) -> None:
        """Reset portfolio to initial state."""
        self._cash = self._initial_capital
        self._positions.clear()
        self._trades.clear()
        self._nav_history.clear()

    # ── Private helpers ───────────────────────────────────────────────────

    def _update_position_buy(
        self, ticker: str, name: str, quantity: int, price: float
    ) -> None:
        """Update position after a buy trade."""
        pos = self._positions.get(ticker)
        if pos:
            # Average up/down
            total_cost = pos["avg_cost"] * pos["quantity"] + price * quantity
            total_qty = pos["quantity"] + quantity
            pos["avg_cost"] = total_cost / total_qty
            pos["quantity"] = total_qty
            pos["current_price"] = price
        else:
            self._positions[ticker] = {
                "name": name or ticker,
                "quantity": quantity,
                "avg_cost": price,
                "current_price": price,
            }

    def _update_position_sell(
        self, ticker: str, quantity: int, price: float
    ) -> None:
        """Update position after a sell trade."""
        pos = self._positions[ticker]
        pos["quantity"] -= quantity
        pos["current_price"] = price
        if pos["quantity"] == 0:
            del self._positions[ticker]

    def _record_nav(self) -> None:
        """Record current NAV to history."""
        market_value = sum(
            pos["quantity"] * pos["current_price"]
            for pos in self._positions.values()
        )
        nav = self._cash + market_value
        self._nav_history.append({
            "timestamp": datetime.now(),
            "nav": nav,
            "cash": self._cash,
            "market_value": market_value,
        })
