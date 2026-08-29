"""Chart Engine — TDX-style chart rendering, indicators, and drawing tools.

Deep module: small interface (ChartEngine class), large implementation
(25+ indicators, 15+ drawing tools, 11 timeframes).

Usage:
    from tradingagents.chart_engine import ChartEngine, Timeframe, DrawingType

    engine = ChartEngine()
    state = engine.render(
        ticker="600519",
        timeframe=Timeframe.DAILY,
        indicators=["MA", "MACD", "RSI"],
        drawings=[],
    )
"""

from .timeframes import Timeframe, TIMEFRAME_REGISTRY
from .indicators import (
    IndicatorDef,
    IndicatorResult,
    Signal,
    SignalType,
    INDICATOR_LIBRARY,
)
from .drawings import (
    Drawing,
    DrawingType,
    DrawingStyle,
    LineStyle,
)
from .renderer import (
    ChartState,
    ChartEngine,
    OHLCVBar,
    Quote,
)

__all__ = [
    # Timeframes
    "Timeframe",
    "TIMEFRAME_REGISTRY",
    # Indicators
    "IndicatorDef",
    "IndicatorResult",
    "Signal",
    "SignalType",
    "INDICATOR_LIBRARY",
    # Drawings
    "Drawing",
    "DrawingType",
    "DrawingStyle",
    "LineStyle",
    # Renderer
    "ChartState",
    "ChartEngine",
    "OHLCVBar",
    "Quote",
]
