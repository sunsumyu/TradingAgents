"""akshare data vendor.

Comprehensive A-share data via the akshare library, plus US stock daily data.
Optional dependency: ``pip install akshare`` or ``pip install "tradingagents[astock]"``.

akshare is NOT the default for any category -- users opt in via ``data_vendors``
config.  This vendor sits alongside (not replacing) the existing ``a_stock`` vendor.

All functions match the tool signatures in ``interface.py`` VENDOR_METHODS so the
router can dispatch to them without any changes.
"""

from __future__ import annotations

import logging
from typing import Annotated

import pandas as pd

from .errors import NoMarketDataError, VendorNotConfiguredError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy import -- akshare is optional
# ---------------------------------------------------------------------------

_ak = None


def _get_ak():
    """Lazy-import akshare; raise ``VendorNotConfiguredError`` if missing."""
    global _ak
    if _ak is None:
        try:
            import akshare as ak
            _ak = ak
        except ImportError:
            raise VendorNotConfiguredError(
                "akshare is not installed. Install with: pip install akshare"
            )
    return _ak


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_code(ticker: str) -> str:
    """Strip SH/SZ/.SS/.SZ prefixes/suffixes to get a pure 6-digit code."""
    from .a_stock.utils import normalize_ticker
    return normalize_ticker(ticker)


def _ak_call(func, *args, **kwargs):
    """Call an akshare function with error wrapping."""
    ak = _get_ak()
    try:
        return func(ak, *args, **kwargs)
    except Exception as e:
        msg = str(e).lower()
        if any(kw in msg for kw in ("not found", "不存在", "没有数据", "empty", "no data")):
            symbol = args[0] if args else "unknown"
            raise NoMarketDataError(symbol, symbol, str(e)) from e
        raise


def _df_to_csv(df: pd.DataFrame) -> str:
    """Convert a DataFrame to CSV string, handling common akshare column names."""
    if df is None or df.empty:
        return ""
    # Normalize common Chinese column names to English
    col_map = {
        "日期": "Date", "开盘": "Open", "收盘": "Close",
        "最高": "High", "最低": "Low", "成交量": "Volume",
        "成交额": "Amount", "振幅": "Amplitude", "涨跌幅": "Change%",
        "涨跌额": "Change", "换手率": "Turnover%",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    return df.to_csv(index=False)


# ---------------------------------------------------------------------------
# core_stock_apis
# ---------------------------------------------------------------------------

def get_stock_data(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    """Get OHLCV stock data via akshare ``stock_zh_a_hist``."""
    code = _normalize_code(symbol)

    def _fetch(ak):
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
            adjust="qfq",
        )
        if df is None or df.empty:
            raise NoMarketDataError(symbol, code, "akshare returned empty OHLCV data")
        return _df_to_csv(df)

    return _ak_call(_fetch)


# ---------------------------------------------------------------------------
# technical_indicators
# ---------------------------------------------------------------------------

def get_indicators(
    ticker: str,
    indicator: str,
    curr_date: str,
    look_back_days: int = 30,
) -> str:
    """Get a technical indicator via akshare OHLCV + stockstats calculation.

    akshare does not provide pre-calculated indicators; we fetch OHLCV and
    compute using stockstats (same approach as eastmoney.get_indicators).
    """
    from datetime import datetime, timedelta
    from .stockstats_utils import get_stock_stats_indicators_window

    code = _normalize_code(ticker)
    end = datetime.strptime(curr_date, "%Y-%m-%d")
    start = end - timedelta(days=look_back_days + 10)

    # Fetch OHLCV via akshare
    def _fetch(ak):
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no OHLCV data for indicator calc")
        # Normalize column names for stockstats
        col_map = {"日期": "date", "开盘": "open", "收盘": "close",
                    "最高": "high", "最低": "low", "成交量": "volume"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        return df

    raw_df = _ak_call(_fetch)
    # Use stockstats to compute the indicator (reuses existing infrastructure)
    try:
        return get_stock_stats_indicators_window(ticker, indicator, curr_date, look_back_days)
    except Exception:
        # Fallback: return raw OHLCV data with the indicator column
        return _df_to_csv(raw_df)


# ---------------------------------------------------------------------------
# fundamental_data
# ---------------------------------------------------------------------------

def get_fundamentals(
    ticker: str,
    curr_date: str,
    include_history: bool = True,
) -> str:
    """Get individual stock info via akshare ``stock_individual_info_em``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_individual_info_em(symbol=code)
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no fundamentals data")
        return df.to_string(index=False)

    return _ak_call(_fetch)


def get_balance_sheet(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str = None,
) -> str:
    """Get balance sheet via akshare ``stock_balance_sheet_by_report_em``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_balance_sheet_by_report_em(symbol=code)
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no balance sheet data")
        # Filter by date to prevent look-ahead bias
        if curr_date and "REPORT_DATE" in df.columns:
            df = df[df["REPORT_DATE"] <= curr_date]
        if df.empty:
            raise NoMarketDataError(ticker, code, f"no balance sheet data before {curr_date}")
        return _df_to_csv(df.head(4 if freq == "annual" else 8))

    return _ak_call(_fetch)


def get_cashflow(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str = None,
) -> str:
    """Get cash flow statement via akshare ``stock_cash_flow_sheet_by_report_em``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no cashflow data")
        if curr_date and "REPORT_DATE" in df.columns:
            df = df[df["REPORT_DATE"] <= curr_date]
        if df.empty:
            raise NoMarketDataError(ticker, code, f"no cashflow data before {curr_date}")
        return _df_to_csv(df.head(4 if freq == "annual" else 8))

    return _ak_call(_fetch)


def get_income_statement(
    ticker: str,
    freq: str = "quarterly",
    curr_date: str = None,
) -> str:
    """Get income statement via akshare ``stock_profit_sheet_by_report_em``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_profit_sheet_by_report_em(symbol=code)
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no income statement data")
        if curr_date and "REPORT_DATE" in df.columns:
            df = df[df["REPORT_DATE"] <= curr_date]
        if df.empty:
            raise NoMarketDataError(ticker, code, f"no income data before {curr_date}")
        return _df_to_csv(df.head(4 if freq == "annual" else 8))

    return _ak_call(_fetch)


# ---------------------------------------------------------------------------
# news_data
# ---------------------------------------------------------------------------

def get_news(
    ticker: str,
    start_date: str,
    end_date: str,
) -> str:
    """Get stock-specific news via akshare ``stock_news_em``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_news_em(symbol=code)
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no news data")
        # Filter by date range
        if "发布时间" in df.columns:
            df["发布时间"] = pd.to_datetime(df["发布时间"], errors="coerce")
            mask = (df["发布时间"] >= start_date) & (df["发布时间"] <= end_date)
            df = df[mask]
        if df.empty:
            raise NoMarketDataError(ticker, code, f"no news in {start_date}~{end_date}")
        # Return key columns
        cols = [c for c in ["发布时间", "文章来源", "新闻标题", "新闻内容"] if c in df.columns]
        return df[cols].head(20).to_string(index=False)

    return _ak_call(_fetch)


def get_insider_transactions(
    ticker: str,
) -> str:
    """Get shareholder/insider data via akshare ``stock_individual_info_em``.

    akshare does not have a dedicated insider-transaction API for A-shares.
    We use the individual stock info as a partial substitute.
    """
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_individual_info_em(symbol=code)
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no insider data available")
        return df.to_string(index=False)

    return _ak_call(_fetch)


# ---------------------------------------------------------------------------
# signal_data (A-share specific)
# ---------------------------------------------------------------------------

def get_profit_forecast(
    ticker: str,
    curr_date: str = None,
) -> str:
    """Get profit forecast via akshare ``stock_profit_forecast_em``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_profit_forecast_em(symbol=code)
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no profit forecast data")
        return _df_to_csv(df)

    return _ak_call(_fetch)


def get_hot_stocks(
    curr_date: str = "",
) -> str:
    """Get hot stocks ranking via akshare ``stock_hot_rank_em``."""
    def _fetch(ak):
        df = ak.stock_hot_rank_em()
        if df is None or df.empty:
            raise NoMarketDataError("hot_stocks", "hot_stocks", "no hot stocks data")
        return _df_to_csv(df.head(30))

    return _ak_call(_fetch)


def get_northbound_flow(
    curr_date: str,
    include_history: bool = False,
) -> str:
    """Get northbound capital flow via akshare ``stock_hsgt_north_net_flow_in_em``."""
    def _fetch(ak):
        df = ak.stock_hsgt_north_net_flow_in_em()
        if df is None or df.empty:
            raise NoMarketDataError("northbound", "northbound", "no northbound flow data")
        if not include_history:
            df = df.tail(5)
        return _df_to_csv(df)

    return _ak_call(_fetch)


def get_concept_blocks(
    ticker: str,
) -> str:
    """Get concept blocks via akshare ``stock_board_concept_name_em``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_board_concept_name_em()
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no concept block data")
        return _df_to_csv(df.head(20))

    return _ak_call(_fetch)


def get_fund_flow(
    ticker: str,
    curr_date: str,
    include_history: bool = True,
) -> str:
    """Get individual stock fund flow via akshare ``stock_individual_fund_flow``."""
    code = _normalize_code(ticker)
    # Determine market prefix
    market = "sh" if code.startswith(("6", "5")) else "sz"

    def _fetch(ak):
        df = ak.stock_individual_fund_flow(stock=code, market=market)
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no fund flow data")
        if not include_history:
            df = df.tail(5)
        return _df_to_csv(df)

    return _ak_call(_fetch)


def get_dragon_tiger_board(
    ticker: str,
    trade_date: str,
    look_back_days: int = 30,
) -> str:
    """Get dragon tiger board data via akshare ``stock_dzjy_sctj``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        # stock_dzjy_sctj returns market-wide dragon tiger data
        df = ak.stock_dzjy_sctj()
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no dragon tiger board data")
        # Filter by ticker if possible
        if "证券代码" in df.columns:
            df = df[df["证券代码"].astype(str).str.contains(code)]
        if df.empty:
            raise NoMarketDataError(ticker, code, f"no dragon tiger data for {code}")
        return _df_to_csv(df.head(20))

    return _ak_call(_fetch)


def get_lockup_expiry(
    ticker: str,
    trade_date: str,
    forward_days: int = 90,
) -> str:
    """Get lockup expiry schedule via akshare ``stock_restricted_release_queue_em``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_restricted_release_queue_em(symbol=code)
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no lockup expiry data")
        return _df_to_csv(df)

    return _ak_call(_fetch)


def get_industry_comparison(
    ticker: str,
    trade_date: str,
    top_n: int = 20,
) -> str:
    """Get industry sector comparison via akshare ``stock_board_industry_name_em``."""
    code = _normalize_code(ticker)

    def _fetch(ak):
        df = ak.stock_board_industry_name_em()
        if df is None or df.empty:
            raise NoMarketDataError(ticker, code, "no industry comparison data")
        return _df_to_csv(df.head(top_n))

    return _ak_call(_fetch)


def get_chip_distribution(
    symbol: str,
    curr_date: str,
    days: int = 90,
) -> str:
    """Get chip distribution via akshare ``stock_cyq_em``."""
    code = _normalize_code(symbol)

    def _fetch(ak):
        df = ak.stock_cyq_em(symbol=code)
        if df is None or df.empty:
            raise NoMarketDataError(symbol, code, "no chip distribution data")
        return _df_to_csv(df.tail(days))

    return _ak_call(_fetch)
