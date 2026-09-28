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
    get_seat_activity_analysis,
    get_stock_activity_analysis,
)
from .mootdx_client import get_insider_transactions, get_insider_change_chart
from .sina_finance import (
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
)
from .tonghuashun import get_profit_forecast, get_hot_stocks
from .chip_distribution import get_chip_distribution
from .northbound_flow import get_northbound_flow
from .ipo_center import get_ipo_declaration, get_ipo_listing
from .margin_trading import get_margin_detail, get_margin_market_stat, get_margin_industry
from .investment_calendar import get_investment_calendar
from .market_overview import get_market_overview, get_index_trends, get_stock_ranking, get_board_ranking, get_market_breadth, get_market_news
from .block_trade import get_block_trade_detail, get_block_trade_industry, get_block_trade_market_stat
from .dividend_bonus import get_dividend_bonus
from .earnings_forecast import get_earnings_forecast, get_earnings_express
from .analyst_rating import get_analyst_rating
from .institutional_hold import get_institutional_hold
# TongDaXin reference data (调研互动/备查资料/三板/港股/美股)
from .survey_reference import (
    get_survey_interaction,
    get_company_name_changes,
    get_st_changes,
)
from .tdx_reference import (
    get_neeq_abnormal_trade,
    get_hk_ipo,
    get_us_ipo,
)
from .futures_position import get_futures_position
from .market_stats import get_market_statistics
# TongDaXin Phase 2: 基金数据/产业链/行业数据/宏观分析
from .fund_data import get_fund_purchase, get_fund_announcement, get_fund_scale, get_fund_open_info, get_fund_data_overview
from .industry_chain import get_industry_chain_categories, get_industry_chain_chains, get_industry_chain_overview
from .industry_data import get_industry_list, get_industry_detail, get_industry_commodity, get_industry_data_overview
from .macro_analysis import get_macro_gdp, get_macro_cpi, get_macro_pmi, get_macro_list, get_macro_overview
from .stock_info_panel import get_stock_info_panel

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
    "get_seat_activity_analysis",
    "get_stock_activity_analysis",
    "get_insider_transactions",
    "get_insider_change_chart",
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
    # IPO center (Phase 7)
    "get_ipo_declaration",
    "get_ipo_listing",
    # Margin trading (Phase 7)
    "get_margin_detail",
    "get_margin_market_stat",
    "get_margin_industry",
    # Investment calendar (Phase 7)
    "get_investment_calendar",
    # Block trade (Phase 9)
    "get_block_trade_detail",
    "get_block_trade_industry",
    "get_block_trade_market_stat",
    # Dividend bonus (Phase 9)
    "get_dividend_bonus",
    # Earnings forecast (Phase 9)
    "get_earnings_forecast",
    "get_earnings_express",
    # Analyst rating (Phase 9)
    "get_analyst_rating",
    # Institutional hold (Phase 9)
    "get_institutional_hold",
    # TongDaXin reference data
    "get_survey_interaction",
    "get_company_name_changes",
    "get_st_changes",
    "get_neeq_abnormal_trade",
    "get_hk_ipo",
    "get_us_ipo",
    "get_futures_position",
    "get_market_statistics",
]
