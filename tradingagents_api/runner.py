"""Core analysis runner for the TradingAgents API.

Manages background analysis tasks, tracks progress, and stores results.
"""

from __future__ import annotations

import logging
import os
import threading
import traceback
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.reporting import write_report_tree
from tradingagents.api_callbacks import ProgressCallbackHandler

from .schemas import AnalyzeRequest, ProgressEvent, ReportResponse, StreamingTokenEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Depth -> debate-round mapping
# ---------------------------------------------------------------------------
DEPTH_ROUNDS = {
    "shallow": 1,
    "medium": 3,
    "deep": 5,
}

# Report keys that indicate analyst completion
ANALYST_REPORT_KEYS = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

# Ordered pipeline phases for progress tracking
PIPELINE_PHASES = [
    ("analysts", "Analyst Team"),
    ("research", "Research Team"),
    ("trading", "Trading Team"),
    ("risk", "Risk Management"),
    ("portfolio", "Portfolio Management"),
]


class TaskState:
    """Holds the mutable state for a single analysis task."""

    def __init__(self, task_id: str, ticker: str, request: AnalyzeRequest):
        self.task_id = task_id
        self.ticker = ticker
        self.request = request
        self.status: str = "pending"  # pending | running | completed | error
        self.config: dict = {}
        self.events: list[ProgressEvent] = []
        self.token_buffer: list[StreamingTokenEvent] = []
        self.report: ReportResponse | None = None
        self.error: str | None = None
        self.signal: str | None = None
        self._lock = threading.Lock()
        self._reported: set[str] = set()  # dedup: "agent:status" keys already emitted
        self._last_token_agent: str | None = None  # track current agent for tokens

    def add_event(self, phase: str, agent: str, status: str, message: str = ""):
        dedup_key = f"{agent}:{status}"
        if dedup_key in self._reported:
            return
        with self._lock:
            # Double-check under lock
            if dedup_key in self._reported:
                return
            self._reported.add(dedup_key)
            event = ProgressEvent(
                phase=phase,
                agent=agent,
                status=status,
                message=message,
                timestamp=datetime.now().isoformat(),
            )
            self.events.append(event)

    def set_completed(self, report: ReportResponse, signal: str):
        with self._lock:
            self.report = report
            self.signal = signal
            self.status = "completed"

    def set_error(self, error: str):
        with self._lock:
            self.error = error
            self.status = "error"

    def add_token(self, agent: str, token: str) -> None:
        """Append a streaming token (no dedup — called at high frequency)."""
        with self._lock:
            self.token_buffer.append(
                StreamingTokenEvent(
                    agent=agent,
                    token=token,
                    timestamp=datetime.now().isoformat(),
                )
            )

    def flush_tokens(self) -> list[StreamingTokenEvent]:
        """Return and clear the token buffer (called by SSE endpoint)."""
        with self._lock:
            tokens = list(self.token_buffer)
            self.token_buffer.clear()
            return tokens


# ---------------------------------------------------------------------------
# Global task registry
# ---------------------------------------------------------------------------
_tasks: dict[str, TaskState] = {}
_tasks_lock = threading.Lock()


def get_task(task_id: str) -> TaskState | None:
    """Return the TaskState for *task_id*, or None if not found."""
    with _tasks_lock:
        return _tasks.get(task_id)


def get_progress_events(task_id: str) -> list[ProgressEvent]:
    """Return the current list of progress events for *task_id*."""
    task = get_task(task_id)
    if task is None:
        return []
    with task._lock:
        return list(task.events)


# ---------------------------------------------------------------------------
# Config builder
# ---------------------------------------------------------------------------

def _build_config(request: AnalyzeRequest) -> dict:
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
# Progress detection helpers
# ---------------------------------------------------------------------------

ANTHROPOLOGIST_NAMES = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}


def _is_analyst_completed(task: TaskState, agent_name: str) -> bool:
    """Check if an analyst already has a 'completed' event."""
    return any(
        e.agent == agent_name and e.status == "completed"
        for e in task.events
    )


def _emit_next_agent(task: TaskState, selected_analysts: list[str],
                      completed_agent_key: str | None = None):
    """Emit an ``in_progress`` event for the next analyst that hasn't started.

    *completed_agent_key* is the short key (``"market"`` etc.) of the analyst
    that just finished.  When *None*, this is the initial call before any
    analyst has completed (used to mark the very first analyst as in_progress).
    """
    skip_agent = (
        ANTHROPOLOGIST_NAMES.get(completed_agent_key, completed_agent_key)
        if completed_agent_key
        else None
    )
    for analyst_key in selected_analysts:
        agent_name = ANTHROPOLOGIST_NAMES.get(analyst_key, analyst_key)
        if agent_name == skip_agent:
            continue  # don't re-emit for the agent that just completed
        if _is_analyst_completed(task, agent_name):
            continue  # already completed — skip
        task.add_event("analysts", agent_name, "in_progress",
                       f"⏳ {agent_name} 正在分析…")
        break  # only emit for the next pending analyst


def _detect_progress(task: TaskState, chunk: dict, selected_analysts: list[str]):
    """Inspect a streaming chunk and emit ProgressEvents for newly appeared content.

    Only emits "completed" events based on chunk content.  "in_progress" events
    are emitted exclusively by the callback handler (on_chat_model_start).
    """

    # -- Analyst reports --
    for analyst_key in selected_analysts:
        report_key = ANALYST_REPORT_KEYS.get(analyst_key)
        if report_key and chunk.get(report_key):
            agent_name = {
                "market": "Market Analyst",
                "social": "Sentiment Analyst",
                "news": "News Analyst",
                "fundamentals": "Fundamentals Analyst",
            }.get(analyst_key, analyst_key)
            task.add_event(
                "analysts",
                agent_name,
                "completed",
                f"{agent_name} report completed",
            )

    # -- Investment debate / Research team --
    debate = chunk.get("investment_debate_state")
    if debate:
        bull = debate.get("bull_history", "").strip()
        bear = debate.get("bear_history", "").strip()
        judge = debate.get("judge_decision", "").strip()
        if bull:
            task.add_event("research", "Bull Researcher", "completed", "Bull analysis complete")
        if bear:
            task.add_event("research", "Bear Researcher", "completed", "Bear analysis complete")
        if judge:
            task.add_event("research", "Research Manager", "completed", "Research manager decision complete")

    # -- Trader --
    if chunk.get("trader_investment_plan"):
        task.add_event("trading", "Trader", "completed", "Trader investment plan complete")

    # -- Risk debate --
    risk = chunk.get("risk_debate_state")
    if risk:
        if risk.get("aggressive_history", "").strip():
            task.add_event("risk", "Aggressive Analyst", "completed", "Aggressive analysis complete")
        if risk.get("conservative_history", "").strip():
            task.add_event("risk", "Conservative Analyst", "completed", "Conservative analysis complete")
        if risk.get("neutral_history", "").strip():
            task.add_event("risk", "Neutral Analyst", "completed", "Neutral analysis complete")
        if risk.get("judge_decision", "").strip():
            task.add_event("portfolio", "Portfolio Manager", "completed", "Portfolio manager decision complete")

    # -- Final trade decision --
    if chunk.get("final_trade_decision"):
        task.add_event("portfolio", "Final Decision", "completed", "Final trade decision reached")


# ---------------------------------------------------------------------------
# Analysis thread
# ---------------------------------------------------------------------------

def _run_analysis(task_id: str, request: AnalyzeRequest):
    """Execute the full analysis pipeline in a background thread."""
    task = get_task(task_id)
    if task is None:
        return

    task.status = "running"

    try:
        # Build config
        config = _build_config(request)
        task.config = config

        # Provider → env-var mapping (shared by API key setup and validation)
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

        # Set API key in environment if provided
        # When using a custom backend_url with no API key, inject a dummy key
        # to satisfy SDK validation (the proxy handles auth).
        def _setup_provider_env(provider: str, api_key: str | None, backend_url: str | None):
            """Set up API key and dummy key for a provider."""
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

        def _validate_provider(provider: str, api_key: str | None, backend_url: str | None) -> str | None:
            """Validate a provider config. Returns error message or None if OK."""
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

        # Multi-platform: validate each model type independently
        if request.quick_model:
            _setup_provider_env(
                request.quick_model.provider,
                request.quick_model.api_key,
                request.quick_model.backend_url,
            )
            error = _validate_provider(
                request.quick_model.provider,
                request.quick_model.api_key,
                request.quick_model.backend_url,
            )
            if error:
                task.set_error(f"快速模型配置错误: {error}")
                return

        if request.deep_model:
            _setup_provider_env(
                request.deep_model.provider,
                request.deep_model.api_key,
                request.deep_model.backend_url,
            )
            error = _validate_provider(
                request.deep_model.provider,
                request.deep_model.api_key,
                request.deep_model.backend_url,
            )
            if error:
                task.set_error(f"深度模型配置错误: {error}")
                return

        # Legacy single-provider validation (backward compatible)
        if not request.quick_model and not request.deep_model:
            _setup_provider_env(
                request.llm_provider,
                request.api_key,
                request.backend_url,
            )
            error = _validate_provider(
                request.llm_provider,
                request.api_key,
                request.backend_url,
            )
            if error:
                task.set_error(error)
                return

        # Log provider configuration
        if request.quick_model:
            logger.info("Quick model: %s/%s", request.quick_model.provider, request.quick_model.model)
        if request.deep_model:
            logger.info("Deep model: %s/%s", request.deep_model.provider, request.deep_model.model)
        if not request.quick_model and not request.deep_model:
            logger.info("Legacy single-provider: %s", request.llm_provider)

        # Emit initial progress
        task.add_event("analysts", "System", "in_progress", "Initializing analysis graph")

        # Create graph with real-time progress callback
        selected = tuple(request.analysts)
        progress_handler = ProgressCallbackHandler()
        def _sink(e):
            task.add_event(e["phase"], e["agent"], e["status"], e["message"])

        progress_handler.set_event_sink(_sink)
        progress_handler.set_token_sink(lambda agent, token: task.add_token(agent, token))
        progress_handler.set_error_callback(
            lambda msg: task.set_error(msg)
        )
        logger.info("Created ProgressCallbackHandler, passing to graph")
        graph = TradingAgentsGraph(
            selected_analysts=selected,
            debug=False,
            config=config,
            callbacks=[progress_handler],
        )
        logger.info("Graph created with %d callbacks", len(graph.callbacks))

        task.add_event("analysts", "System", "in_progress", "Graph initialized, starting streaming")

        # Resolve market type: use explicit override or auto-detect
        from tradingagents.markets.detector import detect_market_type

        market_type = request.market_type or detect_market_type(request.ticker)

        # Initialize state
        instrument_context = graph.resolve_instrument_context(request.ticker, market_type)
        init_state = graph.propagator.create_initial_state(
            request.ticker,
            request.date,
            asset_type=market_type,
            instrument_context=instrument_context,
        )
        args = graph.propagator.get_graph_args()

        # Stream chunks and track progress
        trace = []
        last_event_ts = [datetime.now()]  # mutable container for heartbeat thread
        analysis_start = datetime.now()  # defined BEFORE heartbeat starts
        MAX_ANALYSIS_MINUTES = 30  # safety timeout

        # Heartbeat thread: emits a "still waiting" event every 15s if no
        # new progress has appeared, so the GUI shows the LLM is thinking.
        def _heartbeat_loop():
            while task.status == "running":
                import time as _time
                _time.sleep(15)
                try:
                    if (datetime.now() - last_event_ts[0]).total_seconds() >= 15:
                        # Find the most recent in_progress agent for a useful message
                        current_agent = "System"
                        for ev in reversed(task.events):
                            if ev.status == "in_progress" and ev.agent != "System":
                                current_agent = ev.agent
                                break
                        elapsed = (datetime.now() - analysis_start).total_seconds()
                        task.add_event(
                            "heartbeat", "System", "in_progress",
                            f"⏳ {current_agent} 正在处理中… ({int(elapsed)}s)",
                        )
                except Exception:
                    logger.debug("Heartbeat loop error", exc_info=True)

        hb_thread = threading.Thread(target=_heartbeat_loop, daemon=True, name="heartbeat")
        hb_thread.start()

        # Mark the first analyst as in_progress so the GUI shows a spinner
        # immediately rather than leaving it in "pending" until the second
        # analyst starts.
        _emit_next_agent(task, list(selected))

        # Track which analyst keys have completed so we can correctly emit
        # in_progress for the *next* one after each completion.
        completed_keys: set[str] = set()

        # Timeout monitor: runs in a separate thread to detect hangs even when
        # the stream loop is blocked waiting for an LLM response.
        timeout_event = threading.Event()

        def _timeout_monitor():
            """Set timeout_event after MAX_ANALYSIS_MINUTES."""
            import time as _time
            _time.sleep(MAX_ANALYSIS_MINUTES * 60)
            if not timeout_event.is_set():
                timeout_event.set()
                logger.warning("Analysis timeout monitor triggered after %d minutes", MAX_ANALYSIS_MINUTES)

        timeout_thread = threading.Thread(target=_timeout_monitor, daemon=True)
        timeout_thread.start()

        try:
            logger.info("[stream] Starting graph.stream()")
            for chunk in graph.graph.stream(init_state, **args):
                logger.info("[stream] Received chunk #%d", len(trace) + 1)
                # Abort if a fatal LLM error was reported by the callback handler
                if progress_handler.has_fatal_error:
                    logger.error("Fatal LLM error detected, aborting analysis")
                    break

                # Safety: abort if analysis exceeds time limit
                if timeout_event.is_set():
                    raise TimeoutError(
                        f"Analysis exceeded {MAX_ANALYSIS_MINUTES} minute limit. "
                        "Check LLM proxy URL and API key configuration."
                    )

                _detect_progress(task, chunk, list(selected))
                # Detect newly completed analysts and emit in_progress for the next
                for analyst_key in selected:
                    if analyst_key in completed_keys:
                        continue
                    agent_name = ANTHROPOLOGIST_NAMES.get(analyst_key, analyst_key)
                    if _is_analyst_completed(task, agent_name):
                        completed_keys.add(analyst_key)
                        _emit_next_agent(task, list(selected),
                                         completed_agent_key=analyst_key)
                trace.append(chunk)
                last_event_ts[0] = datetime.now()

                # Log which keys are in the chunk for debugging stalls
                chunk_keys = [k for k in chunk.keys() if chunk[k]]
                if chunk_keys:
                    logger.info("[stream] chunk keys: %s", chunk_keys)
            logger.info("[stream] graph.stream() finished, %d chunks total", len(trace))
        finally:
            # Signal the timeout monitor to stop
            timeout_event.set()

        # If a fatal LLM error occurred, the task is already in error state
        # (set by the callback handler).  Skip result processing.
        if progress_handler.has_fatal_error:
            return

        # Merge chunks into final state (same pattern as CLI)
        final_state = {}
        for chunk in trace:
            final_state.update(chunk)

        # Process signal
        signal = graph.process_signal(final_state["final_trade_decision"])
        task.signal = signal

        # Build report sections
        sections: dict[str, str] = {}

        # Analyst reports — combined into a single "analyst" section for the
        # GUI's 分析师 tab.  Only include analysts that actually ran (the
        # state key is non-empty only for selected analysts).
        analyst_sections: list[str] = []
        for report_key, display_name in (
            ("market_report", "Market Analyst"),
            ("sentiment_report", "Sentiment Analyst"),
            ("news_report", "News Analyst"),
            ("fundamentals_report", "Fundamentals Analyst"),
        ):
            content = final_state.get(report_key)
            if content:
                sections[report_key] = content
                analyst_sections.append(f"## {display_name}\n\n{content}")
        if analyst_sections:
            sections["analyst"] = "\n\n".join(analyst_sections)

        # Research debate
        debate = final_state.get("investment_debate_state", {})
        if debate.get("judge_decision"):
            sections["research_decision"] = debate["judge_decision"]

        # Trader plan
        if final_state.get("trader_investment_plan"):
            sections["trader_plan"] = final_state["trader_investment_plan"]

        # Risk debate
        risk = final_state.get("risk_debate_state", {})
        if risk.get("judge_decision"):
            sections["risk_decision"] = risk["judge_decision"]

        # Final decision
        if final_state.get("final_trade_decision"):
            sections["final_decision"] = final_state["final_trade_decision"]

        # Build the consolidated markdown report by saving to disk
        report_path = graph.save_reports(final_state, request.ticker)
        report_md = report_path.read_text(encoding="utf-8") if report_path.exists() else ""

        # Build the ReportResponse
        report = ReportResponse(
            ticker=request.ticker,
            signal=signal,
            report_md=report_md,
            sections=sections,
        )

        task.set_completed(report, signal)
        logger.info(
            "Analysis completed for %s on %s — signal: %s",
            request.ticker, request.date, signal,
        )

    except TimeoutError as exc:
        tb = traceback.format_exc()
        logger.error("Analysis timed out for %s: %s\n%s", request.ticker, exc, tb)
        task.set_error(f"分析超时: {exc}")

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("Analysis failed for %s: %s\n%s", request.ticker, exc, tb)
        print(f"[ERROR] Analysis failed for {request.ticker}: {exc}\n{tb}",
              flush=True)

        # Provide user-friendly messages for common LLM errors
        err_str = str(exc).lower()
        if "authentication" in err_str or "auth" in err_str or "api_key" in err_str:
            task.set_error(
                f"API 认证失败: 请检查 API Key 是否正确。({exc})"
            )
        elif "connection" in err_str or "connect" in err_str or "timeout" in err_str:
            task.set_error(
                f"连接失败: 无法连接到 LLM 服务。请检查 LLM 代理地址和网络。({exc})"
            )
        elif "rate" in err_str and "limit" in err_str:
            task.set_error(
                f"请求频率超限: LLM API 调用过于频繁，请稍后重试。({exc})"
            )
        elif "not found" in err_str or "404" in err_str:
            task.set_error(
                f"模型不存在: 请检查模型名称是否正确。({exc})"
            )
        else:
            task.set_error(f"分析失败: {exc}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_analysis(request: AnalyzeRequest) -> str:
    """Start a background analysis task. Returns the task_id immediately."""
    task_id = str(uuid.uuid4())
    task = TaskState(task_id, request.ticker, request)

    with _tasks_lock:
        _tasks[task_id] = task

    # Mark analysts as pending on startup
    for analyst_key in request.analysts:
        agent_name = {
            "market": "Market Analyst",
            "social": "Sentiment Analyst",
            "news": "News Analyst",
            "fundamentals": "Fundamentals Analyst",
        }.get(analyst_key, analyst_key)
        task.add_event("analysts", agent_name, "pending", f"Waiting for {agent_name}")

    # Spawn background thread
    thread = threading.Thread(
        target=_run_analysis,
        args=(task_id, request),
        daemon=True,
        name=f"analysis-{task_id[:8]}",
    )
    thread.start()

    # Log provider configuration
    if request.quick_model:
        logger.info(
            "Task %s: quick=%s/%s, deep=%s/%s",
            task_id[:8],
            request.quick_model.provider,
            request.quick_model.model,
            request.deep_model.provider if request.deep_model else request.llm_provider,
            request.deep_model.model if request.deep_model else request.deep_think_llm,
        )
    else:
        logger.info(
            "Task %s: provider=%s, backend_url=%s, api_key=%s",
            task_id[:8],
            request.llm_provider,
            request.backend_url or "(default)",
            "***" + request.api_key[-4:] if request.api_key and len(request.api_key) >= 4 else request.api_key,
        )
    return task_id
