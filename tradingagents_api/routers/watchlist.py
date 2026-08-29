"""Watchlist sync endpoints (ticket #5)."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from ..watchlist import WatchlistState, WatchlistSyncRequest, get_watchlist, sync_watchlist

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/watchlist", response_model=WatchlistState)
async def read_watchlist():
    """Full server-side watchlist state (groups + items)."""
    return get_watchlist()


@router.put("/api/watchlist", response_model=WatchlistState)
async def put_watchlist(request: WatchlistSyncRequest):
    """Merge the client's watchlist state into the server and return the
    merged result (newer-wins-by-updated_at + tombstone deletions)."""
    try:
        return sync_watchlist(request)
    except Exception as exc:
        logger.error("Watchlist sync failed: %s", exc, exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(exc))
