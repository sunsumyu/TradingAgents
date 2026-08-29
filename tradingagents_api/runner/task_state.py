"""Task state management for background analysis tasks.

Holds the mutable state for a single analysis task and the global task
registry shared across the SSE endpoint and the analysis thread.
"""

from __future__ import annotations

import threading
from datetime import datetime

from ..schemas import ProgressEvent, ReportResponse, StreamingTokenEvent


class TaskState:
    """Holds the mutable state for a single analysis task."""

    def __init__(self, task_id: str, ticker: str, request):
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


def register_task(task: TaskState) -> None:
    """Register a new task in the global registry."""
    with _tasks_lock:
        _tasks[task.task_id] = task


def get_progress_events(task_id: str) -> list[ProgressEvent]:
    """Return the current list of progress events for *task_id*."""
    task = get_task(task_id)
    if task is None:
        return []
    with task._lock:
        return list(task.events)
