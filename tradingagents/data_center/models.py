"""Data models for the Data Center."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OHLCVBar:
    """Single OHLCV bar."""

    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float = 0.0
    turnover: float = 0.0


@dataclass
class Quote:
    """Real-time quote for a single ticker."""

    ticker: str
    name: str
    price: float
    change: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: int
    amount: float
    bid_prices: list[float] = field(default_factory=list)
    ask_prices: list[float] = field(default_factory=list)
    bid_volumes: list[int] = field(default_factory=list)
    ask_volumes: list[int] = field(default_factory=list)
    timestamp: float = 0.0


@dataclass
class NewsItem:
    """A single news article."""

    title: str
    publisher: str | None = None
    summary: str | None = None
    link: str | None = None
    pub_date: str | None = None


@dataclass
class FundamentalData:
    """Fundamental data for a stock."""

    ticker: str
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    market_cap: float | None = None
    dividend_yield: float | None = None
    roe: float | None = None
    revenue: float | None = None
    net_income: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)
