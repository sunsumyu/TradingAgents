"""Market Overview API router (Phase 8).

GET /api/market-overview — 全市场概览数据（指数/排行/板块/宽度/新闻）

缓存策略：
- PostgreSQL data_cache 表（JSONB）为主缓存
- 全局数据不区分日期（同一天内数据变化不大）
- 交易时间内 TTL=10 分钟，盘后 TTL=2 小时
- PG 不可用时降级到 SQLite 文件缓存
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局内存缓存作为第一道防线（避免每次请求都走 PG）
_mem_cache: dict[str, Any] = {"data": None, "ts": 0.0}
_MEM_TTL_TRADING = 600      # 交易时间内 10 分钟
_MEM_TTL_AFTER_HOURS = 7200  # 盘后 2 小时


def _is_trading_hours() -> bool:
    """粗略判断是否在 A 股交易时间内（9:15-15:05）。"""
    from datetime import datetime
    now = datetime.now()
    t = now.hour * 60 + now.minute
    return 9 * 60 + 15 <= t <= 15 * 60 + 5


def _ttl() -> int:
    return _MEM_TTL_TRADING if _is_trading_hours() else _MEM_TTL_AFTER_HOURS


@router.get("/api/market-overview")
def market_overview():
    """获取市场全景图数据。

    三级缓存：内存 → PostgreSQL → 实时 fetch
    """
    import time
    from datetime import datetime

    now = time.time()
    ttl = _ttl()

    # Level 1: 内存缓存
    if _mem_cache["data"] is not None and (now - _mem_cache["ts"]) < ttl:
        logger.debug("Market overview: memory cache hit")
        return _mem_cache["data"]

    # Level 2: PostgreSQL 缓存（用固定 key，不按天分）
    from tradingagents.cache.manager import get_cache

    mgr = get_cache("MARKET")
    # CacheManager.get() 直接返回数据本身（不是 {result: ...} 包装）
    cached = mgr.get("market_overview", "latest")
    if cached is not None and isinstance(cached, dict) and "indices" in cached:
        _mem_cache["data"] = cached
        _mem_cache["ts"] = now
        logger.debug("Market overview: PG cache hit")
        return cached

    # Level 3: 实时 fetch
    from tradingagents.dataflows.a_stock.market_overview import get_market_overview

    logger.info("Market overview: cache miss, fetching fresh data...")
    data = get_market_overview()

    # 写入 PG（用固定 key "latest"）
    mgr.set("market_overview", "latest", data)
    _mem_cache["data"] = data
    _mem_cache["ts"] = now

    logger.info(f"Market overview: fetched and cached ({len(data.get('indices', {}))} indices)")
    return data
