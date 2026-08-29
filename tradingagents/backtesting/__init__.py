"""Backtesting module — wraps akquant's Rust-core engine.

Optional dependency: ``pip install "tradingagents[backtest]"`` or
``pip install akquant``.

Usage::

    from tradingagents.backtesting import BacktestEngine

    engine = BacktestEngine(config)
    result = engine.run_from_decision(final_state, ticker="600519")
    print(result.summary())
"""

from .engine import BacktestEngine
from .strategy import AgentDecisionStrategy

__all__ = ["BacktestEngine", "AgentDecisionStrategy"]
