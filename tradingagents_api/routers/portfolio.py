"""Simulated portfolio endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..portfolio import (
    PortfolioResponse,
    TradeRecord,
    execute_trade,
    get_nav_history,
    get_portfolio,
    get_trade_history,
    reset_portfolio,
)
from ..schemas import PortfolioTradeRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/portfolio", response_model=PortfolioResponse)
async def get_portfolio_endpoint():
    """Get current simulated portfolio with positions and P&L."""
    try:
        return get_portfolio()
    except Exception as exc:
        logger.error("Failed to get portfolio: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/portfolio/trade", response_model=PortfolioResponse)
async def post_portfolio_trade(request: PortfolioTradeRequest):
    """Execute a simulated trade (buy/sell)."""
    try:
        return execute_trade(
            ticker=request.ticker,
            action=request.action,
            quantity=request.quantity,
            price=request.price,
            name=request.name,
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Trade failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/portfolio/history", response_model=list[TradeRecord])
async def get_portfolio_history():
    """Get trade history, newest first."""
    try:
        return get_trade_history()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/portfolio/nav")
async def get_portfolio_nav():
    """Get NAV history for the performance chart."""
    try:
        return {"nav_history": get_nav_history()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/portfolio/reset", response_model=PortfolioResponse)
async def post_portfolio_reset(initial_cash: float = 1_000_000.0):
    """Reset portfolio to initial cash amount."""
    try:
        return reset_portfolio(initial_cash)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
