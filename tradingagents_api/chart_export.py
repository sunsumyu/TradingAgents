"""Server-side chart PNG renderer using matplotlib.

Renders K-line candlestick + volume + MA overlays as a high-DPI PNG with
watermark.  matplotlib is an optional dependency: ``pip install
"tradingagents[export]"``.
"""

from __future__ import annotations

import io
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Lazy import for matplotlib ──────────────────────────────────────────────

_mpl = None


def _get_mpl():
    """Lazy-import matplotlib; raise ImportError with install hint if missing."""
    global _mpl
    if _mpl is None:
        try:
            import matplotlib as mpl
            _mpl = mpl
        except ImportError:
            raise ImportError(
                "matplotlib is not installed. Install with: "
                "pip install 'tradingagents[export]'"
            )
    return _mpl


# ── Color constants (mirror tradingview/chart-theme.ts) ─────────────────────

COLOR_UP = "#089981"
COLOR_DOWN = "#F23645"
COLOR_BG = "#131722"
COLOR_GRID = "#1E222D"
COLOR_LABEL = "#787B86"
COLOR_VOLUME_UP = (38 / 255, 166 / 255, 154 / 255, 0.5)
COLOR_VOLUME_DOWN = (242 / 255, 54 / 255, 69 / 255, 0.5)

OVERLAY_COLORS: dict[str, str] = {
    "ma5": "#2962FF",
    "ma10": "#FF6D00",
    "ma20": "#9B59B6",
    "ma50": "#F7B731",
    "ema12": "#089981",
    "ema26": "#F23645",
}

# Overlay keys → default MA period labels for watermark
_OVERLAY_LABELS: dict[str, str] = {
    "ma5": "MA5",
    "ma10": "MA10",
    "ma20": "MA20",
    "ma50": "MA50",
    "ema12": "EMA12",
    "ema26": "EMA26",
}


def render_chart_png(
    kline_data: dict[str, Any],
    overlays: list[str] | None = None,
    ma_params: dict[str, int] | None = None,
    ticker: str = "",
    timeframe: str = "1D",
    date: str = "",
    width: int = 1920,
    height: int = 1080,
    dpi: int = 150,
) -> bytes:
    """Render a K-line chart to PNG bytes.

    Args:
        kline_data: KlineData-like dict with keys: dates, ohlc, volumes,
            ma5, ma10, ma20, ma50, ema12, ema26.
        overlays: List of overlay keys to draw (e.g. ["ma5", "ma10"]).
        ma_params: MA period overrides for watermark (e.g. {"ma5": 5}).
        ticker: Stock symbol for the watermark.
        timeframe: "1D", "60m", etc.
        date: Analysis date for the watermark.
        width: Image width in pixels.
        height: Image height in pixels.
        dpi: Output DPI.

    Returns:
        PNG image bytes.

    Raises:
        ImportError: If matplotlib is not installed.
        ValueError: If kline_data is empty or missing required keys.
    """
    mpl = _get_mpl()
    # Use non-interactive backend for server-side rendering
    mpl.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import FancyBboxPatch
    from datetime import datetime

    # ── Validate input ────────────────────────────────────────────────────
    dates_raw = kline_data.get("dates", [])
    ohlc = kline_data.get("ohlc", [])
    volumes = kline_data.get("volumes", [])

    if not dates_raw or not ohlc:
        raise ValueError("Kline data is empty — nothing to render")

    n = len(dates_raw)
    # Parse dates
    dates: list[datetime] = []
    for d in dates_raw:
        try:
            dates.append(datetime.strptime(d, "%Y-%m-%d"))
        except (ValueError, TypeError):
            dates.append(datetime(2000, 1, 1))

    opens = [c[0] for c in ohlc]
    closes = [c[1] for c in ohlc]
    lows = [c[2] for c in ohlc]
    highs = [c[3] for c in ohlc]

    # ── Figure setup ──────────────────────────────────────────────────────
    fig_w = width / dpi
    fig_h = height / dpi
    fig, (ax_price, ax_vol) = plt.subplots(
        2, 1, figsize=(fig_w, fig_h), dpi=dpi,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.02},
        facecolor=COLOR_BG,
    )

    for ax in (ax_price, ax_vol):
        ax.set_facecolor(COLOR_BG)
        ax.tick_params(colors=COLOR_LABEL, labelsize=8)
        ax.grid(True, color=COLOR_GRID, linewidth=0.5, alpha=0.8)
        for spine in ax.spines.values():
            spine.set_color(COLOR_GRID)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.label.set_color(COLOR_LABEL)

    ax_vol.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax_vol.xaxis.set_major_locator(mdates.AutoDateLocator())

    x = list(range(n))

    # ── Candlesticks (bars with wicks) ───────────────────────────────────
    bar_width = max(0.4, min(0.8, 20 / n))

    for i in range(n):
        o, c, l, h = opens[i], closes[i], lows[i], highs[i]
        color = COLOR_UP if c >= o else COLOR_DOWN
        # Body
        body_height = abs(c - o) or (h - l) * 0.01  # avoid zero-height
        body_bottom = min(o, c)
        ax_price.bar(
            i, body_height, bottom=body_bottom, width=bar_width,
            color=color, edgecolor=color, linewidth=0.3,
        )
        # Wicks
        ax_price.vlines(i, l, h, color=color, linewidth=0.6)

    # ── MA overlays ───────────────────────────────────────────────────────
    overlays = overlays or []
    overlay_arrays: dict[str, list[float | None]] = {
        "ma5": kline_data.get("ma5", []),
        "ma10": kline_data.get("ma10", []),
        "ma20": kline_data.get("ma20", []),
        "ma50": kline_data.get("ma50", []),
        "ema12": kline_data.get("ema12", []),
        "ema26": kline_data.get("ema26", []),
    }

    for key in overlays:
        series = overlay_arrays.get(key, [])
        if not series:
            continue
        color = OVERLAY_COLORS.get(key, COLOR_LABEL)
        # Pad or truncate to match n
        padded: list[float | None] = series[:n] + [None] * max(0, n - len(series))
        # Plot with gaps for None
        ys: list[float | None] = []
        for v in padded:
            ys.append(float(v) if v is not None else None)
        ax_price.plot(
            x, ys, color=color, linewidth=1.0, alpha=0.9,
            label=_OVERLAY_LABELS.get(key, key.upper()),
        )

    # ── Volume bars ───────────────────────────────────────────────────────
    if volumes and len(volumes) >= n:
        for i in range(n):
            o, c = opens[i], closes[i]
            color = COLOR_VOLUME_UP if c >= o else COLOR_VOLUME_DOWN
            ax_vol.bar(i, volumes[i], width=bar_width, color=color)

    # ── Price axis range padding ──────────────────────────────────────────
    all_lows = [lo for lo in lows if lo > 0]
    all_highs = [hi for hi in highs if hi > 0]
    if all_lows and all_highs:
        pmin = min(all_lows)
        pmax = max(all_highs)
        margin = (pmax - pmin) * 0.05 or pmax * 0.01
        ax_price.set_ylim(pmin - margin, pmax + margin)

    # ── X axis: hide date labels on the upper subplot to reduce clutter ───
    ax_price.set_xticklabels([])
    ax_vol.tick_params(axis="x", rotation=45)

    # ── Watermark ─────────────────────────────────────────────────────────
    watermark_parts = [ticker]
    if timeframe:
        watermark_parts.append(timeframe)

    # Build MA params text from active overlays
    if ma_params and overlays:
        param_parts = []
        for key in overlays:
            label = _OVERLAY_LABELS.get(key, key.upper())
            period = ma_params.get(key)
            if period is not None:
                param_parts.append(f"{label}:{period}")
            else:
                param_parts.append(label)
        watermark_parts.append(" ".join(param_parts))

    if date:
        watermark_parts.append(date)

    watermark_text = " | ".join(watermark_parts)

    fig.text(
        0.98, 0.97, watermark_text,
        ha="right", va="top",
        fontsize=10, color="white", alpha=0.6,
        fontfamily="monospace",
        transform=fig.transFigure,
    )

    # ── Render to PNG ─────────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=COLOR_BG,
                bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    return buf.getvalue()
