"""Tests for multi-platform LLM support."""

import pytest
from tradingagents.default_config import DEFAULT_CONFIG


class TestMultiPlatformConfig:
    """Test that multi-platform config keys are properly set up."""

    def test_default_config_has_quick_deep_providers(self):
        """Default config should have quick_llm_provider and deep_llm_provider keys."""
        assert "quick_llm_provider" in DEFAULT_CONFIG
        assert "deep_llm_provider" in DEFAULT_CONFIG
        assert "backend_url_quick" in DEFAULT_CONFIG
        assert "backend_url_deep" in DEFAULT_CONFIG

    def test_default_config_fallback_values(self):
        """Default values should be None (falls back to single-provider)."""
        assert DEFAULT_CONFIG["quick_llm_provider"] is None
        assert DEFAULT_CONFIG["deep_llm_provider"] is None
        assert DEFAULT_CONFIG["backend_url_quick"] is None
        assert DEFAULT_CONFIG["backend_url_deep"] is None


class TestFactoryHelpers:
    """Test create_quick_llm and create_deep_llm factory functions."""

    def test_create_quick_llm_fallback_to_single_provider(self):
        """When quick_llm_provider is None, should use llm_provider."""
        from tradingagents.llm_clients.factory import create_quick_llm

        config = {
            "llm_provider": "openai",
            "quick_think_llm": "gpt-4o-mini",
            "backend_url": None,
        }
        # Factory returns LLM object (doesn't raise without API key, just warns)
        llm = create_quick_llm(config)
        assert llm is not None

    def test_create_deep_llm_fallback_to_single_provider(self):
        """When deep_llm_provider is None, should use llm_provider."""
        from tradingagents.llm_clients.factory import create_deep_llm

        config = {
            "llm_provider": "openai",
            "deep_think_llm": "gpt-4o",
            "backend_url": None,
        }
        llm = create_deep_llm(config)
        assert llm is not None

    def test_create_quick_llm_independent_provider(self):
        """When quick_llm_provider is set, should use that provider."""
        from tradingagents.llm_clients.factory import create_quick_llm

        config = {
            "quick_llm_provider": "anthropic",
            "quick_think_llm": "Kimi",
            "llm_provider": "openai",  # Should be ignored
        }
        llm = create_quick_llm(config)
        assert llm is not None

    def test_create_deep_llm_independent_provider(self):
        """When deep_llm_provider is set, should use that provider."""
        from tradingagents.llm_clients.factory import create_deep_llm

        config = {
            "deep_llm_provider": "google",
            "deep_think_llm": "gemini-2.0-flash",
        }
        llm = create_deep_llm(config)
        assert llm is not None


class TestAPIRequestSchema:
    """Test that API request schema supports multi-platform config."""

    def test_analyze_request_with_model_config(self):
        """AnalyzeRequest should accept quick_model and deep_model."""
        from tradingagents_api.schemas import AnalyzeRequest, ModelConfig

        request = AnalyzeRequest(
            ticker="AAPL",
            date="2026-08-10",
            quick_model=ModelConfig(
                provider="anthropic",
                model="Kimi",
            ),
            deep_model=ModelConfig(
                provider="openai",
                model="gpt-4o",
            ),
        )
        assert request.quick_model is not None
        assert request.quick_model.provider == "anthropic"
        assert request.deep_model is not None
        assert request.deep_model.provider == "openai"

    def test_analyze_request_legacy_config(self):
        """AnalyzeRequest should still work with legacy single-provider config."""
        from tradingagents_api.schemas import AnalyzeRequest

        request = AnalyzeRequest(
            ticker="AAPL",
            date="2026-08-10",
            llm_provider="openai",
            quick_think_llm="gpt-4o-mini",
            deep_think_llm="gpt-4o",
        )
        assert request.llm_provider == "openai"
        assert request.quick_model is None
        assert request.deep_model is None


class TestConfigBuilder:
    """Test that _build_config handles multi-platform config correctly."""

    def test_build_config_with_model_config(self):
        """Config builder should set quick_llm_provider and deep_llm_provider."""
        from tradingagents_api.runner import build_config
        from tradingagents_api.schemas import AnalyzeRequest, ModelConfig

        request = AnalyzeRequest(
            ticker="AAPL",
            date="2026-08-10",
            quick_model=ModelConfig(
                provider="anthropic",
                model="Kimi",
                api_key="test-key-quick",
                backend_url="http://quick-proxy:8080",
            ),
            deep_model=ModelConfig(
                provider="openai",
                model="gpt-4o",
                api_key="test-key-deep",
                backend_url="http://deep-proxy:8080",
            ),
        )
        config = build_config(request)

        assert config["quick_llm_provider"] == "anthropic"
        assert config["quick_think_llm"] == "Kimi"
        assert config["quick_api_key"] == "test-key-quick"
        assert config["backend_url_quick"] == "http://quick-proxy:8080"

        assert config["deep_llm_provider"] == "openai"
        assert config["deep_think_llm"] == "gpt-4o"
        assert config["deep_api_key"] == "test-key-deep"
        assert config["backend_url_deep"] == "http://deep-proxy:8080"

    def test_build_config_legacy_fallback(self):
        """Config builder should use legacy config when model_config not set."""
        from tradingagents_api.runner import build_config
        from tradingagents_api.schemas import AnalyzeRequest

        request = AnalyzeRequest(
            ticker="AAPL",
            date="2026-08-10",
            llm_provider="openai",
            quick_think_llm="gpt-4o-mini",
            deep_think_llm="gpt-4o",
        )
        config = build_config(request)

        assert config["llm_provider"] == "openai"
        assert config["quick_think_llm"] == "gpt-4o-mini"
        assert config["deep_think_llm"] == "gpt-4o"
        # Should NOT set quick_llm_provider/deep_llm_provider when using legacy
        assert config["quick_llm_provider"] is None
        assert config["deep_llm_provider"] is None
