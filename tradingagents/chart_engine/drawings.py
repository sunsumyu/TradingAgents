"""Drawing tools for chart annotation.

Implements 15+ drawing types matching TDX conventions: trendline, horizontal
line, vertical line, rectangle, fibonacci, parallel channel, pitchfork,
Gann fan, arc, ellipse, text annotation, arrow, speed line, time zone line.

All drawings are stored as (time, price) coordinate pairs and rendered
on a canvas overlay on top of the main chart.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum


class DrawingType(Enum):
    """Supported drawing tool types."""

    CROSSHAIR = "crosshair"
    TRENDLINE = "trendline"
    HORIZONTAL_LINE = "horizontal_line"
    VERTICAL_LINE = "vertical_line"
    RECTANGLE = "rectangle"
    FIBONACCI = "fibonacci"
    PARALLEL_CHANNEL = "parallel_channel"
    PITCHFORK = "pitchfork"
    GANN_FAN = "gann_fan"
    ARC = "arc"
    ELLIPSE = "ellipse"
    TEXT = "text"
    ARROW = "arrow"
    SPEED_LINE = "speed_line"
    TIME_ZONE = "time_zone"


class LineStyle(Enum):
    """Line rendering styles."""

    SOLID = "solid"
    DOTTED = "dotted"
    DASHED = "dashed"
    LONG_DASHED = "long_dashed"


@dataclass
class DrawingStyle:
    """Visual style for a drawing element."""

    color: str = "#FFFFFF"
    line_width: int = 1
    line_style: LineStyle = LineStyle.SOLID
    fill_color: str | None = None
    opacity: float = 1.0
    font_size: int = 12


@dataclass
class Drawing:
    """A drawing annotation on the chart.

    Points are (time_index, price) tuples. The time_index is a numeric
    index into the OHLCV data array (not a timestamp), which allows the
    drawing to be re-rendered correctly when the chart scrolls or resizes.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: DrawingType = DrawingType.CROSSHAIR
    points: list[tuple[float, float]] = field(default_factory=list)
    style: DrawingStyle = field(default_factory=DrawingStyle)
    text: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0

    @property
    def point_count(self) -> int:
        return len(self.points)

    def move_point(self, index: int, new_time: float, new_price: float) -> None:
        """Update a single point's coordinates."""
        if 0 <= index < len(self.points):
            self.points[index] = (new_time, new_price)

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            "id": self.id,
            "type": self.type.value,
            "points": self.points,
            "style": {
                "color": self.style.color,
                "line_width": self.style.line_width,
                "line_style": self.style.line_style.value,
                "fill_color": self.style.fill_color,
                "opacity": self.style.opacity,
                "font_size": self.style.font_size,
            },
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Drawing:
        """Deserialize from a dict."""
        style_data = d.get("style", {})
        return cls(
            id=d.get("id", uuid.uuid4().hex[:8]),
            type=DrawingType(d["type"]),
            points=[tuple(p) for p in d.get("points", [])],
            style=DrawingStyle(
                color=style_data.get("color", "#FFFFFF"),
                line_width=style_data.get("line_width", 1),
                line_style=LineStyle(style_data.get("line_style", "solid")),
                fill_color=style_data.get("fill_color"),
                opacity=style_data.get("opacity", 1.0),
                font_size=style_data.get("font_size", 12),
            ),
            text=d.get("text"),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Drawing factory helpers
# ═══════════════════════════════════════════════════════════════════════════════


def create_trendline(
    t1: float, p1: float, t2: float, p2: float, style: DrawingStyle | None = None
) -> Drawing:
    """Create a trendline between two points."""
    return Drawing(
        type=DrawingType.TRENDLINE,
        points=[(t1, p1), (t2, p2)],
        style=style or DrawingStyle(color="#FFD700"),
    )


def create_horizontal_line(
    price: float, t_start: float = 0, t_end: float = 1000, style: DrawingStyle | None = None
) -> Drawing:
    """Create a horizontal line at a given price level."""
    return Drawing(
        type=DrawingType.HORIZONTAL_LINE,
        points=[(t_start, price), (t_end, price)],
        style=style or DrawingStyle(color="#FF6B6B"),
    )


def create_vertical_line(
    time_idx: float, p_bottom: float = 0, p_top: float = 1e9, style: DrawingStyle | None = None
) -> Drawing:
    """Create a vertical line at a given time index."""
    return Drawing(
        type=DrawingType.VERTICAL_LINE,
        points=[(time_idx, p_bottom), (time_idx, p_top)],
        style=style or DrawingStyle(color="#4ECDC4"),
    )


def create_rectangle(
    t1: float, p1: float, t2: float, p2: float, style: DrawingStyle | None = None
) -> Drawing:
    """Create a rectangle from two corner points."""
    return Drawing(
        type=DrawingType.RECTANGLE,
        points=[(t1, p1), (t2, p2)],
        style=style or DrawingStyle(color="#45B7D1", fill_color="rgba(69,183,209,0.15)"),
    )


def create_fibonacci(
    t1: float, p1: float, t2: float, p2: float, style: DrawingStyle | None = None
) -> Drawing:
    """Create Fibonacci retracement levels between two points."""
    return Drawing(
        type=DrawingType.FIBONACCI,
        points=[(t1, p1), (t2, p2)],
        style=style or DrawingStyle(color="#E0E0E0"),
    )


# Standard Fibonacci levels (TDX convention)
FIBONACCI_LEVELS: list[tuple[float, str, str]] = [
    (0.0, "0%", "#FF6B6B"),
    (0.236, "23.6%", "#FFA07A"),
    (0.382, "38.2%", "#FFD700"),
    (0.5, "50%", "#98FB98"),
    (0.618, "61.8%", "#87CEEB"),
    (0.786, "78.6%", "#DDA0DD"),
    (1.0, "100%", "#FF6B6B"),
]


def compute_fibonacci_levels(
    high_price: float, low_price: float
) -> list[tuple[float, str, str]]:
    """Compute Fibonacci retracement price levels.

    Returns list of (price, label, color) tuples.
    """
    diff = high_price - low_price
    return [
        (high_price - level * diff, label, color)
        for level, label, color in FIBONACCI_LEVELS
    ]


def create_parallel_channel(
    t1: float, p1: float, t2: float, p2: float,
    offset: float = 0.02,
    style: DrawingStyle | None = None,
) -> Drawing:
    """Create a parallel channel (upper and lower lines parallel to trendline)."""
    # Store the main trendline + offset for channel width
    return Drawing(
        type=DrawingType.PARALLEL_CHANNEL,
        points=[(t1, p1), (t2, p2)],
        style=style or DrawingStyle(color="#9B59B6"),
        text=str(offset),  # Store channel offset ratio
    )


def create_pitchfork(
    t1: float, p1: float,
    t2: float, p2: float,
    t3: float, p3: float,
    style: DrawingStyle | None = None,
) -> Drawing:
    """Create Andrew's Pitchfork with three pivot points."""
    return Drawing(
        type=DrawingType.PITCHFORK,
        points=[(t1, p1), (t2, p2), (t3, p3)],
        style=style or DrawingStyle(color="#E74C3C"),
    )


def create_gann_fan(
    t1: float, p1: float, t2: float, p2: float, style: DrawingStyle | None = None
) -> Drawing:
    """Create Gann Fan from two points."""
    return Drawing(
        type=DrawingType.GANN_FAN,
        points=[(t1, p1), (t2, p2)],
        style=style or DrawingStyle(color="#F39C12"),
    )


def create_text_annotation(
    t: float, p: float, text: str, style: DrawingStyle | None = None
) -> Drawing:
    """Create a text annotation at a given position."""
    return Drawing(
        type=DrawingType.TEXT,
        points=[(t, p)],
        style=style or DrawingStyle(color="#FFFFFF", font_size=14),
        text=text,
    )


def create_arrow(
    t1: float, p1: float, t2: float, p2: float,
    style: DrawingStyle | None = None,
) -> Drawing:
    """Create an arrow from point 1 to point 2."""
    return Drawing(
        type=DrawingType.ARROW,
        points=[(t1, p1), (t2, p2)],
        style=style or DrawingStyle(color="#2ECC71", line_width=2),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Drawing manager
# ═══════════════════════════════════════════════════════════════════════════════


class DrawingManager:
    """Manage a collection of drawings on the chart.

    Provides add/remove/update/query operations with serialization support.
    """

    def __init__(self) -> None:
        self._drawings: dict[str, Drawing] = {}

    @property
    def count(self) -> int:
        return len(self._drawings)

    def add(self, drawing: Drawing) -> Drawing:
        """Add a drawing and return it (with assigned ID)."""
        self._drawings[drawing.id] = drawing
        return drawing

    def remove(self, drawing_id: str) -> bool:
        """Remove a drawing by ID. Returns True if found and removed."""
        return self._drawings.pop(drawing_id, None) is not None

    def get(self, drawing_id: str) -> Drawing | None:
        """Get a drawing by ID."""
        return self._drawings.get(drawing_id)

    def update(self, drawing: Drawing) -> None:
        """Replace a drawing with updated data."""
        self._drawings[drawing.id] = drawing

    def clear(self) -> None:
        """Remove all drawings."""
        self._drawings.clear()

    def list_all(self) -> list[Drawing]:
        """Return all drawings."""
        return list(self._drawings.values())

    def list_by_type(self, drawing_type: DrawingType) -> list[Drawing]:
        """Return drawings filtered by type."""
        return [d for d in self._drawings.values() if d.type == drawing_type]

    def hit_test(self, time_idx: float, price: float, tolerance: float = 5.0) -> Drawing | None:
        """Find the drawing closest to the given point.

        Args:
            time_idx: Time index coordinate.
            price: Price coordinate.
            tolerance: Maximum distance to consider a hit.

        Returns:
            The closest Drawing within tolerance, or None.
        """
        best: Drawing | None = None
        best_dist = float("inf")

        for drawing in self._drawings.values():
            if drawing.type == DrawingType.CROSSHAIR:
                continue
            for t, p in drawing.points:
                dist = ((t - time_idx) ** 2 + (p - price) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best = drawing

        return best if best_dist <= tolerance else None

    def to_list(self) -> list[dict]:
        """Serialize all drawings to a list of dicts."""
        return [d.to_dict() for d in self._drawings.values()]

    def from_list(self, items: list[dict]) -> int:
        """Load drawings from a list of dicts. Returns count loaded."""
        count = 0
        for item in items:
            try:
                drawing = Drawing.from_dict(item)
                self._drawings[drawing.id] = drawing
                count += 1
            except (KeyError, ValueError):
                continue
        return count
