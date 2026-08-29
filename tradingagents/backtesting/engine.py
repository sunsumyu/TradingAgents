"""BacktestEngine — wraps akquant's Rust-core backtesting engine.

akquant is optional: ``pip install akquant`` or
``pip install "tradingagents[backtest]"``.  The module lazily imports akquant
so the rest of the codebase works without it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import for akquant (Rust core)
# ---------------------------------------------------------------------------

_aq = None


def _get_aq():
    """Lazy-import akquant; raise ImportError with install hint if missing."""
    global _aq
    if _aq is None:
        try:
            import akquant as aq
            _aq = aq
        except ImportError:
            raise ImportError(
                "akquant is not installed. Install with: "
                "pip install akquant  or  pip install 'tradingagents[backtest]'"
            )
    return _aq


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    """Structured result from a backtest run."""

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
    avg_trade_return: float | None = None
    initial_cash: float = 100_000.0
    final_value: float | None = None
    holding_days: int = 5
    raw_result: Any = None  # akquant result object
    report_path: str | None = None

    def summary(self) -> str:
        """Human-readable summary of backtest results."""
        lines = [
            f"=== Backtest Result: {self.ticker} ===",
            f"Decision: {self.decision}",
            f"Holding period: {self.holding_days} days",
            f"Initial cash: ¥{self.initial_cash:,.0f}",
        ]
        if self.final_value is not None:
            lines.append(f"Final value: ¥{self.final_value:,.0f}")
        if self.total_return is not None:
            lines.append(f"Total return: {self.total_return:+.2%}")
        if self.annual_return is not None:
            lines.append(f"Annual return: {self.annual_return:+.2%}")
        if self.sharpe_ratio is not None:
            lines.append(f"Sharpe ratio: {self.sharpe_ratio:.2f}")
        if self.max_drawdown is not None:
            lines.append(f"Max drawdown: {self.max_drawdown:.2%}")
        if self.total_trades > 0:
            lines.append(f"Trades: {self.total_trades} ({self.profit_trades} win / {self.loss_trades} loss)")
            lines.append(f"Win rate: {self.win_rate:.1%}" if self.win_rate else "")
        if self.report_path:
            lines.append(f"Report: {self.report_path}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize to dict for API responses."""
        return {
            "ticker": self.ticker,
            "decision": self.decision,
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "profit_trades": self.profit_trades,
            "loss_trades": self.loss_trades,
            "avg_trade_return": self.avg_trade_return,
            "initial_cash": self.initial_cash,
            "final_value": self.final_value,
            "holding_days": self.holding_days,
            "report_path": self.report_path,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """High-level backtest engine wrapping akquant.

    Provides two entry points:

    1. ``run()`` — generic: pass a strategy class and data.
    2. ``run_from_decision()`` — Agent-oriented: convert a trade decision
       string (from ``final_trade_decision``) into an ``AgentDecisionStrategy``
       and backtest it.
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def _fetch_data(self, ticker: str, start_date: str, end_date: str):
        """Fetch OHLCV data via akshare for backtesting.

        Returns a pandas DataFrame with Date index and OHLCV columns.
        """
        from tradingagents.dataflows.akshare_vendor import _normalize_code

        code = _normalize_code(ticker)
        ak = _get_aq()
        # akquant examples use akshare for data acquisition
        try:
            import akshare as akshare_lib
            df = akshare_lib.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust="qfq",
            )
        except ImportError:
            raise ImportError(
                "akshare is required for data fetching. Install with: pip install akshare"
            )

        if df is None or df.empty:
            raise ValueError(f"No data available for {ticker} ({start_date} ~ {end_date})")

        # Normalize column names for akquant
        col_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df["date"] = df["date"].astype(str)
        return df

    # ------------------------------------------------------------------
    # Generic run
    # ------------------------------------------------------------------

    def run(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        strategy_class: type,
        initial_cash: float = 100_000.0,
        **kwargs,
    ) -> BacktestResult:
        """Run a backtest with a custom strategy class.

        Args:
            ticker: Stock code (e.g. "600519").
            start_date: Start date "YYYY-MM-DD".
            end_date: End date "YYYY-MM-DD".
            strategy_class: A subclass of ``akquant.Strategy``.
            initial_cash: Starting capital.
            **kwargs: Extra args passed to ``akquant.run_backtest()``.

        Returns:
            ``BacktestResult`` with performance metrics.
        """
        aq = _get_aq()
        df = self._fetch_data(ticker, start_date, end_date)

        logger.info(
            "Running backtest: %s %s~%s, strategy=%s, cash=%.0f",
            ticker, start_date, end_date, strategy_class.__name__, initial_cash,
        )

        result = aq.run_backtest(
            data=df,
            strategy=strategy_class,
            initial_cash=initial_cash,
            symbols=ticker,
            **kwargs,
        )

        return self._parse_result(result, ticker, strategy_class, initial_cash)

    # ------------------------------------------------------------------
    # Agent-decision run
    # ------------------------------------------------------------------

    def run_from_decision(
        self,
        final_state: dict,
        ticker: str,
        holding_days: int = 5,
        initial_cash: float = 100_000.0,
    ) -> BacktestResult:
        """Convert an Agent's trade decision into a backtest.

        Reads ``final_trade_decision`` from *final_state*, determines the
        action (BUY/SELL/HOLD), and runs a backtest with
        ``AgentDecisionStrategy``.

        Args:
            final_state: The final graph state dict from a trading run.
            ticker: Stock code.
            holding_days: How many days to hold the position.
            initial_cash: Starting capital.

        Returns:
            ``BacktestResult`` with performance metrics.
        """
        from .strategy import AgentDecisionStrategy

        decision_text = final_state.get("final_trade_decision", "")
        trade_date = final_state.get("trade_date", "")

        # Parse decision from text
        decision = self._parse_decision(decision_text)

        if decision == "HOLD":
            return BacktestResult(
                ticker=ticker,
                decision="HOLD",
                total_return=0.0,
                total_trades=0,
                initial_cash=initial_cash,
                holding_days=holding_days,
            )

        # Calculate date range for backtest
        from datetime import datetime, timedelta
        end_date = trade_date or datetime.now().strftime("%Y-%m-%d")
        start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=holding_days + 30)
        start_date = start_dt.strftime("%Y-%m-%d")

        strategy_class = type(
            "DynamicAgentStrategy",
            (AgentDecisionStrategy,),
            {"__init__": lambda self, **kw: AgentDecisionStrategy.__init__(self, decision=decision, ticker=ticker, holding_days=holding_days, **kw)},
        )

        return self.run(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            strategy_class=strategy_class,
            initial_cash=initial_cash,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_decision(decision_text: str) -> str:
        """Extract BUY/SELL/HOLD from a trade decision string."""
        text = decision_text.upper()
        # Check for explicit signals
        if any(kw in text for kw in ("买入", "BUY", "做多", "LONG", "看多", "BULLISH")):
            return "BUY"
        if any(kw in text for kw in ("卖出", "SELL", "做空", "SHORT", "看空", "BEARISH", "清仓")):
            return "SELL"
        return "HOLD"

    def _parse_result(self, result, ticker, strategy_class, initial_cash) -> BacktestResult:
        """Parse akquant result into BacktestResult."""
        bt_result = BacktestResult(
            ticker=ticker,
            decision=strategy_class.__name__,
            initial_cash=initial_cash,
            raw_result=result,
        )

        # Extract metrics from akquant result
        if hasattr(result, "total_return"):
            bt_result.total_return = result.total_return
        if hasattr(result, "annual_return"):
            bt_result.annual_return = result.annual_return
        if hasattr(result, "sharpe_ratio"):
            bt_result.sharpe_ratio = result.sharpe_ratio
        if hasattr(result, "max_drawdown"):
            bt_result.max_drawdown = result.max_drawdown
        if hasattr(result, "final_value"):
            bt_result.final_value = result.final_value
        elif hasattr(result, "portfolio_value"):
            vals = result.portfolio_value
            if hasattr(vals, "iloc") and len(vals) > 0:
                bt_result.final_value = float(vals.iloc[-1])

        # Trade statistics
        if hasattr(result, "trades") and result.trades is not None:
            trades = result.trades
            bt_result.total_trades = len(trades) if hasattr(trades, "__len__") else 0
            if hasattr(trades, "pnl"):
                pnls = trades.pnl
                bt_result.profit_trades = int((pnls > 0).sum()) if hasattr(pnls, "sum") else 0
                bt_result.loss_trades = int((pnls <= 0).sum()) if hasattr(pnls, "sum") else 0
                if bt_result.total_trades > 0:
                    bt_result.win_rate = bt_result.profit_trades / bt_result.total_trades
                if hasattr(pnls, "mean"):
                    bt_result.avg_trade_return = float(pnls.mean())

        return bt_result
