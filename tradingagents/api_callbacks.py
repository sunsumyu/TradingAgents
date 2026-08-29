"""LangChain callback handlers for real-time progress reporting.

These handlers plug into the LLM client callback chain and emit progress
events that the API server forwards to the GUI via SSE.

Usage::

    from tradingagents.api_callbacks import ProgressCallbackHandler

    handler = ProgressCallbackHandler()
    handler.set_event_sink(my_emit_function)

    graph = TradingAgentsGraph(callbacks=[handler])
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Callable

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)

# ── LLM error message translation ─────────────────────────────────────────
#
# Provider SDKs raise exceptions with opaque English strings (HTTP status
# codes, raw JSON payloads, SDK-specific wrappers).  The GUI shows these
# directly to the user, who usually just sees gibberish.  This translation
# layer pattern-matches on the most common failure modes and rewrites the
# message into an actionable Chinese hint.

import json as _json


def _extract_error_text(error: BaseException) -> str:
    """Pull the most informative string out of a potentially nested exception."""
    for attr in ("message", "body", "response"):
        val = getattr(error, attr, None)
        if val is not None:
            if isinstance(val, dict):
                inner = val.get("error", val)
                if isinstance(inner, dict) and "message" in inner:
                    return str(inner["message"])
                return _json.dumps(val, ensure_ascii=False) if val else str(error)
            if isinstance(val, str) and val:
                return val
    return str(error)


def _translate_llm_error(error: BaseException) -> str:
    """Translate a raw LLM exception into a user-friendly Chinese message.

    Returns a concise, actionable one-liner.  If no pattern matches, returns
    the original ``str(error)`` unchanged so the user can still report it.
    """
    raw = _extract_error_text(error)
    raw_lower = raw.lower()

    # ── HTTP 401 / authentication ────────────────────────────────────────
    if "401" in raw_lower or "authentication" in raw_lower or "unauthorized" in raw_lower:
        if "free promotion has ended" in raw_lower or "subscription" in raw_lower:
            return (
                "LLM 免费额度已用完或试用期已过。请在平台配置中切换到付费模型，"
                "或更换其他 LLM 平台后重试。"
            )
        if "invalid api key" in raw_lower or "incorrect api key" in raw_lower:
            return "API Key 无效或已过期。请在「LLM 平台配置」中检查并更新 API Key。"
        return "API 认证失败（401）。请检查 API Key 是否正确，或确认账户未欠费。"

    # ── HTTP 403 / forbidden ─────────────────────────────────────────────
    if "403" in raw_lower or "forbidden" in raw_lower:
        return "API 访问被拒绝（403）。请确认 API Key 权限是否包含该模型，或联系服务商开通。"

    # ── HTTP 429 / rate limit ────────────────────────────────────────────
    if "429" in raw_lower or "rate limit" in raw_lower or "rate_limit" in raw_lower:
        return "请求频率超限（429）。请稍等片刻后重试，或降低并发数。"

    # ── HTTP 500 / 502 / 503 / server errors ────────────────────────────
    if "502" in raw_lower or "bad gateway" in raw_lower:
        return "LLM 服务暂时不可用（502 Bad Gateway），通常是服务商端临时故障，请稍后重试。"
    if "503" in raw_lower or "service unavailable" in raw_lower:
        return "LLM 服务暂不可用（503），服务商可能正在维护，请稍后重试。"
    if "500" in raw_lower or "internal server error" in raw_lower:
        return "LLM 服务内部错误（500），请稍后重试。"

    # ── Connection / network errors ──────────────────────────────────────
    if "connection" in raw_lower and ("refused" in raw_lower or "reset" in raw_lower):
        return "无法连接到 LLM 服务，请检查网络连接或代理设置。"
    if "timeout" in raw_lower or "timed out" in raw_lower:
        return "LLM 请求超时。可能是网络不稳定或请求内容过长，请稍后重试。"
    if "dns" in raw_lower or "name resolution" in raw_lower or "getaddrinfo" in raw_lower:
        return "DNS 解析失败。请检查网络连接和代理 URL 设置。"

    # ── Model not found ──────────────────────────────────────────────────
    if "404" in raw_lower or "not found" in raw_lower or "does not exist" in raw_lower:
        return "请求的模型不存在（404）。请在「模型选择」中确认模型 ID 拼写正确，或切换到可用模型。"

    # ── Context length / token limit ─────────────────────────────────────
    if "context" in raw_lower and ("length" in raw_lower or "exceed" in raw_lower or "too long" in raw_lower):
        return "输入内容超出模型上下文长度限制。请减少分析师数量或降低研究深度后重试。"
    if "token" in raw_lower and ("limit" in raw_lower or "exceed" in raw_lower):
        return "Token 数量超出限制。请减少分析师数量或降低研究深度后重试。"

    # ── Quota / billing ──────────────────────────────────────────────────
    if "quota" in raw_lower or ("insufficient" in raw_lower and "balance" in raw_lower):
        return "账户余额不足或配额已用完。请充值后重试，或切换到其他 LLM 平台。"

    # ── No match — return original ───────────────────────────────────────
    return raw


# ── Agent name resolution ────────────────────────────────────────────────────

# LangChain tags injected by the graph for each analyst agent.  The callback
# receives these tags and uses them to determine which agent is speaking.
_TAG_TO_AGENT: dict[str, str] = {
    "market_analyst": "Market Analyst",
    "sentiment_analyst": "Sentiment Analyst",
    "social_analyst": "Sentiment Analyst",
    "news_analyst": "News Analyst",
    "fundamentals_analyst": "Fundamentals Analyst",
    "research_manager": "Research Manager",
    "bull_researcher": "Bull Researcher",
    "bear_researcher": "Bear Researcher",
    "trader": "Trader",
    "risk_analyst": "Risk Analyst",
    "aggressive_analyst": "Aggressive Analyst",
    "conservative_analyst": "Conservative Analyst",
    "neutral_analyst": "Neutral Analyst",
    "portfolio_manager": "Portfolio Manager",
}

# Broader phase detection from tags
_TAG_TO_PHASE: dict[str, str] = {
    "market_analyst": "analysts",
    "sentiment_analyst": "analysts",
    "social_analyst": "analysts",
    "news_analyst": "analysts",
    "fundamentals_analyst": "analysts",
    "research_manager": "research",
    "bull_researcher": "research",
    "bear_researcher": "research",
    "trader": "trading",
    "risk_analyst": "risk",
    "aggressive_analyst": "risk",
    "conservative_analyst": "risk",
    "neutral_analyst": "risk",
    "portfolio_manager": "portfolio",
}

# Recognised LangGraph node names (from setup.py).
_KNOWN_NODES: set[str] = {
    "Fundamentals Analyst", "Market Analyst", "Sentiment Analyst", "News Analyst",
    "Bull Researcher", "Bear Researcher", "Research Manager",
    "Trader",
    "Aggressive Analyst", "Conservative Analyst", "Neutral Analyst",
    "Portfolio Manager",
}

# Tool node name prefixes — map to owning analyst agent.
_TOOL_NODE_PREFIX: dict[str, str] = {
    "tools_market": "Market Analyst",
    "tools_sentiment": "Sentiment Analyst",
    "tools_news": "News Analyst",
    "tools_fundamentals": "Fundamentals Analyst",
}

# Fallback: convert snake_case tag to Title Case
_SNAKE_RE = re.compile(r"_+")


def _resolve_agent(tags: list[str] | None, serialized: dict | None = None,
                   metadata: dict | None = None) -> tuple[str, str]:
    """Return ``(phase, agent_name)`` from LangChain tags, metadata, or serialized.

    Priority order:
    1. ``metadata["langgraph_node"]`` — most reliable, set by LangGraph
    2. Recognised tags in ``_TAG_TO_AGENT``
    3. Fallback to ``serialized["name"]`` (model name)
    """
    # 1. LangGraph node name from metadata (most reliable)
    if metadata:
        node = metadata.get("langgraph_node") or metadata.get("langgraph_step")
        if node:
            # Check if it's a known node
            if node in _KNOWN_NODES:
                # Determine phase from node name
                phase = _TAG_TO_PHASE.get(node.lower().replace(" ", "_"), "llm")
                return phase, node
            # Tool node → map to owning agent
            for prefix, agent in _TOOL_NODE_PREFIX.items():
                if node.startswith(prefix):
                    return "analysts", agent
            logger.debug("[resolve] Unknown langgraph_node: %s (tags=%s)", node, tags)

    # 2. Tags
    if tags:
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in _TAG_TO_AGENT:
                return _TAG_TO_PHASE.get(tag_lower, "llm"), _TAG_TO_AGENT[tag_lower]

    # 3. Fallback: model name
    if serialized:
        name = serialized.get("name", "LLM")
        return "llm", name
    return "llm", "LLM"


# ── Event emitter ────────────────────────────────────────────────────────────

EventDict = dict[str, str]


class ProgressCallbackHandler(BaseCallbackHandler):
    """LangChain callback that emits progress events for LLM and tool calls.

    Each event is a dict with keys: ``phase``, ``agent``, ``status``, ``message``.
    Events are dispatched to a configurable *sink* function set via
    :meth:`set_event_sink`.

    Optionally, an *error_callback* can be set — it will be called with the
    error message when a fatal LLM error occurs (e.g. 502, auth failure).
    The runner can use this to terminate the analysis immediately.
    """

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._sink: Callable[[EventDict], None] | None = None
        self._token_sink: Callable[[str, str], None] | None = None
        self._error_callback: Callable[[str], None] | None = None
        # Track active run_ids to avoid duplicate in_progress events
        self._active_runs: dict[str, tuple[str, str]] = {}  # run_id → (phase, agent)
        # Dedup: only emit one in_progress per (phase, agent) until a completed event
        self._emitted_in_progress: set[tuple[str, str]] = set()
        # Set to True by error_callback when a fatal LLM error occurs.
        # The runner's streaming loop checks this to break early.
        self.has_fatal_error: bool = False

    def set_event_sink(self, sink: Callable[[EventDict], None]) -> None:
        """Set the function that receives event dicts."""
        with self._lock:
            self._sink = sink

    def set_token_sink(self, sink: Callable[[str, str], None]) -> None:
        """Set function called with (agent_name, token_text) for streaming."""
        with self._lock:
            self._token_sink = sink

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        """Set a callback to invoke on fatal LLM errors.

        The callback receives the error message string.  The runner should
        use this to call ``task.set_error()`` and terminate the analysis.
        """
        with self._lock:
            self._error_callback = callback

    def _emit(self, phase: str, agent: str, status: str, message: str) -> None:
        """Thread-safe event emission."""
        sink = self._sink
        if sink is None:
            return
        event: EventDict = {
            "phase": phase,
            "agent": agent,
            "status": status,
            "message": message,
        }
        try:
            sink(event)
        except Exception:
            logger.debug("Progress sink raised", exc_info=True)

    # ── LLM callbacks ────────────────────────────────────────────────────

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Fallback for non-chat LLM models."""
        self._handle_llm_start(serialized, prompts, run_id=run_id, tags=tags,
                               metadata=metadata)

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list,
        *,
        run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self._handle_llm_start(serialized, messages, run_id=run_id, tags=tags,
                               metadata=metadata)

    def _handle_llm_start(
        self,
        serialized: dict[str, Any],
        messages_or_prompts: list,
        *,
        run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        try:
            logger.info("[callback] LLM start tags=%s node=%s",
                         tags,
                         metadata.get("langgraph_node") if metadata else None)
            phase, agent = _resolve_agent(tags, serialized, metadata)
            rid = str(run_id) if run_id else None

            with self._lock:
                if rid:
                    self._active_runs[rid] = (phase, agent)
                key = (phase, agent)
                if key in self._emitted_in_progress:
                    return  # already showing in_progress for this agent
                self._emitted_in_progress.add(key)

            self._emit(phase, agent, "in_progress", f"⏳ {agent} 正在调用 LLM…")
        except Exception:
            logger.warning("[callback] Failed to emit LLM start event",
                           exc_info=True)

    def on_chat_model_end(self, response: Any, *, run_id: Any = None, **kwargs: Any) -> None:
        """LangChain calls this for ChatOpenAI / ChatAnthropic etc."""
        self._finish_llm_run(response, run_id=run_id)

    def on_chat_model_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        """LangChain calls this for chat model errors."""
        self._error_llm_run(error, run_id=run_id)

    def on_llm_end(self, response: Any, *, run_id: Any = None, **kwargs: Any) -> None:
        self._finish_llm_run(response, run_id=run_id)

    def on_llm_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        self._error_llm_run(error, run_id=run_id)

    def _finish_llm_run(self, response: Any, *, run_id: Any = None) -> None:
        """Shared logic for on_llm_end / on_chat_model_end."""
        try:
            rid = str(run_id) if run_id else None
            with self._lock:
                info = self._active_runs.pop(rid, None) if rid else None
                if info:
                    self._emitted_in_progress.discard(info)

            if info is None:
                return

            phase, agent = info
            msg = f"✅ {agent} LLM 调用完成"
            try:
                gen = response.generations[0][0]
                usage = getattr(getattr(gen, "message", None), "usage_metadata", None)
                if usage:
                    inp = usage.get("input_tokens", 0)
                    out = usage.get("output_tokens", 0)
                    msg += f" ({inp}+{out} tokens)"
            except (IndexError, TypeError, AttributeError):
                pass

            self._emit(phase, agent, "completed", msg)
        except Exception:
            logger.warning("[callback] Failed to emit LLM end event",
                           exc_info=True)

    def _error_llm_run(self, error: BaseException, *, run_id: Any = None) -> None:
        """Shared logic for on_llm_error / on_chat_model_error."""
        try:
            rid = str(run_id) if run_id else None
            with self._lock:
                info = self._active_runs.pop(rid, None) if rid else None
                if info:
                    self._emitted_in_progress.discard(info)
                error_cb = self._error_callback

            if info is None:
                return
            phase, agent = info
            friendly = _translate_llm_error(error)

            # ── Rate-limit (429): emit warning, NOT fatal ──────────────
            # The runner's streaming loop handles 429 retry with backoff.
            raw = str(error).lower()
            is_429 = ("429" in raw or "rate limit" in raw
                       or "rate_limit" in raw or "too many requests" in raw)
            if is_429:
                msg = f"⚠️ {agent} 触发频率限制（429），将自动重试…"
                self._emit(phase, agent, "in_progress", msg)
                # Do NOT set has_fatal_error — let the runner handle retry
                return

            msg = f"❌ {agent} LLM 调用失败: {friendly}"
            self._emit(phase, agent, "error", msg)

            # Mark as fatal so the runner's streaming loop can break early
            with self._lock:
                self.has_fatal_error = True

            # Notify the runner so it can set task error status
            if error_cb:
                try:
                    error_cb(msg)
                except Exception:
                    logger.warning("Error callback raised", exc_info=True)
        except Exception:
            logger.warning("[callback] Failed to handle LLM error event",
                           exc_info=True)

    # ── Streaming token callbacks ─────────────────────────────────────────

    def on_chat_model_stream(
        self,
        chunk: Any,
        *,
        run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        """Capture per-token streaming chunks from the LLM."""
        try:
            rid = str(run_id) if run_id else None
            with self._lock:
                info = self._active_runs.get(rid) if rid else None
                token_sink = self._token_sink

            if info is None or token_sink is None:
                return

            _phase, agent = info
            # chunk is an AIMessageChunk; content is accumulated text
            content = getattr(chunk, "content", "") or ""
            if isinstance(content, str) and content:
                token_sink(agent, content)
        except Exception:
            # Never let token streaming break the analysis
            pass

    # ── Tool callbacks ────────────────────────────────────────────────────

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        phase, agent = _resolve_agent(tags, serialized)
        tool_name = serialized.get("name", "tool") if serialized else "tool"
        self._emit(phase, agent, "in_progress", f"🔧 {agent} 正在使用工具 {tool_name}…")

    def on_tool_end(self, output: str, *, run_id: Any = None, **kwargs: Any) -> None:
        # Tool end is informational — don't override LLM in_progress status
        pass

    def on_tool_error(self, error: BaseException, *, run_id: Any = None, **kwargs: Any) -> None:
        pass  # Tool errors are non-fatal, the agent continues
