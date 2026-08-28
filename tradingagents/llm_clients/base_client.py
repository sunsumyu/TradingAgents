import logging
import warnings
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


# Truncation detection across providers.  Each provider signals output
# truncation differently — there is no universal field or value.
#   · Anthropic          → stop_reason="max_tokens"
#   · OpenAI compatible  → finish_reason="length"
#   · Gemini             → finish_reason="max_tokens"
#   · OpenAI Responses   → status="incomplete" + incomplete_details.reason="max_output_tokens"
_TRUNCATION_MARKERS = {
    "stop_reason": {"max_tokens"},
    "finish_reason": {"length", "max_tokens"},
}
_RESPONSES_INCOMPLETE_REASONS = {"max_output_tokens", "max_tokens"}


def _truncation_field(metadata: dict):
    """Return (field, value) if the response was truncated, else None."""
    for field, truncated_values in _TRUNCATION_MARKERS.items():
        value = metadata.get(field)
        if isinstance(value, str) and value.strip().lower() in truncated_values:
            return field, value
    # OpenAI Responses API hides truncation in nested incomplete_details
    if str(metadata.get("status", "")).lower() == "incomplete":
        details = metadata.get("incomplete_details") or {}
        reason = details.get("reason") if isinstance(details, dict) else None
        if isinstance(reason, str) and reason.strip().lower() in _RESPONSES_INCOMPLETE_REASONS:
            return "incomplete_details.reason", reason
    return None


def warn_if_truncated(response, model: str):
    """Log a warning when the response was truncated by output token limits.

    Providers signal truncation via different metadata fields; this function
    checks all known patterns.  Only logs — never raises.
    """
    metadata = getattr(response, "response_metadata", {}) or {}
    field, value = _truncation_field(metadata)
    if field:
        logger.warning(
            "LLM response truncated by output token limit "
            "(%s=%s, model=%s). Increase max_tokens or shorten the prompt.",
            field, value, model,
        )


def normalize_content(response):
    """Normalize LLM response content to a plain string.

    Multiple providers (OpenAI Responses API, Google Gemini 3) return content
    as a list of typed blocks, e.g. [{'type': 'reasoning', ...}, {'type': 'text', 'text': '...'}].
    Downstream agents expect response.content to be a string. This extracts
    and joins the text blocks, discarding reasoning/metadata blocks.
    """
    content = response.content
    if isinstance(content, list):
        texts = [
            item.get("text", "") if isinstance(item, dict) and item.get("type") == "text"
            else item if isinstance(item, str) else ""
            for item in content
        ]
        response.content = "\n".join(t for t in texts if t)
    return response


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, model: str, base_url: str | None = None, **kwargs):
        self.model = model
        self.base_url = base_url
        self.kwargs = kwargs

    def get_provider_name(self) -> str:
        """Return the provider name used in warning messages."""
        provider = getattr(self, "provider", None)
        if provider:
            return str(provider)
        return self.__class__.__name__.removesuffix("Client").lower()

    def warn_if_unknown_model(self) -> None:
        """Warn when the model is outside the known list for the provider.

        When a custom base_url is set (proxy/relay), the model is checked
        against ALL providers' known lists, since the proxy may serve models
        from a different provider than the one selected in the UI.
        """
        if self.validate_model():
            return

        # Proxy scenario: model might belong to a different provider
        if self.base_url:
            from .model_catalog import get_known_models
            all_known = get_known_models()
            for provider_models in all_known.values():
                if self.model in provider_models:
                    return  # model found in another provider's catalog

        warnings.warn(
            (
                f"Model '{self.model}' is not in the known model list for "
                f"provider '{self.get_provider_name()}'. Continuing anyway."
            ),
            RuntimeWarning,
            stacklevel=2,
        )

    @abstractmethod
    def get_llm(self) -> Any:
        """Return the configured LLM instance."""
        pass

    @abstractmethod
    def validate_model(self) -> bool:
        """Validate that the model is supported by this client."""
        pass
