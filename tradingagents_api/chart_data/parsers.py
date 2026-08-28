"""Text and CSV parsing utilities for chart data.

Pure parsing — no I/O, no vendor calls.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# OHLCV CSV parsing
# ---------------------------------------------------------------------------

_OHLCV_HEADER_RE = re.compile(r"^Date,", re.IGNORECASE)

# Canonical key -> accepted header names (lowercase).  mootdx emits
# ``vol`` for the raw share count and ``Volume`` for the same value, and
# its column order is Date,Open,Close,High,Low — so we map by name, not
# by position.
_OHLCV_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date",),
    "open": ("open",),
    "high": ("high",),
    "low": ("low",),
    "close": ("close",),
    "adj_close": ("adj close", "adj_close"),
    "volume": ("volume", "vol"),
}


def _ohlcv_column_index_map(header: str) -> dict[str, int] | None:
    """Map canonical OHLCV keys to column indices from a header row.

    Returns None if the header lacks date/open/close — the minimum needed
    to build a kline.  Handles yfinance (``Date,Open,High,Low,Close,Adj
    Close,Volume``), Sina (``Date,Open,High,Low,Close,Volume``) and mootdx
    (``Date,Open,Close,High,Low,vol,Amount,Volume``) layouts in any order.
    """
    names = [c.strip().lower() for c in header.split(",")]
    used: set[int] = set()
    idx_map: dict[str, int] = {}
    for key, aliases in _OHLCV_COLUMN_ALIASES.items():
        for alias in aliases:
            for i, name in enumerate(names):
                if name == alias and i not in used:
                    idx_map[key] = i
                    used.add(i)
                    break
            if key in idx_map:
                break
    if "date" not in idx_map or "open" not in idx_map or "close" not in idx_map:
        return None
    return idx_map


def parse_ohlcv_csv(csv_text: str) -> list[dict[str, Any]]:
    """Parse OHLCV CSV text into structured records.

    The header row is matched by column *name*, not position, so both
    yfinance format (``Date,Open,High,Low,Close,Adj Close,Volume``) and
    a_stock/mootdx format (``Date,Open,Close,High,Low,vol,Amount,Volume``)
    parse correctly.

    Skips comment lines (``# ...``) and the header row.  Returns a list of
    dicts with keys: ``date, open, high, low, close, adj_close, volume``.
    Columns absent from the header fall back: ``adj_close`` to ``close``,
    ``volume`` to 0.0.
    """
    records: list[dict[str, Any]] = []
    idx_map: dict[str, int] | None = None

    for line in csv_text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith("#"):
            continue

        if idx_map is None:
            if _OHLCV_HEADER_RE.match(line):
                idx_map = _ohlcv_column_index_map(line)
            continue

        parts = line.split(",")
        if len(parts) < 2:
            continue

        def _num(key: str, default: float) -> float:
            i = idx_map.get(key)
            if i is None or i >= len(parts):
                return default
            try:
                return float(parts[i])
            except ValueError:
                return default

        try:
            close = _num("close", 0.0)
            records.append(
                {
                    "date": parts[idx_map["date"]].strip(),
                    "open": _num("open", 0.0),
                    "high": _num("high", 0.0),
                    "low": _num("low", 0.0),
                    "close": close,
                    "adj_close": _num("adj_close", close),
                    "volume": _num("volume", 0.0),
                }
            )
        except (ValueError, IndexError):
            continue

    return records


# ---------------------------------------------------------------------------
# Indicator text parsing
# ---------------------------------------------------------------------------

_DATE_VALUE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}):\s*(.+)$")


def parse_indicator_text(text: str) -> dict[str, list[Any]]:
    """Parse the formatted output of ``get_stock_stats_indicators_window``.

    Returns ``{"dates": [...], "values": [...]}`` with N/A entries excluded.
    """
    dates: list[str] = []
    values: list[float] = []

    for line in text.splitlines():
        m = _DATE_VALUE_RE.match(line.strip())
        if not m:
            continue

        date_str, raw_value = m.group(1), m.group(2).strip()

        if raw_value.startswith("N/A") or raw_value == "":
            continue

        try:
            values.append(float(raw_value))
            dates.append(date_str)
        except ValueError:
            continue

    return {"dates": dates, "values": values}


def parse_indicator_bundle(
    indicators: dict[str, str],
) -> dict[str, dict[str, list[Any]]]:
    """Parse a bundle of indicator texts keyed by indicator name.

    Returns ``{indicator_name: {"dates": [...], "values": [...]}, ...}``
    with dates sorted in ascending order (oldest first).
    """
    result = {}
    for name, text in indicators.items():
        parsed = parse_indicator_text(text)
        if parsed["dates"]:
            paired = sorted(zip(parsed["dates"], parsed["values"]))
            parsed["dates"] = [d for d, _ in paired]
            parsed["values"] = [v for _, v in paired]
        result[name] = parsed
    return result


# ---------------------------------------------------------------------------
# Fund flow text parsing
# ---------------------------------------------------------------------------

_FUND_FLOW_ROW_RE = re.compile(
    r"^\s*\d{4}-\d{2}-\d{2}\s*\|?\s*main=([-\d.]+)\s*\|?\s*large=([-\d.]+)"
    r"\s*\|?\s*mid=([-\d.]+)\s*\|?\s*small=([-\d.]+)"
)
_NORTHBOUND_ROW_RE = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}):\s*HGT=([-\d.]+)\s*SGT=([-\d.]+)"
)


def parse_fund_flow_text(text: str) -> dict[str, list[Any]]:
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
            date_match = re.match(r"\s*(\d{4}-\d{2}-\d{2})", line)
            if date_match:
                dates[-1] = date_match.group(1)
            main_force.append(float(m.group(1)))
            retail.append(float(m.group(3)) + float(m.group(4)))

    return {"dates": dates, "mainForce": main_force, "retail": retail}


def parse_northbound_text(text: str) -> dict[str, list[Any]]:
    """Parse the historical daily northbound flow from get_northbound_flow.

    Returns ``{"dates": [...], "values": [...]}`` in 亿元.
    """
    dates: list[str] = []
    values: list[float] = []

    for line in text.splitlines():
        m = _NORTHBOUND_ROW_RE.match(line)
        if m:
            dates.append(m.group(1))
            values.append(float(m.group(2)) + float(m.group(3)))

    return {"dates": dates, "values": values}


# ---------------------------------------------------------------------------
# Signal extraction from markdown
# ---------------------------------------------------------------------------

_RATING_RE = re.compile(r"\*\*Rating\*\*:\s*(\w+)", re.IGNORECASE)
_SENTIMENT_CONFIDENCE_RE = re.compile(r"Confidence:?\*{0,2}:\s*\*{0,2}\s*(low|medium|high)", re.IGNORECASE)

_TECHNICAL_KEYWORDS = re.compile(r"(RSI|MACD|SMA|EMA|Bollinger|KDJ|ATR|trend|momentum)", re.IGNORECASE)
_SENTIMENT_KEYWORDS = re.compile(r"(sentiment|bullish|bearish|social|reddit|stocktwits)", re.IGNORECASE)
_NEWS_KEYWORDS = re.compile(r"(news|headline|announcement|regulatory|macro)", re.IGNORECASE)
_FUNDAMENTALS_KEYWORDS = re.compile(r"(revenue|earnings|P/E|ROE|balance sheet|cash flow|fundamental)", re.IGNORECASE)


def extract_signal_from_decision(final_trade_decision: str) -> str:
    """Extract the rating string from the final trade decision markdown."""
    m = _RATING_RE.search(final_trade_decision)
    if m:
        rating = m.group(1).capitalize()
        valid = {"Buy", "Overweight", "Hold", "Underweight", "Sell"}
        return rating if rating in valid else "Hold"
    return "Hold"


def extract_confidence(sentiment_report: str) -> float:
    """Extract confidence value from sentiment report text."""
    conf_match = _SENTIMENT_CONFIDENCE_RE.search(sentiment_report)
    if conf_match:
        conf_map = {"low": 30.0, "medium": 60.0, "high": 85.0}
        return conf_map.get(conf_match.group(1).lower(), 50.0)
    return 50.0


def compute_dimension_scores(sections: dict[str, str]) -> list[dict[str, Any]]:
    """Compute dimension scores by counting relevant keywords in each analyst report."""
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
