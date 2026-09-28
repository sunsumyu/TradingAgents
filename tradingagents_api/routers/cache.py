"""Data cache management endpoints."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from tradingagents.cache import get_cache, clear_cache, _CACHE_DIR
from tradingagents.cache.manager import _get_pg_pool

from ..schemas import CacheClearRequest

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/cache/clear")
async def clear_data_cache(request: CacheClearRequest):
    """Clear data cache entries. Permanent history (data_history) is untouched."""
    clear_cache(ticker=request.ticker or None, feature=request.data_type)
    return {"status": "ok"}


@router.get("/api/history")
async def get_history(
    data_type: str = Query(..., description="数据类型，如 market_overview"),
    ticker: str = Query("", description="按 ticker 过滤，空为全部"),
    date: str = Query("", description="指定交易日 YYYY-MM-DD，空为最近 N 天"),
    limit: int = Query(30, ge=1, le=500),
):
    """查询永久归档的历史快照（data_history，不随缓存清理删除）。"""
    pool = _get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="PostgreSQL 不可用，无法查询历史数据")

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            if date:
                cur.execute(
                    """SELECT ticker, data_type, trade_date, updated_at, result
                       FROM data_history
                       WHERE data_type = %s AND (%s = '' OR ticker = %s) AND trade_date = %s
                       ORDER BY ticker, param_hash""",
                    (data_type, ticker, ticker, date),
                )
            else:
                cur.execute(
                    """SELECT ticker, data_type, trade_date, updated_at, result
                       FROM data_history
                       WHERE data_type = %s AND (%s = '' OR ticker = %s)
                       ORDER BY trade_date DESC, ticker, param_hash
                       LIMIT %s""",
                    (data_type, ticker, ticker, limit),
                )
            rows = cur.fetchall()
    except Exception as exc:
        conn.rollback()
        logger.warning("History query failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"历史查询失败: {exc}")
    finally:
        pool.putconn(conn)

    items = []
    for t, dt, td, updated_at, result in rows:
        result_obj = result if isinstance(result, (dict, list)) else json.loads(result)
        items.append({
            "ticker": t,
            "data_type": dt,
            "trade_date": td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(updated_at)),
            "result": result_obj,
        })
    return {"count": len(items), "items": items}


@router.get("/api/history/types")
async def get_history_types():
    """列出归档中已有的数据类型及快照数（按天计数）。"""
    pool = _get_pg_pool()
    if pool is None:
        raise HTTPException(status_code=503, detail="PostgreSQL 不可用")

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT data_type, COUNT(*) AS snapshots, COUNT(DISTINCT trade_date) AS days,
                          MIN(trade_date) AS first_date, MAX(trade_date) AS last_date
                   FROM data_history
                   GROUP BY data_type
                   ORDER BY data_type"""
            )
            rows = cur.fetchall()
    except Exception as exc:
        conn.rollback()
        logger.warning("History types query failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"查询失败: {exc}")
    finally:
        pool.putconn(conn)

    return {
        "types": [
            {
                "data_type": dt,
                "snapshots": n,
                "days": d,
                "first_date": fd.strftime("%Y-%m-%d") if hasattr(fd, "strftime") else str(fd),
                "last_date": ld.strftime("%Y-%m-%d") if hasattr(ld, "strftime") else str(ld),
            }
            for dt, n, d, fd, ld in rows
        ]
    }


@router.get("/api/cache/stats")
async def get_cache_stats():
    """Return data cache statistics."""
    if not _CACHE_DIR.exists():
        return {"enabled": True, "tickers": [], "total_entries": 0}

    tickers = []
    total_entries = 0
    for db_file in sorted(_CACHE_DIR.glob("*.db")):
        try:
            s = get_cache(db_file.stem).stats()
            total_entries += s["total_entries"]
            tickers.append(s)
        except Exception as exc:
            logger.warning("Cache stats failed for %s: %s", db_file.stem, exc)

    return {
        "enabled": True,
        "tickers": tickers,
        "total_entries": total_entries,
    }
