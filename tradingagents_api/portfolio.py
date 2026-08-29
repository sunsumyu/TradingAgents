"""Simulated portfolio service — backed by the portfolio engine (ticket #2).

The engine owns the trading math (cash / average cost / commission /
performance); this module owns JSON persistence and the stable HTTP
contract. Legacy behaviour is preserved exactly:

- zero commission by default (opt-in via TRADINGAGENTS_PORTFOLIO_COMMISSION_RATE
  / TRADINGAGENTS_PORTFOLIO_MIN_COMMISSION),
- Chinese validation messages (现金不足 / 持仓不足 / 未知操作),
- NAV snapshots computed at average cost, per day.

Storage: ~/.tradingagents/portfolio.json
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from tradingagents.portfolio_engine import PortfolioEngine

logger = logging.getLogger(__name__)

PORTFOLIO_DIR = Path.home() / ".tradingagents"
PORTFOLIO_FILE = PORTFOLIO_DIR / "portfolio.json"

# Zero by default so migrated behaviour matches the legacy no-commission
# arithmetic exactly; operators can opt in to a realistic fee model.
COMMISSION_RATE = float(os.environ.get("TRADINGAGENTS_PORTFOLIO_COMMISSION_RATE", "0"))
MIN_COMMISSION = float(os.environ.get("TRADINGAGENTS_PORTFOLIO_MIN_COMMISSION", "0"))

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
    commission: float = 0  # Engine-charged fee (0 under the legacy zero rate)
    reason: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class PortfolioPerformance(BaseModel):
    """Optional performance metrics block on the portfolio response."""

    total_return: float = 0
    sharpe_ratio: float = 0
    max_drawdown: float = 0
    win_rate: float = 0
    profit_factor: float = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0


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
    performance: PortfolioPerformance | None = None


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


def _build_engine(p: PortfolioSnapshot) -> PortfolioEngine:
    """Rebuild the engine from the persisted snapshot (restore, not replay,
    so a changed commission rate between sessions cannot rewrite history)."""
    engine = PortfolioEngine(
        initial_capital=p.initial_cash,
        commission_rate=COMMISSION_RATE,
        min_commission=MIN_COMMISSION,
    )
    engine.restore(
        cash=p.cash,
        positions={
            pos.ticker: {
                "name": pos.name,
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
                "current_price": pos.current_price,
            }
            for pos in p.positions
        },
        trades=[
            _to_engine_trade(t)
            for t in p.trades
        ],
    )
    return engine


def _to_engine_trade(t: TradeRecord):
    """Map a persisted legacy trade record onto the engine's TradeRecord."""
    from tradingagents.portfolio_engine import TradeRecord as EngineTrade

    return EngineTrade(
        id=t.id,
        ticker=t.ticker,
        name=t.name,
        side=t.action,
        quantity=t.quantity,
        price=t.price,
        amount=t.total,
        commission=t.commission,
        timestamp=datetime.fromisoformat(t.timestamp),
        reason=t.reason,
    )


def _performance_block(engine: PortfolioEngine) -> PortfolioPerformance:
    perf = engine.get_performance()
    return PortfolioPerformance(
        total_return=perf.total_return,
        sharpe_ratio=perf.sharpe_ratio,
        max_drawdown=perf.max_drawdown,
        win_rate=perf.win_rate,
        profit_factor=perf.profit_factor,
        total_trades=perf.total_trades,
        winning_trades=perf.winning_trades,
        losing_trades=perf.losing_trades,
    )


# ── Public API ───────────────────────────────────────────────────────────────


def get_portfolio() -> PortfolioResponse:
    """Get current portfolio with computed P&L."""
    p = _load_portfolio()

    positions = []
    total_market = 0.0

    for pos in p.positions:
        qty = pos.quantity
        cost = pos.avg_cost * qty
        price = pos.current_price or pos.avg_cost
        mv = price * qty
        pnl = mv - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0

        total_market += mv

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

    performance = None
    if p.trades:
        performance = _performance_block(_build_engine(p))

    return PortfolioResponse(
        positions=positions,
        cash=round(p.cash, 2),
        total_value=round(total_value, 2),
        total_pnl=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        performance=performance,
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

    # Pre-validate with the legacy Chinese messages — these are surfaced
    # verbatim as HTTP 400 details, so they are part of the contract.
    if action not in ("buy", "sell"):
        raise ValueError(f"未知操作: {action}（仅支持 buy/sell）")

    total_cost = quantity * price
    existing = next((pos for pos in p.positions if pos.ticker == ticker), None)

    if action == "buy" and p.cash < total_cost:
        raise ValueError(
            f"现金不足：需要 ¥{total_cost:,.2f}，当前可用 ¥{p.cash:,.2f}"
        )
    if action == "sell" and (not existing or existing.quantity < quantity):
        avail = existing.quantity if existing else 0
        raise ValueError(
            f"持仓不足：{ticker} 可卖 {avail} 股，请求卖出 {quantity} 股"
        )

    # The engine owns the math (cash movement, average cost, commission).
    engine = _build_engine(p)
    trade = engine.execute_trade(
        ticker=ticker,
        side=action,
        quantity=quantity,
        price=price,
        name=name,
        reason=reason,
    )

    # Sync the snapshot from engine state.
    p.cash = engine._cash
    p.positions = [
        Position(
            ticker=t,
            name=pos["name"],
            quantity=pos["quantity"],
            avg_cost=pos["avg_cost"],
            current_price=None,  # Legacy contract: never set on positions
        )
        for t, pos in engine._positions.items()
    ]
    p.trades.append(TradeRecord(
        id=trade.id,
        ticker=trade.ticker,
        name=trade.name,
        action=trade.side,
        quantity=trade.quantity,
        price=trade.price,
        total=trade.amount,
        commission=trade.commission,
        reason=trade.reason,
        timestamp=trade.timestamp.isoformat(),
    ))

    # NAV snapshot at average cost (legacy formula).
    total_market = sum(pos.avg_cost * pos.quantity for pos in p.positions)
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
