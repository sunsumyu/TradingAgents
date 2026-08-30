"""Chart export endpoint — server-side high-DPI PNG rendering.

Provides ``POST /api/chart-export`` for exporting K-line + indicators as PNG
with watermark.  Requires matplotlib: ``pip install "tradingagents[export]"``.
"""

from __future__ import annotations

import logging
from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()

INSTALL_HINT = (
    "pip install 'tradingagents[export]'"
)


class ChartExportRequest(BaseModel):
    """Request body for /api/chart-export."""

    ticker: str = Field(..., description="Stock code, e.g. 600519")
    date: str = Field(..., description="Analysis date YYYY-MM-DD")
    days: int = Field(90, description="Calendar days of history")
    interval: str | None = Field(None, description="Minute interval (1m/5m/15m/30m/60m) or None for daily")
    overlays: list[str] = Field(
        default_factory=lambda: ["ma5", "ma10", "ma20"],
        description="Active indicator overlays to draw",
    )
    ma_params: dict[str, int] = Field(
        default_factory=lambda: {"ma5": 5, "ma10": 10, "ma20": 20, "ma50": 50},
        description="MA period overrides for watermark text",
    )
    width: int = Field(1920, ge=320, le=7680, description="Output width in pixels")
    height: int = Field(1080, ge=240, le=4320, description="Output height in pixels")
    dpi: int = Field(150, ge=72, le=600, description="Output DPI")


def _get_render_fn():
    """Lazy-import the renderer; raises ImportError if matplotlib is missing."""
    from tradingagents_api.chart_export import render_chart_png
    return render_chart_png


@router.post("/api/chart-export")
async def export_chart(request: ChartExportRequest):
    """Export a high-DPI PNG of the K-line chart with indicators and watermark.

    Requires matplotlib: ``pip install "tradingagents[export]"``.
    """
    # 1. Import renderer (raises ImportError → 503 if matplotlib missing)
    try:
        render_chart_png = _get_render_fn()
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Chart export not available: {e}. Install with: {INSTALL_HINT}",
        )

    # 2. Fetch chart data
    try:
        from tradingagents_api.chart_data import build_chart_data
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Chart data module not available: {e}",
        )

    chart = build_chart_data(
        {}, request.ticker, request.date,
        days=request.days, interval=request.interval,
    )

    if chart is None or chart.kline is None:
        raise HTTPException(
            status_code=404,
            detail=f"No chart data available for {request.ticker}",
        )

    kline = chart.kline

    # 3. Convert KlineData pydantic model to dict for the renderer
    kline_dict = {
        "dates": kline.dates,
        "ohlc": kline.ohlc,
        "volumes": kline.volumes,
        "ma5": kline.ma5,
        "ma10": kline.ma10,
        "ma20": kline.ma20,
        "ma50": kline.ma50,
        "ema12": kline.ema12,
        "ema26": kline.ema26,
    }

    # 4. Render
    try:
        png_bytes = render_chart_png(
            kline_data=kline_dict,
            overlays=request.overlays,
            ma_params=request.ma_params,
            ticker=request.ticker,
            timeframe=request.interval or "1D",
            date=request.date,
            width=request.width,
            height=request.height,
            dpi=request.dpi,
        )
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Chart export not available: {e}. Install with: {INSTALL_HINT}",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Chart export failed for %s: %s", request.ticker, e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chart render failed: {e}",
        )

    if not png_bytes:
        raise HTTPException(
            status_code=500,
            detail="Chart render produced empty output",
        )

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{request.ticker}_chart.png"',
        },
    )
