"""Hot stocks panel endpoint - market-wide stock rankings by different dimensions.

Similar to Tongdaxin's enhanced stock selection (增强选股), this endpoint
returns 4 sections:
1. 今日关注 (Today's Attention) - from hot_stocks feature
2. 北向青睐 (Northbound Favorites) - stocks with consistent northbound buying
3. 龙虎活跃 (Dragon-Tiger Active) - stocks with institutional activity
4. 机构关注 (Institutional Attention) - stocks with high analyst coverage
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Response models ─────────────────────────────────────────────────────────


class HotStockItem(BaseModel):
    """One hot stock entry."""

    ticker: str
    name: str
    change_pct: float | None = None
    turnover_rate: float | None = None
    volume_wan: float | None = None
    net_flow_wan: float | None = None
    topics: str = ""


class NorthboundFavoriteItem(BaseModel):
    """Stock with consistent northbound capital inflow."""

    ticker: str
    name: str
    change_pct: float | None = None
    northbound_net_wan: float | None = None
    northbound_days: int | None = None
    industry: str = ""


class DragonTigerActiveItem(BaseModel):
    """Stock with dragon-tiger list activity."""

    ticker: str
    name: str
    change_pct: float | None = None
    net_buy_wan: float | None = None
    reason: str = ""
    appearances: int = 0


class InstitutionalAttentionItem(BaseModel):
    """Stock with high analyst coverage."""

    ticker: str
    name: str
    change_pct: float | None = None
    analyst_count: int | None = None
    pe_ttm: float | None = None
    peg: float | None = None


class HotStocksPanelResponse(BaseModel):
    """Response for the hot stocks panel endpoint."""

    date: str
    attention: list[HotStockItem] = Field(default_factory=list)
    northbound: list[NorthboundFavoriteItem] = Field(default_factory=list)
    dragon_tiger: list[DragonTigerActiveItem] = Field(default_factory=list)
    institutional: list[InstitutionalAttentionItem] = Field(default_factory=list)


# ─ Data fetching helpers ───────────────────────────────────────────────────


def _fetch_hot_stocks(today: str) -> list[HotStockItem]:
    """Fetch today's hot stocks from 同花顺."""
    from tradingagents.dataflows.a_stock import get_hot_stocks

    try:
        md = get_hot_stocks(today)
        # Parse the markdown - reuse the parser logic
        import re

        def _f(text: str) -> float | None:
            try:
                return float(text.replace(",", "").strip())
            except (ValueError, TypeError):
                return None

        items = []
        blocks = re.split(r"(?=^## )", md, flags=re.MULTILINE)

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            header_match = re.match(r"^##\s+(.+?)\s*\((\d{6})\)", block)
            if not header_match:
                continue

            name = header_match.group(1)
            code = header_match.group(2)

            change_pct = None
            turnover_rate = None
            volume_wan = None
            net_flow_wan = None
            topics = ""

            reason_match = re.search(r"Reason:\s*(.+)", block)
            if reason_match:
                topics = reason_match.group(1).strip()

            zhangfu_match = re.search(r"涨幅:\s*([\d.]+)%?", block)
            if zhangfu_match:
                change_pct = _f(zhangfu_match.group(1))

            huanshou_match = re.search(r"换手:\s*([\d.]+)%?", block)
            if huanshou_match:
                turnover_rate = _f(huanshou_match.group(1))

            chengjiao_match = re.search(r"成交额:\s*([\d,.]+)", block)
            if chengjiao_match:
                volume_wan = _f(chengjiao_match.group(1))

            dde_match = re.search(r"DDE净量:\s*([\d.]+)", block)
            if dde_match:
                net_flow_wan = _f(dde_match.group(1))

            items.append(
                HotStockItem(
                    ticker=code,
                    name=name,
                    change_pct=change_pct,
                    turnover_rate=turnover_rate,
                    volume_wan=volume_wan,
                    net_flow_wan=net_flow_wan,
                    topics=topics,
                )
            )

        # Sort by volume (成交额) descending - most attention = highest volume
        items.sort(key=lambda x: x.volume_wan or 0, reverse=True)
        return items[:20]  # Top 20

    except Exception as exc:
        logger.warning("Failed to fetch hot stocks: %s", exc)
        return []


def _fetch_northbound_favorites(today: str) -> list[NorthboundFavoriteItem]:
    """Fetch stocks with consistent northbound capital inflow.

    Note: This is a simplified version. In production, we'd need to aggregate
    northbound flow data across all stocks, which requires additional data sources.
    For now, return empty list - this feature needs more data infrastructure.
    """
    # TODO: Implement when northbound per-stock data is available
    return []


def _fetch_dragon_tiger_active(today: str) -> list[DragonTigerActiveItem]:
    """Fetch stocks with dragon-tiger list activity.

    Note: Dragon-tiger data is per-stock. We'd need a market-wide dragon-tiger
    ranking endpoint. For now, return empty list.
    """
    # TODO: Implement when market-wide dragon-tiger ranking is available
    return []


def _fetch_institutional_attention(today: str) -> list[InstitutionalAttentionItem]:
    """Fetch stocks with high analyst coverage.

    Note: Profit forecast data is per-stock. We'd need to aggregate across
    multiple stocks. For now, return empty list.
    """
    # TODO: Implement when market-wide analyst coverage ranking is available
    return []


# ── Endpoint ────────────────────────────────────────────────────────────────


@router.get("/api/hot-stocks")
async def get_hot_stocks_panel(date_str: str | None = None):
    """Get hot stocks panel data with 4 sections.

    PG cache with daily TTL — hot stocks data only changes once per day.
    """
    from datetime import datetime
    from tradingagents.cache.manager import get_cache

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        target_date = date.today().strftime("%Y-%m-%d")

    mgr = get_cache("__hot_stocks__")

    def _source():
        attention = _fetch_hot_stocks(target_date)
        northbound = _fetch_northbound_favorites(target_date)
        dragon_tiger = _fetch_dragon_tiger_active(target_date)
        institutional = _fetch_institutional_attention(target_date)
        resp = HotStocksPanelResponse(
            date=target_date,
            attention=attention,
            northbound=northbound,
            dragon_tiger=dragon_tiger,
            institutional=institutional,
        )
        return resp.model_dump()

    with mgr.fetch("hot_stocks", target_date, source_fn=_source) as (data, hit):
        if hit and isinstance(data, dict):
            return HotStocksPanelResponse(**data)
        return HotStocksPanelResponse(**data)

