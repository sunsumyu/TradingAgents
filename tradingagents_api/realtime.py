"""Batch realtime price fetching for the watchlist polling endpoint.

A-share codes (6-digit) are quoted through the Tencent batch API - one HTTP
request covers the whole list and works from mainland networks. Everything
else (US tickers, ETFs, ...) is fetched concurrently via yfinance fast_info.

Per-ticker failure isolation: a ticker that fails to quote is simply absent
from the result; it never breaks the other tickers in the same request.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .schemas import RealtimePriceItem

logger = logging.getLogger(__name__)

# Keep yfinance fan-out bounded - the watchlist is capped at 100 tickers
# upstream, and unbounded threads would hammer Yahoo on large lists.
_MAX_YFINANCE_WORKERS = 8


def _is_astock(symbol: str) -> bool:
    """True if the symbol looks like a 6-digit A-share code (mirrors chart_data)."""
    code = symbol.strip().split(".")[0]
    return code.isdigit() and len(code) == 6


def _fetch_one_yfinance(symbol: str) -> RealtimePriceItem | None:
    """Realtime quote for a non-A-share symbol via yfinance fast_info."""
    try:
        import yfinance as yf

        from tradingagents.dataflows.symbol_utils import normalize_symbol

        fast = yf.Ticker(normalize_symbol(symbol)).fast_info
        price = float(fast["last_price"])
        prev = float(fast["previous_close"])
        if price <= 0 or prev <= 0:
            return None
        return RealtimePriceItem(
            price=round(price, 4),
            change=round(price - prev, 4),
            changePct=round((price - prev) / prev * 100, 4),
        )
    except Exception as exc:
        logger.debug("realtime quote failed for %s: %s", symbol, exc)
        return None


def fetch_realtime_prices(tickers: list[str]) -> dict[str, RealtimePriceItem]:
    """Fetch latest price/change/changePct for a mixed list of tickers."""
    result: dict[str, RealtimePriceItem] = {}

    astock: list[str] = []
    others: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        symbol = str(raw).strip()
        if not symbol or symbol.upper() in seen:
            continue
        seen.add(symbol.upper())
        (astock if _is_astock(symbol) else others).append(symbol)

    # A-shares: single batched Tencent quote request (keys echo the inputs)
    if astock:
        try:
            from tradingagents.dataflows.a_stock import get_realtime_quotes

            quotes = get_realtime_quotes(astock)
        except Exception as exc:
            logger.warning("A-share realtime batch failed: %s", exc)
            quotes = {}
        for symbol, q in quotes.items():
            result[symbol] = RealtimePriceItem(
                price=round(float(q.get("price") or 0.0), 4),
                change=round(float(q.get("change") or 0.0), 4),
                changePct=round(float(q.get("change_pct") or 0.0), 4),
                name=q.get("name"),
            )

    # Global tickers: concurrent yfinance fast_info fetches
    if others:
        workers = min(_MAX_YFINANCE_WORKERS, len(others))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_fetch_one_yfinance, s): s for s in others}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    item = future.result()
                    if item is not None:
                        result[symbol] = item
                except Exception as exc:  # defensive - _fetch_one never raises
                    logger.debug("realtime fetch failed for %s: %s", symbol, exc)

    return result
