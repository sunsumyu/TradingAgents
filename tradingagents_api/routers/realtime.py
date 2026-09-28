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
    """Batch realtime quotes for the watchlist (polled every ~5s by the GUI).

    PG cache with 5s TTL — prevents redundant API calls when GUI polls
    the same tickers multiple times within a few seconds.
    """
    from tradingagents.cache.manager import get_cache
    import time

    logger.info("HTTP realtime request for tickers: %s", request.tickers)

    # Use a fixed ticker key for realtime (not per-stock)
    mgr = get_cache("__realtime__")
    tickers_key = ",".join(sorted(request.tickers))

    def _source():
        result = fetch_realtime_prices(request.tickers)
        return {k: v.model_dump() for k, v in result.items()}

    with mgr.fetch("realtime", tickers_key, source_fn=_source) as (data, hit):
        if hit and isinstance(data, dict):
            logger.info("HTTP realtime cache hit for %s", tickers_key)
            return {k: RealtimePriceItem(**v) for k, v in data.items()}
        logger.info("HTTP realtime cache miss, fetched fresh data for %s", tickers_key)
        return data


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
    logger.info("WebSocket client connected")
    tickers: list[str] = []
    push_count = 0
    try:
        data = await websocket.receive_json()
        if isinstance(data, dict) and isinstance(data.get("tickers"), list):
            tickers = [str(t) for t in data["tickers"]]
            logger.info("WebSocket subscription: %s", tickers)

        while True:
            if tickers:
                try:
                    prices = await asyncio.to_thread(fetch_realtime_prices, tickers)
                    await websocket.send_json({k: v.model_dump() for k, v in prices.items()})
                    push_count += 1
                    if push_count % 10 == 0:
                        logger.info("WebSocket pushed %d times for %s", push_count, tickers)
                except Exception as e:
                    logger.warning("WebSocket push failed: %s", e)
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=_WS_PUSH_INTERVAL_S
                )
                if isinstance(data, dict) and isinstance(data.get("tickers"), list):
                    tickers = [str(t) for t in data["tickers"]]
                    logger.info("WebSocket subscription updated: %s", tickers)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected (pushed %d times)", push_count)
    except Exception as exc:
        logger.debug("WebSocket ended: %s", exc)
        try:
            await websocket.close()
        except Exception:
            pass
