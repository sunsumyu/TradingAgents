"""Pydantic schemas for the TradingAgents API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Configuration for a single LLM model (provider + model + auth)."""

    provider: str = Field(description="LLM provider name")
    model: str = Field(description="Model identifier")
    api_key: str | None = Field(default=None, description="API key for this provider")
    backend_url: str | None = Field(default=None, description="Custom API base URL")


class AnalyzeRequest(BaseModel):
    """Request body for starting an analysis."""

    ticker: str = Field(..., description="Ticker symbol, e.g. AAPL, 0700.HK, BTC-USD")
    date: str = Field(..., description="Analysis date in YYYY-MM-DD format")
    market_type: str | None = Field(
        default=None,
        description="Market type override: us, astock, hk, crypto. Auto-detected from ticker if omitted.",
    )
    language: str = Field(default="Chinese", description="Output language for reports")
    analysts: list[str] = Field(
        default=["market", "social", "news", "fundamentals"],
        description="Analyst types to run",
    )
    depth: str = Field(
        default="medium",
        description="Research depth: shallow=1 round, medium=3 rounds, deep=5 rounds",
    )
    # Multi-platform LLM config: each model type can use independent providers
    quick_model: ModelConfig | None = Field(
        default=None,
        description="Quick-thinking model config (provider, model, api_key, backend_url)",
    )
    deep_model: ModelConfig | None = Field(
        default=None,
        description="Deep-thinking model config (provider, model, api_key, backend_url)",
    )
    # Legacy single-provider config (backward compatible)
    llm_provider: str = Field(default="google", description="LLM provider name (used if quick_model/deep_model not set)")
    deep_think_llm: str = Field(default="gemini-3.1-pro-preview", description="Model ID for deep thinking")
    quick_think_llm: str = Field(default="gemini-3.5-flash", description="Model ID for quick thinking")
    api_key: str | None = Field(default=None, description="Optional API key override (legacy)")
    backend_url: str | None = Field(default=None, description="Custom LLM API base URL (legacy)")
    temperature: float | None = Field(default=None, description="Sampling temperature")
    openai_reasoning_effort: str | None = Field(
        default=None, description="OpenAI reasoning effort level"
    )
    google_thinking_level: str | None = Field(
        default=None, description="Gemini thinking mode level"
    )
    anthropic_effort: str | None = Field(
        default=None, description="Claude effort level"
    )


class AnalyzeResponse(BaseModel):
    """Response returned when an analysis task is started."""

    task_id: str
    status: str = "started"


class ProgressEvent(BaseModel):
    """A single progress update emitted during analysis."""

    phase: str = Field(
        description="Current pipeline phase (e.g. analysts, research, trading, risk, portfolio)"
    )
    agent: str = Field(description="Agent or component name")
    status: str = Field(description="Agent status: in_progress, completed, error")
    message: str = Field(default="", description="Human-readable progress message")
    timestamp: str = Field(description="ISO 8601 timestamp")


class StreamingTokenEvent(BaseModel):
    """A single streaming token emitted during LLM generation."""

    agent: str = Field(description="Agent producing the token")
    token: str = Field(description="Accumulated text content so far")
    timestamp: str = Field(description="ISO 8601 timestamp")


class ModelInfo(BaseModel):
    """A single model option."""

    label: str = Field(description="Display label for the model")
    id: str = Field(description="Model identifier string")


class ProviderInfo(BaseModel):
    """Information about an LLM provider."""

    name: str = Field(description="Provider identifier")
    api_key_env: str | None = Field(
        default=None, description="Environment variable holding the API key, if any"
    )
    models: dict[str, list[ModelInfo]] = Field(
        default_factory=dict,
        description="Model options keyed by mode (quick, deep)",
    )


class ReportResponse(BaseModel):
    """The completed analysis report."""

    ticker: str
    signal: str = Field(description="Trading signal: Buy, Overweight, Hold, Underweight, or Sell")
    report_md: str = Field(description="Full consolidated markdown report")
    sections: dict[str, str] = Field(
        default_factory=dict,
        description="Individual report sections keyed by phase name",
    )
