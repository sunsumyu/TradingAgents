"""A-share signal data tool functions -- thin wrappers over route_to_vendor."""
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_profit_forecast(
    ticker: Annotated[str, "A-share stock code, e.g. 600519"],
    curr_date: Annotated[str, "Current date YYYY-MM-DD"] = "",
) -> str:
    """Get consensus EPS forecasts with forward valuation for an A-share stock.

    Args:
        ticker: 6-digit A-share stock code
        curr_date: Current date in YYYY-MM-DD format
    Returns:
        Analyst consensus EPS forecast with forward PE/PEG analysis
    """
    return route_to_vendor("get_profit_forecast", ticker, curr_date)


@tool
def get_hot_stocks(
    curr_date: Annotated[str, "Date YYYY-MM-DD, empty for today"] = "",
) -> str:
    """Get strong stocks with topic attribution (limit-up stocks with reasons).

    Args:
        curr_date: Date in YYYY-MM-DD format, empty string for today
    Returns:
        List of hot stocks with curated reason tags
    """
    return route_to_vendor("get_hot_stocks", curr_date)


@tool
def get_northbound_flow(
    curr_date: Annotated[str, "Date YYYY-MM-DD"],
    include_history: Annotated[bool, "Include historical daily data"] = False,
) -> str:
    """Get northbound capital flow (Shanghai/Shenzhen-Hong Kong Stock Connect).

    Args:
        curr_date: Date in YYYY-MM-DD format
        include_history: Whether to include last 20 trading days history
    Returns:
        Northbound capital flow data with signal interpretation
    """
    return route_to_vendor("get_northbound_flow", curr_date, include_history)


@tool
def get_concept_blocks(
    ticker: Annotated[str, "A-share stock code, e.g. 688017"],
) -> str:
    """Get concept/sector/region blocks that a stock belongs to.

    Args:
        ticker: 6-digit A-share stock code
    Returns:
        Industry classification, concept themes, and region blocks
    """
    return route_to_vendor("get_concept_blocks", ticker)


@tool
def get_fund_flow(
    ticker: Annotated[str, "A-share stock code"],
    curr_date: Annotated[str, "Date YYYY-MM-DD"],
    include_history: Annotated[bool, "Include historical daily fund flow"] = True,
) -> str:
    """Get individual stock fund flow (main/large/small/super order net inflow).

    Args:
        ticker: 6-digit A-share stock code
        curr_date: Date in YYYY-MM-DD format
        include_history: Whether to include last 20 trading days history
    Returns:
        Fund flow data with signal interpretation
    """
    return route_to_vendor("get_fund_flow", ticker, curr_date, include_history)


@tool
def get_dragon_tiger_board(
    ticker: Annotated[str, "A-share stock code"],
    trade_date: Annotated[str, "Trade date YYYY-MM-DD"],
    look_back_days: Annotated[int, "Days to look back"] = 30,
) -> str:
    """Get dragon-tiger board (LHB) appearances and seat details.

    Args:
        ticker: 6-digit A-share stock code
        trade_date: Trade date in YYYY-MM-DD format
        look_back_days: How many days back to search
    Returns:
        Dragon-tiger board data with buyer/seller seats and institutional activity
    """
    return route_to_vendor("get_dragon_tiger_board", ticker, trade_date, look_back_days)


@tool
def get_lockup_expiry(
    ticker: Annotated[str, "A-share stock code"],
    trade_date: Annotated[str, "Trade date YYYY-MM-DD"],
    forward_days: Annotated[int, "Days to look forward"] = 90,
) -> str:
    """Get lockup expiry schedule for a stock.

    Args:
        ticker: 6-digit A-share stock code
        trade_date: Trade date in YYYY-MM-DD format
        forward_days: How many days forward to check
    Returns:
        Lockup expiry calendar with historical unlock records and upcoming expiry
    """
    return route_to_vendor("get_lockup_expiry", ticker, trade_date, forward_days)


@tool
def get_industry_comparison(
    ticker: Annotated[str, "A-share stock code"],
    trade_date: Annotated[str, "Trade date YYYY-MM-DD"],
    top_n: Annotated[int, "Number of top/bottom industries to show"] = 20,
) -> str:
    """Get industry sector performance comparison.

    Args:
        ticker: 6-digit A-share stock code (used to identify relevant sector)
        trade_date: Trade date in YYYY-MM-DD format
        top_n: Number of top/bottom industries to show
    Returns:
        Sector performance ranking with the target stock's sector highlighted
    """
    return route_to_vendor("get_industry_comparison", ticker, trade_date, top_n)
