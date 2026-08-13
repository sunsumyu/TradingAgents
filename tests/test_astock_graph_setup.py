import pytest
from unittest.mock import MagicMock


def test_astock_factories_importable():
    from tradingagents.agents import (
        create_policy_analyst,
        create_hot_money_tracker,
        create_lockup_watcher,
    )
    assert callable(create_policy_analyst)
    assert callable(create_hot_money_tracker)
    assert callable(create_lockup_watcher)
