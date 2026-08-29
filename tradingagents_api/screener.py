"""Natural-language stock screener service (migrated onto screener_engine, ticket #3).

Translates a user's free-form Chinese query into structured filter criteria
via the quick LLM, then evaluates candidates through the screener engine —
the single comparison implementation across the codebase. The service keeps:
NL parsing, candidate discovery (hot-stocks universe), FEATURE_TABLE data
fetching, the legacy partial-match scoring formula, and the response contract.

Field vocabulary is unified onto the engine's Filter/FilterOperator. Legacy
semantics are preserved per field, including "missing optional data does not
disqualify" (translated into pass-sentinels) vs. strict fields like pe_ratio
(missing pe disqualifies, exactly as before).
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Callable, NamedTuple

from pydantic import BaseModel, Field

from tradingagents.screener_engine import Filter, FilterOperator, ScreenerEngine

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


# ── LLM parsing ──────────────────────────────────────────────────────────────


def _parse_query_with_llm(query: str, config: dict[str, Any]) -> ScreenerCriteria:
    """Use the quick LLM to translate NL query → structured filters.

    Responses are cached (ticket #13): identical queries against the same
    model return from the per-installation LLM cache instead of re-billing.
    """
    from tradingagents.agents.utils.cached_llm import CachedLLM
    from tradingagents.llm_cache import LLMCache
    from tradingagents.llm_clients.factory import create_quick_llm

    cache = LLMCache(config.get("data_cache_dir"), ticker="screener")
    llm = CachedLLM(create_quick_llm(config), cache)
    prompt = SCREENER_USER_PROMPT.format(query=query)

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        response = llm.invoke([
            SystemMessage(content=SCREENER_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
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


# ── Candidate discovery & data fetching ─────────────────────────────────────


def _get_candidate_stocks(
    filters: list[ScreenerFilter], config: dict[str, Any]
) -> list[dict[str, str]]:
    """Determine candidate stocks based on filters.

    Uses hot_stocks (人气榜) as the primary candidate universe — the
    most-watched A-shares — falling back to northbound data if unavailable.
    """
    from .astock_features import FEATURE_TABLE

    today = date.today().isoformat()
    candidates: list[dict[str, str]] = []

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

    return candidates


def _fetch_stock_data(
    ticker: str, filters: list[ScreenerFilter], config: dict[str, Any]
) -> dict[str, Any]:
    """Fetch relevant FEATURE_TABLE data for one stock based on active filters."""
    from .astock_features import FEATURE_TABLE

    today = date.today().isoformat()
    stock_data: dict[str, Any] = {"ticker": ticker}

    field_to_feature = {
        "northbound_flow": "northbound_flow",
        "hot_stocks": "hot_stocks",
        "concept_blocks": "concept_blocks",
        "chip_distribution": "chip_distribution",
        "dragon_tiger": "dragon_tiger",
        "industry_comparison": "industry_comparison",
        "profit_forecast": "profit_forecast",
        "lockup_expiry": "lockup_expiry",
        # Legacy gap fixed (ticket #3): these criteria previously fetched no
        # data, so the filters never matched anything.
        "pe_ratio": "profit_forecast",
        "industry": "concept_blocks",
    }

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


# ── Filter translation: legacy criteria → engine evaluation ─────────────────


class _FilterPlan(NamedTuple):
    """One legacy filter translated for engine evaluation.

    Either ``engine_filter`` is set (row evaluated via ScreenerEngine, with
    ``column``/``sentinel`` describing how to build the row value), or
    ``predicate`` is set for semantics the engine cannot express (OR-lists,
    boolean feature flags). Everything the engine *can* express goes through
    the engine — it is the single comparison implementation.
    """

    field: str
    filt: ScreenerFilter
    engine_filter: Filter | None = None
    predicate: Callable[[dict[str, Any]], bool] | None = None
    column: str | None = None
    filler: Callable[[dict[str, Any]], Any] | None = None
    sentinel: Any = None  # Backfilled when the data is missing (legacy: pass)


_NUMERIC_OPS = {">": FilterOperator.GT, "<": FilterOperator.LT,
                ">=": FilterOperator.GTE, "<=": FilterOperator.LTE,
                "=": FilterOperator.EQ}


def _translate_filters(filters: list[ScreenerFilter]) -> list[_FilterPlan]:
    """Translate legacy LLM-parsed criteria into engine-based plans.

    Per-field legacy semantics preserved:
    - pe_ratio: missing pe disqualifies (no sentinel)
    - market_cap / change_pct / northbound_flow / hot_stocks /
      industry_comparison: always pass (universe-level or unavailable)
    - industry / concept_blocks: substring match; list values = OR (predicate)
    - chip_distribution: missing ratio passes (sentinel); >/>= compare
    - dragon_tiger: net_buy compares max net amount; other ops = has records
    - profit_forecast: pe, falling back to peg; both missing passes (sentinel)
    - lockup_expiry: boolean has_future flag
    """
    plans: list[_FilterPlan] = []

    for f in filters:
        op = f.operator
        plan = _FilterPlan(field=f.field, filt=f)

        if f.field == "pe_ratio":
            if op in _NUMERIC_OPS:
                plan = plan._replace(
                    engine_filter=Filter("pe_ratio", _NUMERIC_OPS[op], f.value),
                    column="pe_ratio",
                    filler=lambda d: d.get("profit_forecast", {}).get("pe_ttm"),
                )
            else:
                plan = plan._replace(predicate=lambda d: True)

        elif f.field in ("market_cap", "change_pct", "northbound_flow",
                         "hot_stocks", "industry_comparison"):
            # Legacy: universe-level or unavailable — always pass
            plan = plan._replace(predicate=lambda d: True)

        elif f.field in ("industry", "concept_blocks"):
            # Both legacy fields read their names from the concept_blocks data
            def _names(d: dict[str, Any]) -> str:
                blocks = d.get("concept_blocks", {})
                concepts = blocks.get("concepts", [])
                names = [b.get("name", "") for b in blocks.get("blocks", [])]
                return " ".join(concepts + names)

            if isinstance(f.value, list):
                # OR-of-substrings — not expressible in engine operators
                joined_any = lambda d, _names=_names, _vals=f.value: any(
                    str(v) in _names(d) for v in _vals
                )
                plan = plan._replace(predicate=joined_any)
            else:
                plan = plan._replace(
                    engine_filter=Filter(f.field, FilterOperator.CONTAINS, f.value),
                    column=f.field,
                    filler=_names,
                )

        elif f.field == "chip_distribution":
            if op in (">", ">="):
                plan = plan._replace(
                    engine_filter=Filter("chip_profit_ratio", _NUMERIC_OPS[op], f.value),
                    column="chip_profit_ratio",
                    filler=lambda d: d.get("chip_distribution", {}).get("profit_ratio"),
                    sentinel=float("inf"),  # Legacy: missing ratio passes
                )
            else:
                plan = plan._replace(predicate=lambda d: True)

        elif f.field == "dragon_tiger":
            if op == "net_buy":
                plan = plan._replace(
                    engine_filter=Filter("dragon_tiger_net_buy", FilterOperator.GT,
                                         float(f.value or 0)),
                    column="dragon_tiger_net_buy",
                    filler=lambda d: max(
                        (a.get("net_buy_wan", 0)
                         for a in d.get("dragon_tiger", {}).get("appearances", [])),
                        default=None,
                    ),
                )  # No sentinel: legacy fails when no records
            else:
                has_records = lambda d: len(
                    d.get("dragon_tiger", {}).get("appearances", [])
                ) > 0
                plan = plan._replace(predicate=has_records)

        elif f.field == "profit_forecast":
            if op in _NUMERIC_OPS:
                plan = plan._replace(
                    engine_filter=Filter("profit_forecast_pe", _NUMERIC_OPS[op], f.value),
                    column="profit_forecast_pe",
                    # Legacy: pe, falling back to peg
                    filler=lambda d: d.get("profit_forecast", {}).get("pe_ttm")
                    if d.get("profit_forecast", {}).get("pe_ttm") is not None
                    else d.get("profit_forecast", {}).get("peg"),
                    # Legacy: both missing passes
                    sentinel=float("-inf") if op in ("<", "<=") else float("inf"),
                )
            else:
                plan = plan._replace(predicate=lambda d: True)

        elif f.field == "lockup_expiry":
            want = f.value is True or str(f.value).lower() == "true"
            has_future = lambda d, _want=want: bool(
                d.get("lockup_expiry", {}).get("has_future", False)
            ) == _want
            plan = plan._replace(predicate=has_future)

        else:
            plan = plan._replace(predicate=lambda d: True)

        plans.append(plan)

    return plans


def _build_row(stock_data: dict[str, Any], plans: list[_FilterPlan]) -> dict[str, Any]:
    """Build the engine-evaluation row: fill translated columns, backfilling
    pass-sentinels where the underlying data is missing."""
    row: dict[str, Any] = {"ticker": stock_data.get("ticker", "")}
    for plan in plans:
        if plan.engine_filter is None or plan.column is None:
            continue
        value = plan.filler(stock_data) if plan.filler else None
        row[plan.column] = value if value is not None else plan.sentinel
    return row


def _score_stock(
    plans: list[_FilterPlan],
    matches: list[bool],
    stock_data: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Legacy partial-match scoring over engine-evaluated results."""
    score = 0.0
    details: dict[str, Any] = {}
    total_filters = len(plans) if plans else 1

    for plan, matched in zip(plans, matches):
        if matched:
            score += 100.0 / total_filters
        details[plan.field] = {"matched": matched, "filter": plan.filt.model_dump()}

    # Bonus for rich data availability (legacy formula)
    feature_count = sum(
        1 for k in (
            "chip_distribution", "dragon_tiger", "concept_blocks",
            "profit_forecast", "lockup_expiry",
        ) if stock_data.get(k)
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
    from .astock_features import is_astock_code

    engine = ScreenerEngine()

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

    # Step 3: Fetch data, evaluate through the engine, score each candidate
    plans = _translate_filters(criteria.filters)
    engine_filters = [p.engine_filter for p in plans if p.engine_filter is not None]
    scored: list[tuple[float, dict[str, Any]]] = []

    for cand in candidates[:50]:  # Limit to 50 candidates for performance
        ticker = cand["ticker"]
        try:
            stock_data = _fetch_stock_data(ticker, criteria.filters, config)
            stock_data["name"] = cand.get("name", "")

            row = _build_row(stock_data, plans)
            engine_results = iter(engine.evaluate_row(row, engine_filters))
            matches = [
                bool(next(engine_results)) if plan.engine_filter is not None
                else bool(plan.predicate(stock_data))
                for plan in plans
            ]

            score, details = _score_stock(plans, matches, stock_data)

            pe = stock_data.get("profit_forecast", {}).get("pe_ttm")
            item = ScreenerResultItem(
                ticker=ticker,
                name=cand.get("name", ""),
                pe=pe,
                score=score,
                match_details=details,
            )
            scored.append((score, item.model_dump()))
        except Exception as exc:
            logger.debug("Error scoring %s: %s", ticker, exc)

    # Step 4: Sort and limit
    scored.sort(key=lambda x: x[0], reverse=not criteria.ascending)
    results = []
    for score, item_dict in scored[:max_results]:
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


def run_template_screener(
    template_id: str,
    max_results: int = 20,
) -> ScreenerResponse:
    """Run one of the engine's preset screening templates.

    The template runs against the engine's own stock pool with the engine's
    50-field vocabulary — the engine is fully in charge here.
    """
    engine = ScreenerEngine()
    template = engine.get_template(template_id)

    query = template.name if template else template_id
    criteria = ScreenerCriteria()

    if template is None:
        return ScreenerResponse(
            query=query,
            parsed_criteria=criteria,
            results=[],
            count=0,
            suggestion=f"未知选股模板：{template_id}。可用模板可从 GET 模板列表获取。",
        )

    engine_results = engine.run_template(template_id, limit=max_results)
    results = [
        ScreenerResultItem(
            ticker=r.ticker,
            name=r.name,
            pe=r.data.get("pe_ratio"),
            score=round(r.score, 1),
            match_details={"matched_filters": r.matched_filters, "data": {
                k: v for k, v in r.data.items() if not str(k).startswith("_")
            }},
        )
        for r in engine_results
    ]

    suggestion = ""
    if results:
        top_names = [r.name or r.ticker for r in results[:3]]
        suggestion = (
            f"模板「{template.name}」命中 {len(results)} 只。"
            f"排名前三：{', '.join(top_names)}。"
        )
    else:
        suggestion = f"模板「{template.name}」未命中候选股票。"

    return ScreenerResponse(
        query=query,
        parsed_criteria=criteria,
        results=results,
        count=len(results),
        suggestion=suggestion,
    )
