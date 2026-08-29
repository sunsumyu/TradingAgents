"""SignalEngine — technical analysis, signal fusion, and alert management.

This is the deep module's main class. It provides three methods:

1. compute_signals() — multi-indicator signal analysis with composite scoring
2. run_strategy() — strategy backtesting on historical data
3. check_alerts() — price/indicator alert monitoring
"""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
import pandas as pd

from tradingagents.chart_engine import ChartEngine
from tradingagents.data_center import DataCenter

from .models import (
    Alert,
    AlertCondition,
    CompositeSignal,
    Signal,
    SignalStrength,
    SignalType,
    Strategy,
    StrategyResult,
    TradeAction,
)


class SignalEngine:
    """Signal Engine — deep module with small interface.

    Interface (3 methods)::

        engine = SignalEngine()
        result = engine.compute_signals("600519", "1D", ["MACD", "RSI", "KDJ"])
        backtest = engine.run_strategy(some_strategy, "600519", "1D", "2024-01-01", "2025-01-01")
        triggered = engine.check_alerts("600519", 1800.0, 50000)

    Implementation hides: indicator weight calculation, signal aggregation,
    strategy simulation engine, and alert state management.
    """

    def __init__(
        self,
        chart_engine: ChartEngine | None = None,
        data_center: DataCenter | None = None,
    ) -> None:
        self._chart = chart_engine or ChartEngine()
        self._data = data_center or DataCenter()
        self._alerts: dict[str, Alert] = {}

    # ── Indicator weights for composite scoring ───────────────────────────

    _DEFAULT_WEIGHTS: dict[str, float] = {
        "MACD": 1.5,
        "RSI": 1.2,
        "KDJ": 1.2,
        "BOLL": 1.0,
        "DMI": 1.0,
        "CCI": 0.8,
        "WR": 0.8,
        "TRIX": 0.7,
        "SAR": 0.9,
        "MA": 1.3,
    }

    # ── Public interface ──────────────────────────────────────────────────

    def compute_signals(
        self,
        ticker: str,
        timeframe: str,
        indicators: list[str] | None = None,
        params: dict[str, dict[str, Any]] | None = None,
    ) -> CompositeSignal:
        """Compute composite trading signal from multiple indicators.

        Fetches OHLCV data, computes each indicator, detects individual
        signals, then aggregates into a weighted composite score.

        Args:
            ticker: Stock ticker.
            timeframe: Chart timeframe.
            indicators: List of indicator keys. Defaults to ["MACD", "RSI", "KDJ"].
            params: Per-indicator parameter overrides.

        Returns:
            CompositeSignal with score, recommendation, and per-indicator breakdown.
        """
        if indicators is None:
            indicators = ["MACD", "RSI", "KDJ"]

        # Fetch OHLCV data
        from tradingagents.chart_engine.timeframes import Timeframe
        tf = Timeframe(timeframe)
        df = self._data.get_ohlcv(
            ticker, timeframe,
            start_date="2024-01-01",
            end_date=pd.Timestamp.now().strftime("%Y-%m-%d"),
        )

        if df is None or df.empty or len(df) < 5:
            return CompositeSignal(
                ticker=ticker,
                timeframe=timeframe,
                signals=[],
                composite_score=50.0,
                recommendation="HOLD",
                confidence=0.0,
            )

        # Ensure numeric columns
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Compute each indicator and collect signals
        all_signals: list[Signal] = []
        indicator_scores: dict[str, float] = {}

        for ind_key in indicators:
            try:
                result = self._chart.compute_indicator(df, ind_key, (params or {}).get(ind_key))
                # Convert chart_engine signals to signal_engine signals
                for sig in result.signals:
                    all_signals.append(Signal(
                        type=SignalType(sig.type.value),
                        strength=sig.strength,
                        indicator=ind_key,
                        reason=sig.reason,
                    ))
                # Compute individual indicator score
                score = self._score_indicator(ind_key, result.data, df)
                indicator_scores[ind_key] = score
            except Exception:
                indicator_scores[ind_key] = 50.0  # Neutral on error

        # Composite scoring
        composite_score = self._compute_composite_score(indicator_scores)
        recommendation = self._score_to_recommendation(composite_score)
        confidence = self._compute_confidence(indicator_scores)

        return CompositeSignal(
            ticker=ticker,
            timeframe=timeframe,
            signals=all_signals,
            composite_score=round(composite_score, 1),
            recommendation=recommendation,
            confidence=round(confidence, 1),
            indicator_scores=indicator_scores,
        )

    def run_strategy(
        self,
        strategy: Strategy,
        ticker: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 1_000_000,
    ) -> StrategyResult:
        """Run a strategy backtest on historical data.

        Args:
            strategy: Strategy definition with rules.
            ticker: Stock ticker.
            timeframe: Chart timeframe.
            start_date: Backtest start date.
            end_date: Backtest end date.
            initial_capital: Starting capital.

        Returns:
            StrategyResult with performance metrics.
        """
        df = self._data.get_ohlcv(ticker, timeframe, start_date, end_date)

        if df is None or df.empty or len(df) < 10:
            return StrategyResult(
                strategy_name=strategy.name,
                ticker=ticker,
                timeframe=timeframe,
                total_return=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                total_trades=0,
            )

        # Ensure numeric
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Simple strategy simulation
        capital = initial_capital
        position = 0
        trades: list[dict[str, Any]] = []
        equity_curve: list[float] = []

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            price = float(row["close"])

            # Check strategy rules
            action = self._evaluate_strategy_rules(strategy, df, i)

            if action == TradeAction.BUY and position == 0:
                # Buy with 90% of capital
                shares = int(capital * 0.9 / price)
                if shares > 0:
                    cost = shares * price
                    capital -= cost
                    position = shares
                    trades.append({
                        "action": "BUY",
                        "price": price,
                        "shares": shares,
                        "date": str(row.get("date", i)),
                        "capital_after": capital,
                    })

            elif action == TradeAction.SELL and position > 0:
                # Sell all
                revenue = position * price
                capital += revenue
                trades.append({
                    "action": "SELL",
                    "price": price,
                    "shares": position,
                    "date": str(row.get("date", i)),
                    "capital_after": capital,
                })
                position = 0

            # Track equity
            equity = capital + position * price
            equity_curve.append(equity)

        # Calculate metrics
        total_value = capital + position * float(df.iloc[-1]["close"])
        total_return = (total_value - initial_capital) / initial_capital * 100

        # Sharpe ratio (annualized)
        if len(equity_curve) > 1:
            returns = np.diff(equity_curve) / equity_curve[:-1]
            sharpe = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252)
        else:
            sharpe = 0.0

        # Max drawdown
        if equity_curve:
            peak = equity_curve[0]
            max_dd = 0.0
            for eq in equity_curve:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak * 100
                if dd > max_dd:
                    max_dd = dd
        else:
            max_dd = 0.0

        # Win rate
        winning_trades = sum(1 for i in range(1, len(trades), 2) if i < len(trades))
        total_round_trips = len(trades) // 2
        win_rate = (winning_trades / total_round_trips * 100) if total_round_trips > 0 else 0.0

        return StrategyResult(
            strategy_name=strategy.name,
            ticker=ticker,
            timeframe=timeframe,
            total_return=round(total_return, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown=round(max_dd, 2),
            win_rate=round(win_rate, 2),
            total_trades=len(trades),
            trades=trades,
        )

    def check_alerts(
        self,
        ticker: str,
        price: float,
        volume: float = 0,
        indicator_values: dict[str, float] | None = None,
    ) -> list[Alert]:
        """Check if any alerts should be triggered.

        All 7 condition types are evaluable:
        price_above / price_below / volume_above use the arguments directly;
        indicator_above / below and cross_above / below need the current
        indicator value(s) via *indicator_values* — when the value for an
        alert's indicator is missing, that alert is skipped (stays armed).

        Args:
            ticker: Stock ticker.
            price: Current price.
            volume: Current volume.
            indicator_values: Current indicator readings, e.g. {"RSI": 25.0}.

        Returns:
            List of newly triggered alerts.
        """
        import time

        indicator_values = indicator_values or {}
        triggered: list[Alert] = []

        for alert in self._alerts.values():
            if alert.ticker != ticker or alert.triggered or not alert.enabled:
                continue

            should_trigger = False
            ind_value = (
                indicator_values.get(alert.indicator)
                if alert.indicator
                else None
            )

            if alert.condition == AlertCondition.PRICE_ABOVE and price >= alert.threshold:
                should_trigger = True
            elif alert.condition == AlertCondition.PRICE_BELOW and price <= alert.threshold:
                should_trigger = True
            elif alert.condition == AlertCondition.VOLUME_ABOVE and volume >= alert.threshold:
                should_trigger = True
            elif alert.condition == AlertCondition.INDICATOR_ABOVE:
                should_trigger = ind_value is not None and ind_value >= alert.threshold
            elif alert.condition == AlertCondition.INDICATOR_BELOW:
                should_trigger = ind_value is not None and ind_value <= alert.threshold
            elif alert.condition in (AlertCondition.CROSS_ABOVE, AlertCondition.CROSS_BELOW):
                # Needs both sides of the comparison: the indicator line now
                # and the previous check's price/line baseline.
                if ind_value is not None and alert.last_price is not None \
                        and alert.last_indicator_value is not None:
                    was_above = alert.last_price >= alert.last_indicator_value
                    is_above = price >= ind_value
                    if alert.condition == AlertCondition.CROSS_ABOVE:
                        should_trigger = not was_above and is_above
                    else:
                        should_trigger = was_above and not is_above
            # Unknown conditions: never trigger silently

            # Update the cross-detection baseline every check
            alert.last_price = price
            if ind_value is not None:
                alert.last_indicator_value = ind_value

            if should_trigger:
                alert.triggered = True
                alert.triggered_at = time.time()
                triggered.append(alert)

        return triggered

    # ── Alert management ──────────────────────────────────────────────────

    def add_alert(
        self,
        ticker: str,
        condition: AlertCondition,
        threshold: float,
        message: str = "",
        indicator: str | None = None,
        enabled: bool = True,
    ) -> Alert:
        """Create a new alert."""
        import time
        alert = Alert(
            id=uuid.uuid4().hex[:8],
            ticker=ticker,
            condition=condition,
            threshold=threshold,
            indicator=indicator,
            message=message,
            enabled=enabled,
            created_at=time.time(),
        )
        self._alerts[alert.id] = alert
        return alert

    def restore_alerts(self, alerts: list[Alert]) -> None:
        """Load persisted alerts (including cross-detection baselines)."""
        for alert in alerts:
            self._alerts[alert.id] = alert

    def set_alert_enabled(self, alert_id: str, enabled: bool) -> bool:
        """Enable or disable an alert without deleting it. Returns True if found."""
        alert = self._alerts.get(alert_id)
        if alert is None:
            return False
        alert.enabled = enabled
        return True

    def remove_alert(self, alert_id: str) -> bool:
        """Remove an alert by ID."""
        return self._alerts.pop(alert_id, None) is not None

    def get_alerts(self, ticker: str | None = None) -> list[Alert]:
        """Get all alerts, optionally filtered by ticker."""
        alerts = list(self._alerts.values())
        if ticker:
            alerts = [a for a in alerts if a.ticker == ticker]
        return alerts

    def clear_alerts(self, ticker: str | None = None) -> int:
        """Clear alerts. Returns count removed."""
        if ticker:
            to_remove = [k for k, v in self._alerts.items() if v.ticker == ticker]
        else:
            to_remove = list(self._alerts.keys())
        for k in to_remove:
            del self._alerts[k]
        return len(to_remove)

    # ── Private helpers ───────────────────────────────────────────────────

    def _score_indicator(
        self, indicator: str, data: dict[str, list], df: pd.DataFrame
    ) -> float:
        """Score a single indicator's current state (0-100).

        0-30: bearish, 50: neutral, 70-100: bullish.
        """
        try:
            if indicator == "RSI":
                rsi_vals = [v for v in data.get("rsi", []) if v is not None and not np.isnan(v)]
                if rsi_vals:
                    rsi = rsi_vals[-1]
                    # RSI < 30 oversold (bullish), > 70 overbought (bearish)
                    if rsi < 30:
                        return 75 + (30 - rsi)  # Strong buy
                    elif rsi > 70:
                        return 25 - (rsi - 70)  # Strong sell
                    else:
                        return 50 + (rsi - 50) * 0.5
                return 50.0

            elif indicator == "MACD":
                dif = data.get("dif", [])
                dea = data.get("dea", [])
                if len(dif) >= 2 and len(dea) >= 2:
                    if dif[-1] is not None and dea[-1] is not None:
                        # Golden cross (bullish) or death cross (bearish)
                        if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
                            return 80  # Golden cross
                        elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
                            return 20  # Death cross
                        elif dif[-1] > dea[-1]:
                            return 60  # Above signal
                        else:
                            return 40  # Below signal
                return 50.0

            elif indicator == "KDJ":
                k = data.get("k", [])
                d = data.get("d", [])
                if len(k) >= 2 and len(d) >= 2:
                    if k[-1] is not None and d[-1] is not None:
                        if k[-1] < 20 and d[-1] < 20:
                            return 75  # Oversold
                        elif k[-1] > 80 and d[-1] > 80:
                            return 25  # Overbought
                        elif k[-1] > d[-1]:
                            return 60
                        else:
                            return 40
                return 50.0

            elif indicator == "BOLL":
                upper = data.get("upper", [])
                lower = data.get("lower", [])
                if upper and lower and len(df) > 0:
                    close = float(df["close"].iloc[-1])
                    if upper[-1] is not None and lower[-1] is not None:
                        if close <= lower[-1]:
                            return 75  # At lower band (oversold)
                        elif close >= upper[-1]:
                            return 25  # At upper band (overbought)
                        mid = (upper[-1] + lower[-1]) / 2
                        return 50 + (close - mid) / (upper[-1] - lower[-1] + 1e-10) * 30
                return 50.0

            elif indicator == "DMI":
                plus_di = data.get("plus_di", [])
                minus_di = data.get("minus_di", [])
                if plus_di and minus_di:
                    if plus_di[-1] is not None and minus_di[-1] is not None:
                        diff = plus_di[-1] - minus_di[-1]
                        return 50 + diff * 0.5
                return 50.0

            # Default: neutral
            return 50.0

        except Exception:
            return 50.0

    def _compute_composite_score(self, indicator_scores: dict[str, float]) -> float:
        """Compute weighted composite score from individual indicator scores."""
        if not indicator_scores:
            return 50.0

        total_weight = 0.0
        weighted_sum = 0.0

        for ind, score in indicator_scores.items():
            weight = self._DEFAULT_WEIGHTS.get(ind, 1.0)
            weighted_sum += score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 50.0

    def _score_to_recommendation(self, score: float) -> str:
        """Convert composite score to recommendation."""
        if score >= 65:
            return "BUY"
        elif score <= 35:
            return "SELL"
        else:
            return "HOLD"

    def _compute_confidence(self, indicator_scores: dict[str, float]) -> float:
        """Compute confidence based on agreement between indicators.

        High confidence when indicators agree (all buy or all sell).
        Low confidence when indicators disagree.
        """
        if len(indicator_scores) < 2:
            return 50.0

        scores = list(indicator_scores.values())
        mean = np.mean(scores)
        std = np.std(scores)

        # Low std = high agreement = high confidence
        # Map: std 0 → 100, std 25 → 50, std 50+ → 0
        confidence = max(0, 100 - std * 2)
        return confidence

    def _evaluate_strategy_rules(
        self, strategy: Strategy, df: pd.DataFrame, index: int
    ) -> TradeAction:
        """Evaluate strategy rules at a given bar index.

        Default strategy: simple MA crossover if no rules defined.
        """
        if not strategy.rules:
            # Default: MA crossover strategy
            return self._ma_crossover_action(df, index)

        # Evaluate custom rules
        for rule in strategy.rules:
            action = self._evaluate_rule(rule, df, index)
            if action != TradeAction.HOLD:
                return action

        return TradeAction.HOLD

    def _ma_crossover_action(self, df: pd.DataFrame, index: int) -> TradeAction:
        """Simple MA crossover strategy: buy when MA5 > MA20, sell when MA5 < MA20."""
        if index < 20:
            return TradeAction.HOLD

        close = df["close"].astype(float)
        ma5 = close.rolling(5).mean()
        ma20 = close.rolling(20).mean()

        if pd.isna(ma5.iloc[index]) or pd.isna(ma20.iloc[index]):
            return TradeAction.HOLD
        if pd.isna(ma5.iloc[index - 1]) or pd.isna(ma20.iloc[index - 1]):
            return TradeAction.HOLD

        # Golden cross: MA5 crosses above MA20
        if ma5.iloc[index] > ma20.iloc[index] and ma5.iloc[index - 1] <= ma20.iloc[index - 1]:
            return TradeAction.BUY

        # Death cross: MA5 crosses below MA20
        if ma5.iloc[index] < ma20.iloc[index] and ma5.iloc[index - 1] >= ma20.iloc[index - 1]:
            return TradeAction.SELL

        return TradeAction.HOLD

    def _evaluate_rule(
        self, rule: dict[str, Any], df: pd.DataFrame, index: int
    ) -> TradeAction:
        """Evaluate a single strategy rule."""
        rule_type = rule.get("type", "")
        action = rule.get("action", "hold")

        if rule_type == "ma_cross":
            fast = rule.get("fast", 5)
            slow = rule.get("slow", 20)
            close = df["close"].astype(float)
            ma_fast = close.rolling(fast).mean()
            ma_slow = close.rolling(slow).mean()

            if index < 1 or pd.isna(ma_fast.iloc[index]) or pd.isna(ma_slow.iloc[index]):
                return TradeAction.HOLD
            if pd.isna(ma_fast.iloc[index - 1]) or pd.isna(ma_slow.iloc[index - 1]):
                return TradeAction.HOLD

            if action == "buy" and ma_fast.iloc[index] > ma_slow.iloc[index] and ma_fast.iloc[index - 1] <= ma_slow.iloc[index - 1]:
                return TradeAction.BUY
            elif action == "sell" and ma_fast.iloc[index] < ma_slow.iloc[index] and ma_fast.iloc[index - 1] >= ma_slow.iloc[index - 1]:
                return TradeAction.SELL

        elif rule_type == "rsi_threshold":
            period = rule.get("period", 14)
            threshold = rule.get("threshold", 30)
            close = df["close"].astype(float)
            delta = close.diff()
            gain = delta.clip(lower=0)
            loss = (-delta).clip(lower=0)
            avg_gain = gain.ewm(span=period, adjust=False).mean()
            avg_loss = loss.ewm(span=period, adjust=False).mean()
            rs = avg_gain / (avg_loss + 1e-10)
            rsi = 100 - 100 / (1 + rs)

            if index < 1 or pd.isna(rsi.iloc[index]):
                return TradeAction.HOLD

            if action == "buy" and rsi.iloc[index] < threshold:
                return TradeAction.BUY
            elif action == "sell" and rsi.iloc[index] > (100 - threshold):
                return TradeAction.SELL

        return TradeAction.HOLD
