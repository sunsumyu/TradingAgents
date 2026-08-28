"""YAML configuration endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException

from ..schemas import ConfigSaveRequest

router = APIRouter()
logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".tradingagents"
CONFIG_FILE = CONFIG_DIR / "gui_config.yaml"


@router.get("/api/config")
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


@router.post("/api/config")
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
