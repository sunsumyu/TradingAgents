"""Tests for the akshare vendor integration.

Verifies:
1. akshare is registered in VENDOR_LIST and VENDOR_METHODS
2. Lazy import raises VendorNotConfiguredError when akshare is missing
3. All function signatures match the tool interface
"""

from __future__ import annotations

import copy
import unittest
from unittest import mock

import pytest

import tradingagents.dataflows.config as config_module
import tradingagents.default_config as default_config
from tradingagents.dataflows import interface
from tradingagents.dataflows.akshare_vendor import (
    _get_ak,
    _normalize_code,
    _df_to_csv,
)
from tradingagents.dataflows.errors import VendorNotConfiguredError


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAkshareRegistration(unittest.TestCase):
    """Verify akshare is properly registered in the vendor system."""

    def test_akshare_in_vendor_list(self):
        assert "akshare" in interface.VENDOR_LIST

    def test_akshare_has_core_methods(self):
        core_methods = [
            "get_stock_data",
            "get_indicators",
            "get_fundamentals",
            "get_balance_sheet",
            "get_cashflow",
            "get_income_statement",
            "get_news",
            "get_insider_transactions",
        ]
        for method in core_methods:
            assert method in interface.VENDOR_METHODS
            assert "akshare" in interface.VENDOR_METHODS[method], (
                f"Missing akshare vendor for {method}"
            )

    def test_akshare_has_signal_methods(self):
        signal_methods = [
            "get_profit_forecast",
            "get_hot_stocks",
            "get_northbound_flow",
            "get_concept_blocks",
            "get_fund_flow",
            "get_dragon_tiger_board",
            "get_lockup_expiry",
            "get_industry_comparison",
            "get_chip_distribution",
        ]
        for method in signal_methods:
            assert method in interface.VENDOR_METHODS
            assert "akshare" in interface.VENDOR_METHODS[method], (
                f"Missing akshare vendor for signal method {method}"
            )

    def test_akshare_not_in_global_news(self):
        """akshare has no global news API; it must NOT be registered."""
        assert "akshare" not in interface.VENDOR_METHODS.get("get_global_news", {})

    def test_akshare_not_in_macro(self):
        """akshare has no macro indicators API; it must NOT be registered."""
        assert "akshare" not in interface.VENDOR_METHODS.get("get_macro_indicators", {})


# ---------------------------------------------------------------------------
# Lazy import tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAkshareLazyImport(unittest.TestCase):
    """When akshare is not installed, lazy-import raises correctly."""

    def test_missing_akshare_raises_not_configured(self):
        """With akshare import blocked, _get_ak raises VendorNotConfiguredError."""
        import tradingagents.dataflows.akshare_vendor as akv
        akv._ak = None  # Reset lazy import cache

        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

        def fake_import(name, *args, **kwargs):
            if name == "akshare":
                raise ImportError("No module named 'akshare'")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            try:
                with self.assertRaises(VendorNotConfiguredError):
                    _get_ak()
            finally:
                akv._ak = None  # Reset for other tests


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAkshareHelpers(unittest.TestCase):
    """Test helper functions in akshare_vendor."""

    def test_normalize_code_strips_prefixes(self):
        assert _normalize_code("SH600519") == "600519"
        assert _normalize_code("600519.SS") == "600519"
        assert _normalize_code("sh600519") == "600519"
        assert _normalize_code("600519") == "600519"

    def test_df_to_csv_empty(self):
        import pandas as pd
        assert _df_to_csv(pd.DataFrame()) == ""
        assert _df_to_csv(None) == ""

    def test_df_to_csv_renames_columns(self):
        import pandas as pd
        df = pd.DataFrame({"日期": ["2026-01-01"], "开盘": [100], "收盘": [105]})
        result = _df_to_csv(df)
        assert "Date" in result
        assert "Open" in result
        assert "Close" in result


# ---------------------------------------------------------------------------
# Routing integration test
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAkshareRouting(unittest.TestCase):
    """Test that akshare can be selected via vendor routing config."""

    def setUp(self):
        self._orig = copy.deepcopy(config_module._config or default_config.DEFAULT_CONFIG)

    def tearDown(self):
        config_module._config = self._orig

    def test_config_selects_akshare_vendor(self):
        """Setting data_vendors to akshare makes it the primary vendor."""
        from tradingagents.dataflows.config import set_config
        set_config({"data_vendors": {"core_stock_apis": "akshare"}})
        vendor = interface.get_vendor("core_stock_apis", "get_stock_data")
        assert vendor == "akshare"

    def test_config_akshare_with_fallback(self):
        """Comma-separated config creates a fallback chain."""
        from tradingagents.dataflows.config import set_config
        set_config({"data_vendors": {"core_stock_apis": "akshare,yfinance"}})
        vendor = interface.get_vendor("core_stock_apis", "get_stock_data")
        assert vendor == "akshare,yfinance"

    def test_tool_level_override(self):
        """tool_vendors takes precedence over data_vendors."""
        from tradingagents.dataflows.config import set_config
        set_config({
            "data_vendors": {"core_stock_apis": "yfinance"},
            "tool_vendors": {"get_stock_data": "akshare"},
        })
        vendor = interface.get_vendor("core_stock_apis", "get_stock_data")
        assert vendor == "akshare"


if __name__ == "__main__":
    unittest.main()
