import pytest
from tradingagents.default_config import DEFAULT_CONFIG


def test_market_type_in_config():
    assert "market_type" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["market_type"] == "auto"


def test_astock_config_keys():
    assert "astock_lookback_days" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["astock_lookback_days"] == 60
    assert "astock_trading_sessions" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["astock_trading_sessions"] is True


def test_market_type_env_override():
    import os
    os.environ["TRADINGAGENTS_MARKET_TYPE"] = "astock"
    try:
        from importlib import reload
        import tradingagents.default_config as cfg
        reload(cfg)
        assert cfg.DEFAULT_CONFIG["market_type"] == "astock"
    finally:
        del os.environ["TRADINGAGENTS_MARKET_TYPE"]
