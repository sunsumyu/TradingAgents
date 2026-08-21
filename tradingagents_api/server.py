"""FastAPI server for the TradingAgents GUI backend.

Run with:
    uvicorn tradingagents_api.server:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from tradingagents.llm_clients.api_key_env import PROVIDER_API_KEY_ENV
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

from .market_data import build_market_data
from .runner import get_task, start_analysis
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    MarketDataRequest,
    MarketDataResponse,
    ModelInfo,
    ProviderInfo,
    ReportResponse,
)

logger = logging.getLogger(__name__)

# YAML config file path
CONFIG_DIR = Path.home() / ".tradingagents"
CONFIG_FILE = CONFIG_DIR / "gui_config.yaml"

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TradingAgents API",
    description="Backend API for the TradingAgents GUI",
    version="1.0.0",
)

# CORS: allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "tradingagents-api"}


@app.get("/api/providers")
async def list_providers():
    """Return all LLM providers with their API key env vars and model options."""
    providers: list[ProviderInfo] = []

    for provider_name in MODEL_OPTIONS:
        mode_options = MODEL_OPTIONS[provider_name]
        models: dict[str, list[ModelInfo]] = {}
        for mode, option_list in mode_options.items():
            models[mode] = [
                ModelInfo(label=label, id=model_id)
                for label, model_id in option_list
            ]

        providers.append(
            ProviderInfo(
                name=provider_name,
                api_key_env=PROVIDER_API_KEY_ENV.get(provider_name),
                models=models,
            )
        )

    return providers


@app.get("/api/models/{provider}")
async def get_models(provider: str, proxy_url: str | None = None, api_key: str | None = None):
    """Return model options for a specific provider.

    If proxy_url is provided, attempt to query the proxy's /v1/models endpoint.
    Falls back to hardcoded models if proxy query fails or proxy_url is not provided.
    """
    import httpx

    provider_lower = provider.lower()

    # If proxy_url is provided, attempt to query the proxy's /v1/models endpoint.
    # This allows multi-model proxies to return their available models.
    if proxy_url:
        try:
            base = proxy_url.rstrip("/")
            models_urls = [
                f"{base}/v1/models",
                f"{base}/models",
            ]

            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=5.0) as client:
                for url in models_urls:
                    try:
                        response = await client.get(url, headers=headers)
                        if response.status_code == 200:
                            data = response.json()
                            # OpenAI-compatible format: {"data": [{"id": "model-id", ...}]}
                            if "data" in data and isinstance(data["data"], list):
                                models = [
                                    ModelInfo(label=m.get("id", m.get("name", "Unknown")), id=m["id"])
                                    for m in data["data"] if "id" in m
                                ]
                                if models:
                                    return {
                                        "name": provider_lower,
                                        "api_key_env": PROVIDER_API_KEY_ENV.get(provider_lower),
                                        "quick": models,
                                        "deep": models,
                                        "source": "proxy",
                                    }
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Failed to query proxy models: {e}")

    # Fallback to hardcoded models
    if provider_lower not in MODEL_OPTIONS:
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found")

    mode_options = MODEL_OPTIONS[provider_lower]
    models: dict[str, list[ModelInfo]] = {}
    for mode, option_list in mode_options.items():
        models[mode] = [
            ModelInfo(label=label, id=model_id)
            for label, model_id in option_list
        ]

    return {
        "name": provider_lower,
        "api_key_env": PROVIDER_API_KEY_ENV.get(provider_lower),
        "quick": models.get("quick", []),
        "deep": models.get("deep", []),
        "source": "hardcoded",
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def start_analyze(request: AnalyzeRequest):
    """Start a new analysis task and return its ID immediately."""
    try:
        task_id = start_analysis(request)
        return AnalyzeResponse(task_id=task_id, status="started")
    except Exception as exc:
        logger.error("Failed to start analysis: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start analysis: {exc}")


@app.get("/api/analyze/{task_id}/stream")
async def stream_progress(task_id: str):
    """SSE endpoint that streams analysis progress events.

    Emits events of type 'progress', 'complete', or 'error'.
    Polls the task state every 0.5 seconds and sends new events as they appear.
    """
    task = get_task(task_id)
    if task is None:
        # Return a single error event and close
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

            # Send any new progress events
            with task._lock:
                current_events = list(task.events)
                current_status = task.status
                current_ticker = task.ticker
                current_signal = task.signal
                current_error = task.error

            for event in current_events[seen:]:
                yield f"event: progress\ndata: {event.model_dump_json()}\n\n"
            seen = len(current_events)

            # Flush streaming tokens (high-frequency, batched per 0.5s poll)
            tokens = task.flush_tokens()
            if tokens:
                # Send latest accumulated text per agent (not every token)
                latest_per_agent: dict[str, str] = {}
                for tok in tokens:
                    latest_per_agent[tok.agent] = tok.token
                for agent, text in latest_per_agent.items():
                    yield f"event: token\ndata: {json.dumps({'agent': agent, 'token': text})}\n\n"

            # Check for completion
            if current_status == "completed":
                yield (
                    f"event: complete\ndata: "
                    f"{json.dumps({'ticker': current_ticker, 'signal': current_signal})}\n\n"
                )
                break

            # Check for error
            if current_status == "error":
                yield (
                    f"event: error\ndata: "
                    f"{json.dumps({'message': current_error or 'Unknown error'})}\n\n"
                )
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/report/{task_id}")
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


@app.get("/api/report/{task_id}/sections/{section}")
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


@app.post("/api/market-data", response_model=MarketDataResponse)
async def get_market_data(request: MarketDataRequest):
    """Fetch chart data, fundamentals, and news without running agents."""
    return build_market_data(request.ticker, request.date)


# ---------------------------------------------------------------------------
# YAML Config endpoints
# ---------------------------------------------------------------------------

class ConfigSaveRequest(BaseModel):
    """Request body for saving GUI config."""
    config: dict[str, Any]


@app.get("/api/config")
async def load_config():
    """Load GUI configuration from YAML file."""
    if not CONFIG_FILE.exists():
        return {"config": None, "path": str(CONFIG_FILE)}

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return {"config": config, "path": str(CONFIG_FILE)}
    except Exception as e:
        logger.error("Failed to load config: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to load config: {e}")


@app.post("/api/config")
async def save_config(request: ConfigSaveRequest):
    """Save GUI configuration to YAML file."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(request.config, f, allow_unicode=True, default_flow_style=False)
        logger.info("Config saved to %s", CONFIG_FILE)
        return {"status": "ok", "path": str(CONFIG_FILE)}
    except Exception as e:
        logger.error("Failed to save config: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save config: {e}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    """Run the server with uvicorn."""
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    uvicorn.run(
        "tradingagents_api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
