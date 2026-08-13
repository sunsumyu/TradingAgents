import pytest
from tradingagents.graph.analyst_execution import (
    ASTOCK_ANALYST_NODE_SPECS,
    build_analyst_execution_plan,
)


def test_astock_specs_exist():
    assert "policy" in ASTOCK_ANALYST_NODE_SPECS
    assert "hot_money" in ASTOCK_ANALYST_NODE_SPECS
    assert "lockup" in ASTOCK_ANALYST_NODE_SPECS


def test_astock_spec_naming():
    policy = ASTOCK_ANALYST_NODE_SPECS["policy"]
    assert policy.agent_node == "Policy Analyst"
    assert policy.clear_node == "Msg Clear Policy"
    assert policy.tool_node == "tools_policy"
    assert policy.report_key == "policy_report"


def test_build_plan_with_astock():
    plan = build_analyst_execution_plan(
        ["market", "social", "news", "fundamentals", "policy", "hot_money", "lockup"]
    )
    assert len(plan.specs) == 7
    keys = [s.key for s in plan.specs]
    assert "policy" in keys
    assert "hot_money" in keys
    assert "lockup" in keys
