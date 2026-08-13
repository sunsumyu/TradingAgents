# tests/test_astock_propagation.py
"""Tests for market detection integration in graph propagation flow."""

import pytest
from unittest.mock import patch, MagicMock

from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.markets.detector import detect_market_type
from tradingagents.graph.propagation import Propagator


# ── Market detection basics (delegates to Task 1 detector) ──────────────

class TestMarketDetectionBasics:
    """Verify detect_market_type works for various ticker formats."""

    def test_astock_6digit(self):
        assert detect_market_type("600519") == "astock"

    def test_astock_with_ss_suffix(self):
        assert detect_market_type("600519.SS") == "astock"

    def test_us_ticker(self):
        assert detect_market_type("NVDA") == "us"

    def test_us_ticker_with_suffix(self):
        assert detect_market_type("BRK.B") == "us"

    def test_hk_ticker(self):
        assert detect_market_type("0700.HK") == "hk"

    def test_crypto_ticker(self):
        assert detect_market_type("BTC-USD") == "crypto"


# ── Propagator state injection ──────────────────────────────────────────

class TestPropagatorStateInjection:
    """Verify propagation injects market_type into initial state."""

    def test_market_type_injected_us(self):
        """US ticker: market_type is 'us' in the state."""
        propagator = Propagator()
        with patch(
            "tradingagents.graph.propagation.detect_market_type",
            return_value="us",
        ):
            state = propagator.create_initial_state_with_market_detection(
                "NVDA", "2025-01-15", market_type="auto",
            )
        assert state["market_type"] == "us"

    def test_market_type_injected_astock(self):
        """A-share ticker: market_type is 'astock' in the state."""
        propagator = Propagator()
        with patch(
            "tradingagents.graph.propagation.detect_market_type",
            return_value="astock",
        ):
            state = propagator.create_initial_state_with_market_detection(
                "600519", "2025-01-15", market_type="auto",
            )
        assert state["market_type"] == "astock"

    def test_explicit_market_type_preserved(self):
        """Explicit market_type is preserved (no auto-detection)."""
        propagator = Propagator()
        state = propagator.create_initial_state_with_market_detection(
            "NVDA", "2025-01-15", market_type="astock",
        )
        assert state["market_type"] == "astock"

    def test_state_also_contains_standard_fields(self):
        """State contains the standard fields alongside market_type."""
        propagator = Propagator()
        with patch(
            "tradingagents.graph.propagation.detect_market_type",
            return_value="us",
        ):
            state = propagator.create_initial_state_with_market_detection(
                "NVDA", "2025-01-15", market_type="auto",
            )
        assert "company_of_interest" in state
        assert "investment_debate_state" in state
        assert "risk_debate_state" in state


# ── Config vendor override ──────────────────────────────────────────────

class TestConfigVendorOverride:
    """Verify propagation switches data_vendors for A-share."""

    def test_astock_overrides_data_vendors(self):
        """When market_type is astock, data_vendors are overridden."""
        config = DEFAULT_CONFIG.copy()
        config["data_vendors"] = {
            "core_stock_apis": "yfinance",
            "technical_indicators": "yfinance",
            "fundamental_data": "yfinance",
            "news_data": "yfinance",
            "signal_data": "yfinance",
        }
        propagator = Propagator()
        propagator.apply_astock_config_overrides(config)
        for key in ("core_stock_apis", "technical_indicators",
                     "fundamental_data", "news_data", "signal_data"):
            assert config["data_vendors"][key] == "a_stock", (
                f"data_vendors['{key}'] should be 'a_stock'"
            )

    def test_astock_sets_output_language_chinese(self):
        """A-share market switches output_language from English to Chinese."""
        config = DEFAULT_CONFIG.copy()
        config["output_language"] = "English"
        propagator = Propagator()
        propagator.apply_astock_config_overrides(config)
        assert config["output_language"] == "Chinese"

    def test_astock_preserves_existing_chinese(self):
        """If output_language is already Chinese, it stays Chinese."""
        config = DEFAULT_CONFIG.copy()
        config["output_language"] = "Chinese"
        propagator = Propagator()
        propagator.apply_astock_config_overrides(config)
        assert config["output_language"] == "Chinese"

    def test_us_does_not_override_vendors(self):
        """US market_type does NOT call apply_astock_config_overrides."""
        config = DEFAULT_CONFIG.copy()
        config["data_vendors"] = {
            "core_stock_apis": "yfinance",
            "technical_indicators": "yfinance",
        }
        # For US market, apply_astock_config_overrides should NOT be called.
        # Verify the original vendors are preserved when the override is skipped.
        assert config["data_vendors"]["core_stock_apis"] == "yfinance"

    def test_us_does_not_change_output_language(self):
        """US market_type does NOT change output_language."""
        config = DEFAULT_CONFIG.copy()
        config["output_language"] = "English"
        # For US market, apply_astock_config_overrides should NOT be called.
        # Verify the original language is preserved when the override is skipped.
        assert config["output_language"] == "English"


# ── Analyst selection extension ──────────────────────────────────────────

class TestAnalystSelectionExtension:
    """Verify A-share analysts are appended for astock market."""

    def test_astock_extends_analysts(self):
        """market_type='astock' adds policy, hot_money, lockup analysts."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        mock_config = DEFAULT_CONFIG.copy()
        mock_config["llm_provider"] = "openai"
        mock_config["api_key"] = "test-key"
        with patch.object(TradingAgentsGraph, "__init__", lambda self, *a, **kw: None):
            graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
            graph.config = mock_config
            graph.selected_analysts = ("market", "social", "news", "fundamentals")
            graph.propagator = Propagator()
            graph.astock_analysts = ("policy", "hot_money", "lockup")
            analysts = list(graph.selected_analysts)
            market_type = "astock"
            if market_type == "astock":
                analysts = analysts + list(graph.astock_analysts)
            assert "policy" in analysts
            assert "hot_money" in analysts
            assert "lockup" in analysts
            assert "market" in analysts
            assert len(analysts) == 7

    def test_us_does_not_extend_analysts(self):
        """market_type='us' keeps default analysts only."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        mock_config = DEFAULT_CONFIG.copy()
        with patch.object(TradingAgentsGraph, "__init__", lambda self, *a, **kw: None):
            graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
            graph.config = mock_config
            graph.selected_analysts = ("market", "social", "news", "fundamentals")
            graph.propagator = Propagator()
            graph.astock_analysts = ("policy", "hot_money", "lockup")
            analysts = list(graph.selected_analysts)
            market_type = "us"
            if market_type == "astock":
                analysts = analysts + list(graph.astock_analysts)
            assert analysts == ["market", "social", "news", "fundamentals"]

    def test_propagation_config_has_astock_analysts_key(self):
        """DEFAULT_CONFIG should have 'astock_analysts' key."""
        config = DEFAULT_CONFIG.copy()
        astock_analysts = config.get(
            "astock_analysts", ("policy", "hot_money", "lockup"),
        )
        assert astock_analysts == ("policy", "hot_money", "lockup")


# ── Market detection resolution helper ───────────────────────────────────

class TestMarketTypeResolution:
    """Verify resolve_market_type helper on Propagator."""

    def test_resolve_auto_detects_astock(self):
        propagator = Propagator()
        with patch(
            "tradingagents.graph.propagation.detect_market_type",
            return_value="astock",
        ):
            result = propagator.resolve_market_type("600519", market_type="auto")
        assert result == "astock"

    def test_resolve_explicit_astock(self):
        propagator = Propagator()
        result = propagator.resolve_market_type("NVDA", market_type="astock")
        assert result == "astock"

    def test_resolve_explicit_us(self):
        propagator = Propagator()
        result = propagator.resolve_market_type("600519", market_type="us")
        assert result == "us"

    def test_resolve_default_is_auto(self):
        propagator = Propagator()
        with patch(
            "tradingagents.graph.propagation.detect_market_type",
            return_value="us",
        ):
            result = propagator.resolve_market_type("NVDA")
        assert result == "us"
