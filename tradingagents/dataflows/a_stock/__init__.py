"""A-share data vendor — facade over sub-modules.

Zero third-party data dependency (no akshare). All sources are direct HTTP APIs
or mootdx TCP.

Re-exports all 21 public functions so that
``from tradingagents.dataflows import a_stock as _a_stock`` continues to work
unchanged after the split of the original monolithic ``a_stock.py``.
"""

from .utils import resolve_ticker, reject_non_a_share, normalize_ticker
from .mootdx_client import reset_mootdx_client
from .tencent_quote import get_realtime_quotes
from .ohlcv import get_stock_data, load_ohlcv_astock
from .eastmoney import (
    get_indicators,
    get_fundamentals,
    get_concept_blocks,
    get_fund_flow,
    get_dragon_tiger_board,
    get_lockup_expiry,
    get_industry_comparison,
    get_global_news,
)
from .mootdx_client import get_insider_transactions
from .sina_finance import (
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
)
from .tonghuashun import get_profit_forecast, get_hot_stocks
from .chip_distribution import get_chip_distribution
from .northbound_flow import get_northbound_flow

# Also re-export helpers used by other modules (e.g. stockstats_utils)
from .utils import get_prefix as _get_prefix

__all__ = [
    # Utilities
    "resolve_ticker",
    "reject_non_a_share",
    "normalize_ticker",
    # mootdx
    "reset_mootdx_client",
    # Tencent
    "get_realtime_quotes",
    # OHLCV
    "get_stock_data",
    "load_ohlcv_astock",
    # Eastmoney / Baidu PAE
    "get_indicators",
    "get_fundamentals",
    "get_concept_blocks",
    "get_fund_flow",
    "get_dragon_tiger_board",
    "get_lockup_expiry",
    "get_industry_comparison",
    "get_global_news",
    "get_insider_transactions",
    # Sina Finance
    "get_balance_sheet",
    "get_cashflow",
    "get_income_statement",
    "get_news",
    # 同花顺
    "get_profit_forecast",
    "get_hot_stocks",
    # Chip distribution
    "get_chip_distribution",
    # Northbound flow
    "get_northbound_flow",
]
