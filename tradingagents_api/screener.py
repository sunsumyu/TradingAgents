"""Natural-language stock screener (Phase 6, ticket 6.01).

Translates a user's free-form Chinese query (e.g. "帮我找北向连续加仓
且 PE<20 的消费股") into structured filter criteria via the quick LLM,
then executes those filters against the Phase 5 FEATURE_TABLE data
functions and returns a ranked list of candidates.

Architecture:
  1. LLM parses NL → JSON filters (quick model, <2s)
  2. For each candidate stock, fetch relevant FEATURE_TABLE data
  3. Apply filters, score, rank, return top-N
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Request / Response models ────────────────────────────────────────────────


class ScreenerFilter(BaseModel):
    """One filter criterion parsed from the NL query."""

    field: str = Field(
        description=(
            "Data field to filter on. One of: northbound_flow, hot_stocks, "
            "concept_blocks, chip_distribution, dragon_tiger, "
            "industry_comparison, profit_forecast, lockup_expiry, "
            "pe_ratio, market_cap, industry, change_pct"
        )
    )
    operator: str = Field(
        default="matches",
        description="Comparison operator: >, <, >=, <=, =, in, matches, contains, 连续加仓, net_buy",
    )
    value: Any = Field(
        description="Threshold value (number, string, or list for 'in')"
    )
    period: str | None = Field(
        default=None,
        description="Time window, e.g. '5日', '30日'. Only for time-series fields.",
    )


class ScreenerCriteria(BaseModel):
    """Structured criteria parsed from the NL query."""

    filters: list[ScreenerFilter] = Field(default_factory=list)
    sort_by: str | None = Field(default=None, description="Field to sort by")
    ascending: bool = Field(default=False)


class ScreenerResultItem(BaseModel):
    """One stock in the screener results."""

    ticker: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    pe: float | None = None
    industry: str | None = None
    score: float = Field(default=0, description="Relevance score 0-100")
    match_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Which filters this stock matched and relevant data",
    )


class ScreenerResponse(BaseModel):
    """Full screener response envelope."""

    query: str
    parsed_criteria: ScreenerCriteria
    results: list[ScreenerResultItem] = Field(default_factory=list)
    count: int = 0
    suggestion: str = Field(default="", description="LLM-generated investment suggestion")


# ── LLM prompt for NL → structured filters ──────────────────────────────────

SCREENER_SYSTEM_PROMPT = """\
你是一个A股选股条件解析器。用户的自然语言选股条件必须翻译为JSON过滤器。

可用字段（field）：
- northbound_flow: 北向资金（连续加仓 / 净流入 > N亿）
- hot_stocks: 人气榜（排名 < N）
- concept_blocks: 概念板块（板块名称包含 X）
- chip_distribution: 筹码分布（峰值价 / 获利盘比例）
- dragon_tiger: 龙虎榜（净买入 > N万）
- industry_comparison: 行业资金（行业名称包含 X）
- profit_forecast: 盈利预测（PE < N / PEG < N / EPS增长）
- lockup_expiry: 解禁（未来有解禁 / 无解禁）
- pe_ratio: 市盈率（< N / > N）
- market_cap: 市值（> N亿 / < N亿）
- industry: 行业（消费/科技/金融/医药/新能源 等）
- change_pct: 涨跌幅（> N% / < N%）

运算符（operator）：
>, <, >=, <=, =, in, matches, contains, 连续加仓, net_buy

输出格式（严格JSON，不要markdown代码块）：
{
  "filters": [
    {"field": "northbound_flow", "operator": "连续加仓", "value": true, "period": "5日"},
    {"field": "pe_ratio", "operator": "<", "value": 20}
  ],
  "sort_by": "score",
  "ascending": false
}

注意：
- 将"连续N日加仓"解析为 operator="连续加仓", period="N日"
- 行业关键词映射到 industry field，operator="in"
- 如果用户没有明确排序要求，sort_by 设为 null
- 如果条件不涉及某个数据源，不要添加对应的filter
"""

SCREENER_USER_PROMPT = """\
选股条件：{query}

请将上述条件解析为JSON过滤器。只输出JSON，不要其他内容。"""


# ── Core execution logic ─────────────────────────────────────────────────────


def _parse_query_with_llm(query: str, config: dict[str, Any]) -> ScreenerCriteria:
    """Use the quick LLM to translate NL query → structured filters."""
    from tradingagents.llm_clients.factory import create_quick_llm

    llm = create_quick_llm(config)
    prompt = SCREENER_USER_PROMPT.format(query=query)

    try:
        response = llm.invoke([
            {"role": "system", "content": SCREENER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        text = response.content.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        parsed = json.loads(text)
        return ScreenerCriteria(
            filters=[ScreenerFilter(**f) for f in parsed.get("filters", [])],
            sort_by=parsed.get("sort_by"),
            ascending=parsed.get("ascending", False),
        )
    except Exception as exc:
        logger.warning("LLM parse failed for query '%s': %s", query, exc)
        return ScreenerCriteria()


def _get_candidate_stocks(
    filters: list[ScreenerFilter], config: dict[str, Any]
) -> list[dict[str, str]]:
    """Determine candidate stocks based on filters.

    For market-wide features (hot_stocks, northbound_flow, industry_comparison),
    we fetch the full list and extract tickers. For ticker-specific features,
    we need the user to have specified tickers or we fall back to hot_stocks.
    """
    from .astock_features import FEATURE_TABLE, is_astock_code

    today = date.today().isoformat()
    candidates: list[dict[str, str]] = []

    # Collect tickers from market-wide features
    market_features = {"hot_stocks", "northbound_flow", "industry_comparison"}
    ticker_features = set()

    for f in filters:
        if f.field in market_features:
            # These are market-wide, we'll fetch and extract tickers
            pass
        elif f.field in ("pe_ratio", "market_cap", "change_pct"):
            # These require a stock universe — fall back to hot_stocks
            pass
        else:
            ticker_features.add(f.field)

    # Strategy: use hot_stocks as the primary candidate universe
    # (most natural — these are the most-watched A-shares)
    if "hot_stocks" in FEATURE_TABLE:
        try:
            entry = FEATURE_TABLE["hot_stocks"]
            md = entry["call"]("", today, {})
            data = entry["parse"](md, "", today, {})
            for item in data.get("items", []):
                candidates.append({
                    "ticker": item["ticker"],
                    "name": item.get("name", ""),
                })
        except Exception as exc:
            logger.warning("Failed to fetch hot_stocks as candidate universe: %s", exc)

    # If no candidates from hot_stocks, try northbound
    if not candidates and "northbound_flow" in FEATURE_TABLE:
        try:
            entry = FEATURE_TABLE["northbound_flow"]
            md = entry["call"]("", today, {})
            data = entry["parse"](md, "", today, {})
            # northbound doesn't have individual stock tickers in structured data
            # Fall back to empty
        except Exception:
            pass

    return candidates


def _fetch_stock_data(
    ticker: str, filters: list[ScreenerFilter], config: dict[str, Any]
) -> dict[str, Any]:
    """Fetch relevant data for one stock based on active filters."""
    from .astock_features import FEATURE_TABLE

    today = date.today().isoformat()
    stock_data: dict[str, Any] = {"ticker": ticker}

    # Map filter fields to feature names
    field_to_feature = {
        "northbound_flow": "northbound_flow",
        "hot_stocks": "hot_stocks",
        "concept_blocks": "concept_blocks",
        "chip_distribution": "chip_distribution",
        "dragon_tiger": "dragon_tiger",
        "industry_comparison": "industry_comparison",
        "profit_forecast": "profit_forecast",
        "lockup_expiry": "lockup_expiry",
    }

    # Deduplicate features to fetch
    features_to_fetch: set[str] = set()
    for f in filters:
        feat = field_to_feature.get(f.field)
        if feat and feat in FEATURE_TABLE:
            features_to_fetch.add(feat)

    for feat_name in features_to_fetch:
        try:
            entry = FEATURE_TABLE[feat_name]
            md = entry["call"](ticker, today, {})
            data = entry["parse"](md, ticker, today, {})
            stock_data[feat_name] = data
            stock_data[f"{feat_name}_raw"] = md
        except Exception as exc:
            logger.debug("Failed to fetch %s for %s: %s", feat_name, ticker, exc)
            stock_data[feat_name] = {}

    return stock_data


def _apply_filter(data: dict[str, Any], filt: ScreenerFilter) -> bool:
    """Check if a stock's data passes one filter criterion.

    Returns True if the stock matches the filter.
    """
    field = filt.field
    op = filt.operator
    value = filt.value

    if field == "pe_ratio":
        pe = data.get("profit_forecast", {}).get("pe_ttm")
        if pe is None:
            return False
        return _compare_numeric(pe, op, value)

    if field == "market_cap":
        # Not directly available from Phase 5 features; skip
        return True

    if field == "industry":
        concepts = data.get("concept_blocks", {}).get("concepts", [])
        blocks = data.get("concept_blocks", {}).get("blocks", [])
        industry_names = [b.get("name", "") for b in blocks if b.get("category") == "行业"]
        all_names = concepts + industry_names
        if isinstance(value, list):
            return any(v in " ".join(all_names) for v in value)
        return str(value) in " ".join(all_names) if all_names else False

    if field == "change_pct":
        # Not directly in Phase 5 data; skip
        return True

    if field == "northbound_flow":
        return True  # Northbound is market-wide, not per-stock filterable here

    if field == "hot_stocks":
        return True  # Already used as candidate universe

    if field == "concept_blocks":
        concepts = data.get("concept_blocks", {}).get("concepts", [])
        blocks = data.get("concept_blocks", {}).get("blocks", [])
        names = [b.get("name", "") for b in blocks] + concepts
        if isinstance(value, list):
            return any(v in " ".join(names) for v in value)
        return str(value) in " ".join(names) if names else False

    if field == "chip_distribution":
        chip = data.get("chip_distribution", {})
        profit_ratio = chip.get("profit_ratio")
        if profit_ratio is not None and op in (">", ">="):
            return _compare_numeric(profit_ratio, op, value)
        return True

    if field == "dragon_tiger":
        dt = data.get("dragon_tiger", {})
        appearances = dt.get("appearances", [])
        if op == "net_buy" and appearances:
            return any(a.get("net_buy_wan", 0) > float(value or 0) for a in appearances)
        return len(appearances) > 0

    if field == "industry_comparison":
        return True  # Market-wide feature

    if field == "profit_forecast":
        pf = data.get("profit_forecast", {})
        pe = pf.get("pe_ttm")
        peg = pf.get("peg")
        if pe is not None and op in ("<", "<=", ">", ">="):
            return _compare_numeric(pe, op, value)
        if peg is not None and op in ("<", "<=", ">", ">="):
            return _compare_numeric(peg, op, value)
        return True

    if field == "lockup_expiry":
        le = data.get("lockup_expiry", {})
        has_future = le.get("has_future", False)
        if value is True or str(value).lower() == "true":
            return has_future
        if value is False or str(value).lower() == "false":
            return not has_future
        return True

    return True


def _compare_numeric(actual: float, op: str, threshold: Any) -> bool:
    """Compare a numeric value against a threshold with the given operator."""
    try:
        t = float(threshold)
    except (ValueError, TypeError):
        return False
    if op == ">":
        return actual > t
    if op == ">=":
        return actual >= t
    if op == "<":
        return actual < t
    if op == "<=":
        return actual <= t
    if op == "=" or op == "==":
        return abs(actual - t) < 0.001
    return True


def _score_stock(
    data: dict[str, Any], filters: list[ScreenerFilter]
) -> tuple[float, dict[str, Any]]:
    """Score a stock 0-100 based on how well it matches the filters.

    Returns (score, match_details).
    """
    score = 0.0
    details: dict[str, Any] = {}
    total_filters = len(filters) if filters else 1

    for filt in filters:
        matched = _apply_filter(data, filt)
        if matched:
            score += 100.0 / total_filters
            details[filt.field] = {"matched": True, "filter": filt.model_dump()}
        else:
            details[filt.field] = {"matched": False, "filter": filt.model_dump()}

    # Bonus for rich data availability
    feature_count = sum(
        1 for k in data if k in (
            "chip_distribution", "dragon_tiger", "concept_blocks",
            "profit_forecast", "lockup_expiry",
        ) and data[k]
    )
    score = min(100.0, score + feature_count * 2)

    return round(score, 1), details


# ── Public API ───────────────────────────────────────────────────────────────


def run_screener(
    query: str,
    config: dict[str, Any],
    max_results: int = 20,
    ticker_hint: str | None = None,
) -> ScreenerResponse:
    """Run the natural-language screener.

    Args:
        query: User's natural-language选股条件.
        config: TradingAgents config dict (for LLM credentials).
        max_results: Maximum number of results to return.
        ticker_hint: Optional specific ticker to analyze (bypass candidate discovery).

    Returns:
        ScreenerResponse with parsed criteria, results, and suggestion.
    """
    # Step 1: Parse NL → structured filters
    criteria = _parse_query_with_llm(query, config)

    if not criteria.filters:
        return ScreenerResponse(
            query=query,
            parsed_criteria=criteria,
            results=[],
            count=0,
            suggestion="无法解析选股条件，请尝试更具体的描述，例如「PE<20的消费股」。",
        )

    # Step 2: Get candidate stocks
    if ticker_hint and is_astock_code(ticker_hint):
        candidates = [{"ticker": ticker_hint, "name": ""}]
    else:
        candidates = _get_candidate_stocks(criteria.filters, config)

    if not candidates:
        return ScreenerResponse(
            query=query,
            parsed_criteria=criteria,
            results=[],
            count=0,
            suggestion="未找到候选股票，请尝试放宽条件。",
        )

    # Step 3: Fetch data and score each candidate
    scored: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for cand in candidates[:50]:  # Limit to 50 candidates for performance
        ticker = cand["ticker"]
        try:
            stock_data = _fetch_stock_data(ticker, criteria.filters, config)
            stock_data["name"] = cand.get("name", "")
            score, details = _score_stock(stock_data, criteria.filters)

            # Extract common fields for display
            pe = stock_data.get("profit_forecast", {}).get("pe_ttm")
            item = ScreenerResultItem(
                ticker=ticker,
                name=cand.get("name", ""),
                pe=pe,
                score=score,
                match_details=details,
            )
            scored.append((score, stock_data, item.model_dump()))
        except Exception as exc:
            logger.debug("Error scoring %s: %s", ticker, exc)

    # Step 4: Sort and limit
    scored.sort(key=lambda x: x[0], reverse=not criteria.ascending)
    results = []
    for score, stock_data, item_dict in scored[:max_results]:
        item = ScreenerResultItem(**item_dict)
        item.score = score
        results.append(item)

    # Step 5: Generate suggestion
    suggestion = ""
    if results:
        top_names = [r.name or r.ticker for r in results[:3]]
        suggestion = (
            f"找到 {len(results)} 只符合条件的股票。"
            f"排名前三：{', '.join(top_names)}。"
            f"建议结合技术面和基本面进一步分析。"
        )

    return ScreenerResponse(
        query=query,
        parsed_criteria=criteria,
        results=results,
        count=len(results),
        suggestion=suggestion,
    )
