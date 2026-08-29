"""Analysis runner package.

Manages background analysis tasks, tracks progress, and stores results.
The public API is ``start_analysis`` and ``get_task``.
"""

from __future__ import annotations

import logging
import threading
import uuid

from ..schemas import AnalyzeRequest
from .config_builder import (
    build_config,
    compute_analysis_timeout_minutes,
)
from .graph_runner import _run_analysis
from .progress import PIPELINE_PHASES
from .task_state import TaskState, get_task, get_progress_events, register_task

__all__ = [
    "start_analysis",
    "get_task",
    "get_progress_events",
    "compute_analysis_timeout_minutes",
    # Re-export for tests that import _build_config directly
    "build_config",
    # Symbols used by server.py
    "PIPELINE_PHASES",
]

logger = logging.getLogger(__name__)


def start_analysis(request: AnalyzeRequest) -> str:
    """Start a background analysis task. Returns the task_id immediately."""
    task_id = str(uuid.uuid4())
    task = TaskState(task_id, request.ticker, request)

    register_task(task)

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
