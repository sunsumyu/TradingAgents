"""Analysis lifecycle endpoints: start, stream progress, retrieve report."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from ..runner import get_task, start_analysis
from ..schemas import AnalyzeRequest, AnalyzeResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/analyze", response_model=AnalyzeResponse)
async def start_analyze(request: AnalyzeRequest):
    """Start a new analysis task and return its ID immediately."""
    try:
        task_id = start_analysis(request)
        return AnalyzeResponse(task_id=task_id, status="started")
    except Exception as exc:
        logger.error("Failed to start analysis: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {exc}")


@router.get("/api/analyze/{task_id}/stream")
async def stream_progress(task_id: str):
    """SSE endpoint that streams analysis progress events.

    Emits events of type 'progress', 'complete', or 'error'.
    Polls the task state every 0.5 seconds and sends new events as they appear.
    """
    task = get_task(task_id)
    if task is None:
        async def immediate_error():
            yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
        return StreamingResponse(immediate_error(), media_type="text/event-stream")

    async def event_generator():
        seen = 0
        logger.info("[sse] Starting SSE stream for task %s", task_id)
        while True:
            task = get_task(task_id)
            if task is None:
                yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                break

            with task._lock:
                current_events = list(task.events)
                current_status = task.status
                current_ticker = task.ticker
                current_signal = task.signal
                current_error = task.error

            for event in current_events[seen:]:
                yield f"event: progress\ndata: {event.model_dump_json()}\n\n"
            seen = len(current_events)

            tokens = task.flush_tokens()
            if tokens:
                latest_per_agent: dict[str, str] = {}
                for tok in tokens:
                    latest_per_agent[tok.agent] = tok.token
                for agent, text in latest_per_agent.items():
                    yield f"event: token\ndata: {json.dumps({'agent': agent, 'token': text})}\n\n"

            if current_status == "completed":
                yield (
                    f"event: complete\ndata: "
                    f"{json.dumps({'ticker': current_ticker, 'signal': current_signal})}\n\n"
                )
                break

            if current_status == "error":
                yield (
                    f"event: error\ndata: "
                    f"{json.dumps({'message': current_error or 'Unknown error'})}\n\n"
                )
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/report/{task_id}")
async def get_report(task_id: str):
    """Return the completed analysis report for a task."""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status == "running" or task.status == "pending":
        raise HTTPException(status_code=202, detail="Analysis still in progress")
    if task.status == "error":
        raise HTTPException(status_code=500, detail=f"Analysis failed: {task.error}")
    if task.report is None:
        raise HTTPException(status_code=404, detail="Report not yet available")

    return task.report


@router.get("/api/report/{task_id}/sections/{section}")
async def get_report_section(task_id: str, section: str):
    """Return a single section of the report."""
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "completed" or task.report is None:
        raise HTTPException(status_code=404, detail="Report not yet available")
    if section not in task.report.sections:
        raise HTTPException(
            status_code=404,
            detail=f"Section '{section}' not found. Available: {list(task.report.sections.keys())}",
        )

    return {"section": section, "content": task.report.sections[section]}
