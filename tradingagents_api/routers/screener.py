"""Natural-language stock screener endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..schemas import ScreenerRequest
from ..screener import ScreenerResponse, run_screener, run_template_screener

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/screener", response_model=ScreenerResponse)
async def post_screener(request: ScreenerRequest):
    """Natural-language stock screener (Phase 6, ticket 6.01).

    Translates a Chinese NL query into structured filters via the quick LLM,
    then executes those filters against A-stock data and returns ranked results.
    """
    from tradingagents.default_config import DEFAULT_CONFIG

    try:
        if request.template_id:
            return run_template_screener(
                template_id=request.template_id,
                max_results=request.max_results,
            )
        config = dict(DEFAULT_CONFIG)
        return run_screener(
            query=request.query,
            config=config,
            max_results=request.max_results,
            ticker_hint=request.ticker_hint,
        )
    except Exception as exc:
        logger.error("Screener failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Screener failed: {exc}")
