"""LLM client creation and provider-kwargs resolution.

Extracted from TradingAgentsGraph._get_provider_kwargs to follow SRP:
the God Class should not need to know about per-provider thinking configs.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── retry coercion (kept here because it validates an LLM-side config) ────────

def coerce_max_retries(value) -> int:
    """Validate an ``llm_max_retries`` value to a non-negative int.

    Accepts an int or a numeric string (env vars arrive as strings).  Rejects
    booleans and negatives loudly so a misconfiguration fails at startup rather
    than silently disabling retries.
    """
    if isinstance(value, bool):
        raise ValueError(f"llm_max_retries must be an integer, not a boolean: {value!r}")
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"llm_max_retries must be an integer, got {value!r}") from exc
    if n < 0:
        raise ValueError(f"llm_max_retries must be >= 0, got {n}")
    return n


# ── provider-kwargs resolution ────────────────────────────────────────────────

def get_provider_kwargs(config: dict[str, Any], model_type: str = "quick") -> dict[str, Any]:
    """Build provider-specific kwargs for LLM client creation.

    Args:
        config: The full TradingAgents config dict.
        model_type: ``"quick"`` or ``"deep"`` — determines which provider config
            to read.  A fallback chain (model-type-specific → generic) is used
            for provider, api_key, and temperature.

    Returns:
        Keyword arguments suitable for passing to ``create_quick_llm`` /
        ``create_deep_llm``.
    """
    kwargs: dict[str, Any] = {}

    # Resolve provider for this model type (falls back to single-provider config)
    provider_key = (
        f"{model_type}_llm_provider"
        if model_type in ("quick", "deep")
        else "llm_provider"
    )
    provider = config.get(provider_key) or config.get("llm_provider", "openai")
    provider = provider.lower()

    # Forward API key: check model-type-specific key first, then generic
    api_key = config.get(f"{model_type}_api_key") or config.get("api_key")
    if api_key:
        kwargs["api_key"] = api_key

    # ── provider-specific thinking configuration ──────────────────────────
    if provider == "google":
        thinking_level = config.get("google_thinking_level")
        if thinking_level:
            kwargs["thinking_level"] = thinking_level

    elif provider == "openai":
        reasoning_effort = config.get("openai_reasoning_effort")
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

    elif provider == "anthropic":
        effort = config.get("anthropic_effort")
        if effort:
            kwargs["effort"] = effort

    # ── cross-provider settings ───────────────────────────────────────────
    # Sampling temperature — float() so env-string "0.2" works like 0.2.
    temperature = config.get("temperature")
    if temperature is not None and temperature != "":
        kwargs["temperature"] = float(temperature)

    # SDK retry budget — forward only when explicitly set so each provider
    # keeps its own default (usually 2) otherwise (#1091).
    max_retries = config.get("llm_max_retries")
    if max_retries is not None and max_retries != "":
        kwargs["max_retries"] = coerce_max_retries(max_retries)

    # HTTP timeout — forward only when explicitly set.
    timeout = config.get("llm_timeout")
    if timeout is not None and timeout != "":
        kwargs["timeout"] = float(timeout)

    return kwargs
