"""A-stock data feature endpoints."""

from fastapi import APIRouter, HTTPException

from ..astock_features import (
    AstockFeatureRequest,
    AstockFeatureResponse,
    UnknownFeatureError,
    is_astock_code,
    run_astock_feature,
)

router = APIRouter()


@router.post("/api/astock-features", response_model=AstockFeatureResponse)
async def post_astock_feature(request: AstockFeatureRequest):
    """A-stock data center features (Phase 5).

    Single endpoint + feature dispatch table. Non-A-share tickers are
    rejected with 400; vendor failures inside backend functions come back
    as markdown in raw_md (HTTP 200) so panels can render them.
    """
    if not is_astock_code(request.ticker):
        raise HTTPException(
            status_code=400,
            detail=(
                f"'{request.ticker}' 不是 A 股代码：本端点仅支持 6 位数字"
                f"A 股代码（如 600519）。"
            ),
        )

    try:
        return run_astock_feature(request)
    except UnknownFeatureError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/stock-info/{ticker}")
async def get_stock_info(ticker: str):
    """Get structured stock info panel data (financial, shareholder, fund, dividend)."""
    if not is_astock_code(ticker):
        raise HTTPException(status_code=400, detail=f"'{ticker}' is not a valid A-share code")
    
    try:
        from tradingagents.dataflows.a_stock import get_stock_info_panel
        data = get_stock_info_panel(code=ticker)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
