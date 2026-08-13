import pytest


def test_a_stock_module_importable():
    """Verify the a_stock module can be imported."""
    from tradingagents.dataflows import a_stock

    assert hasattr(a_stock, "get_stock_data")
    assert hasattr(a_stock, "get_indicators")
    assert hasattr(a_stock, "get_fundamentals")
    assert hasattr(a_stock, "get_balance_sheet")
    assert hasattr(a_stock, "get_cashflow")
    assert hasattr(a_stock, "get_income_statement")
    assert hasattr(a_stock, "get_news")
    assert hasattr(a_stock, "get_global_news")
    assert hasattr(a_stock, "get_insider_transactions")
    assert hasattr(a_stock, "get_profit_forecast")
    assert hasattr(a_stock, "get_hot_stocks")
    assert hasattr(a_stock, "get_northbound_flow")
    assert hasattr(a_stock, "get_concept_blocks")
    assert hasattr(a_stock, "get_fund_flow")
    assert hasattr(a_stock, "get_dragon_tiger_board")
    assert hasattr(a_stock, "get_lockup_expiry")
    assert hasattr(a_stock, "get_industry_comparison")


def test_normalize_ticker():
    from tradingagents.dataflows.a_stock import _normalize_ticker

    assert _normalize_ticker("600519.SS") == "600519"
    assert _normalize_ticker("000001.SZ") == "000001"
    assert _normalize_ticker("sh600519") == "600519"
    assert _normalize_ticker("600519") == "600519"


def test_reject_non_a_share():
    from tradingagents.dataflows.a_stock import _reject_non_a_share

    # Should raise ValueError for non-A-share codes
    with pytest.raises(ValueError):
        _reject_non_a_share("get_stock_data", "NVDA")
    with pytest.raises(ValueError):
        _reject_non_a_share("get_stock_data", "0700.HK")
