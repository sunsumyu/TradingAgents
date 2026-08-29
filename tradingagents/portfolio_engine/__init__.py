"""Portfolio Engine — position tracking, order management, performance analysis.

Deep module: small interface (4 methods), large implementation
(position tracking, P&L calculation, risk metrics, benchmark comparison).

Usage::

    from tradingagents.portfolio_engine import PortfolioEngine

    engine = PortfolioEngine(initial_capital=1_000_000)
    engine.execute_trade("600519", "buy", 100, 1800.0, "技术突破")
    summary = engine.get_positions()
    perf = engine.get_performance(benchmark="000300")
"""

from .models import (
    Position,
    TradeRecord,
    PortfolioSummary,
    PerformanceResult,
    TradeAction,
)
from .engine import PortfolioEngine

__all__ = [
    "Position",
    "TradeRecord",
    "PortfolioSummary",
    "PerformanceResult",
    "TradeAction",
    "PortfolioEngine",
]
