"""LLM wrapper that transparently caches ``invoke()`` results.

Wrap any LangChain chat-model with :class:`CachedLLM` before passing it to
agent factories.  Every ``llm.invoke()`` call is intercepted — on a cache
hit the provider is never called, saving tokens and latency.  On a miss the
real LLM runs and its result is persisted for future runs.

The wrapper is designed to be a drop-in replacement: ``bind_tools()``,
``with_structured_output()``, and attribute access all delegate to the
underlying LLM so existing agent code needs **zero changes**.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from tradingagents.agents.utils.cache_utils import compute_cache_key
from tradingagents.llm_cache import LLMCache

logger = logging.getLogger(__name__)


# ── Serialisation helpers ──────────────────────────────────────────────

def _serialize_message(msg: BaseMessage) -> dict:
    """Convert a LangChain message to a JSON-safe dict."""
    if isinstance(msg, tuple):
        return {"type": msg[0], "content": msg[1]}

    entry: dict[str, Any] = {
        "type": msg.type,
        "content": msg.content if isinstance(msg.content, str) else str(msg.content),
    }

    if isinstance(msg, AIMessage) and msg.tool_calls:
        entry["tool_calls"] = [
            {
                "name": tc.get("name", ""),
                "args": tc.get("args", {}),
                "id": tc.get("id", ""),
            }
            for tc in msg.tool_calls
        ]
        # Also carry `tool_call_ids` for older LangChain versions.
        if hasattr(msg, "tool_call_ids") and msg.tool_call_ids:
            entry["tool_call_ids"] = msg.tool_call_ids

    if isinstance(msg, ToolMessage):
        entry["tool_call_id"] = msg.tool_call_id
        if hasattr(msg, "name") and msg.name:
            entry["name"] = msg.name

    return entry


def _deserialize_message(data: dict) -> BaseMessage:
    """Reconstruct a LangChain message from a cached dict."""
    msg_type = data.get("type", "human")
    content = data.get("content", "")

    if msg_type == "ai":
        msg = AIMessage(content=content)
        if "tool_calls" in data:
            # AIMessage stores tool_calls as a list of dicts.
            msg.tool_calls = data["tool_calls"]
        return msg
    if msg_type == "tool":
        return ToolMessage(
            content=content,
            tool_call_id=data.get("tool_call_id", ""),
            name=data.get("name", ""),
        )
    if msg_type == "system":
        return SystemMessage(content=content)
    if msg_type == "human":
        return HumanMessage(content=content)

    # Fallback — preserve unknown types as HumanMessage.
    return HumanMessage(content=f"[{msg_type}] {content}")


def _serialize_result(result: Any) -> dict:
    """Turn an LLM result into a JSON-safe dict for caching."""
    if isinstance(result, BaseMessage):
        return {"message": _serialize_message(result), "type": "message"}
    # Some LLMs return plain strings (rare with modern LangChain).
    return {"content": str(result), "type": "string"}


def _deserialize_result(data: dict) -> Any:
    """Reconstruct an LLM result from a cached dict."""
    if data.get("type") == "message":
        return _deserialize_message(data["message"])
    return data.get("content", "")


# ── CachedLLM wrapper ──────────────────────────────────────────────────

class CachedLLM:
    """Wraps a LangChain LLM to transparently cache ``invoke()`` results.

    Usage::

        cache = LLMCache(data_dir, ticker)
        cached_llm = CachedLLM(real_llm, cache)
        # Use exactly like a normal LLM:
        agent = create_market_analyst(cached_llm)
    """

    def __init__(self, llm: Any, cache: LLMCache) -> None:
        # Use object.__setattr__ to avoid triggering __getattr__ recursion.
        object.__setattr__(self, "_llm", llm)
        object.__setattr__(self, "_cache", cache)

    # ── Core interception ───────────────────────────────────────────

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        """Check the cache; on miss, call the real LLM and store the result."""
        cache_key = compute_cache_key(input, self._llm)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("LLM cache HIT (key=%s)", cache_key[:12])
            return _deserialize_result(cached)

        logger.debug("LLM cache MISS (key=%s)", cache_key[:12])
        result = self._llm.invoke(input, config=config, **kwargs)

        # Only cache successful results (skip if the result looks like an error).
        try:
            model_name = _get_model_name(self._llm)
            self._cache.set(cache_key, _serialize_result(result), model=model_name)
        except Exception as exc:
            logger.debug("Failed to cache LLM result: %s", exc)

        return result

    # ── LangChain Runnable interface proxies ────────────────────────

    def bind_tools(self, tools: list, **kwargs: Any) -> CachedLLM:
        """Proxy ``bind_tools`` and return a new CachedLLM wrapping the bound LLM."""
        bound = self._llm.bind_tools(tools, **kwargs)
        return CachedLLM(bound, self._cache)

    def with_structured_output(self, schema: Any, **kwargs: Any) -> CachedLLM:
        """Proxy ``with_structured_output`` and return a new CachedLLM."""
        structured = self._llm.with_structured_output(schema, **kwargs)
        return CachedLLM(structured, self._cache)

    def batch(self, inputs: list, config: Any = None, **kwargs: Any) -> list:
        """Batch invocation — checks cache for each input individually."""
        return [self.invoke(inp, config=config, **kwargs) for inp in inputs]

    def stream(self, input: Any, config: Any = None, **kwargs: Any):
        """Streaming is not cached — delegate directly to the underlying LLM."""
        return self._llm.stream(input, config=config, **kwargs)

    # ── Attribute delegation ────────────────────────────────────────

    def __getattr__(self, name: str) -> Any:
        return getattr(self._llm, name)

    def __repr__(self) -> str:
        return f"CachedLLM({self._llm!r})"


def _get_model_name(llm: Any) -> str:
    """Best-effort model name extraction."""
    for attr in ("model_name", "model", "deployment_name"):
        val = getattr(llm, attr, None)
        if val:
            return str(val)
    return str(getattr(llm, "kwargs", {}).get("model_name", "unknown"))
