"""Backtest API endpoints.

Provides ``POST /api/backtest`` for running backtests from trade decisions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

INSTALL_HINT = (
    "pip install akquant  or  pip install 'tradingagents[backtest]'"
)


def _load_engine():
    """Import and return the BacktestEngine class (lazily, for testability)."""
    from tradingagents.backtesting.engine import BacktestEngine

    return BacktestEngine


def _create_strategy(decision: str, ticker: str, holding_days: int):
    """Import and call the strategy factory (lazily, for testability)."""
    from tradingagents.backtesting.strategy import create_strategy_class

    return create_strategy_class(
        decision=decision,
        ticker=ticker,
        holding_days=holding_days,
    )


class EquityPoint(BaseModel):
    """One point on the equity curve."""

    date: str
    value: float


class BacktestRequest(BaseModel):
    """Request body for /api/backtest."""

    ticker: str = Field(..., description="Stock code, e.g. 600519")
    start_date: str = Field(..., description="Start date YYYY-MM-DD")
    end_date: str = Field(..., description="End date YYYY-MM-DD")
    decision: str = Field("HOLD", description="Trade decision: BUY, SELL, or HOLD")
    holding_days: int = Field(5, description="Number of days to hold position")
    initial_cash: float = Field(100_000.0, description="Starting capital")


class BacktestResponse(BaseModel):
    """Response from /api/backtest."""

    ticker: str
    decision: str
    total_return: float | None = None
    annual_return: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    total_trades: int = 0
    profit_trades: int = 0
    loss_trades: int = 0
    initial_cash: float = 100_000.0
    final_value: float | None = None
    holding_days: int = 5
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    report_path: str | None = None
    report_markdown: str | None = None


@router.post("/api/backtest", response_model=BacktestResponse)
async def run_backtest(request: BacktestRequest):
    """Run a backtest from a trade decision.

    Uses akquant's Rust-core engine for high-performance backtesting.
    Requires akquant to be installed: ``pip install akquant``.
    """
    try:
        engine_cls = _load_engine()
        from tradingagents.backtesting.report import generate_backtest_report
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Backtesting engine not available: {e}. Install with: {INSTALL_HINT}",
        )

    engine = engine_cls()

    # Build a strategy class from the decision (imports akquant eagerly,
    # so an ImportError here must also surface as 503, not a bare 500)
    try:
        strategy_class = _create_strategy(
            decision=request.decision,
            ticker=request.ticker,
            holding_days=request.holding_days,
        )
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Backtesting engine not available: {e}. Install with: {INSTALL_HINT}",
        )

    try:
        result = engine.run(
            ticker=request.ticker,
            start_date=request.start_date,
            end_date=request.end_date,
            strategy_class=strategy_class,
            initial_cash=request.initial_cash,
            holding_days=request.holding_days,
        )
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Backtesting engine not available: {e}. Install with: {INSTALL_HINT}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Backtest failed for %s: %s", request.ticker, e)
        raise HTTPException(status_code=500, detail=f"Backtest failed: {e}")

    # Generate report
    report_md = generate_backtest_report(result)

    return BacktestResponse(
        ticker=result.ticker,
        decision=result.decision,
        total_return=result.total_return,
        annual_return=result.annual_return,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown=result.max_drawdown,
        win_rate=result.win_rate,
        total_trades=result.total_trades,
        profit_trades=result.profit_trades,
        loss_trades=result.loss_trades,
        initial_cash=result.initial_cash,
        final_value=result.final_value,
        holding_days=result.holding_days,
        equity_curve=[
            EquityPoint(date=p["date"], value=p["value"])
            for p in (result.equity_curve or [])
        ],
        report_path=result.report_path,
        report_markdown=report_md,
    )
