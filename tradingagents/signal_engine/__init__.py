"""Signal Engine — technical analysis, strategy execution, and alerts.

Deep module: small interface (3 methods), large implementation
(multi-indicator signal fusion, strategy backtesting, price/indicator alerts).

Usage::

    from tradingagents.signal_engine import SignalEngine

    engine = SignalEngine()
    result = engine.compute_signals("600519", "1D", ["MACD", "RSI", "KDJ"])
    print(result.composite_score)  # 0-100
    print(result.recommendation)   # "BUY" | "SELL" | "HOLD"
"""

from .models import (
    Signal,
    SignalType,
    SignalStrength,
    CompositeSignal,
    Strategy,
    StrategyResult,
    TradeAction,
    Alert,
    AlertCondition,
)
from .engine import SignalEngine

__all__ = [
    "Signal",
    "SignalType",
    "SignalStrength",
    "CompositeSignal",
    "Strategy",
    "StrategyResult",
    "TradeAction",
    "Alert",
    "AlertCondition",
    "SignalEngine",
]
