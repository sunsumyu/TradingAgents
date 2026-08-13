import pytest


def test_lockup_watcher_importable():
    from tradingagents.agents.analysts.lockup_watcher import create_lockup_watcher
    assert callable(create_lockup_watcher)
