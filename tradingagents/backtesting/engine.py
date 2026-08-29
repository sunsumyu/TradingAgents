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
    equity_curve: list[dict] = field(default_factory=list)
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
            "equity_curve": self.equity_curve,
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
        """Parse akquant result into BacktestResult.

        The installed akquant exposes metrics under ``result.metrics.*``
        (a wrapper delegating to Rust ``PerformanceMetrics``: total_return and
        annualized_return are decimals, win_rate is percent,
        max_drawdown is a negative decimal), trades as ``result.trades_df``
        (pnl column), and the equity curve as ``result.equity_curve``
        (tz-aware pd.Series).  Flat top-level attributes are kept as a
        fallback for simple fakes and older versions.
        """
        bt_result = BacktestResult(
            ticker=ticker,
            decision=strategy_class.__name__,
            initial_cash=initial_cash,
            raw_result=result,
        )

        # -- Metrics: prefer result.metrics.*, fall back to top-level attrs --
        metrics = getattr(result, "metrics", None)

        def _metric(name: str, aliases: tuple[str, ...] = ()) -> Any:
            """Read a metric from the wrapper (or aliases), then flat attrs."""
            for source in (metrics, result):
                for key in (name, *aliases):
                    try:
                        val = getattr(source, key)
                    except AttributeError:
                        continue
                    if isinstance(val, property):
                        continue
                    if val is not None:
                        return val
            return None

        total_return = _metric("total_return")
        annual_return = _metric("annual_return", ("annualized_return",))
        sharpe_ratio = _metric("sharpe_ratio")
        max_drawdown = _metric("max_drawdown")
        final_value = _metric("final_value", ("end_market_value",))

        bt_result.total_return = self._to_float(total_return)
        bt_result.annual_return = self._to_float(annual_return)
        bt_result.sharpe_ratio = self._to_float(sharpe_ratio)
        bt_result.max_drawdown = self._to_float(max_drawdown)
        bt_result.final_value = self._to_float(final_value)

        # -- Equity curve: tz-aware (or naive) Series -> daily points --
        bt_result.equity_curve = self._extract_equity_curve(result)

        # -- Derive missing metrics from available data --
        if bt_result.final_value is None and bt_result.equity_curve:
            bt_result.final_value = bt_result.equity_curve[-1]["value"]
        if bt_result.total_return is None and bt_result.final_value is not None:
            if initial_cash > 0:
                bt_result.total_return = (
                    bt_result.final_value - initial_cash
                ) / initial_cash
        elif total_return == 0.0 and bt_result.final_value is not None:
            # akquant reports 0.0 total_return when the strategy never trades;
            # re-derive only when it disagrees with the equity evidence so a
            # genuine flat curve (final == initial) stays 0.0.
            derived = (bt_result.final_value - initial_cash) / initial_cash
            if abs(derived) > 1e-9:
                bt_result.total_return = derived

        # -- Trade statistics: prefer trades_df (pnl column) --
        trade_metrics = getattr(result, "trade_metrics", None)
        win_rate_pct = self._to_float(_metric("win_rate"))
        trades_df = getattr(result, "trades_df", None)

        if trades_df is not None and hasattr(trades_df, "columns"):
            try:
                if "pnl" in trades_df.columns and len(trades_df) > 0:
                    pnls = trades_df["pnl"]
                    bt_result.total_trades = int(len(pnls))
                    bt_result.profit_trades = int((pnls > 0).sum())
                    bt_result.loss_trades = int((pnls <= 0).sum())
                    if bt_result.total_trades > 0:
                        bt_result.win_rate = (
                            bt_result.profit_trades / bt_result.total_trades
                        )
                    if hasattr(pnls, "mean"):
                        bt_result.avg_trade_return = self._to_float(pnls.mean())
            except Exception:
                logger.debug("trades_df extraction failed", exc_info=True)

        if trade_metrics is not None:
            # Fill trade stats from Rust TradePnL when trades_df was unusable
            if bt_result.total_trades == 0:
                closed = self._to_float(getattr(trade_metrics, "total_closed_trades", None))
                if closed is not None and closed > 0:
                    bt_result.total_trades = int(closed)
                    won = self._to_float(getattr(trade_metrics, "won_count", None))
                    lost = self._to_float(getattr(trade_metrics, "lost_count", None))
                    if won is not None:
                        bt_result.profit_trades = int(won)
                    if lost is not None:
                        bt_result.loss_trades = int(lost)

        # win_rate: prefer per-trade fraction computed from trades_df; fall
        # back to the percent-form win_rate (metrics or trade_metrics)
        if bt_result.win_rate is None and win_rate_pct is not None:
            bt_result.win_rate = win_rate_pct / 100.0

        return bt_result

    # ------------------------------------------------------------------
    # Extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_float(value) -> float | None:
        """Coerce a metric to float; None / NaN / non-numeric -> None."""
        if value is None or isinstance(value, property):
            return None
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        if f != f:  # NaN
            return None
        return f

    @staticmethod
    def _extract_equity_curve(result) -> list[dict]:
        """Convert ``result.equity_curve`` (pd.Series) to daily points.

        Handles tz-aware and naive DatetimeIndex, resamples intraday marks to
        end-of-day, and returns ``[{"date": "YYYY-MM-DD", "value": float}]``.
        """
        try:
            curve = getattr(result, "equity_curve", None)
            if curve is None:
                return []
            if isinstance(curve, (list, tuple)):
                # Already point-shaped [(ts, value)] or [{"date":...}]
                points = []
                for item in curve:
                    if isinstance(item, dict):
                        points.append({
                            "date": str(item.get("date", "")),
                            "value": float(item.get("value", 0.0)),
                        })
                    else:
                        # (timestamp, value) tuple like the Rust raw curve
                        ts, val = item
                        import datetime as _dt
                        if isinstance(ts, (int, float)):
                            dt = _dt.datetime.fromtimestamp(ts)
                        else:
                            dt = _dt.datetime.fromisoformat(str(ts))
                        points.append({
                            "date": dt.strftime("%Y-%m-%d"),
                            "value": float(val),
                        })
                return points

            # pd.Series path
            import pandas as pd

            if not hasattr(curve, "index") or len(curve) == 0:
                return []
            series = pd.Series(curve) if not isinstance(curve, pd.Series) else curve
            series = series.dropna()
            if series.empty:
                return []
            idx = series.index
            if not isinstance(idx, pd.DatetimeIndex):
                return []
            daily = series.resample("D").last().dropna()
            return [
                {"date": ts.strftime("%Y-%m-%d"), "value": float(v)}
                for ts, v in daily.items()
            ]
        except Exception:
            logger.debug("equity curve extraction failed", exc_info=True)
            return []
