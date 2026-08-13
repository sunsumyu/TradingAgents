import pytest


def test_hot_money_tracker_importable():
    from tradingagents.agents.analysts.hot_money_tracker import create_hot_money_tracker
    assert callable(create_hot_money_tracker)
