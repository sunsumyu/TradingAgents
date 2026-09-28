"""Market data and chart data endpoints."""

from fastapi import APIRouter, HTTPException

from ..market_data import build_market_data
from ..schemas import ChartDataRequest, MarketDataRequest, MarketDataResponse

router = APIRouter()


@router.post("/api/market-data")
async def get_market_data(request: MarketDataRequest):
    """Fetch chart data, fundamentals, and news without running agents.

    PG cache: hit → return from DB (~5ms), miss → fetch APIs + write PG.
    Cache key: {ticker}:market_data:{date}:1.0:{hash}
    """
    from tradingagents.cache.manager import get_cache

    mgr = get_cache(request.ticker)

    def _source():
        resp = build_market_data(request.ticker, request.date)
        # Convert Pydantic model → dict for PG storage
        return resp.model_dump()

    with mgr.fetch("market_data", request.date, source_fn=_source) as (data, hit):
        if hit:
            # PG returns plain dict; FastAPI serializes it the same way
            return data
        # First call: data is already a dict from _source's model_dump()
        return data


@router.post("/api/chart-data")
async def get_chart_data(request: ChartDataRequest):
    """Fetch chart data with configurable date range for the TradingView chart.

    Returns kline, MACD, RSI, Bollinger, and fund flow data for the specified
    number of calendar days.
    """
    from ..chart_data import build_chart_data

    chart = build_chart_data(
        {}, request.ticker, request.date, days=request.days, interval=request.interval
    )
    if chart is None:
        raise HTTPException(status_code=404, detail=f"No chart data available for {request.ticker}")
    return {
        "ticker": request.ticker,
        "date": request.date,
        "days": request.days,
        "interval": request.interval,
        "kline": chart.kline,
        "macd": chart.macd,
        "rsi": chart.rsi,
        "bollinger": chart.bollinger,
        "fundFlow": chart.fundFlow,
    }
