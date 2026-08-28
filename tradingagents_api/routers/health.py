"""Health check and utility endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "tradingagents-api"}


@router.get("/api/today")
async def get_today():
    """Return today's date in YYYY-MM-DD format (server-side, always accurate)."""
    from datetime import date
    return {"date": date.today().isoformat()}
