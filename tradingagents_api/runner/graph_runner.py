"""Graph execution orchestrator for analysis tasks.

Runs the LangGraph pipeline in a background thread with progress tracking,
retry logic, checkpointing, and timeout monitoring.
"""

from __future__ import annotations

import logging
import threading
import time
import traceback
from datetime import datetime

from tradingagents.api_callbacks import ProgressCallbackHandler, _translate_llm_error
from tradingagents.graph.trading_graph import TradingAgentsGraph

from ..schemas import AnalyzeRequest
from .config_builder import (
    build_config,
    compute_analysis_timeout_minutes,
    setup_provider_env,
    validate_provider,
)
from .progress import (
    ANTHROPOLOGIST_NAMES,
    detect_progress,
    emit_next_agent,
    is_analyst_completed,
    start_heartbeat,
)
from .report_builder import build_report
from .task_state import TaskState, get_task

logger = logging.getLogger(__name__)


def _run_analysis(task_id: str, request: AnalyzeRequest):
    """Execute the full analysis pipeline in a background thread."""
    task = get_task(task_id)
    if task is None:
        return

    task.status = "running"
    config = None  # ensure finally block can safely reference it

    try:
        # Build config
        config = build_config(request)
        task.config = config

        # ── Provider setup + validation ────────────────────────────────────
        # Multi-platform: validate each model type independently
        if request.quick_model:
            setup_provider_env(
                request.quick_model.provider,
                request.quick_model.api_key,
                request.quick_model.backend_url,
            )
            error = validate_provider(
                request.quick_model.provider,
                request.quick_model.api_key,
                request.quick_model.backend_url,
            )
            if error:
                task.set_error(f"快速模型配置错误: {error}")
                return

        if request.deep_model:
            setup_provider_env(
                request.deep_model.provider,
                request.deep_model.api_key,
                request.deep_model.backend_url,
            )
            error = validate_provider(
                request.deep_model.provider,
                request.deep_model.api_key,
                request.deep_model.backend_url,
            )
            if error:
                task.set_error(f"深度模型配置错误: {error}")
                return

        # Legacy single-provider validation (backward compatible)
        if not request.quick_model and not request.deep_model:
            setup_provider_env(
                request.llm_provider,
                request.api_key,
                request.backend_url,
            )
            error = validate_provider(
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

        # ── Market type detection + A-share overrides ──────────────────────
        from tradingagents.markets.detector import detect_market_type, _try_fix_astock_ticker

        market_type = request.market_type or detect_market_type(request.ticker, fix_astock=True)

        _corrected_ticker = request.ticker
        if market_type == "astock":
            fixed = _try_fix_astock_ticker(request.ticker)
            if fixed:
                _corrected_ticker = fixed

        logger.info("Detected market_type: %s for ticker %s (corrected: %s)",
                     market_type, request.ticker, _corrected_ticker)

        if market_type == "astock":
            config["data_vendors"] = {
                "core_stock_apis": "a_stock",
                "technical_indicators": "a_stock",
                "fundamental_data": "a_stock",
                "news_data": "a_stock",
                "signal_data": "a_stock",
            }
            if config.get("output_language") == "English":
                config["output_language"] = "Chinese"
            astock_analysts = ("policy", "hot_money", "lockup")
            current_analysts = list(selected)
            for a in astock_analysts:
                if a not in current_analysts:
                    current_analysts.append(a)
            selected = tuple(current_analysts)
            logger.info("A-share mode: analysts=%s, vendors=a_stock", selected)
            graph = TradingAgentsGraph(
                selected_analysts=selected,
                debug=False,
                config=config,
                callbacks=[progress_handler],
            )

        config["market_type"] = market_type

        if market_type == "astock" and request.ticker != _corrected_ticker:
            logger.info("A-share ticker corrected: %s -> %s", request.ticker, _corrected_ticker)
            request.ticker = _corrected_ticker

        # ── Enable checkpointing for resume support ────────────────────────
        config["checkpoint_enabled"] = True
        from tradingagents.graph.checkpointer import (
            get_checkpointer, thread_id as cp_thread_id,
            checkpoint_step, clear_checkpoint,
        )
        _run_sig = graph._run_signature(market_type)
        _cp_ticker = request.ticker
        _cp_tid = cp_thread_id(_cp_ticker, request.date, _run_sig)

        graph._checkpointer_ctx = get_checkpointer(
            config["data_cache_dir"], _cp_ticker
        )
        _saver = graph._checkpointer_ctx.__enter__()
        graph.graph = graph.workflow.compile(checkpointer=_saver)

        existing_step = checkpoint_step(
            config["data_cache_dir"], _cp_ticker, request.date, _run_sig,
        )

        if existing_step is not None and request.resume:
            logger.info(
                "Resuming from checkpoint step %d for %s on %s (thread=%s)",
                existing_step, _cp_ticker, request.date, _cp_tid,
            )
            task.add_event(
                "analysts", "System", "in_progress",
                f"♻️ 从断点恢复（已完成步骤 {existing_step}），继续分析…",
            )
        elif existing_step is not None and not request.resume:
            logger.info(
                "Clearing old checkpoint for %s on %s (step=%d) — starting fresh",
                _cp_ticker, request.date, existing_step,
            )
            clear_checkpoint(config["data_cache_dir"], _cp_ticker, request.date, _run_sig)
        else:
            logger.info("No existing checkpoint for %s on %s — starting fresh", _cp_ticker, request.date)

        task._cp_ticker = _cp_ticker
        task._cp_date = request.date
        task._cp_run_sig = _run_sig

        # ── Initialize graph state ─────────────────────────────────────────
        instrument_context = graph.resolve_instrument_context(request.ticker, market_type)
        init_state = graph.propagator.create_initial_state(
            request.ticker,
            request.date,
            asset_type=market_type,
            instrument_context=instrument_context,
        )
        init_state["market_type"] = market_type
        args = graph.propagator.get_graph_args()

        args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = _cp_tid
        logger.info("Checkpoint thread_id: %s", _cp_tid)

        # ── Stream chunks with retry logic ─────────────────────────────────
        trace = []
        last_event_ts = [datetime.now()]
        analysis_start = datetime.now()
        MAX_ANALYSIS_MINUTES = compute_analysis_timeout_minutes(
            n_analysts=len(selected),
            debate_rounds=config.get("max_debate_rounds", 3),
            risk_rounds=config.get("max_risk_discuss_rounds", 3),
        )
        logger.info("Analysis timeout set to %d minutes (for %d analysts)",
                     MAX_ANALYSIS_MINUTES, len(selected))

        hb_thread = start_heartbeat(task, analysis_start, last_event_ts)
        _emit_next_agent(task, list(selected))

        completed_keys: set[str] = set()
        timeout_event = threading.Event()

        def _timeout_monitor():
            import time as _time
            _time.sleep(MAX_ANALYSIS_MINUTES * 60)
            if not timeout_event.is_set():
                timeout_event.set()
                logger.warning("Analysis timeout monitor triggered after %d minutes", MAX_ANALYSIS_MINUTES)

        timeout_thread = threading.Thread(target=_timeout_monitor, daemon=True)
        timeout_thread.start()

        try:
            _stream_with_retry(
                task=task,
                graph=graph,
                init_state=init_state,
                args=args,
                selected=selected,
                progress_handler=progress_handler,
                trace=trace,
                last_event_ts=last_event_ts,
                completed_keys=completed_keys,
                timeout_event=timeout_event,
                max_minutes=MAX_ANALYSIS_MINUTES,
            )
        finally:
            timeout_event.set()

        if progress_handler.has_fatal_error:
            return

        # Merge chunks into final state
        final_state = {}
        for chunk in trace:
            final_state.update(chunk)

        signal = graph.process_signal(final_state["final_trade_decision"])
        task.signal = signal

        report_md_path = graph.save_reports(final_state, request.ticker)
        report_md = report_md_path.read_text(encoding="utf-8") if report_md_path.exists() else ""

        report = build_report(
            final_state=final_state,
            ticker=request.ticker,
            date=request.date,
            signal=signal,
            report_md=report_md,
        )

        task.set_completed(report, signal)
        logger.info(
            "Analysis completed for %s on %s — signal: %s",
            request.ticker, request.date, signal,
        )

        # Clear checkpoint on successful completion
        if config.get("checkpoint_enabled"):
            try:
                clear_checkpoint(
                    config["data_cache_dir"], task._cp_ticker,
                    task._cp_date, task._cp_run_sig,
                )
                logger.info("Checkpoint cleared after successful completion")
            except Exception:
                logger.debug("Failed to clear checkpoint", exc_info=True)

    except TimeoutError as exc:
        tb = traceback.format_exc()
        logger.error("Analysis timed out for %s: %s\n%s", request.ticker, exc, tb)
        task.set_error(f"分析超时: {exc}")

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error("Analysis failed for %s: %s\n%s", request.ticker, exc, tb)
        print(f"[ERROR] Analysis failed for {request.ticker}: {exc}\n{tb}",
              flush=True)

        friendly = _translate_llm_error(exc)
        if friendly != str(exc):
            task.set_error(f"❌ {friendly}")
        else:
            task.set_error(f"分析失败: {exc}")

    finally:
        if config is not None and config.get("checkpoint_enabled"):
            try:
                graph._checkpointer_ctx.__exit__(None, None, None)
            except Exception:
                logger.debug("Failed to close checkpointer", exc_info=True)


# ---------------------------------------------------------------------------
# Stream with retry
# ---------------------------------------------------------------------------

def _stream_with_retry(
    *,
    task: TaskState,
    graph: TradingAgentsGraph,
    init_state: dict,
    args: dict,
    selected: tuple,
    progress_handler: ProgressCallbackHandler,
    trace: list,
    last_event_ts: list[datetime],
    completed_keys: set[str],
    timeout_event: threading.Event,
    max_minutes: int,
):
    """Stream graph chunks with retry on rate-limit and network errors."""
    import httpx as _httpx

    def _is_rate_limit_error(exc: Exception) -> bool:
        raw = str(exc).lower()
        return ("429" in raw or "rate limit" in raw
                or "rate_limit" in raw or "too many requests" in raw)

    _MAX_NETWORK_RETRIES = 2
    _MAX_429_RETRIES = 3
    _NETWORK_RETRY_DELAY = 5
    total_attempts = _MAX_NETWORK_RETRIES + 1 + _MAX_429_RETRIES + 1
    attempt = 0

    while attempt < total_attempts:
        attempt += 1
        try:
            for chunk in graph.graph.stream(init_state, **args):
                logger.info("[stream] Received chunk #%d", len(trace) + 1)

                if progress_handler.has_fatal_error:
                    last_err = ""
                    for ev in reversed(task.events):
                        if ev.status == "error":
                            last_err = ev.message.lower()
                            break
                    if "429" in last_err or "rate limit" in last_err:
                        logger.warning("Rate-limit (429) detected in callback — will retry")
                        progress_handler.has_fatal_error = False
                        break
                    logger.error("Fatal LLM error detected, aborting analysis")
                    break

                if timeout_event.is_set():
                    raise TimeoutError(
                        f"Analysis exceeded {max_minutes} minute limit. "
                        "Check LLM proxy URL and API key configuration."
                    )

                detect_progress(task, chunk, list(selected))
                for analyst_key in selected:
                    if analyst_key in completed_keys:
                        continue
                    agent_name = ANTHROPOLOGIST_NAMES.get(analyst_key, analyst_key)
                    if is_analyst_completed(task, agent_name):
                        completed_keys.add(analyst_key)
                        emit_next_agent(task, list(selected),
                                        completed_agent_key=analyst_key)
                trace.append(chunk)
                last_event_ts[0] = datetime.now()

                chunk_keys = [k for k in chunk.keys() if chunk[k]]
                if chunk_keys:
                    logger.info("[stream] chunk keys: %s", chunk_keys)
            logger.info("[stream] graph.stream() finished, %d chunks total", len(trace))
            return  # success
        except Exception as exc:
            # Rate-limit (429) — exponential backoff
            if _is_rate_limit_error(exc) and attempt <= _MAX_429_RETRIES:
                delay = 30 * (2 ** (attempt - 1))  # 30, 60, 120s
                logger.warning(
                    "Rate-limit 429 (attempt %d/%d): retrying in %ds",
                    attempt, _MAX_429_RETRIES, delay,
                )
                task.add_event(
                    "system", "System", "in_progress",
                    f"⚠️ 请求频率超限（429），等待 {delay}s 后自动重试 "
                    f"({attempt}/{_MAX_429_RETRIES})…",
                )
                time.sleep(delay)
                progress_handler.has_fatal_error = False
                trace.clear()
                completed_keys.clear()
                continue
            # Transient network errors — short retry
            if isinstance(exc, (_httpx.RemoteProtocolError,
                               _httpx.ProtocolError,
                               ConnectionError, OSError)):
                if attempt <= _MAX_NETWORK_RETRIES:
                    logger.warning(
                        "Transient network error (attempt %d/%d): %s — retrying in %ds",
                        attempt, _MAX_NETWORK_RETRIES + 1, exc, _NETWORK_RETRY_DELAY,
                    )
                    task.add_event(
                        "system", "System", "in_progress",
                        f"⚠️ 连接中断，{attempt}/{_MAX_NETWORK_RETRIES + 1} 次重试中… ({exc})",
                    )
                    time.sleep(_NETWORK_RETRY_DELAY)
                    trace.clear()
                    completed_keys.clear()
                    continue
            # All retries exhausted or non-retryable error
            raise
