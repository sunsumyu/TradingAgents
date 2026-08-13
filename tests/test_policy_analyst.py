import pytest


def test_policy_analyst_importable():
    from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
    assert callable(create_policy_analyst)
