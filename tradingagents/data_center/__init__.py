"""Data Center — unified data access layer for the chart engine.

This module wraps the existing ``tradingagents.dataflows`` vendor routing
system with a clean adapter pattern, adds SQLite-based offline caching,
and provides a simple interface for the chart engine.

Usage::

    from tradingagents.data_center import DataCenter

    dc = DataCenter(cache_dir="~/.tradingagents/cache")
    df = dc.get_ohlcv("600519", "1D", "2025-01-01", "2025-06-01")
    quotes = dc.get_realtime(["600519", "000001"])
"""

from .cache import CacheManager
from .center import DataCenter
from .models import OHLCVBar, Quote, NewsItem, FundamentalData

__all__ = [
    "CacheManager",
    "DataCenter",
    "OHLCVBar",
    "Quote",
    "NewsItem",
    "FundamentalData",
]
