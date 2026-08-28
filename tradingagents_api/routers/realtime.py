"""Realtime price endpoints (HTTP + WebSocket)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..realtime import fetch_realtime_prices
from ..schemas import RealtimePriceItem, RealtimePriceRequest

router = APIRouter()
logger = logging.getLogger(__name__)

# Push interval for /ws/realtime (seconds).
_WS_PUSH_INTERVAL_S = 3.0


@router.post("/api/realtime-prices", response_model=dict[str, RealtimePriceItem])
async def get_realtime_prices(request: RealtimePriceRequest) -> dict[str, RealtimePriceItem]:
    """Batch realtime quotes for the watchlist (polled every ~5s by the GUI)."""
    return fetch_realtime_prices(request.tickers)


@router.websocket("/ws/realtime")
async def realtime_prices_ws(websocket: WebSocket):
    """Push realtime quotes to the GUI over WebSocket (ticket 11).

    Protocol:
      Client -> Server: {"tickers": ["600519", "AAPL"]} on connect;
                        re-sending the full list updates the subscription.
      Server -> Client: {ticker: {price, change, changePct, name}, ...}
                        pushed every ~3 seconds.
    """
    await websocket.accept()
    tickers: list[str] = []
    try:
        data = await websocket.receive_json()
        if isinstance(data, dict) and isinstance(data.get("tickers"), list):
            tickers = [str(t) for t in data["tickers"]]

        while True:
            if tickers:
                prices = await asyncio.to_thread(fetch_realtime_prices, tickers)
                await websocket.send_json({k: v.model_dump() for k, v in prices.items()})
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=_WS_PUSH_INTERVAL_S
                )
                if isinstance(data, dict) and isinstance(data.get("tickers"), list):
                    tickers = [str(t) for t in data["tickers"]]
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("realtime websocket ended: %s", exc)
        try:
            await websocket.close()
        except Exception:
            pass
