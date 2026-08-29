"""Data models for the Signal Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalType(Enum):
    """Trade signal direction."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class SignalStrength(Enum):
    """Signal strength levels."""

    STRONG = "strong"    # > 75
    MODERATE = "moderate"  # 50-75
    WEAK = "weak"        # 25-50
    NEUTRAL = "neutral"  # < 25


@dataclass
class Signal:
    """A single technical signal from an indicator."""

    type: SignalType
    strength: float  # 0-100
    indicator: str   # Which indicator produced this
    reason: str      # Human-readable explanation
    timestamp: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompositeSignal:
    """Aggregated signal from multiple indicators."""

    ticker: str
    timeframe: str
    signals: list[Signal]
    composite_score: float  # 0-100 (weighted average)
    recommendation: str     # "BUY" | "SELL" | "HOLD"
    confidence: float       # 0-100 (agreement between indicators)
    indicator_scores: dict[str, float] = field(default_factory=dict)
    timestamp: float | None = None


class TradeAction(Enum):
    """Action to take in a strategy."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


@dataclass
class Strategy:
    """A trading strategy definition."""

    name: str
    description: str
    params: dict[str, Any] = field(default_factory=dict)
    indicators: list[str] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StrategyResult:
    """Result of running a strategy on historical data."""

    strategy_name: str
    ticker: str
    timeframe: str
    total_return: float  # Percentage
    sharpe_ratio: float
    max_drawdown: float  # Percentage
    win_rate: float      # Percentage
    total_trades: int
    trades: list[dict[str, Any]] = field(default_factory=list)


class AlertCondition(Enum):
    """Types of alert conditions."""

    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    INDICATOR_ABOVE = "indicator_above"
    INDICATOR_BELOW = "indicator_below"
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"
    VOLUME_ABOVE = "volume_above"


@dataclass
class Alert:
    """A price/indicator alert."""

    id: str
    ticker: str
    condition: AlertCondition
    threshold: float
    indicator: str | None = None
    message: str = ""
    triggered: bool = False
    created_at: float = 0.0
    triggered_at: float | None = None
