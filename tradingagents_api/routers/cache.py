"""Data cache management endpoints."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter

from tradingagents.data_cache import DataCache

from ..schemas import CacheClearRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/cache/clear")
async def clear_data_cache(request: CacheClearRequest):
    """Clear data cache entries.

    If *ticker* is provided, only that ticker's DB is cleared.
    If *data_type* is provided, only entries of that type are removed.
    If neither is provided, ALL cached data is cleared.
    """
    from tradingagents.default_config import get_config

    config = get_config()
    data_dir = config.get("data_cache_dir", "")
    if not data_dir:
        return {"status": "ok", "cleared": 0}

    cache_dir = Path(data_dir) / "data_cache"
    if not cache_dir.exists():
        return {"status": "ok", "cleared": 0}

    total_cleared = 0
    db_files = (
        [cache_dir / f"{request.ticker.upper()}.db"]
        if request.ticker
        else list(cache_dir.glob("*.db"))
    )

    for db_file in db_files:
        if not db_file.exists():
            continue
        try:
            cache = DataCache(data_dir, db_file.stem)
            cleared = cache.clear(request.data_type)
            total_cleared += cleared
            cache.close()
        except Exception as exc:
            logger.warning("Cache clear failed for %s: %s", db_file.name, exc)

    return {"status": "ok", "cleared": total_cleared}


@router.get("/api/cache/stats")
async def get_cache_stats():
    """Return data cache statistics across all cached tickers."""
    from tradingagents.default_config import get_config

    config = get_config()
    data_dir = config.get("data_cache_dir", "")
    if not data_dir:
        return {"enabled": False, "tickers": []}

    cache_dir = Path(data_dir) / "data_cache"
    if not cache_dir.exists():
        return {"enabled": True, "tickers": [], "total_entries": 0}

    tickers = []
    total_entries = 0
    for db_file in sorted(cache_dir.glob("*.db")):
        try:
            cache = DataCache(data_dir, db_file.stem)
            s = cache.stats()
            total_entries += s["total_entries"]
            tickers.append(s)
            cache.close()
        except Exception:
            pass

    return {"enabled": True, "tickers": tickers, "total_entries": total_entries}
