import pytest
from tradingagents.dataflows.interface import (
    VENDOR_LIST,
    VENDOR_METHODS,
    TOOLS_CATEGORIES,
    get_category_for_method,
)


def test_a_stock_in_vendor_list():
    assert "a_stock" in VENDOR_LIST


def test_a_stock_has_all_core_methods():
    """All existing tool methods must have an a_stock implementation."""
    core_methods = [
        "get_stock_data",
        "get_indicators",
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
        "get_news",
        "get_global_news",
        "get_insider_transactions",
    ]
    for method in core_methods:
        assert method in VENDOR_METHODS, f"Missing VENDOR_METHODS entry for {method}"
        assert "a_stock" in VENDOR_METHODS[method], f"Missing a_stock vendor for {method}"


def test_astock_signal_methods_exist():
    """A-stock signal methods (available via a_stock and akshare)."""
    signal_methods = [
        "get_profit_forecast",
        "get_hot_stocks",
        "get_northbound_flow",
        "get_concept_blocks",
        "get_fund_flow",
        "get_dragon_tiger_board",
        "get_lockup_expiry",
        "get_industry_comparison",
    ]
    for method in signal_methods:
        assert method in VENDOR_METHODS, f"Missing VENDOR_METHODS for {method}"
        assert "a_stock" in VENDOR_METHODS[method], f"Missing a_stock for {method}"
        # a_stock + akshare both provide these signal methods
        assert "akshare" in VENDOR_METHODS[method], f"Missing akshare for {method}"


def test_signal_data_category_exists():
    assert "signal_data" in TOOLS_CATEGORIES
    signal_tools = TOOLS_CATEGORIES["signal_data"]["tools"]
    assert "get_profit_forecast" in signal_tools
    assert "get_hot_stocks" in signal_tools
    assert "get_lockup_expiry" in signal_tools
