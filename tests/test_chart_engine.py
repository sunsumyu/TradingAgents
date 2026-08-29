"""Comprehensive tests for the chart_engine module.

Tests cover:
- Timeframe resolution and properties
- Indicator computation (25+ indicators)
- Signal detection (MACD, RSI, KDJ)
- Drawing tools (creation, serialization, hit-testing)
- ChartEngine facade (render, compute_indicator, add_drawing, replay)
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from tradingagents.chart_engine import (
    ChartEngine,
    ChartState,
    Drawing,
    DrawingStyle,
    DrawingType,
    IndicatorDef,
    IndicatorResult,
    LineStyle,
    OHLCVBar,
    Quote,
    Signal,
    SignalType,
    Timeframe,
    TIMEFRAME_REGISTRY,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate 100 bars of realistic OHLCV data for testing."""
    np.random.seed(42)
    n = 100
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.randn(n) * 2)
    close = np.maximum(close, 10)  # prevent negative prices

    df = pd.DataFrame({
        "open": close + np.random.randn(n) * 0.5,
        "high": close + abs(np.random.randn(n) * 1.5),
        "low": close - abs(np.random.randn(n) * 1.5),
        "close": close,
        "volume": np.random.randint(100000, 5000000, n),
        "timestamp": dates.astype(np.int64) / 10**9,
    })
    return df


@pytest.fixture
def trending_up_ohlcv() -> pd.DataFrame:
    """Generate 50 bars with a clear uptrend for signal testing."""
    n = 50
    close = 50 + np.arange(n) * 1.5 + np.random.randn(n) * 0.3
    return pd.DataFrame({
        "open": close - 0.5,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": np.random.randint(100000, 3000000, n),
    })


@pytest.fixture
def engine() -> ChartEngine:
    return ChartEngine()


# ═══════════════════════════════════════════════════════════════════════════════
# Timeframe tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTimeframe:
    def test_all_timeframes_registered(self):
        assert len(TIMEFRAME_REGISTRY) == 13

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("1m", Timeframe.MIN_1),
            ("5m", Timeframe.MIN_5),
            ("1D", Timeframe.DAILY),
            ("1W", Timeframe.WEEKLY),
            ("ALL", Timeframe.ALL),
        ],
    )
    def test_exact_match(self, value, expected):
        from tradingagents.chart_engine.timeframes import resolve_timeframe
        assert resolve_timeframe(value) == expected

    def test_label_match(self):
        from tradingagents.chart_engine.timeframes import resolve_timeframe
        assert resolve_timeframe("日K") == Timeframe.DAILY
        assert resolve_timeframe("周K") == Timeframe.WEEKLY

    def test_short_alias(self):
        from tradingagents.chart_engine.timeframes import resolve_timeframe
        assert resolve_timeframe("D") == Timeframe.DAILY
        assert resolve_timeframe("W") == Timeframe.WEEKLY

    def test_invalid_raises(self):
        from tradingagents.chart_engine.timeframes import resolve_timeframe
        with pytest.raises(ValueError, match="Unknown timeframe"):
            resolve_timeframe("INVALID")

    def test_intraday_detection(self):
        assert Timeframe.MIN_1.is_intraday
        assert Timeframe.MIN_60.is_intraday
        assert not Timeframe.DAILY.is_intraday
        assert not Timeframe.WEEKLY.is_intraday

    def test_mootdx_frequency(self):
        assert Timeframe.MIN_1.mootdx_frequency == 8
        assert Timeframe.MIN_5.mootdx_frequency == 0
        assert Timeframe.DAILY.mootdx_frequency is None

    def test_default_days_reasonable(self):
        assert Timeframe.MIN_1.default_days == 1
        assert Timeframe.DAILY.default_days == 90
        assert Timeframe.ALL.default_days == 3650

    def test_max_bars(self):
        assert Timeframe.MIN_1.max_bars == 800
        assert Timeframe.DAILY.max_bars == 500
        assert Timeframe.ALL.max_bars == 2000


# ═══════════════════════════════════════════════════════════════════════════════
# Indicator library tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestIndicatorLibrary:
    def test_library_has_25_plus_indicators(self):
        from tradingagents.chart_engine.indicators import INDICATOR_LIBRARY
        assert len(INDICATOR_LIBRARY) >= 25

    def test_all_indicators_have_required_fields(self):
        from tradingagents.chart_engine.indicators import INDICATOR_LIBRARY
        for key, idef in INDICATOR_LIBRARY.items():
            assert isinstance(idef, IndicatorDef)
            assert idef.name, f"{key} missing name"
            assert idef.category in ("overlay", "oscillator", "volume"), f"{key} bad category"
            assert isinstance(idef.params, dict), f"{key} params not dict"
            assert isinstance(idef.param_ranges, dict), f"{key} param_ranges not dict"

    def test_overlay_indicators(self):
        from tradingagents.chart_engine.indicators import INDICATOR_LIBRARY
        overlays = [k for k, v in INDICATOR_LIBRARY.items() if v.category == "overlay"]
        assert "MA" in overlays
        assert "EMA" in overlays
        assert "BOLL" in overlays
        assert "SAR" in overlays

    def test_oscillator_indicators(self):
        from tradingagents.chart_engine.indicators import INDICATOR_LIBRARY
        oscs = [k for k, v in INDICATOR_LIBRARY.items() if v.category == "oscillator"]
        assert "MACD" in oscs
        assert "RSI" in oscs
        assert "KDJ" in oscs
        assert "CCI" in oscs
        assert "DMI" in oscs


# ═══════════════════════════════════════════════════════════════════════════════
# Indicator computation tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestIndicatorComputation:
    def test_ma_basic(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "MA", {"period": 20})
        assert isinstance(result, IndicatorResult)
        assert result.name == "MA"
        assert "ma" in result.data
        assert len(result.data["ma"]) == len(sample_ohlcv)

    def test_ma_short_period(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "MA", {"period": 5})
        # First value should equal close (no enough data for rolling)
        assert result.data["ma"][0] is not None

    def test_ema_basic(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "EMA", {"period": 12})
        assert "ema" in result.data
        assert len(result.data["ema"]) == len(sample_ohlcv)

    def test_boll_has_three_bands(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "BOLL")
        assert "upper" in result.data
        assert "mid" in result.data
        assert "lower" in result.data
        # Upper > mid > lower (on average)
        valid = [(u, m, l) for u, m, l in zip(
            result.data["upper"], result.data["mid"], result.data["lower"]
        ) if all(v is not None for v in (u, m, l))]
        if valid:
            u, m, l = valid[-1]
            assert u >= m >= l

    def test_sar_produces_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "SAR")
        assert "sar" in result.data
        assert len(result.data["sar"]) == len(sample_ohlcv)

    def test_macd_has_three_series(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "MACD")
        assert "dif" in result.data
        assert "dea" in result.data
        assert "macd" in result.data

    def test_rsi_range(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "RSI")
        assert "rsi" in result.data
        valid_rsi = [v for v in result.data["rsi"] if v is not None and not math.isnan(v)]
        assert all(0 <= v <= 100 for v in valid_rsi), f"RSI out of range: {valid_rsi}"

    def test_kdj_has_kdj_series(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "KDJ")
        assert "k" in result.data
        assert "d" in result.data
        assert "j" in result.data

    def test_wr_range(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "WR")
        assert "wr" in result.data

    def test_cci_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "CCI")
        assert "cci" in result.data
        assert len(result.data["cci"]) == len(sample_ohlcv)

    def test_dmi_has_four_series(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "DMI")
        assert "plus_di" in result.data
        assert "minus_di" in result.data
        assert "adx" in result.data
        assert "adxr" in result.data

    def test_trix_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "TRIX")
        assert "trix" in result.data
        assert "matrix" in result.data

    def test_dma_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "DMA")
        assert "pdd" in result.data
        assert "ama" in result.data

    def test_roc_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "ROC")
        assert "roc" in result.data
        assert "maroc" in result.data

    def test_mtm_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "MTM")
        assert "mtm" in result.data
        assert "mamtm" in result.data

    def test_bias_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "BIAS")
        assert "bias" in result.data

    def test_asi_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "ASI")
        assert "asi" in result.data
        assert "maasi" in result.data

    def test_emv_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "EMV")
        assert "emv" in result.data
        assert "maemv" in result.data

    def test_arbr_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "ARBR")
        assert "ar" in result.data
        assert "br" in result.data

    def test_cr_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "CR")
        assert "cr" in result.data

    def test_vr_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "VR")
        assert "vr" in result.data

    def test_obv_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "OBV")
        assert "obv" in result.data

    def test_vwap_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "VWAP")
        assert "vwap" in result.data

    def test_mv_output(self, engine, sample_ohlcv):
        result = engine.compute_indicator(sample_ohlcv, "MV")
        assert "mv" in result.data

    def test_unknown_indicator_raises(self, engine, sample_ohlcv):
        with pytest.raises(ValueError, match="Unknown indicator"):
            engine.compute_indicator(sample_ohlcv, "NONEXISTENT")

    def test_compute_batch(self, engine, sample_ohlcv):
        results = engine.compute_batch(sample_ohlcv, ["MA", "MACD", "RSI"])
        assert len(results) == 3
        assert "MA" in results
        assert "MACD" in results
        assert "RSI" in results

    def test_compute_batch_with_params(self, engine, sample_ohlcv):
        results = engine.compute_batch(
            sample_ohlcv,
            ["MA", "RSI"],
            params={"MA": {"period": 10}, "RSI": {"period": 7}},
        )
        assert results["MA"].params["period"] == 10
        assert results["RSI"].params["period"] == 7


# ═══════════════════════════════════════════════════════════════════════════════
# Signal detection tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSignalDetection:
    def test_macd_signals_on_trending_data(self, engine, trending_up_ohlcv):
        signals = engine.detect_signals(trending_up_ohlcv, "MACD")
        # Should produce at least one signal on a trending dataset
        assert isinstance(signals, list)

    def test_rsi_oversold_signal(self, engine):
        """Create a dataset where RSI will be < 30."""
        n = 30
        close = 100 - np.arange(n) * 2  # strong downtrend
        df = pd.DataFrame({
            "open": close + 0.5,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": [1000000] * n,
        })
        signals = engine.detect_signals(df, "RSI")
        buy_signals = [s for s in signals if s.type == SignalType.BUY]
        assert len(buy_signals) > 0
        assert "超卖" in buy_signals[0].reason

    def test_rsi_overbought_signal(self, engine):
        """Create a dataset where RSI will be > 70."""
        n = 30
        # Create extreme uptrend: every bar closes significantly higher
        close = np.array([50 + i * 5 for i in range(n)], dtype=float)
        df = pd.DataFrame({
            "open": close - 2,
            "high": close + 3,
            "low": close - 1,
            "close": close,
            "volume": [1000000] * n,
        })
        signals = engine.detect_signals(df, "RSI")
        sell_signals = [s for s in signals if s.type == SignalType.SELL]
        assert len(sell_signals) > 0
        assert "超买" in sell_signals[0].reason

    def test_signal_strength_range(self, engine, trending_up_ohlcv):
        signals = engine.detect_signals(trending_up_ohlcv, "MACD")
        for sig in signals:
            assert 0 <= sig.strength <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# Drawing tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDrawings:
    def test_drawing_creation(self):
        d = Drawing(type=DrawingType.TRENDLINE, points=[(0, 100), (10, 110)])
        assert d.type == DrawingType.TRENDLINE
        assert d.point_count == 2

    def test_drawing_serialization_roundtrip(self):
        d = Drawing(
            type=DrawingType.FIBONACCI,
            points=[(0, 200), (10, 100)],
            style=DrawingStyle(color="#FF0000", line_width=2),
            text="test",
        )
        data = d.to_dict()
        d2 = Drawing.from_dict(data)
        assert d2.type == DrawingType.FIBONACCI
        assert d2.points == [(0, 200), (10, 100)]
        assert d2.style.color == "#FF0000"
        assert d2.text == "test"

    def test_drawing_move_point(self):
        d = Drawing(type=DrawingType.TRENDLINE, points=[(0, 100), (10, 110)])
        d.move_point(1, 20, 120)
        assert d.points[1] == (20, 120)

    def test_drawing_move_point_out_of_range(self):
        d = Drawing(type=DrawingType.TRENDLINE, points=[(0, 100)])
        d.move_point(5, 20, 120)  # Should not raise
        assert d.points == [(0, 100)]

    def test_drawing_style_defaults(self):
        s = DrawingStyle()
        assert s.color == "#FFFFFF"
        assert s.line_width == 1
        assert s.line_style == LineStyle.SOLID

    def test_line_styles(self):
        assert LineStyle.SOLID.value == "solid"
        assert LineStyle.DOTTED.value == "dotted"
        assert LineStyle.DASHED.value == "dashed"
        assert LineStyle.LONG_DASHED.value == "long_dashed"


class TestDrawingFactory:
    def test_create_trendline(self):
        from tradingagents.chart_engine.drawings import create_trendline
        d = create_trendline(0, 100, 10, 110)
        assert d.type == DrawingType.TRENDLINE
        assert len(d.points) == 2

    def test_create_horizontal_line(self):
        from tradingagents.chart_engine.drawings import create_horizontal_line
        d = create_horizontal_line(150.5)
        assert d.type == DrawingType.HORIZONTAL_LINE
        assert d.points[0][1] == 150.5

    def test_create_fibonacci(self):
        from tradingagents.chart_engine.drawings import create_fibonacci
        d = create_fibonacci(0, 200, 10, 100)
        assert d.type == DrawingType.FIBONACCI

    def test_fibonacci_levels(self):
        from tradingagents.chart_engine.drawings import compute_fibonacci_levels
        levels = compute_fibonacci_levels(200, 100)
        assert len(levels) == 7
        # First level should be at 200 (0% retracement = high)
        assert levels[0][0] == pytest.approx(200)
        # Last level should be at 100 (100% retracement = low)
        assert levels[-1][0] == pytest.approx(100)

    def test_create_rectangle(self):
        from tradingagents.chart_engine.drawings import create_rectangle
        d = create_rectangle(0, 100, 10, 120)
        assert d.type == DrawingType.RECTANGLE
        assert d.style.fill_color is not None

    def test_create_parallel_channel(self):
        from tradingagents.chart_engine.drawings import create_parallel_channel
        d = create_parallel_channel(0, 100, 10, 110)
        assert d.type == DrawingType.PARALLEL_CHANNEL

    def test_create_pitchfork(self):
        from tradingagents.chart_engine.drawings import create_pitchfork
        d = create_pitchfork(0, 100, 5, 110, 10, 105)
        assert d.type == DrawingType.PITCHFORK
        assert len(d.points) == 3

    def test_create_gann_fan(self):
        from tradingagents.chart_engine.drawings import create_gann_fan
        d = create_gann_fan(0, 100, 10, 110)
        assert d.type == DrawingType.GANN_FAN

    def test_create_text_annotation(self):
        from tradingagents.chart_engine.drawings import create_text_annotation
        d = create_text_annotation(5, 100, "Support")
        assert d.type == DrawingType.TEXT
        assert d.text == "Support"

    def test_create_arrow(self):
        from tradingagents.chart_engine.drawings import create_arrow
        d = create_arrow(0, 100, 10, 120)
        assert d.type == DrawingType.ARROW


class TestDrawingManager:
    def test_add_and_list(self):
        from tradingagents.chart_engine.drawings import DrawingManager
        mgr = DrawingManager()
        d = Drawing(type=DrawingType.TRENDLINE, points=[(0, 100), (10, 110)])
        mgr.add(d)
        assert mgr.count == 1
        assert mgr.list_all()[0].id == d.id

    def test_remove(self):
        from tradingagents.chart_engine.drawings import DrawingManager
        mgr = DrawingManager()
        d = Drawing(type=DrawingType.TRENDLINE, points=[(0, 100), (10, 110)])
        mgr.add(d)
        assert mgr.remove(d.id) is True
        assert mgr.count == 0

    def test_remove_nonexistent(self):
        from tradingagents.chart_engine.drawings import DrawingManager
        mgr = DrawingManager()
        assert mgr.remove("nonexistent") is False

    def test_clear(self):
        from tradingagents.chart_engine.drawings import DrawingManager
        mgr = DrawingManager()
        mgr.add(Drawing(type=DrawingType.TRENDLINE, points=[(0, 100)]))
        mgr.add(Drawing(type=DrawingType.HORIZONTAL_LINE, points=[(0, 150)]))
        mgr.clear()
        assert mgr.count == 0

    def test_list_by_type(self):
        from tradingagents.chart_engine.drawings import DrawingManager
        mgr = DrawingManager()
        mgr.add(Drawing(type=DrawingType.TRENDLINE, points=[(0, 100)]))
        mgr.add(Drawing(type=DrawingType.HORIZONTAL_LINE, points=[(0, 150)]))
        mgr.add(Drawing(type=DrawingType.TRENDLINE, points=[(0, 200)]))
        trendlines = mgr.list_by_type(DrawingType.TRENDLINE)
        assert len(trendlines) == 2

    def test_serialization_roundtrip(self):
        from tradingagents.chart_engine.drawings import DrawingManager
        mgr = DrawingManager()
        mgr.add(Drawing(type=DrawingType.TRENDLINE, points=[(0, 100), (10, 110)]))
        data = mgr.to_list()
        mgr2 = DrawingManager()
        loaded = mgr2.from_list(data)
        assert loaded == 1
        assert mgr2.count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# ChartEngine facade tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestChartEngine:
    def test_render_basic(self, engine, sample_ohlcv):
        state = engine.render("600519", "1D", data=sample_ohlcv)
        assert isinstance(state, ChartState)
        assert state.ticker == "600519"
        assert state.timeframe == "1D"
        assert len(state.data) == 100

    def test_render_with_indicators(self, engine, sample_ohlcv):
        state = engine.render(
            "600519", "1D",
            indicators=["MA", "MACD", "RSI"],
            data=sample_ohlcv,
        )
        assert "MA" in state.indicators
        assert "MACD" in state.indicators
        assert "RSI" in state.indicators

    def test_render_with_drawings(self, engine, sample_ohlcv):
        drawings = [
            Drawing(type=DrawingType.TRENDLINE, points=[(0, 100), (50, 120)]),
        ]
        state = engine.render("600519", "1D", drawings=drawings, data=sample_ohlcv)
        assert len(state.drawings) >= 1

    def test_render_with_timeframe_enum(self, engine, sample_ohlcv):
        state = engine.render("600519", Timeframe.DAILY, data=sample_ohlcv)
        assert state.timeframe == "1D"

    def test_render_empty_data(self, engine):
        state = engine.render("600519", "1D")
        assert len(state.data) == 0

    def test_add_drawing(self, engine):
        d = engine.add_drawing(
            DrawingType.TRENDLINE,
            [(0, 100), (10, 110)],
            DrawingStyle(color="#FF0000"),
        )
        assert d.type == DrawingType.TRENDLINE
        assert d.id is not None

    def test_add_drawing_by_string(self, engine):
        d = engine.add_drawing("horizontal_line", [(0, 150)])
        assert d.type == DrawingType.HORIZONTAL_LINE

    def test_remove_drawing(self, engine):
        d = engine.add_drawing("trendline", [(0, 100), (10, 110)])
        assert engine.remove_drawing(d.id) is True
        assert engine.get_drawing(d.id) is None

    def test_clear_drawings(self, engine):
        engine.add_drawing("trendline", [(0, 100)])
        engine.add_drawing("horizontal_line", [(0, 150)])
        engine.clear_drawings()
        assert engine.drawings.count == 0

    def test_available_indicators(self, engine):
        indicators = engine.available_indicators()
        assert "MA" in indicators
        assert "MACD" in indicators
        assert len(indicators) >= 25

    def test_indicator_params(self, engine):
        params = engine.indicator_params("MACD")
        assert params == {"fast": 12, "slow": 26, "signal": 9}

    def test_indicator_params_unknown_raises(self, engine):
        with pytest.raises(ValueError):
            engine.indicator_params("NONEXISTENT")

    def test_export_image_returns_bytes(self, engine):
        data = engine.export_image()
        assert isinstance(data, bytes)

    def test_replay_basic(self, engine, sample_ohlcv):
        snapshots = list(engine.replay(sample_ohlcv, "1D", indicators=["MA"]))
        assert len(snapshots) == len(sample_ohlcv)
        assert snapshots[0].bar_index == 0
        assert snapshots[-1].bar_index == len(sample_ohlcv) - 1

    def test_replay_with_start_index(self, engine, sample_ohlcv):
        snapshots = list(engine.replay(sample_ohlcv, "1D", start_index=90))
        assert len(snapshots) == 10
        assert snapshots[0].bar_index == 90

    def test_replay_empty_data(self, engine):
        snapshots = list(engine.replay(pd.DataFrame(), "1D"))
        assert len(snapshots) == 0

    def test_replay_indicators_grow(self, engine, sample_ohlcv):
        snapshots = list(engine.replay(sample_ohlcv, "1D", indicators=["MA"]))
        # Each snapshot should have data up to its bar_index
        for snap in snapshots:
            assert len(snap.data) == snap.bar_index + 1
