"""FastAPI server — application factory.

All route logic lives in ``routers/`` modules.  This file owns only the
FastAPI application instance, CORS, router wiring, and the CLI entry point.

Run with:
    granian tradingagents_api.server:app --interface asgi --host 0.0.0.0 --port 8420
"""

from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    analysis,
    astock,
    cache,
    config,
    health,
    market,
    portfolio,
    providers,
    realtime,
    screener,
)

logger = logging.getLogger(__name__)

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
# Register routers
# ---------------------------------------------------------------------------

for _router in (
    health,
    providers,
    analysis,
    market,
    astock,
    screener,
    portfolio,
    realtime,
    config,
    cache,
):
    app.include_router(_router.router)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    """Run the server with granian."""
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
