"""Standalone market data fetching — no agent analysis required."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    """Fetch fundamental data — try A-stock vendor first, then yfinance."""
    try:
        # Try A-stock vendor first (works in China without VPN)
        from tradingagents.dataflows.a_stock import get_fundamentals as astock_fundamentals
        try:
            text = astock_fundamentals(ticker, date)
        except Exception:
            text = None

        # Fallback: try route_to_vendor (yfinance path)
        if not text:
            try:
                from tradingagents.dataflows.interface import route_to_vendor
                text = route_to_vendor("get_fundamentals", ticker, date)
            except Exception:
                text = None

        if not text:
            return None

        # Parse key: value lines from the text output
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
        import re
        from tradingagents.dataflows.interface import route_to_vendor

        start_dt = datetime.strptime(date, "%Y-%m-%d") - timedelta(days=7)
        start_date = start_dt.strftime("%Y-%m-%d")

        # Try A-stock vendor first (works in China without VPN)
        text = None
        try:
            from tradingagents.dataflows.a_stock import get_news as astock_news
            raw = astock_news(ticker, date)
            if isinstance(raw, list):
                # A-stock vendor returns list of dicts with title/summary/link
                items = []
                for article in raw:
                    items.append(NewsItem(
                        title=article.get("title", ""),
                        publisher=article.get("source") or article.get("publisher"),
                        summary=article.get("summary") or article.get("content"),
                        link=article.get("url") or article.get("link"),
                    ))
                return items[:20]
            text = raw
        except Exception:
            text = None

        # Fallback: try route_to_vendor (yfinance path)
        if not text:
            text = route_to_vendor("get_news", ticker, start_date, date)
        if not text:
            return []

        # Vendor returns markdown format:
        #   ### Title (source: Publisher)
        #   Summary text...
        #   Link: http://...
        items: list[NewsItem] = []
        lines = str(text).splitlines()
        current_title = ""
        current_publisher = ""
        current_summary = ""
        current_link = ""

        def _flush():
            nonlocal current_title, current_publisher, current_summary, current_link
            if current_title:
                items.append(NewsItem(
                    title=current_title.strip(),
                    publisher=current_publisher.strip() or None,
                    summary=current_summary.strip() or None,
                    link=current_link.strip() or None,
                ))
            current_title = ""
            current_publisher = ""
            current_summary = ""
            current_link = ""

        for line in lines:
            stripped = line.strip()

            # Markdown heading: ### Title (source: Publisher)
            heading_match = re.match(r"^#{1,4}\s+(.+)", stripped)
            if heading_match:
                _flush()
                raw = heading_match.group(1)
                # Extract publisher from "(source: XXX)"
                src_match = re.search(r"\(source:\s*(.+?)\)", raw)
                if src_match:
                    current_publisher = src_match.group(1)
                    current_title = raw[:src_match.start()].strip()
                else:
                    current_title = raw
                continue

            # Link line
            if stripped.lower().startswith("link:"):
                current_link = stripped[5:].strip()
                continue

            # Accumulate summary
            if stripped and current_title:
                if current_summary:
                    current_summary += " " + stripped
                else:
                    current_summary = stripped

        _flush()  # flush last article
        return items[:20]
    except Exception as exc:
        logger.warning("Failed to fetch news for %s: %s", ticker, exc)
        return []


def build_market_data(ticker: str, date: str) -> MarketDataResponse:
    """Fetch chart data, fundamentals, and news concurrently.

    This runs without agents — it only calls vendor APIs directly.
    All three data sources are fetched in parallel to minimize total latency.
    """
    chart = None
    fundamentals = None
    news = None

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(build_chart_data, {}, ticker, date): "chart",
            executor.submit(_fetch_fundamentals, ticker, date): "fundamentals",
            executor.submit(_fetch_news, ticker, date): "news",
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                result = future.result()
                if label == "chart":
                    chart = result
                elif label == "fundamentals":
                    fundamentals = result
                elif label == "news":
                    news = result
            except Exception as exc:
                logger.warning("Parallel fetch failed for %s: %s", label, exc)

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
