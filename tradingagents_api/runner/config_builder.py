"""Build analysis config dicts from API requests.

Pure data transformation — no side effects, no I/O.
"""

from __future__ import annotations

from copy import deepcopy

from tradingagents.default_config import DEFAULT_CONFIG

from ..schemas import AnalyzeRequest

# ---------------------------------------------------------------------------
# Depth -> debate-round mapping
# ---------------------------------------------------------------------------
DEPTH_ROUNDS = {
    "shallow": 1,
    "medium": 3,
    "deep": 5,
}


def build_config(request: AnalyzeRequest) -> dict:
    """Build a config dict from the API request, merging over defaults."""
    config = deepcopy(DEFAULT_CONFIG)

    # Research depth -> round counts
    rounds = DEPTH_ROUNDS.get(request.depth.lower(), 3)
    config["max_debate_rounds"] = rounds
    config["max_risk_discuss_rounds"] = rounds

    # Multi-platform LLM config: each model type can use independent providers
    if request.quick_model:
        config["quick_llm_provider"] = request.quick_model.provider.lower()
        config["quick_think_llm"] = request.quick_model.model
        if request.quick_model.api_key:
            config["quick_api_key"] = request.quick_model.api_key
        if request.quick_model.backend_url:
            config["backend_url_quick"] = request.quick_model.backend_url

    if request.deep_model:
        config["deep_llm_provider"] = request.deep_model.provider.lower()
        config["deep_think_llm"] = request.deep_model.model
        if request.deep_model.api_key:
            config["deep_api_key"] = request.deep_model.api_key
        if request.deep_model.backend_url:
            config["backend_url_deep"] = request.deep_model.backend_url

    # Legacy single-provider config (backward compatible)
    # Only set if quick_model/deep_model not provided
    if not request.quick_model and not request.deep_model:
        config["llm_provider"] = request.llm_provider.lower()
        config["deep_think_llm"] = request.deep_think_llm
        config["quick_think_llm"] = request.quick_think_llm
        if request.backend_url:
            config["backend_url"] = request.backend_url
        if request.api_key:
            config["api_key"] = request.api_key

    config["output_language"] = request.language

    # Optional overrides
    if request.temperature is not None:
        config["temperature"] = request.temperature
    if request.openai_reasoning_effort is not None:
        config["openai_reasoning_effort"] = request.openai_reasoning_effort
    if request.google_thinking_level is not None:
        config["google_thinking_level"] = request.google_thinking_level
    if request.anthropic_effort is not None:
        config["anthropic_effort"] = request.anthropic_effort

    return config


# ---------------------------------------------------------------------------
# Analysis timeout scaling
# ---------------------------------------------------------------------------
_MIN_TIMEOUT_MINUTES = 30  # historical floor for small graphs


def compute_analysis_timeout_minutes(
    n_analysts: int,
    debate_rounds: int,
    risk_rounds: int,
) -> int:
    """Derive an analysis timeout from graph size.

    Each analyst averages ~5 min in steady state (tool calls + LLM round-trips).
    Debates add ~2 min per round.  A safety margin covers rate-limit retries
    and slow vendor responses.
    """
    analyst_minutes = n_analysts * 6  # 6 min per analyst (conservative)
    debate_minutes = (debate_rounds + risk_rounds) * 2
    safety = 5
    return max(_MIN_TIMEOUT_MINUTES, analyst_minutes + debate_minutes + safety)


# ---------------------------------------------------------------------------
# Provider env-var setup + validation
# ---------------------------------------------------------------------------
_API_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
    "xai": "XAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "qwen-cn": "DASHSCOPE_CN_API_KEY",
    "glm": "ZHIPU_API_KEY",
    "glm-cn": "ZHIPU_CN_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "minimax-cn": "MINIMAX_CN_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "groq": "GROQ_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "openai_compatible": "OPENAI_COMPATIBLE_API_KEY",
}


def setup_provider_env(provider: str, api_key: str | None, backend_url: str | None) -> None:
    """Set up API key and dummy key for a provider."""
    import logging
    import os

    logger = logging.getLogger(__name__)
    provider = provider.lower()

    # Inject dummy key if using custom backend_url without API key
    if backend_url and not api_key:
        _DUMMY_KEY_MAP = {
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openai_compatible": "OPENAI_COMPATIBLE_API_KEY",
        }
        env_var = _DUMMY_KEY_MAP.get(provider)
        if env_var and not os.environ.get(env_var):
            os.environ[env_var] = "sk-placeholder"
            logger.info("Injected dummy key for %s (using custom backend_url)", provider)

    # Set actual API key if provided
    if api_key:
        env_var = _API_KEY_MAP.get(provider)
        if env_var:
            os.environ[env_var] = api_key
            logger.info("Set %s for provider %s", env_var, provider)


def validate_provider(provider: str, api_key: str | None, backend_url: str | None) -> str | None:
    """Validate a provider config. Returns error message or None if OK."""
    import os

    provider = provider.lower()
    has_proxy = bool(backend_url)
    has_api_key = bool(api_key)
    env_key_var = _API_KEY_MAP.get(provider, "")
    has_env_key = bool(
        os.environ.get(env_key_var)
        and os.environ[env_key_var] not in ("placeholder", "sk-placeholder", "")
    )

    if not has_proxy and not has_api_key and not has_env_key:
        return (
            f"未配置 LLM API：提供商 {provider} 需要 API Key 或 LLM 代理地址。"
            f"请在 GUI 中填写 API Key 或 LLM 代理 URL。"
        )

    if has_proxy and not backend_url.startswith(("http://", "https://")):
        return f"LLM 代理地址格式错误: {backend_url}。必须以 http:// 或 https:// 开头。"

    return None
