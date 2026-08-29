"""Unit tests for the data_center module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tradingagents.data_center import CacheManager, DataCenter
from tradingagents.data_center.models import (
    OHLCVBar,
    Quote,
    NewsItem,
    FundamentalData,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_ohlcv_df() -> pd.DataFrame:
    """Generate sample OHLCV DataFrame."""
    return pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=10, freq="D"),
        "open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        "high": [102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
        "low": [99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
        "close": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
        "volume": [1000000] * 10,
    })


@pytest.fixture
def cache_dir():
    """Create a temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cache_manager(cache_dir):
    """Create a CacheManager instance, closed after test."""
    mgr = CacheManager(cache_dir)
    yield mgr
    mgr.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Model tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestModels:
    def test_ohlcv_bar_creation(self):
        bar = OHLCVBar(
            timestamp=1000000,
            open=100.0,
            high=105.0,
            low=99.0,
            close=102.0,
            volume=1000000,
        )
        assert bar.open == 100.0
        assert bar.volume == 1000000

    def test_quote_creation(self):
        quote = Quote(
            ticker="600519",
            name="贵州茅台",
            price=1800.0,
            change=20.0,
            change_pct=1.12,
            open=1780.0,
            high=1810.0,
            low=1775.0,
            volume=50000,
            amount=90000000.0,
        )
        assert quote.ticker == "600519"
        assert quote.change_pct == 1.12

    def test_news_item_creation(self):
        item = NewsItem(
            title="茅台发布三季报",
            publisher="东方财富",
            summary="营收增长15%",
            link="https://example.com",
        )
        assert item.title == "茅台发布三季报"

    def test_fundamental_data_creation(self):
        fd = FundamentalData(
            ticker="600519",
            pe_ratio=30.5,
            pb_ratio=10.2,
            market_cap=2000000000000,
        )
        assert fd.pe_ratio == 30.5


# ═══════════════════════════════════════════════════════════════════════════════
# CacheManager tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCacheManager:
    def test_set_and_get_ohlcv(self, cache_manager, sample_ohlcv_df):
        cache_manager.set_ohlcv("600519", "1D", sample_ohlcv_df)
        result = cache_manager.get_ohlcv("600519", "1D", "2025-01-01", "2025-01-10")
        assert result is not None
        assert len(result) == 10
        assert "open" in result.columns

    def test_get_returns_none_on_miss(self, cache_manager):
        result = cache_manager.get_ohlcv("NONEXIST", "1D", "2025-01-01", "2025-01-10")
        assert result is None

    def test_set_and_get_indicator(self, cache_manager):
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=5, freq="D"),
            "ma": [100, 101, 102, 103, 104],
        })
        cache_manager.set_indicator("600519", "MA", {"period": 20}, df)
        result = cache_manager.get_indicator("600519", "MA", {"period": 20}, "2025-01-01", "2025-01-05")
        assert result is not None
        assert len(result) == 5

    def test_clear_specific_ticker(self, cache_manager, sample_ohlcv_df):
        cache_manager.set_ohlcv("600519", "1D", sample_ohlcv_df)
        cache_manager.set_ohlcv("000001", "1D", sample_ohlcv_df)
        deleted = cache_manager.clear("600519")
        assert deleted >= 1
        # 600519 should be cleared, 000001 should remain
        result = cache_manager.get_ohlcv("000001", "1D", "2025-01-01", "2025-01-10")
        assert result is not None

    def test_clear_all(self, cache_manager, sample_ohlcv_df):
        cache_manager.set_ohlcv("600519", "1D", sample_ohlcv_df)
        cache_manager.set_ohlcv("000001", "1D", sample_ohlcv_df)
        deleted = cache_manager.clear()
        assert deleted >= 2

    def test_stats(self, cache_manager, sample_ohlcv_df):
        cache_manager.set_ohlcv("600519", "1D", sample_ohlcv_df)
        stats = cache_manager.stats()
        assert stats["enabled"] is True
        assert stats["total_entries"] >= 10
        assert len(stats["tickers"]) >= 1

    def test_close(self, cache_manager, sample_ohlcv_df):
        cache_manager.set_ohlcv("600519", "1D", sample_ohlcv_df)
        cache_manager.close()
        assert len(cache_manager._connections) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DataCenter tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDataCenter:
    def test_init_with_cache_dir(self, cache_dir):
        dc = DataCenter(cache_dir=str(cache_dir))
        assert dc._cache is not None
        dc.close()

    def test_is_astock(self):
        dc = DataCenter.__new__(DataCenter)
        assert dc._is_astock("600519") is True
        assert dc._is_astock("000001") is True
        assert dc._is_astock("600519.SS") is True
        assert dc._is_astock("AAPL") is False
        assert dc._is_astock("NVDA") is False

    @patch("tradingagents.data_center.center.DataCenter._fetch_ohlcv_from_vendor")
    def test_get_ohlcv_cache_miss(self, mock_fetch, cache_dir, sample_ohlcv_df):
        mock_fetch.return_value = sample_ohlcv_df
        dc = DataCenter(cache_dir=str(cache_dir))
        result = dc.get_ohlcv("600519", "1D", "2025-01-01", "2025-01-10")
        assert result is not None
        assert len(result) == 10
        mock_fetch.assert_called_once()
        dc.close()

    @patch("tradingagents.data_center.center.DataCenter._fetch_ohlcv_from_vendor")
    def test_get_ohlcv_cache_hit(self, mock_fetch, cache_dir, sample_ohlcv_df):
        mock_fetch.return_value = sample_ohlcv_df
        dc = DataCenter(cache_dir=str(cache_dir))

        # First call - cache miss
        dc.get_ohlcv("600519", "1D", "2025-01-01", "2025-01-10")
        assert mock_fetch.call_count == 1

        # Second call - cache hit
        result = dc.get_ohlcv("600519", "1D", "2025-01-01", "2025-01-10")
        assert result is not None
        assert mock_fetch.call_count == 1  # Not called again
        dc.close()

    @patch("tradingagents.data_center.center.DataCenter._fetch_ohlcv_from_vendor")
    def test_get_ohlcv_force_refresh(self, mock_fetch, cache_dir, sample_ohlcv_df):
        mock_fetch.return_value = sample_ohlcv_df
        dc = DataCenter(cache_dir=str(cache_dir))

        # First call
        dc.get_ohlcv("600519", "1D", "2025-01-01", "2025-01-10")

        # Force refresh
        dc.get_ohlcv("600519", "1D", "2025-01-01", "2025-01-10", force_refresh=True)
        assert mock_fetch.call_count == 2
        dc.close()

    def test_get_realtime_empty(self, cache_dir):
        dc = DataCenter(cache_dir=str(cache_dir))
        result = dc.get_realtime([])
        assert result == {}
        dc.close()

    def test_clear_cache(self, cache_dir, sample_ohlcv_df):
        dc = DataCenter(cache_dir=str(cache_dir))
        # Manually set cache
        dc._cache.set_ohlcv("600519", "1D", sample_ohlcv_df)
        deleted = dc.clear_cache("600519")
        assert deleted >= 1
        dc.close()

    def test_cache_stats(self, cache_dir):
        dc = DataCenter(cache_dir=str(cache_dir))
        stats = dc.cache_stats()
        assert "enabled" in stats
        assert "total_entries" in stats
        dc.close()
