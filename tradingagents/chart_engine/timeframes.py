"""K-line timeframe management.

Defines all supported timeframes with their properties (default lookback days,
maximum bars, and display labels). The Timeframe enum is the single source of
truth for timeframe logic throughout the chart engine.
"""

from __future__ import annotations

from enum import Enum


class Timeframe(Enum):
    """Supported K-line timeframes.

    Naming convention: minute bars use ``"Nm"`` format, daily+ use ``"1D"``
    style to avoid ambiguity with numeric values.
    """

    # Intraday
    MIN_1 = "1m"
    MIN_2 = "2m"
    MIN_3 = "3m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    MIN_60 = "60m"

    # Daily+
    DAILY = "1D"
    WEEKLY = "1W"
    MONTHLY = "1M"
    QUARTERLY = "3M"
    YEARLY = "1Y"
    ALL = "ALL"

    @property
    def default_days(self) -> int:
        """Default lookback period in days when loading chart data."""
        return _TIMEFRAME_PROPS[self.value]["days"]

    @property
    def max_bars(self) -> int:
        """Maximum number of bars to return per request."""
        return _TIMEFRAME_PROPS[self.value]["max_bars"]

    @property
    def is_intraday(self) -> bool:
        """True for minute-level timeframes."""
        return self.value.endswith("m")

    @property
    def display_label(self) -> str:
        """Human-readable label for UI display."""
        return _TIMEFRAME_PROPS[self.value]["label"]

    @property
    def mootdx_frequency(self) -> int | None:
        """mootdx frequency code for A-share minute bars, or None for daily+."""
        if not self.is_intraday:
            return None
        return _MOOTDX_FREQ.get(self.value)


# ── Properties table ──────────────────────────────────────────────────────────

_TIMEFRAME_PROPS: dict[str, dict] = {
    "1m":  {"days": 1,    "max_bars": 800, "label": "1分钟"},
    "2m":  {"days": 2,    "max_bars": 800, "label": "2分钟"},
    "3m":  {"days": 3,    "max_bars": 800, "label": "3分钟"},
    "5m":  {"days": 5,    "max_bars": 800, "label": "5分钟"},
    "15m": {"days": 10,   "max_bars": 800, "label": "15分钟"},
    "30m": {"days": 20,   "max_bars": 800, "label": "30分钟"},
    "60m": {"days": 60,   "max_bars": 800, "label": "60分钟"},
    "1D":  {"days": 90,   "max_bars": 500, "label": "日K"},
    "1W":  {"days": 180,  "max_bars": 500, "label": "周K"},
    "1M":  {"days": 365,  "max_bars": 500, "label": "月K"},
    "3M":  {"days": 730,  "max_bars": 500, "label": "季K"},
    "1Y":  {"days": 1825, "max_bars": 500, "label": "年K"},
    "ALL": {"days": 3650, "max_bars": 2000, "label": "全部"},
}

# mootdx frequency codes for A-share minute bars
_MOOTDX_FREQ: dict[str, int] = {
    "1m": 8,
    "5m": 0,
    "15m": 1,
    "30m": 2,
    "60m": 3,
}


# ── Registry ──────────────────────────────────────────────────────────────────

TIMEFRAME_REGISTRY: dict[str, Timeframe] = {tf.value: tf for tf in Timeframe}


def resolve_timeframe(value: str) -> Timeframe:
    """Resolve a string to a Timeframe enum, with fuzzy matching.

    Accepts exact values (``"1D"``), labels (``"日K"``), or short forms
    (``"D"`` for daily, ``"W"`` for weekly).

    Raises:
        ValueError: If the value cannot be resolved to a known timeframe.
    """
    # Exact match
    if value in TIMEFRAME_REGISTRY:
        return TIMEFRAME_REGISTRY[value]

    # Label match
    for tf in Timeframe:
        if tf.display_label == value:
            return tf

    # Short-form aliases
    _ALIASES = {
        "D": Timeframe.DAILY,
        "W": Timeframe.WEEKLY,
        "M": Timeframe.MONTHLY,
        "Q": Timeframe.QUARTERLY,
        "Y": Timeframe.YEARLY,
    }
    if value.upper() in _ALIASES:
        return _ALIASES[value.upper()]

    raise ValueError(
        f"Unknown timeframe {value!r}. "
        f"Valid values: {list(TIMEFRAME_REGISTRY.keys())}"
    )
