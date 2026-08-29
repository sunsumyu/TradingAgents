"""Deterministic cache-key computation for LLM results.

The key is a SHA-256 hash of normalised messages plus model identity and
temperature.  Normalisation strips volatile fields (message IDs, usage
metadata) and deduplicates tool results so that the same logical
conversation always produces the same key — even when LangGraph re-executes
a ToolNode on resume and appends duplicate ``ToolMessage`` entries.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

logger = logging.getLogger(__name__)

# Fields that vary between runs and must not affect the cache key.
_VOLATILE_FIELDS = frozenset({
    "id",
    "response_metadata",
    "usage_metadata",
    "example",
    "tool_call_id",  # kept on ToolMessage for dedup, stripped from others
})


def _message_to_dict(msg: BaseMessage) -> dict:
    """Convert a LangChain message to a plain dict for hashing."""
    if isinstance(msg, tuple):
        # LangGraph sometimes stores messages as (role, content) tuples.
        role, content = msg
        return {"type": role, "content": content}

    entry: dict[str, Any] = {
        "type": msg.type,
        "content": msg.content if isinstance(msg.content, str) else str(msg.content),
    }

    if isinstance(msg, AIMessage) and msg.tool_calls:
        # Sort tool calls by name for determinism; sort args within each call.
        calls = []
        for tc in msg.tool_calls:
            calls.append({
                "name": tc.get("name", ""),
                "args": dict(sorted(tc.get("args", {}).items()))
                if isinstance(tc.get("args"), dict)
                else tc.get("args"),
            })
        entry["tool_calls"] = sorted(calls, key=lambda c: c["name"])

    if isinstance(msg, ToolMessage):
        entry["tool_call_id"] = msg.tool_call_id

    return entry


def _normalise_messages(messages: list) -> list[dict]:
    """Normalise a message list for deterministic hashing.

    * Deduplicates ``ToolMessage`` entries that share the same
      ``tool_call_id`` (happens when LangGraph replays a ToolNode on
      resume).
    * Sorts ``tool_calls`` and their ``args`` inside ``AIMessage`` entries.
    * Strips volatile fields (``id``, ``response_metadata``, …).
    """
    seen_tool_results: set[str] = set()
    normalised: list[dict] = []

    for msg in messages:
        entry = _message_to_dict(msg)

        # Deduplicate tool results.
        if entry.get("type") == "tool":
            tcid = entry.get("tool_call_id", "")
            if tcid in seen_tool_results:
                continue
            seen_tool_results.add(tcid)

        # Strip volatile fields.
        for field in _VOLATILE_FIELDS:
            entry.pop(field, None)

        normalised.append(entry)

    return normalised


def _extract_messages(input_data: Any) -> list:
    """Pull the message list out of whatever ``llm.invoke()`` received.

    LangChain accepts several shapes:

    * A plain ``list[BaseMessage]`` (most common).
    * A ``str`` (wrapped into a single-element list).
    * A ``dict`` with a ``"messages"`` key (prompt-template output).
    """
    if isinstance(input_data, list):
        return input_data
    if isinstance(input_data, str):
        return [HumanMessage(content=input_data)]
    if isinstance(input_data, dict) and "messages" in input_data:
        msgs = input_data["messages"]
        return msgs if isinstance(msgs, list) else [msgs]
    # Fallback: treat the whole thing as a single message content.
    return [HumanMessage(content=str(input_data))]


def _get_model_name(llm: Any) -> str:
    """Best-effort extraction of the model name from an LLM instance."""
    for attr in ("model_name", "model", "deployment_name"):
        val = getattr(llm, attr, None)
        if val:
            return str(val)
    # LangChain wrappers often store it in kwargs.
    return str(getattr(llm, "kwargs", {}).get("model_name", "unknown"))


def _get_temperature(llm: Any) -> float:
    """Best-effort extraction of temperature from an LLM instance."""
    val = getattr(llm, "temperature", None)
    if val is not None:
        return float(val)
    return getattr(llm, "kwargs", {}).get("temperature", 0.0)


def compute_cache_key(input_data: Any, llm: Any) -> str:
    """Return a 32-char hex SHA-256 cache key for an LLM invocation.

    The key is deterministic for identical logical inputs regardless of
    message ordering quirks, duplicate tool results, or volatile metadata.
    """
    messages = _extract_messages(input_data)
    normalised = _normalise_messages(messages)
    payload = json.dumps(
        {
            "msgs": normalised,
            "model": _get_model_name(llm),
            "temp": _get_temperature(llm),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
