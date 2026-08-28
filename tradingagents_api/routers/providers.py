"""LL provider and model listing endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from tradingagents.llm_clients.api_key_env import PROVIDER_API_KEY_ENV
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS

from ..schemas import ModelInfo, ProviderInfo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/providers")
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


@router.get("/api/models/{provider}")
async def get_models(provider: str, proxy_url: str | None = None, api_key: str | None = None):
    """Return model options for a specific provider.

    If proxy_url is provided, attempt to query the proxy's /v1/models endpoint.
    Falls back to hardcoded models if proxy query fails or proxy_url is not provided.
    """
    import httpx

    provider_lower = provider.lower()

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
