"""Parsing utilities and assembly logic for chart visualization data."""

from __future__ import annotations

import logging
import re
from typing import Any

from .schemas import (
    BollingerData,
    ChartData,
    DashboardData,
    FundFlowData,
    KlineData,
    MacdData,
    RsiData,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

_OHLCV_HEADER_RE = re.compile(r"^Date,Open,High,Low,Close")


def parse_ohlcv_csv(csv_text: str) -> list[dict[str, Any]]:
    """Parse the CSV output of ``get_YFin_data_online`` into structured records.

    Skips comment lines (``# ...``) and the header row.  Returns a list of
    dicts with keys: ``date, open, high, low, close, adj_close, volume``.
    """
    records: list[dict[str, Any]] = []
    header_found = False

    for line in csv_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Skip comment lines
        if line.startswith("#"):
            # Detect the CSV header row embedded in comments context
            continue

        # Detect the actual CSV header
        if _OHLCV_HEADER_RE.match(line):
            header_found = True
            continue

        if not header_found:
            continue

        # Parse data row: Date,Open,High,Low,Close,Adj Close,Volume
        parts = line.split(",")
        if len(parts) < 7:
            continue

        try:
            records.append(
                {
                    "date": parts[0],
                    "open": float(parts[1]),
                    "high": float(parts[2]),
                    "low": float(parts[3]),
                    "close": float(parts[4]),
                    "adj_close": float(parts[5]),
                    "volume": float(parts[6]),
                }
            )
        except (ValueError, IndexError):
            # Skip malformed rows
            continue

    return records


# ---------------------------------------------------------------------------
# Indicator text parsing
# ---------------------------------------------------------------------------

_DATE_VALUE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}):\s*(.+)$")


def parse_indicator_text(text: str) -> dict[str, list[Any]]:
    """Parse the formatted output of ``get_stock_stats_indicators_window``.

    Returns ``{"dates": [...], "values": [...]}`` with N/A entries excluded.
    Numeric values are converted to ``float``; non-numeric strings are skipped.
    """
    dates: list[str] = []
    values: list[float] = []

    for line in text.splitlines():
        m = _DATE_VALUE_RE.match(line.strip())
        if not m:
            continue

        date_str, raw_value = m.group(1), m.group(2).strip()

        # Skip N/A entries
        if raw_value.startswith("N/A") or raw_value == "":
            continue

        try:
            values.append(float(raw_value))
            dates.append(date_str)
        except ValueError:
            # Non-numeric value (e.g. description text leaked in) — skip
            continue

    return {"dates": dates, "values": values}


# ---------------------------------------------------------------------------
# Convenience: parse multiple indicators at once
# ---------------------------------------------------------------------------


def parse_indicator_bundle(
    indicators: dict[str, str],
) -> dict[str, dict[str, list[Any]]]:
    """Parse a bundle of indicator texts keyed by indicator name.

    Returns ``{indicator_name: {"dates": [...], "values": [...]}, ...}``.
    """
    return {name: parse_indicator_text(text) for name, text in indicators.items()}


# ---------------------------------------------------------------------------
# Signal extraction from markdown
# ---------------------------------------------------------------------------

_RATING_RE = re.compile(r"\*\*Rating\*\*:\s*(\w+)", re.IGNORECASE)
_SENTIMENT_CONFIDENCE_RE = re.compile(r"Confidence:?\*{0,2}:\s*\*{0,2}\s*(low|medium|high)", re.IGNORECASE)

# Dimension keywords for scoring from analyst reports
_TECHNICAL_KEYWORDS = re.compile(r"(RSI|MACD|SMA|EMA|Bollinger|KDJ|ATR|trend|momentum)", re.IGNORECASE)
_SENTIMENT_KEYWORDS = re.compile(r"(sentiment|bullish|bearish|social|reddit|stocktwits)", re.IGNORECASE)
_NEWS_KEYWORDS = re.compile(r"(news|headline|announcement|regulatory|macro)", re.IGNORECASE)
_FUNDAMENTALS_KEYWORDS = re.compile(r"(revenue|earnings|P/E|ROE|balance sheet|cash flow|fundamental)", re.IGNORECASE)


def _extract_signal_from_decision(final_trade_decision: str) -> str:
    """Extract the rating string from the final trade decision markdown."""
    m = _RATING_RE.search(final_trade_decision)
    if m:
        rating = m.group(1).capitalize()
        valid = {"Buy", "Overweight", "Hold", "Underweight", "Sell"}
        return rating if rating in valid else "Hold"
    return "Hold"


def _compute_dimension_scores(
    sections: dict[str, str],
) -> list[dict[str, Any]]:
    """Compute dimension scores by counting relevant keywords in each analyst report.

    Heuristic by design: richer keyword coverage maps to a higher score,
    capped at 10.  Reports with no keyword matches get a neutral 5.
    """
    dimensions = [
        ("Technical", _TECHNICAL_KEYWORDS, "market_report"),
        ("Sentiment", _SENTIMENT_KEYWORDS, "sentiment_report"),
        ("News", _NEWS_KEYWORDS, "news_report"),
        ("Fundamentals", _FUNDAMENTALS_KEYWORDS, "fundamentals_report"),
    ]
    scores = []
    for name, pattern, report_key in dimensions:
        text = sections.get(report_key, "")
        matches = pattern.findall(text)
        score = float(min(len(matches), 10)) if matches else 5.0
        scores.append({"name": name, "value": score, "max": 10})
    return scores


# ---------------------------------------------------------------------------
# Data fetching (re-fetches from vendor APIs)
# ---------------------------------------------------------------------------

def _fetch_ohlcv(
    symbol: str, start_date: str, end_date: str
) -> str | None:
    """Fetch OHLCV CSV via the vendor routing layer."""
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        return route_to_vendor("get_stock_data", symbol, start_date, end_date)
    except Exception as exc:
        logger.warning("Failed to fetch OHLCV for %s: %s", symbol, exc)
        return None


def _fetch_indicator(
    symbol: str, indicator: str, curr_date: str, look_back_days: int = 30
) -> str | None:
    """Fetch a single technical indicator via the vendor routing layer."""
    try:
        from tradingagents.dataflows.interface import route_to_vendor
        return route_to_vendor("get_indicators", symbol, indicator, curr_date, look_back_days)
    except Exception as exc:
        logger.warning("Failed to fetch indicator %s for %s: %s", indicator, symbol, exc)
        return None


# ---------------------------------------------------------------------------
# Main assembly function
# ---------------------------------------------------------------------------

_MACD_INDICATORS = ["macd", "macds", "macdh"]
_BOLLINGER_INDICATORS = ["boll", "boll_ub", "boll_lb"]

_FUND_FLOW_ROW_RE = re.compile(
    r"^\s*\d{4}-\d{2}-\d{2}\s*\|?\s*main=([-\d.]+)\s*\|?\s*large=([-\d.]+)"
    r"\s*\|?\s*mid=([-\d.]+)\s*\|?\s*small=([-\d.]+)"
)
_NORTHBOUND_ROW_RE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}):\s*HGT=([-\d.]+)\s*SGT=([-\d.]+)"
)


def _is_astock_ticker(ticker: str) -> bool:
    """Return True if the ticker looks like a 6-digit A-share code."""
    code = ticker.strip().split(".")[0]
    return code.isdigit() and len(code) == 6


def _parse_fund_flow_text(text: str) -> dict[str, list[Any]]:
    """Parse the historical daily fund flow table from get_fund_flow.

    Returns ``{"dates": [...], "mainForce": [...], "retail": [...]}``
    where retail = small + mid (散户净流入).
    """
    dates: list[str] = []
    main_force: list[float] = []
    retail: list[float] = []

    for line in text.splitlines():
        m = _FUND_FLOW_ROW_RE.match(line)
        if m:
            dates.append(m.group(0).split("|")[0].strip().split()[0]
                         if "|" in line else m.group(0).strip().split()[0])
            # Extract date more robustly
            date_match = re.match(r"\s*(\d{4}-\d{2}-\d{2})", line)
            if date_match:
                dates[-1] = date_match.group(1)
            main_force.append(float(m.group(1)))
            retail.append(float(m.group(3)) + float(m.group(4)))  # mid + small

    return {"dates": dates, "mainForce": main_force, "retail": retail}


def _parse_northbound_text(text: str) -> dict[str, list[Any]]:
    """Parse the historical daily northbound flow from get_northbound_flow.

    Returns ``{"dates": [...], "values": [...]}`` in 亿元.
    """
    dates: list[str] = []
    values: list[float] = []

    for line in text.splitlines():
        m = _NORTHBOUND_ROW_RE.match(line)
        if m:
            dates.append(m.group(1))
            values.append(float(m.group(2)) + float(m.group(3)))  # HGT + SGT

    return {"dates": dates, "values": values}


def _compute_ma(closes: list[float], period: int) -> list[float | None]:
    """Compute a simple moving average over close prices.

    Returns a list of the same length as ``closes``, with ``None`` for
    positions where not enough data is available.
    """
    result: list[float | None] = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            window = closes[i - period + 1 : i + 1]
            result.append(round(sum(window) / period, 2))
    return result


def build_chart_data(
    final_state: dict[str, Any],
    ticker: str,
    date: str,
) -> ChartData | None:
    """Build chart visualization data for a completed analysis.

    Re-fetches OHLCV and indicator data from vendor APIs, then assembles
    a ``ChartData`` model.  Returns ``None`` if no market data is available.

    Parameters
    ----------
    final_state:
        The merged LangGraph state dict after analysis completes (used for
        the signal, confidence, and dimension scores).
    ticker:
        The stock ticker symbol.
    date:
        The analysis date in YYYY-MM-DD format.
    """
    from datetime import datetime, timedelta

    # Determine date range for K-line data (60 days for MA50)
    try:
        curr_dt = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        logger.warning("Invalid date format: %s", date)
        return None

    start_dt = curr_dt - timedelta(days=90)  # ~60 trading days
    start_date = start_dt.strftime("%Y-%m-%d")

    # --- K-line data ---
    kline = None
    ohlcv_text = _fetch_ohlcv(ticker, start_date, date)
    if ohlcv_text:
        records = parse_ohlcv_csv(ohlcv_text)
        if records:
            dates = [r["date"] for r in records]
            ohlc = [(r["open"], r["close"], r["low"], r["high"]) for r in records]
            volumes = [r["volume"] for r in records]
            closes = [r["close"] for r in records]

            # Compute moving averages from close prices
            ma5 = _compute_ma(closes, 5)
            ma10 = _compute_ma(closes, 10)
            ma20 = _compute_ma(closes, 20)
            ma50 = _compute_ma(closes, 50)

            kline = KlineData(
                dates=dates,
                ohlc=ohlc,
                volumes=volumes,
                ma5=ma5,
                ma10=ma10,
                ma20=ma20,
                ma50=ma50,
            )

    # --- MACD data ---
    macd = None
    macd_texts = {}
    for ind in _MACD_INDICATORS:
        text = _fetch_indicator(ticker, ind, date)
        if text:
            macd_texts[ind] = text
    if len(macd_texts) == 3:
        parsed = parse_indicator_bundle(macd_texts)
        # Align by date intersection - each indicator may have different
        # N/A (non-trading day) gaps.
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
    rsi_text = _fetch_indicator(ticker, "rsi", date)
    if rsi_text:
        parsed = parse_indicator_text(rsi_text)
        if parsed["values"]:
            rsi = RsiData(dates=parsed["dates"], values=parsed["values"])

    # --- Bollinger Bands data ---
    bollinger = None
    boll_texts = {}
    for ind in _BOLLINGER_INDICATORS:
        text = _fetch_indicator(ticker, ind, date)
        if text:
            boll_texts[ind] = text
    if len(boll_texts) == 3 and kline:
        parsed = parse_indicator_bundle(boll_texts)
        boll_map = dict(zip(parsed["boll"]["dates"], parsed["boll"]["values"]))
        ub_map = dict(zip(parsed["boll_ub"]["dates"], parsed["boll_ub"]["values"]))
        lb_map = dict(zip(parsed["boll_lb"]["dates"], parsed["boll_lb"]["values"]))
        # Only keep dates where all three bands AND a close price exist
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
    dashboard = None
    final_decision = final_state.get("final_trade_decision", "")
    signal = _extract_signal_from_decision(final_decision)
    sections = {}
    for key in ("market_report", "sentiment_report", "news_report", "fundamentals_report"):
        val = final_state.get(key)
        if val:
            sections[key] = val

    # Try to extract confidence from sentiment report
    confidence = 50.0  # default
    sentiment_report = final_state.get("sentiment_report", "")
    conf_match = _SENTIMENT_CONFIDENCE_RE.search(sentiment_report)
    if conf_match:
        conf_map = {"low": 30.0, "medium": 60.0, "high": 85.0}
        confidence = conf_map.get(conf_match.group(1).lower(), 50.0)

    scores = _compute_dimension_scores(sections) if sections else []
    dashboard = DashboardData(
        signal=signal,
        confidence=confidence,
        scores=scores,
    )

    # --- Fund Flow data (A-share only) ---
    fund_flow = None
    if _is_astock_ticker(ticker):
        try:
            from tradingagents.dataflows.interface import route_to_vendor

            # Per-stock main force + retail flow
            ff_text = route_to_vendor("get_fund_flow", ticker, date, True)
            ff_parsed = _parse_fund_flow_text(ff_text) if ff_text else {}

            # Market-wide northbound flow
            nb_text = route_to_vendor("get_northbound_flow", date, True)
            nb_parsed = _parse_northbound_text(nb_text) if nb_text else {}

            # Merge by date intersection
            if ff_parsed.get("dates"):
                ff_map = dict(zip(ff_parsed["dates"], zip(
                    ff_parsed["mainForce"], ff_parsed["retail"]
                )))
                nb_map = dict(zip(nb_parsed.get("dates", []),
                                  nb_parsed.get("values", [])))
                common = [d for d in ff_map if d in nb_map]
                if not common:
                    # Northbound may not align; use ff dates with 0 northbound
                    common = ff_parsed["dates"]
                fund_flow = FundFlowData(
                    dates=common,
                    northbound=[nb_map.get(d, 0.0) for d in common],
                    mainForce=[ff_map[d][0] for d in common],
                    retail=[ff_map[d][1] for d in common],
                )
        except Exception as exc:
            logger.warning("Fund flow assembly failed for %s: %s", ticker, exc)

    # --- Assemble final ChartData ---
    chart_data = ChartData(
        kline=kline,
        macd=macd,
        rsi=rsi,
        bollinger=bollinger,
        dashboard=dashboard,
        fundFlow=fund_flow,
    )

    # Return None only if we got nothing useful
    if kline is None and macd is None and rsi is None and bollinger is None:
        logger.warning("No chart data could be assembled for %s", ticker)
        return None

    return chart_data
