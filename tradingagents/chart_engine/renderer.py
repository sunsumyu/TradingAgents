"""Chart renderer and main ChartEngine facade.

The ChartEngine is the deep module's public interface — a small surface
that hides indicator computation, drawing management, and data orchestration
behind five methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

import pandas as pd

from .drawings import Drawing, DrawingManager, DrawingStyle, DrawingType
from .indicators import INDICATOR_LIBRARY, IndicatorComputer, IndicatorResult, Signal
from .timeframes import Timeframe


# ═══════════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class OHLCVBar:
    """Single OHLCV bar."""

    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float = 0.0
    turnover: float = 0.0
    adjust_factor: float = 1.0


@dataclass
class Quote:
    """Real-time quote for a single ticker."""

    ticker: str
    name: str
    price: float
    change: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: int
    amount: float
    bid_prices: list[float] = field(default_factory=list)
    ask_prices: list[float] = field(default_factory=list)
    bid_volumes: list[int] = field(default_factory=list)
    ask_volumes: list[int] = field(default_factory=list)
    timestamp: float = 0.0


@dataclass
class ChartState:
    """Complete chart rendering state returned by ChartEngine.render()."""

    ticker: str
    timeframe: str
    data: pd.DataFrame
    indicators: dict[str, IndicatorResult]
    drawings: list[Drawing]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChartSnapshot:
    """A single frame during K-line replay."""

    bar_index: int
    data: pd.DataFrame  # data up to and including the current bar
    indicators: dict[str, IndicatorResult]
    timestamp: float


# ═══════════════════════════════════════════════════════════════════════════════
# ChartEngine — the deep module facade
# ═══════════════════════════════════════════════════════════════════════════════


class ChartEngine:
    """TDX-style chart engine — deep module with small interface.

    Interface (5 methods)::

        engine = ChartEngine()
        state = engine.render(ticker, timeframe, indicators, drawings)
        result = engine.compute_indicator(data, "MACD", params)
        drawing = engine.add_drawing(type, points, style)
        png = engine.export_image("png", 1920, 1080)
        for snap in engine.replay(ticker, timeframe): ...

    Implementation hides: 25+ indicator formulas, drawing hit-testing,
    image compositing, replay state machine, and data caching.
    """

    def __init__(self) -> None:
        self._indicator_computer = IndicatorComputer()
        self._drawing_manager = DrawingManager()

    # ── Public interface ──────────────────────────────────────────────────

    def render(
        self,
        ticker: str,
        timeframe: str | Timeframe,
        indicators: list[str] | None = None,
        drawings: list[Drawing] | None = None,
        data: pd.DataFrame | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChartState:
        """Render a complete chart state.

        Args:
            ticker: Stock ticker symbol.
            timeframe: Chart timeframe (string or Timeframe enum).
            indicators: List of indicator keys to compute (e.g., ["MA", "MACD"]).
            drawings: Drawing annotations to include.
            data: Pre-loaded OHLCV DataFrame. If None, an empty frame is used.
            metadata: Extra metadata (stock name, industry, etc.).

        Returns:
            ChartState with all data needed for frontend rendering.
        """
        if isinstance(timeframe, str):
            timeframe = Timeframe(timeframe)

        if data is None:
            data = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # Compute requested indicators
        indicator_results: dict[str, IndicatorResult] = {}
        if indicators:
            for ind_key in indicators:
                if ind_key in INDICATOR_LIBRARY:
                    try:
                        result = self._indicator_computer.compute(data, ind_key)
                        indicator_results[ind_key] = result
                    except Exception:
                        # Skip indicators that fail on insufficient data
                        pass

        # Merge provided drawings with the drawing manager's state
        all_drawings = list(drawings or [])
        all_drawings.extend(self._drawing_manager.list_all())

        return ChartState(
            ticker=ticker,
            timeframe=timeframe.value,
            data=data,
            indicators=indicator_results,
            drawings=all_drawings,
            metadata=metadata or {},
        )

    def compute_indicator(
        self,
        data: pd.DataFrame,
        indicator: str,
        params: dict[str, Any] | None = None,
    ) -> IndicatorResult:
        """Compute a single technical indicator.

        Args:
            data: OHLCV DataFrame.
            indicator: Indicator key (e.g., "MACD", "RSI", "KDJ").
            params: Parameter overrides.

        Returns:
            IndicatorResult with data series and signals.

        Raises:
            ValueError: If indicator is unknown.
        """
        return self._indicator_computer.compute(data, indicator, params)

    def compute_batch(
        self,
        data: pd.DataFrame,
        indicators: list[str],
        params: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, IndicatorResult]:
        """Compute multiple indicators in one call."""
        return self._indicator_computer.compute_batch(data, indicators, params)

    def detect_signals(
        self,
        data: pd.DataFrame,
        indicator: str,
        params: dict[str, Any] | None = None,
    ) -> list[Signal]:
        """Compute indicator and return only its trading signals."""
        return self._indicator_computer.detect_signals(data, indicator, params)

    def add_drawing(
        self,
        drawing_type: DrawingType | str,
        points: list[tuple[float, float]],
        style: DrawingStyle | None = None,
        text: str | None = None,
    ) -> Drawing:
        """Add a drawing annotation to the chart.

        Args:
            drawing_type: Type of drawing (enum or string value).
            points: List of (time_index, price) coordinate pairs.
            style: Visual style (color, width, etc.).
            text: Optional text content (for TEXT type).

        Returns:
            The created Drawing object with assigned ID.
        """
        if isinstance(drawing_type, str):
            drawing_type = DrawingType(drawing_type)

        drawing = Drawing(
            type=drawing_type,
            points=points,
            style=style or DrawingStyle(),
            text=text,
        )
        return self._drawing_manager.add(drawing)

    def export_image(
        self,
        format: str = "png",
        width: int = 1920,
        height: int = 1080,
    ) -> bytes:
        """Export the current chart view as an image.

        Args:
            format: Image format ("png" or "jpeg").
            width: Image width in pixels.
            height: Image height in pixels.

        Returns:
            Raw image bytes.

        Note:
            This is a placeholder that returns empty bytes. The actual
            rendering is delegated to the frontend ECharts canvas export.
            Backend export can be added via matplotlib if needed.
        """
        # Placeholder — real implementation would use matplotlib or
        # a headless browser to rasterize the ECharts output.
        return b""

    def replay(
        self,
        data: pd.DataFrame,
        timeframe: str | Timeframe,
        indicators: list[str] | None = None,
        speed: float = 1.0,
        start_index: int = 0,
    ) -> Iterator[ChartSnapshot]:
        """Replay historical bars one at a time.

        Args:
            data: Full OHLCV dataset.
            timeframe: Chart timeframe.
            indicators: Indicators to compute at each step.
            speed: Playback speed multiplier (not used in sync iteration).
            start_index: Bar index to start replay from.

        Yields:
            ChartSnapshot for each bar, with indicators computed on data
            up to that bar.
        """
        if isinstance(timeframe, str):
            timeframe = Timeframe(timeframe)

        if data.empty:
            return

        total_bars = len(data)
        for i in range(start_index, total_bars):
            # Slice data up to current bar (inclusive)
            slice_data = data.iloc[: i + 1].copy()

            indicator_results: dict[str, IndicatorResult] = {}
            if indicators:
                for ind_key in indicators:
                    if ind_key in INDICATOR_LIBRARY:
                        try:
                            result = self._indicator_computer.compute(slice_data, ind_key)
                            indicator_results[ind_key] = result
                        except Exception:
                            pass

            # Extract timestamp from the index or use bar position
            ts = 0.0
            if "timestamp" in slice_data.columns:
                ts = float(slice_data["timestamp"].iloc[-1])
            elif hasattr(slice_data.index, "astype"):
                try:
                    ts = float(slice_data.index[-1])
                except (TypeError, ValueError):
                    ts = float(i)

            yield ChartSnapshot(
                bar_index=i,
                data=slice_data,
                indicators=indicator_results,
                timestamp=ts,
            )

    # ── Drawing manager delegation ────────────────────────────────────────

    @property
    def drawings(self) -> DrawingManager:
        """Access the drawing manager for direct manipulation."""
        return self._drawing_manager

    def remove_drawing(self, drawing_id: str) -> bool:
        """Remove a drawing by ID."""
        return self._drawing_manager.remove(drawing_id)

    def clear_drawings(self) -> None:
        """Remove all drawings."""
        self._drawing_manager.clear()

    def get_drawing(self, drawing_id: str) -> Drawing | None:
        """Get a drawing by ID."""
        return self._drawing_manager.get(drawing_id)

    # ── Utility ───────────────────────────────────────────────────────────

    @staticmethod
    def available_indicators() -> dict[str, str]:
        """Return a dict of indicator_key → Chinese name."""
        return {k: v.name for k, v in INDICATOR_LIBRARY.items()}

    @staticmethod
    def indicator_params(indicator: str) -> dict[str, Any]:
        """Return the default parameters for an indicator."""
        if indicator not in INDICATOR_LIBRARY:
            raise ValueError(f"Unknown indicator {indicator!r}")
        return dict(INDICATOR_LIBRARY[indicator].params)
