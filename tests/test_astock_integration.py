# tests/test_astock_integration.py
import pytest
from tradingagents.markets.detector import detect_market_type
from tradingagents.graph.analyst_execution import build_analyst_execution_plan


def test_full_astock_pipeline_config():
    """Verify the full A-share pipeline can be configured."""
    # 1. Detect market
    assert detect_market_type("600519") == "astock"

    # 2. Build analyst plan with all 7 analysts
    plan = build_analyst_execution_plan(
        ["market", "social", "news", "fundamentals", "policy", "hot_money", "lockup"]
    )
    assert len(plan.specs) == 7

    # 3. Verify report keys
    report_keys = {s.report_key for s in plan.specs}
    assert "market_report" in report_keys
    assert "sentiment_report" in report_keys
    assert "news_report" in report_keys
    assert "fundamentals_report" in report_keys
    assert "policy_report" in report_keys
    assert "hot_money_report" in report_keys
    assert "lockup_report" in report_keys


def test_us_pipeline_unchanged():
    """Verify US pipeline still works with 4 analysts."""
    assert detect_market_type("NVDA") == "us"

    plan = build_analyst_execution_plan(
        ["market", "social", "news", "fundamentals"]
    )
    assert len(plan.specs) == 4
    report_keys = {s.report_key for s in plan.specs}
    assert "policy_report" not in report_keys
