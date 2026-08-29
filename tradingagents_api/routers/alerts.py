"""Price/indicator alert endpoints (ticket #4)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..alerts import (
    AlertOut,
    check_alerts,
    create_alert,
    delete_alert,
    get_alert_history,
    list_alerts,
    set_alert_enabled,
)
from ..schemas import AlertCheckRequest, AlertCreateRequest, AlertEnabledRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/alerts", response_model=list[AlertOut])
async def get_alerts(ticker: str | None = None):
    """List alert rules, optionally filtered by ticker."""
    try:
        return list_alerts(ticker)
    except Exception as exc:
        logger.error("Failed to list alerts: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/alerts", response_model=AlertOut)
async def post_alert(request: AlertCreateRequest):
    """Create an alert rule."""
    try:
        return create_alert(
            ticker=request.ticker,
            condition=request.condition,
            threshold=request.threshold,
            indicator=request.indicator,
            message=request.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to create alert: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/api/alerts/{alert_id}")
async def remove_alert(alert_id: str):
    """Delete an alert rule and its trigger history."""
    try:
        return {"deleted": delete_alert(alert_id)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/alerts/{alert_id}/enabled", response_model=AlertOut)
async def post_alert_enabled(alert_id: str, request: AlertEnabledRequest):
    """Enable or disable an alert (re-enabling re-arms it)."""
    try:
        alert = set_alert_enabled(alert_id, request.enabled)
        if alert is None:
            raise HTTPException(status_code=404, detail=f"预警不存在: {alert_id}")
        return alert
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/alerts/{alert_id}/history")
async def get_history(alert_id: str):
    """Trigger history for one alert, newest first."""
    try:
        return get_alert_history(alert_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/api/alerts/check")
async def post_check(request: AlertCheckRequest):
    """Evaluate armed alerts for a ticker against the latest quote.

    Driven by the GUI's realtime loop; indicator conditions need the
    current indicator readings via ``indicator_values``.
    """
    try:
        triggered = check_alerts(
            ticker=request.ticker,
            price=request.price,
            volume=request.volume,
            indicator_values=request.indicator_values,
        )
        return {"ticker": request.ticker, "triggered": triggered}
    except Exception as exc:
        logger.error("Alert check failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
