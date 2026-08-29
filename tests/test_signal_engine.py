"""Unit tests for the signal_engine module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from tradingagents.signal_engine import (
    Alert,
    AlertCondition,
    CompositeSignal,
    Signal,
    SignalEngine,
    SignalStrength,
    SignalType,
    Strategy,
    StrategyResult,
    TradeAction,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    """Generate 100 bars of OHLCV data."""
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 2)
    close = np.maximum(close, 10)
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=n, freq="D"),
        "open": close + np.random.randn(n) * 0.5,
        "high": close + abs(np.random.randn(n) * 1.5),
        "low": close - abs(np.random.randn(n) * 1.5),
        "close": close,
        "volume": np.random.randint(100000, 5000000, n),
    })


@pytest.fixture
def signal_engine():
    """Create a SignalEngine with mocked dependencies."""
    engine = SignalEngine.__new__(SignalEngine)
    engine._chart = MagicMock()
    engine._data = MagicMock()
    engine._alerts = {}
    return engine


# ═══════════════════════════════════════════════════════════════════════════════
# Model tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestModels:
    def test_signal_creation(self):
        sig = Signal(
            type=SignalType.BUY,
            strength=80.0,
            indicator="MACD",
            reason="Golden cross",
        )
        assert sig.type == SignalType.BUY
        assert sig.strength == 80.0

    def test_composite_signal(self):
        cs = CompositeSignal(
            ticker="600519",
            timeframe="1D",
            signals=[],
            composite_score=72.5,
            recommendation="BUY",
            confidence=65.0,
        )
        assert cs.recommendation == "BUY"
        assert cs.composite_score == 72.5

    def test_strategy_creation(self):
        strat = Strategy(
            name="MA Crossover",
            description="Buy when MA5 > MA20",
            indicators=["MA"],
            rules=[{"type": "ma_cross", "fast": 5, "slow": 20, "action": "buy"}],
        )
        assert strat.name == "MA Crossover"
        assert len(strat.rules) == 1

    def test_alert_creation(self):
        alert = Alert(
            id="abc123",
            ticker="600519",
            condition=AlertCondition.PRICE_ABOVE,
            threshold=1800.0,
            message="Price above 1800",
        )
        assert alert.ticker == "600519"
        assert alert.threshold == 1800.0


# ═══════════════════════════════════════════════════════════════════════════════
# SignalEngine tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSignalEngine:
    def test_compute_signals_empty_data(self, signal_engine):
        signal_engine._data.get_ohlcv.return_value = pd.DataFrame()
        result = signal_engine.compute_signals("600519", "1D")
        assert result.recommendation == "HOLD"
        assert result.confidence == 0.0

    def test_compute_signals_with_data(self, signal_engine, sample_ohlcv_df):
        signal_engine._data.get_ohlcv.return_value = sample_ohlcv_df
        # Mock chart engine to return no signals
        signal_engine._chart.compute_indicator.return_value = MagicMock(
            signals=[], data={"rsi": [50.0], "dif": [0.0], "dea": [0.0]}
        )
        result = signal_engine.compute_signals("600519", "1D", ["MACD", "RSI"])
        assert isinstance(result, CompositeSignal)
        assert result.ticker == "600519"
        assert 0 <= result.composite_score <= 100

    def test_run_strategy_returns_result(self, signal_engine, sample_ohlcv_df):
        signal_engine._data.get_ohlcv.return_value = sample_ohlcv_df
        strategy = Strategy(name="Test", description="Test strategy")
        result = signal_engine.run_strategy(
            strategy, "600519", "1D", "2025-01-01", "2025-04-10"
        )
        assert isinstance(result, StrategyResult)
        assert result.strategy_name == "Test"

    def test_run_strategy_empty_data(self, signal_engine):
        signal_engine._data.get_ohlcv.return_value = pd.DataFrame()
        strategy = Strategy(name="Test", description="Test")
        result = signal_engine.run_strategy(
            strategy, "600519", "1D", "2025-01-01", "2025-04-10"
        )
        assert result.total_trades == 0
        assert result.total_return == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Alert tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlertConditionsComplete:
    """All 7 AlertCondition types are evaluable (ticket #4)."""

    def test_indicator_above_triggers(self, signal_engine):
        signal_engine.add_alert(
            "600519", AlertCondition.INDICATOR_BELOW, 30.0, indicator="RSI"
        )
        triggered = signal_engine.check_alerts(
            "600519", 1800.0, indicator_values={"RSI": 25.0}
        )
        assert len(triggered) == 1
        assert triggered[0].condition == AlertCondition.INDICATOR_BELOW

    def test_indicator_above_no_trigger(self, signal_engine):
        signal_engine.add_alert(
            "600519", AlertCondition.INDICATOR_ABOVE, 80.0, indicator="RSI"
        )
        triggered = signal_engine.check_alerts(
            "600519", 1800.0, indicator_values={"RSI": 55.0}
        )
        assert triggered == []

    def test_indicator_missing_value_skips(self, signal_engine):
        """No indicator data -> skip silently, alert stays armed."""
        alert = signal_engine.add_alert(
            "600519", AlertCondition.INDICATOR_ABOVE, 80.0, indicator="RSI"
        )
        triggered = signal_engine.check_alerts("600519", 1800.0, indicator_values=None)
        assert triggered == []
        assert alert.triggered is False
        # And still triggers once the value arrives
        triggered = signal_engine.check_alerts(
            "600519", 1800.0, indicator_values={"RSI": 85.0}
        )
        assert len(triggered) == 1

    def test_cross_above_arms_then_triggers(self, signal_engine):
        """First check arms the baseline; a genuine upward cross triggers."""
        signal_engine.add_alert(
            "600519", AlertCondition.CROSS_ABOVE, 0.0, indicator="MA20"
        )
        # Below the line: baseline stored, no trigger
        assert signal_engine.check_alerts(
            "600519", 1750.0, indicator_values={"MA20": 1800.0}
        ) == []
        # Still below: no trigger
        assert signal_engine.check_alerts(
            "600519", 1790.0, indicator_values={"MA20": 1800.0}
        ) == []
        # Cross above: trigger
        triggered = signal_engine.check_alerts(
            "600519", 1815.0, indicator_values={"MA20": 1800.0}
        )
        assert len(triggered) == 1
        assert triggered[0].condition == AlertCondition.CROSS_ABOVE

    def test_cross_below_triggers(self, signal_engine):
        signal_engine.add_alert(
            "600519", AlertCondition.CROSS_BELOW, 0.0, indicator="MA20"
        )
        signal_engine.check_alerts("600519", 1850.0, indicator_values={"MA20": 1800.0})
        triggered = signal_engine.check_alerts(
            "600519", 1780.0, indicator_values={"MA20": 1800.0}
        )
        assert len(triggered) == 1
        assert triggered[0].condition == AlertCondition.CROSS_BELOW

    def test_disabled_alert_skipped(self, signal_engine):
        alert = signal_engine.add_alert("600519", AlertCondition.PRICE_ABOVE, 1800.0)
        signal_engine.set_alert_enabled(alert.id, False)
        assert signal_engine.check_alerts("600519", 1900.0) == []
        signal_engine.set_alert_enabled(alert.id, True)
        assert len(signal_engine.check_alerts("600519", 1900.0)) == 1

    def test_alert_to_dict(self, signal_engine):
        alert = signal_engine.add_alert(
            "600519", AlertCondition.INDICATOR_BELOW, 30.0,
            indicator="RSI", message="超卖",
        )
        d = alert.to_dict()
        assert d["condition"] == "indicator_below"
        assert d["indicator"] == "RSI"
        assert d["enabled"] is True


class TestAlerts:
    def test_add_alert(self, signal_engine):
        alert = signal_engine.add_alert(
            "600519", AlertCondition.PRICE_ABOVE, 1800.0, "Test alert"
        )
        assert alert.id is not None
        assert alert.ticker == "600519"

    def test_remove_alert(self, signal_engine):
        alert = signal_engine.add_alert("600519", AlertCondition.PRICE_ABOVE, 1800.0)
        assert signal_engine.remove_alert(alert.id) is True
        assert signal_engine.get_alerts() == []

    def test_check_alerts_triggers(self, signal_engine):
        signal_engine.add_alert("600519", AlertCondition.PRICE_ABOVE, 1800.0)
        triggered = signal_engine.check_alerts("600519", 1850.0)
        assert len(triggered) == 1
        assert triggered[0].triggered is True

    def test_check_alerts_no_trigger(self, signal_engine):
        signal_engine.add_alert("600519", AlertCondition.PRICE_ABOVE, 1800.0)
        triggered = signal_engine.check_alerts("600519", 1750.0)
        assert len(triggered) == 0

    def test_check_alerts_price_below(self, signal_engine):
        signal_engine.add_alert("600519", AlertCondition.PRICE_BELOW, 1500.0)
        triggered = signal_engine.check_alerts("600519", 1450.0)
        assert len(triggered) == 1

    def test_check_alerts_wrong_ticker(self, signal_engine):
        signal_engine.add_alert("600519", AlertCondition.PRICE_ABOVE, 1800.0)
        triggered = signal_engine.check_alerts("000001", 2000.0)
        assert len(triggered) == 0

    def test_clear_alerts(self, signal_engine):
        signal_engine.add_alert("600519", AlertCondition.PRICE_ABOVE, 1800.0)
        signal_engine.add_alert("000001", AlertCondition.PRICE_ABOVE, 15.0)
        cleared = signal_engine.clear_alerts("600519")
        assert cleared == 1
        assert len(signal_engine.get_alerts()) == 1

    def test_clear_all_alerts(self, signal_engine):
        signal_engine.add_alert("600519", AlertCondition.PRICE_ABOVE, 1800.0)
        signal_engine.add_alert("000001", AlertCondition.PRICE_ABOVE, 15.0)
        cleared = signal_engine.clear_alerts()
        assert cleared == 2
        assert len(signal_engine.get_alerts()) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Scoring tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestScoring:
    def test_score_to_recommendation_buy(self, signal_engine):
        assert signal_engine._score_to_recommendation(70) == "BUY"

    def test_score_to_recommendation_sell(self, signal_engine):
        assert signal_engine._score_to_recommendation(30) == "SELL"

    def test_score_to_recommendation_hold(self, signal_engine):
        assert signal_engine._score_to_recommendation(50) == "HOLD"

    def test_composite_score_with_weights(self, signal_engine):
        scores = {"MACD": 80.0, "RSI": 60.0, "KDJ": 70.0}
        score = signal_engine._compute_composite_score(scores)
        assert 50 < score < 80  # Weighted average

    def test_confidence_high_agreement(self, signal_engine):
        scores = {"MACD": 80.0, "RSI": 82.0, "KDJ": 78.0}
        conf = signal_engine._compute_confidence(scores)
        assert conf > 80  # High agreement

    def test_confidence_low_agreement(self, signal_engine):
        scores = {"MACD": 20.0, "RSI": 80.0, "KDJ": 50.0}
        conf = signal_engine._compute_confidence(scores)
        assert conf < 60  # Low agreement
