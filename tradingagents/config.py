"""TradingAgents unified configuration.

Centralizes all ports, paths, and connection settings.
Environment variables override defaults.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Home directory ────────────────────────────────────────────────────────────

TRADINGAGENTS_HOME = Path(os.environ.get(
    "TRADINGAGENTS_HOME",
    os.path.join(os.path.expanduser("~"), ".tradingagents")
))

# ── Backend ───────────────────────────────────────────────────────────────────

BACKEND_HOST = os.environ.get("TRADINGAGENTS_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.environ.get("TRADINGAGENTS_BACKEND_PORT", "8425"))

# ── Database ──────────────────────────────────────────────────────────────────

PG_HOST = os.environ.get("TRADINGAGENTS_PG_HOST", "127.0.0.1")
PG_PORT = int(os.environ.get("TRADINGAGENTS_PG_PORT", "5432"))
PG_USER = os.environ.get("TRADINGAGENTS_PG_USER", "postgres")
PG_PASSWORD = os.environ.get("TRADINGAGENTS_PG_PASSWORD", "postgres")
PG_DB = os.environ.get("TRADINGAGENTS_PG_DB", "tradingagents")

PG_DSN = f"dbname={PG_DB} user={PG_USER} password={PG_PASSWORD} host={PG_HOST} port={PG_PORT}"

# ── TDengine ─────────────────────────────────────────────────────────────────
# 运行时凭据走 .env（ta_runtime，仅 SELECT/INSERT/CREATE TABLE）；
# 管理口令不进仓库，见 C:\backups\2026-09-20\credentials.txt。

TD_HOST = os.environ.get("TRADINGAGENTS_TD_HOST", "localhost")
TD_PORT = os.environ.get("TRADINGAGENTS_TD_PORT", "6041")
TD_USER = os.environ.get("TRADINGAGENTS_TD_USER", "ta_runtime")
TD_PASSWORD = os.environ.get("TRADINGAGENTS_TD_PASSWORD", "")
TD_DB = os.environ.get("TRADINGAGENTS_TD_DB", "trading_market")

TD_DSN = f"taosws://{TD_USER}:{TD_PASSWORD}@{TD_HOST}:{TD_PORT}/{TD_DB}"

# ── Paths ─────────────────────────────────────────────────────────────────────

CACHE_DIR = Path(os.environ.get(
    "TRADINGAGENTS_CACHE_DIR",
    TRADINGAGENTS_HOME / "cache"
))

DATA_CACHE_DIR = CACHE_DIR / "data_cache"
DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_DIR = Path(os.environ.get(
    "TRADINGAGENTS_RESULTS_DIR",
    TRADINGAGENTS_HOME / "logs"
))
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

MEMORY_LOG_PATH = Path(os.environ.get(
    "TRADINGAGENTS_MEMORY_LOG_PATH",
    TRADINGAGENTS_HOME / "memory" / "trading_memory.md"
))
MEMORY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

PROJECT_DIR = Path(__file__).resolve().parent.parent

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_LLM_MODEL = os.environ.get("TRADINGAGENTS_LLM_MODEL", "qwen3-max")
DEFAULT_LLM_PROVIDER = os.environ.get("TRADINGAGENTS_LLM_PROVIDER", "dashscope")
REPORT_LANG = os.environ.get("TRADINGAGENTS_REPORT_LANG", "zh")
