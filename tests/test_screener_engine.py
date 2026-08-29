"""Unit tests for the screener_engine module."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tradingagents.screener_engine import (
    Filter,
    FilterOperator,
    ScreenerEngine,
    ScreenerResult,
    ScreenerTemplate,
    SCREEN_FIELDS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_stock_pool() -> pd.DataFrame:
    """Generate sample stock pool for screening."""
    return pd.DataFrame({
        "ticker": ["600519", "000858", "000001", "601318", "000333"],
        "name": ["贵州茅台", "五粮液", "平安银行", "中国平安", "美的集团"],
        "pe_ratio": [30.5, 25.2, 5.8, 9.5, 15.3],
        "pb_ratio": [10.2, 7.5, 0.6, 1.2, 3.8],
        "market_cap": [2000e8, 500e8, 3000e8, 4000e8, 800e8],
        "roe": [30.0, 25.0, 12.0, 15.0, 20.0],
        "dividend_yield": [1.5, 2.0, 5.0, 4.0, 3.5],
        "change_pct": [2.5, -1.0, 0.5, 1.2, 3.0],
        "volume_ratio": [1.2, 0.8, 1.5, 1.1, 2.0],
        "turnover_rate": [0.5, 1.2, 0.3, 0.8, 1.5],
        "rsi_14": [65.0, 45.0, 30.0, 55.0, 70.0],
        "revenue_growth": [15.0, 20.0, 8.0, 12.0, 25.0],
        "profit_growth": [18.0, 22.0, 10.0, 15.0, 28.0],
    })


@pytest.fixture
def screener_engine():
    """Create a ScreenerEngine with mocked data center."""
    engine = ScreenerEngine.__new__(ScreenerEngine)
    engine._data = None
    engine._stock_pool = None
    engine._templates = {}
    return engine


# ═══════════════════════════════════════════════════════════════════════════════
# Model tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestModels:
    def test_filter_creation(self):
        f = Filter("pe_ratio", FilterOperator.LT, 15)
        assert f.field == "pe_ratio"
        assert f.operator == FilterOperator.LT

    def test_filter_between(self):
        f = Filter("market_cap", FilterOperator.BETWEEN, 5e9, 20e9)
        assert f.value2 == 20e9

    def test_screener_result(self):
        r = ScreenerResult(
            ticker="600519",
            name="贵州茅台",
            score=85.0,
            matched_filters=4,
        )
        assert r.ticker == "600519"
        assert r.score == 85.0

    def test_screen_fields_count(self):
        assert len(SCREEN_FIELDS) >= 50

    def test_screen_fields_chinese(self):
        assert "市盈率" in SCREEN_FIELDS.values()
        assert "市净率" in SCREEN_FIELDS.values()


# ═══════════════════════════════════════════════════════════════════════════════
# Filter application tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFilterApplication:
    def test_lt_filter(self):
        from tradingagents.screener_engine.engine import _apply_filter
        f = Filter("pe", FilterOperator.LT, 15)
        assert _apply_filter(10, f) is True
        assert _apply_filter(20, f) is False

    def test_gt_filter(self):
        from tradingagents.screener_engine.engine import _apply_filter
        f = Filter("roe", FilterOperator.GT, 15)
        assert _apply_filter(20, f) is True
        assert _apply_filter(10, f) is False

    def test_between_filter(self):
        from tradingagents.screener_engine.engine import _apply_filter
        f = Filter("cap", FilterOperator.BETWEEN, 5, 20)
        assert _apply_filter(10, f) is True
        assert _apply_filter(3, f) is False
        assert _apply_filter(25, f) is False

    def test_eq_filter(self):
        from tradingagents.screener_engine.engine import _apply_filter
        f = Filter("name", FilterOperator.EQ, "test")
        assert _apply_filter("test", f) is True
        assert _apply_filter("other", f) is False

    def test_contains_filter(self):
        from tradingagents.screener_engine.engine import _apply_filter
        f = Filter("industry", FilterOperator.CONTAINS, "消费")
        assert _apply_filter("食品消费", f) is True
        assert _apply_filter("科技", f) is False

    def test_none_value_returns_false(self):
        from tradingagents.screener_engine.engine import _apply_filter
        f = Filter("pe", FilterOperator.LT, 15)
        assert _apply_filter(None, f) is False


# ═══════════════════════════════════════════════════════════════════════════════
# ScreenerEngine tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestScreenerEngine:
    def test_screen_empty_pool(self, screener_engine):
        screener_engine._stock_pool = pd.DataFrame()
        results = screener_engine.screen([Filter("pe", FilterOperator.LT, 15)])
        assert results == []

    def test_screen_single_filter(self, screener_engine, sample_stock_pool):
        screener_engine._stock_pool = sample_stock_pool
        results = screener_engine.screen(
            [Filter("pe_ratio", FilterOperator.LT, 10)],
            sort_by="pe_ratio",
        )
        assert len(results) > 0
        # Should include 平安银行 (PE=5.8) and 中国平安 (PE=9.5)
        tickers = [r.ticker for r in results]
        assert "000001" in tickers
        assert "601318" in tickers

    def test_screen_multiple_filters(self, screener_engine, sample_stock_pool):
        screener_engine._stock_pool = sample_stock_pool
        results = screener_engine.screen([
            Filter("pe_ratio", FilterOperator.LT, 20),
            Filter("roe", FilterOperator.GT, 15),
        ])
        # PE<20 AND ROE>15: 美的集团 (PE=15.3, ROE=20)
        # 五粮液 PE=25.2 fails PE<20, 平安银行 ROE=12 fails ROE>15
        assert len(results) >= 1
        tickers = [r.ticker for r in results]
        assert "000333" in tickers

    def test_screen_with_limit(self, screener_engine, sample_stock_pool):
        screener_engine._stock_pool = sample_stock_pool
        results = screener_engine.screen(
            [Filter("pe_ratio", FilterOperator.LT, 100)],
            limit=2,
        )
        assert len(results) <= 2

    def test_get_templates(self, screener_engine):
        from tradingagents.screener_engine.engine import PRESET_TEMPLATES
        screener_engine._templates = {t.id: t for t in PRESET_TEMPLATES}
        templates = screener_engine.get_templates()
        assert len(templates) >= 10
        ids = [t.id for t in templates]
        assert "value" in ids
        assert "growth" in ids

    def test_get_template_by_id(self, screener_engine):
        from tradingagents.screener_engine.engine import PRESET_TEMPLATES
        screener_engine._templates = {t.id: t for t in PRESET_TEMPLATES}
        t = screener_engine.get_template("value")
        assert t is not None
        assert t.name == "价值股筛选"

    def test_run_template(self, screener_engine, sample_stock_pool):
        from tradingagents.screener_engine.engine import PRESET_TEMPLATES
        screener_engine._stock_pool = sample_stock_pool
        screener_engine._templates = {t.id: t for t in PRESET_TEMPLATES}
        results = screener_engine.run_template("low_pe")
        # low_pe: PE<10, PB<1.5, Market Cap>100亿
        # Should include 平安银行 (PE=5.8, PB=0.6, Cap=3000亿)
        tickers = [r.ticker for r in results]
        assert "000001" in tickers

    def test_set_stock_pool(self, screener_engine, sample_stock_pool):
        screener_engine.set_stock_pool(sample_stock_pool)
        assert screener_engine._stock_pool is not None
        assert len(screener_engine._stock_pool) == 5

    def test_screen_natural_pe(self, screener_engine, sample_stock_pool):
        screener_engine._stock_pool = sample_stock_pool
        results = screener_engine.screen_natural("PE<10")
        tickers = [r.ticker for r in results]
        assert "000001" in tickers

    def test_screen_natural_roe(self, screener_engine, sample_stock_pool):
        screener_engine._stock_pool = sample_stock_pool
        results = screener_engine.screen_natural("ROE>20")
        tickers = [r.ticker for r in results]
        assert "600519" in tickers  # ROE=30
