"""Chart data assembly — facade over sub-modules.

Re-exports the public API so callers can do:
    from tradingagents_api.chart_data import build_chart_data, parse_ohlcv_csv

``build_chart_data`` lives here (not in assemblers.py) so that
``unittest.mock.patch("tradingagents_api.chart_data._fetch_ohlcv")``
intercepts the lazy import — the mock replaces the name on this module,
and the lazy ``import tradingagents_api.chart_data as _cd`` inside
``build_chart_data`` picks it up at call time.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

from ..schemas import (
    BollingerData,
    ChartData,
    DashboardData,
    FundFlowData,
    KlineData,
    MacdData,
    RsiData,
)
from .computors import compute_ema, compute_kdj, compute_ma
from .parsers import (
    compute_dimension_scores,
    extract_confidence,
    extract_signal_from_decision,
    parse_fund_flow_text,
    parse_indicator_bundle,
    parse_indicator_text,
    parse_northbound_text,
    parse_ohlcv_csv,
)

# Re-export fetcher symbols (prefixed with _ so tests can patch them)
from .fetchers import (
    fetch_indicator as _fetch_indicator,
    fetch_ohlcv as _fetch_ohlcv,
    fetch_minute_astock,
    fetch_minute_global,
    is_minute_interval as _is_minute_interval,
    MINUTE_BAR_LIMIT,
    MINUTE_TDX_FREQUENCY,
)

logger = logging.getLogger(__name__)

_MACD_INDICATORS = ["macd", "macds", "macdh"]
_BOLLINGER_INDICATORS = ["boll", "boll_ub", "boll_lb"]

# Re-export private aliases used by tests via mock patching
_is_astock_ticker = _fetch_ohlcv  # placeholder; real alias set below
_parse_fund_flow_text = parse_fund_flow_text
_parse_northbound_text = parse_northbound_text


def _is_astock_ticker(ticker: str) -> bool:
    """Return True if the ticker looks like a 6-digit A-share code."""
    code = ticker.strip().split(".")[0]
    return code.isdigit() and len(code) == 6


def _build_kline_from_records(records: list[dict[str, Any]]) -> KlineData:
    """Build a KlineData from parsed OHLCV records (chronological order)."""
    dates = [r["date"] for r in records]
    ohlc = [(r["open"], r["close"], r["low"], r["high"]) for r in records]
    volumes = [r["volume"] for r in records]
    closes = [r["close"] for r in records]
    highs = [r["high"] for r in records]
    lows = [r["low"] for r in records]

    kdj_k, kdj_d, kdj_j = compute_kdj(highs, lows, closes)

    return KlineData(
        dates=dates,
        ohlc=ohlc,
        volumes=volumes,
        ma5=compute_ma(closes, 5),
        ma10=compute_ma(closes, 10),
        ma20=compute_ma(closes, 20),
        ma50=compute_ma(closes, 50),
        ema12=compute_ema(closes, 12),
        ema26=compute_ema(closes, 26),
        kdj_k=kdj_k,
        kdj_d=kdj_d,
        kdj_j=kdj_j,
    )


def _build_kline_from_minute_records(records: list[dict[str, Any]]) -> KlineData:
    """Build a KlineData from minute-bar records (chronological order)."""
    dates = [r["date"] for r in records]
    ohlc = [(r["open"], r["close"], r["low"], r["high"]) for r in records]
    volumes = [r["volume"] for r in records]
    closes = [r["close"] for r in records]
    highs = [r["high"] for r in records]
    lows = [r["low"] for r in records]

    kdj_k, kdj_d, kdj_j = compute_kdj(highs, lows, closes)

    return KlineData(
        dates=dates,
        ohlc=ohlc,
        volumes=volumes,
        ma5=compute_ma(closes, 5),
        ma10=compute_ma(closes, 10),
        ma20=compute_ma(closes, 20),
        ma50=[],
        ema12=compute_ema(closes, 12),
        ema26=compute_ema(closes, 26),
        kdj_k=kdj_k,
        kdj_d=kdj_d,
        kdj_j=kdj_j,
    )


def _build_dashboard(final_state: dict[str, Any]) -> DashboardData:
    """Assemble the signal dashboard from the analysis final state."""
    final_decision = final_state.get("final_trade_decision", "")
    signal = extract_signal_from_decision(final_decision)
    sections = {}
    for key in ("market_report", "sentiment_report", "news_report", "fundamentals_report"):
        val = final_state.get(key)
        if val:
            sections[key] = val

    sentiment_report = final_state.get("sentiment_report", "")
    confidence = extract_confidence(sentiment_report)

    scores = compute_dimension_scores(sections) if sections else []
    return DashboardData(
        signal=signal,
        confidence=confidence,
        scores=scores,
    )


def _build_minute_kline(ticker: str, interval: str, days: int) -> KlineData | None:
    """Build a KlineData from minute bars for the given ticker and interval."""
    # Lazy import through package namespace so mock patches work
    import tradingagents_api.chart_data as _cd

    frequency_code = MINUTE_TDX_FREQUENCY[interval]
    if _is_astock_symbol(ticker):
        try:
            records = fetch_minute_astock(ticker, frequency_code, MINUTE_BAR_LIMIT)
        except Exception as exc:
            logger.warning("A-stock minute fetch failed for %s %s: %s", ticker, interval, exc)
            records = []
    else:
        try:
            records = fetch_minute_global(ticker, interval, days)
        except Exception as exc:
            logger.warning("Global minute fetch failed for %s %s: %s", ticker, interval, exc)
            records = []

    if not records:
        logger.warning("No minute bars for %s interval=%s", ticker, interval)
        return None

    records = sorted(records, key=lambda r: r["date"])
    return _build_kline_from_minute_records(records)


def _is_astock_symbol(symbol: str) -> bool:
    """Return True if the symbol looks like a 6-digit A-share code."""
    code = symbol.strip().split(".")[0]
    return code.isdigit() and len(code) == 6


# ---------------------------------------------------------------------------
# Main assembly function
# ---------------------------------------------------------------------------

def build_chart_data(
    final_state: dict[str, Any],
    ticker: str,
    date: str,
    days: int = 90,
    interval: str | None = None,
) -> ChartData | None:
    """Build chart visualization data for a completed analysis.

    Re-fetches OHLCV and indicator data from vendor APIs, then assembles
    a ``ChartData`` model.  Returns ``None`` if no market data is available.
    """
    # Lazy import through package namespace so mock patches on
    # chart_data._fetch_ohlcv / chart_data._fetch_indicator are intercepted.
    import tradingagents_api.chart_data as _cd

    try:
        curr_dt = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        logger.warning("Invalid date format: %s", date)
        return None

    start_dt = curr_dt - timedelta(days=days)
    start_date = start_dt.strftime("%Y-%m-%d")

    # --- Minute-granularity path ---
    if interval is not None and _is_minute_interval(interval):
        kline = _build_minute_kline(ticker, interval, days)
        if kline is None:
            logger.warning(
                "No chart data could be assembled for %s interval=%s", ticker, interval
            )
            return None
        dashboard = _build_dashboard(final_state)
        return ChartData(kline=kline, dashboard=dashboard)

    # --- K-line data ---
    kline = None
    ohlcv_text = _cd._fetch_ohlcv(ticker, start_date, date)
    if ohlcv_text:
        records = parse_ohlcv_csv(ohlcv_text)
        if records:
            # Vendors disagree on row order (yfinance newest-first, mootdx
            # oldest-first) — sort instead of reverse so MA/KDJ are computed
            # over a chronological series.
            records = sorted(records, key=lambda r: r["date"])
            kline = _build_kline_from_records(records)

    # --- Fetch all indicators in parallel ---
    macd = None
    macd_texts = {}
    rsi_text = None
    boll_texts = {}

    all_indicators = _MACD_INDICATORS + ["rsi"] + _BOLLINGER_INDICATORS
    with ThreadPoolExecutor(max_workers=len(all_indicators)) as executor:
        future_to_ind = {
            executor.submit(_cd._fetch_indicator, ticker, ind, date): ind
            for ind in all_indicators
        }
        for future in as_completed(future_to_ind):
            ind = future_to_ind[future]
            try:
                text = future.result()
                if text:
                    if ind in _MACD_INDICATORS:
                        macd_texts[ind] = text
                    elif ind == "rsi":
                        rsi_text = text
                    elif ind in _BOLLINGER_INDICATORS:
                        boll_texts[ind] = text
            except Exception as exc:
                logger.warning("Failed to fetch indicator %s: %s", ind, exc)

    # --- MACD data ---
    if len(macd_texts) == 3:
        parsed = parse_indicator_bundle(macd_texts)
        macd_map = dict(zip(parsed["macd"]["dates"], parsed["macd"]["values"]))
        signal_map = dict(zip(parsed["macds"]["dates"], parsed["macds"]["values"]))
        hist_map = dict(zip(parsed["macdh"]["dates"], parsed["macdh"]["values"]))
        common_dates = [
            d for d in macd_map if d in signal_map and d in hist_map
        ]
        if common_dates:
            macd = MacdData(
                dates=common_dates,
                macd=[macd_map[d] for d in common_dates],
                signal=[signal_map[d] for d in common_dates],
                histogram=[hist_map[d] for d in common_dates],
            )

    # --- RSI data ---
    rsi = None
    if rsi_text:
        parsed = parse_indicator_text(rsi_text)
        if parsed["values"]:
            paired = sorted(zip(parsed["dates"], parsed["values"]))
            rsi = RsiData(dates=[d for d, _ in paired], values=[v for _, v in paired])

    # --- Bollinger Bands data ---
    bollinger = None
    if len(boll_texts) == 3 and kline:
        parsed = parse_indicator_bundle(boll_texts)
        boll_map = dict(zip(parsed["boll"]["dates"], parsed["boll"]["values"]))
        ub_map = dict(zip(parsed["boll_ub"]["dates"], parsed["boll_ub"]["values"]))
        lb_map = dict(zip(parsed["boll_lb"]["dates"], parsed["boll_lb"]["values"]))
        kline_close_map = {d: o[1] for d, o in zip(kline.dates, kline.ohlc)}
        common_dates = [
            d for d in boll_map if d in ub_map and d in lb_map and d in kline_close_map
        ]
        if common_dates:
            bollinger = BollingerData(
                dates=common_dates,
                upper=[ub_map[d] for d in common_dates],
                middle=[boll_map[d] for d in common_dates],
                lower=[lb_map[d] for d in common_dates],
                close=[kline_close_map[d] for d in common_dates],
            )

    # --- Dashboard data ---
    dashboard = _build_dashboard(final_state)

    # --- Fund Flow data (A-share only, with cache) ---
    fund_flow = None
    if _is_astock_ticker(ticker):
        from tradingagents.data_cache import get_data_cache, make_cache_key

        ff_cache = get_data_cache(ticker)
        ff_cache_key = make_cache_key("fund_flow", ticker=ticker, date=date)

        if ff_cache is not None:
            cached_ff = ff_cache.get(ff_cache_key)
            if cached_ff is not None:
                fund_flow = FundFlowData(**cached_ff)
                ff_cache.close()
            else:
                ff_cache.close()

        if fund_flow is None:
            from .fetchers import fetch_fund_flow_data

            ff_data = fetch_fund_flow_data(ticker, date)
            if ff_data:
                fund_flow = FundFlowData(**ff_data)
                c2 = get_data_cache(ticker)
                if c2 is not None:
                    c2.set(ff_cache_key, fund_flow.model_dump(), "fund_flow")
                    c2.close()

    # --- Assemble final ChartData ---
    chart_data = ChartData(
        kline=kline,
        macd=macd,
        rsi=rsi,
        bollinger=bollinger,
        dashboard=dashboard,
        fundFlow=fund_flow,
    )

    if kline is None and macd is None and rsi is None and bollinger is None:
        logger.warning("No chart data could be assembled for %s", ticker)
        return None

    return chart_data


__all__ = [
    "build_chart_data",
    "compute_ema",
    "compute_kdj",
    "compute_ma",
    "_fetch_indicator",
    "_fetch_ohlcv",
    "_is_minute_interval",
    "parse_fund_flow_text",
    "parse_indicator_bundle",
    "parse_indicator_text",
    "parse_northbound_text",
    "parse_ohlcv_csv",
]
