"""Simulated portfolio (Phase 6, ticket 6.04).

JSON-file-backed paper trading portfolio. Tracks positions, cash,
trade history, and computes P&L from realtime prices.

Storage: ~/.tradingagents/portfolio.json
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PORTFOLIO_DIR = Path.home() / ".tradingagents"
PORTFOLIO_FILE = PORTFOLIO_DIR / "portfolio.json"

# ── Models ───────────────────────────────────────────────────────────────────


class Position(BaseModel):
    """One holding in the portfolio."""

    ticker: str
    name: str = ""
    quantity: int = Field(ge=0, description="股数")
    avg_cost: float = Field(description="平均成本价")
    current_price: float | None = None


class TradeRecord(BaseModel):
    """One executed (simulated) trade."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    ticker: str
    name: str = ""
    action: str = Field(description="'buy' or 'sell'")
    quantity: int = Field(ge=1)
    price: float
    total: float = 0  # quantity * price
    reason: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class PortfolioSnapshot(BaseModel):
    """Full portfolio state."""

    positions: list[Position] = Field(default_factory=list)
    cash: float = Field(default=1_000_000.0, description="可用现金")
    initial_cash: float = Field(default=1_000_000.0, description="初始资金")
    trades: list[TradeRecord] = Field(default_factory=list)
    nav_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="[{date, nav}] — 净资产历史，用于收益曲线",
    )


class PortfolioPositionResponse(BaseModel):
    """One position with computed P&L fields."""

    ticker: str
    name: str
    quantity: int
    avg_cost: float
    current_price: float | None = None
    market_value: float = 0
    pnl: float = 0
    pnl_pct: float = 0


class PortfolioResponse(BaseModel):
    """GET /api/portfolio response."""

    positions: list[PortfolioPositionResponse] = Field(default_factory=list)
    cash: float = 0
    total_value: float = 0
    total_pnl: float = 0
    total_pnl_pct: float = 0


# ── Storage ──────────────────────────────────────────────────────────────────


def _load_portfolio() -> PortfolioSnapshot:
    """Load portfolio from JSON file, returning empty if missing."""
    if not PORTFOLIO_FILE.exists():
        return PortfolioSnapshot()
    try:
        raw = json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        return PortfolioSnapshot(**raw)
    except Exception as exc:
        logger.warning("Failed to load portfolio: %s", exc)
        return PortfolioSnapshot()


def _save_portfolio(portfolio: PortfolioSnapshot) -> None:
    """Persist portfolio to JSON file."""
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_FILE.write_text(
        json.dumps(portfolio.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Public API ───────────────────────────────────────────────────────────────


def get_portfolio() -> PortfolioResponse:
    """Get current portfolio with computed P&L."""
    p = _load_portfolio()

    positions = []
    total_market = 0.0
    total_cost = 0.0

    for pos in p.positions:
        qty = pos.quantity
        cost = pos.avg_cost * qty
        price = pos.current_price or pos.avg_cost
        mv = price * qty
        pnl = mv - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0

        total_market += mv
        total_cost += cost

        positions.append(PortfolioPositionResponse(
            ticker=pos.ticker,
            name=pos.name,
            quantity=qty,
            avg_cost=round(pos.avg_cost, 3),
            current_price=round(price, 3) if pos.current_price else None,
            market_value=round(mv, 2),
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 2),
        ))

    total_value = p.cash + total_market
    total_pnl = total_value - p.initial_cash
    total_pnl_pct = (total_pnl / p.initial_cash * 100) if p.initial_cash > 0 else 0

    return PortfolioResponse(
        positions=positions,
        cash=round(p.cash, 2),
        total_value=round(total_value, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
    )


def execute_trade(
    ticker: str,
    action: str,
    quantity: int,
    price: float,
    name: str = "",
    reason: str = "",
) -> PortfolioResponse:
    """Execute a simulated trade and return updated portfolio."""
    p = _load_portfolio()
    total_cost = quantity * price

    if action == "buy":
        if p.cash < total_cost:
            raise ValueError(
                f"现金不足：需要 ¥{total_cost:,.2f}，当前可用 ¥{p.cash:,.2f}"
            )

        p.cash -= total_cost

        # Find existing position
        existing = next((pos for pos in p.positions if pos.ticker == ticker), None)
        if existing:
            # Average up/down
            old_qty = existing.quantity
            old_cost = existing.avg_cost * old_qty
            new_qty = old_qty + quantity
            existing.avg_cost = (old_cost + total_cost) / new_qty
            existing.quantity = new_qty
            if name:
                existing.name = name
        else:
            p.positions.append(Position(
                ticker=ticker,
                name=name,
                quantity=quantity,
                avg_cost=price,
            ))

    elif action == "sell":
        existing = next((pos for pos in p.positions if pos.ticker == ticker), None)
        if not existing or existing.quantity < quantity:
            avail = existing.quantity if existing else 0
            raise ValueError(
                f"持仓不足：{ticker} 可卖 {avail} 股，请求卖出 {quantity} 股"
            )

        p.cash += total_cost
        existing.quantity -= quantity
        if existing.quantity == 0:
            p.positions = [pos for pos in p.positions if pos.ticker != ticker]
    else:
        raise ValueError(f"未知操作: {action}（仅支持 buy/sell）")

    # Record trade
    p.trades.append(TradeRecord(
        ticker=ticker,
        name=name,
        action=action,
        quantity=quantity,
        price=price,
        total=total_cost,
        reason=reason,
    ))

    # Record NAV snapshot
    total_market = sum(
        (pos.current_price or pos.avg_cost) * pos.quantity
        for pos in p.positions
    )
    nav = p.cash + total_market
    today = datetime.now().strftime("%Y-%m-%d")
    p.nav_history.append({"date": today, "nav": round(nav, 2)})

    _save_portfolio(p)
    return get_portfolio()


def get_trade_history() -> list[TradeRecord]:
    """Get full trade history, newest first."""
    p = _load_portfolio()
    return list(reversed(p.trades))


def get_nav_history() -> list[dict[str, Any]]:
    """Get NAV history for the performance chart."""
    p = _load_portfolio()
    return p.nav_history


def reset_portfolio(initial_cash: float = 1_000_000.0) -> PortfolioResponse:
    """Reset portfolio to initial state."""
    p = PortfolioSnapshot(cash=initial_cash, initial_cash=initial_cash)
    _save_portfolio(p)
    return get_portfolio()
