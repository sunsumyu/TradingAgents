"""Data models for the Portfolio Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TradeAction(Enum):
    """Trade action type."""

    BUY = "buy"
    SELL = "sell"


@dataclass
class Position:
    """A stock position in the portfolio."""

    ticker: str
    name: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight: float  # Position weight in portfolio

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "weight": self.weight,
        }


@dataclass
class TradeRecord:
    """A completed trade record."""

    id: str
    ticker: str
    name: str
    side: str  # "buy" | "sell"
    quantity: int
    price: float
    amount: float
    commission: float
    timestamp: datetime
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "name": self.name,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "amount": self.amount,
            "commission": self.commission,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
        }


@dataclass
class PortfolioSummary:
    """Portfolio summary with key metrics."""

    total_value: float
    cash: float
    market_value: float
    total_pnl: float
    total_pnl_pct: float
    today_pnl: float
    today_pnl_pct: float
    positions: list[Position]
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_value": self.total_value,
            "cash": self.cash,
            "market_value": self.market_value,
            "total_pnl": self.total_pnl,
            "total_pnl_pct": self.total_pnl_pct,
            "today_pnl": self.today_pnl,
            "today_pnl_pct": self.today_pnl_pct,
            "positions": [p.to_dict() for p in self.positions],
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
        }


@dataclass
class PerformanceResult:
    """Detailed performance analysis."""

    total_return: float  # Percentage
    annual_return: float  # Percentage
    sharpe_ratio: float
    max_drawdown: float  # Percentage
    win_rate: float  # Percentage
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float  # Average winning trade %
    avg_loss: float  # Average losing trade %
    best_trade: float  # Best single trade %
    worst_trade: float  # Worst single trade %
    benchmark_return: float = 0.0  # Benchmark return %
    alpha: float = 0.0  # Alpha vs benchmark
    beta: float = 0.0  # Beta vs benchmark
    trades: list[TradeRecord] = field(default_factory=list)
