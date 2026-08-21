"""Standalone market data fetching — no agent analysis required."""

from __future__ import annotations

import logging
from typing import Any

from .chart_data import build_chart_data
from .schemas import (
    FundamentalsData,
    FundFlowData,
    KlineData,
    MacdData,
    MarketDataResponse,
    NewsItem,
    RsiData,
)

logger = logging.getLogger(__name__)


def _fetch_fundamentals(ticker: str, date: str) -> FundamentalsData | None:
    """Fetch fundamental data via vendor routing."""
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        text = route_to_vendor("get_fundamentals", ticker, date)
        if not text:
            return None

        # Parse the text output — yfinance returns key: value lines
        data: dict[str, Any] = {}
        for line in str(text).splitlines():
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower().replace(" ", "_").replace("/", "_")
                value = value.strip()
                data[key] = value

        def _float(key: str) -> float | None:
            raw = data.get(key)
            if raw is None:
                return None
            try:
                return float(str(raw).replace(",", "").replace("$", ""))
            except (ValueError, TypeError):
                return None

        def _str(key: str) -> str | None:
            raw = data.get(key)
            return str(raw).strip() if raw else None

        return FundamentalsData(
            market_cap=_float("market_cap"),
            pe_ratio=_float("trailing_pe") or _float("pe_ratio_(ttm)") or _float("pe_ratio"),
            forward_pe=_float("forward_pe"),
            pb_ratio=_float("price_to_book"),
            eps_ttm=_float("trailing_eps") or _float("eps_(ttm)"),
            dividend_yield=_float("dividend_yield"),
            beta=_float("beta"),
            fifty_two_week_high=_float("fifty_two_week_high"),
            fifty_two_week_low=_float("fifty_two_week_low"),
            fifty_day_average=_float("fifty_day_average"),
            two_hundred_day_average=_float("two_hundred_day_average"),
            sector=_str("sector"),
            industry=_str("industry"),
            name=_str("short_name") or _str("long_name"),
        )
    except Exception as exc:
        logger.warning("Failed to fetch fundamentals for %s: %s", ticker, exc)
        return None


def _fetch_news(ticker: str, date: str) -> list[NewsItem]:
    """Fetch recent news articles via vendor routing."""
    try:
        from datetime import datetime, timedelta
        from tradingagents.dataflows.interface import route_to_vendor

        start_dt = datetime.strptime(date, "%Y-%m-%d") - timedelta(days=7)
        start_date = start_dt.strftime("%Y-%m-%d")

        text = route_to_vendor("get_news", ticker, start_date, date)
        if not text:
            return []

        items: list[NewsItem] = []
        for line in str(text).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("Title"):
                continue

            # Try to parse "title | publisher | date | link" format
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 1 and parts[0]:
                items.append(NewsItem(
                    title=parts[0],
                    publisher=parts[1] if len(parts) > 1 else None,
                    pub_date=parts[2] if len(parts) > 2 else None,
                    link=parts[3] if len(parts) > 3 else None,
                ))

        return items[:20]  # Limit to 20 articles
    except Exception as exc:
        logger.warning("Failed to fetch news for %s: %s", ticker, exc)
        return []


def build_market_data(ticker: str, date: str) -> MarketDataResponse:
    """Fetch chart data, fundamentals, and news independently.

    This runs without agents — it only calls vendor APIs directly.
    """
    # Charts (reuses existing logic with empty final_state)
    chart = None
    try:
        chart = build_chart_data({}, ticker, date)
    except Exception as exc:
        logger.warning("Chart data assembly failed for %s: %s", ticker, exc)

    # Fundamentals
    fundamentals = _fetch_fundamentals(ticker, date)

    # News
    news = _fetch_news(ticker, date)

    return MarketDataResponse(
        ticker=ticker,
        date=date,
        kline=chart.kline if chart else None,
        macd=chart.macd if chart else None,
        rsi=chart.rsi if chart else None,
        bollinger=chart.bollinger if chart else None,
        fund_flow=chart.fundFlow if chart else None,
        fundamentals=fundamentals,
        news=news,
    )
