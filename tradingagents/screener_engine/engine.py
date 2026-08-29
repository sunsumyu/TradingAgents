"""ScreenerEngine — stock screening with filters, templates, and LLM.

This is the deep module's main class. It provides three methods:

1. screen() — structured filter-based screening
2. screen_natural() — LLM natural language screening
3. get_templates() — preset screening templates
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd

from tradingagents.data_center import DataCenter

from .models import (
    Filter,
    FilterOperator,
    ScreenerResult,
    ScreenerTemplate,
    SCREEN_FIELDS,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Preset templates
# ═══════════════════════════════════════════════════════════════════════════════

PRESET_TEMPLATES: list[ScreenerTemplate] = [
    ScreenerTemplate(
        id="value",
        name="价值股筛选",
        description="低PE/PB、高股息率的价值型股票",
        category="value",
        filters=[
            Filter("pe_ratio", FilterOperator.LT, 15),
            Filter("pb_ratio", FilterOperator.LT, 2),
            Filter("dividend_yield", FilterOperator.GT, 3),
            Filter("roe", FilterOperator.GT, 10),
        ],
        sort_by="dividend_yield",
        tags=["价值投资", "防御型"],
    ),
    ScreenerTemplate(
        id="growth",
        name="成长股筛选",
        description="高增长、高ROE的成长型股票",
        category="growth",
        filters=[
            Filter("revenue_growth", FilterOperator.GT, 20),
            Filter("profit_growth", FilterOperator.GT, 25),
            Filter("roe", FilterOperator.GT, 15),
            Filter("market_cap", FilterOperator.GT, 50_000_000_000),
        ],
        sort_by="profit_growth",
        tags=["成长投资", "进攻型"],
    ),
    ScreenerTemplate(
        id="momentum",
        name="动量突破",
        description="放量突破、资金流入的强势股",
        category="momentum",
        filters=[
            Filter("change_pct", FilterOperator.GT, 3),
            Filter("volume_ratio", FilterOperator.GT, 2),
            Filter("turnover_rate", FilterOperator.GT, 5),
        ],
        sort_by="volume_ratio",
        tags=["短线", "动量"],
    ),
    ScreenerTemplate(
        id="oversold",
        name="超跌反弹",
        description="RSI超卖、跌幅较大的反弹机会",
        category="technical",
        filters=[
            Filter("rsi_14", FilterOperator.LT, 30),
            Filter("change_pct", FilterOperator.LT, -5),
        ],
        sort_by="rsi_14",
        tags=["短线", "反弹"],
    ),
    ScreenerTemplate(
        id="large_cap",
        name="大盘蓝筹",
        description="市值500亿以上的蓝筹股",
        category="fundamental",
        filters=[
            Filter("market_cap", FilterOperator.GT, 50_000_000_000),
            Filter("pe_ratio", FilterOperator.LT, 25),
            Filter("dividend_yield", FilterOperator.GT, 2),
        ],
        sort_by="market_cap",
        tags=["蓝筹", "稳健"],
    ),
    ScreenerTemplate(
        id="small_cap_growth",
        name="小盘成长",
        description="市值50-200亿、高增长的小盘股",
        category="growth",
        filters=[
            Filter("market_cap", FilterOperator.BETWEEN, 5_000_000_000, 20_000_000_000),
            Filter("profit_growth", FilterOperator.GT, 30),
            Filter("roe", FilterOperator.GT, 12),
        ],
        sort_by="profit_growth",
        tags=["小盘", "成长"],
    ),
    ScreenerTemplate(
        id="dividend",
        name="高股息策略",
        description="高股息率、低波动的防御型股票",
        category="value",
        filters=[
            Filter("dividend_yield", FilterOperator.GT, 4),
            Filter("pe_ratio", FilterOperator.LT, 20),
            Filter("debt_ratio", FilterOperator.LT, 60),
        ],
        sort_by="dividend_yield",
        tags=["股息", "防御"],
    ),
    ScreenerTemplate(
        id="low_pe",
        name="低估值",
        description="PE低于行业平均的低估股票",
        category="value",
        filters=[
            Filter("pe_ratio", FilterOperator.LT, 10),
            Filter("pb_ratio", FilterOperator.LT, 1.5),
            Filter("market_cap", FilterOperator.GT, 10_000_000_000),
        ],
        sort_by="pe_ratio",
        tags=["估值", "价值"],
    ),
    ScreenerTemplate(
        id="high_volatility",
        name="高波动",
        description="高振幅、适合短线交易的股票",
        category="technical",
        filters=[
            Filter("amplitude", FilterOperator.GT, 5),
            Filter("turnover_rate", FilterOperator.GT, 8),
            Filter("volume_ratio", FilterOperator.GT, 1.5),
        ],
        sort_by="amplitude",
        tags=["短线", "波动"],
    ),
    ScreenerTemplate(
        id="northbound",
        name="北向资金流入",
        description="北向资金连续流入的股票",
        category="fundamental",
        filters=[
            Filter("northbound_flow", FilterOperator.GT, 0),
            Filter("northbound_days", FilterOperator.GTE, 3),
        ],
        sort_by="northbound_flow",
        tags=["北向", "外资"],
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# Filter evaluation
# ═══════════════════════════════════════════════════════════════════════════════


def _apply_filter(value: Any, f: Filter) -> bool:
    """Apply a single filter to a value. Returns True if it matches."""
    if value is None:
        return False

    try:
        val = float(value)
    except (ValueError, TypeError):
        # String comparison for non-numeric fields
        val_str = str(value).lower()
        f_val_str = str(f.value).lower()
        if f.operator == FilterOperator.EQ:
            return val_str == f_val_str
        elif f.operator == FilterOperator.CONTAINS:
            return f_val_str in val_str
        elif f.operator == FilterOperator.IN:
            if isinstance(f.value, (list, tuple)):
                return val_str in [str(v).lower() for v in f.value]
            return val_str == f_val_str
        return False

    if f.operator == FilterOperator.GT:
        return val > f.value
    elif f.operator == FilterOperator.LT:
        return val < f.value
    elif f.operator == FilterOperator.GTE:
        return val >= f.value
    elif f.operator == FilterOperator.LTE:
        return val <= f.value
    elif f.operator == FilterOperator.EQ:
        return abs(val - f.value) < 1e-10
    elif f.operator == FilterOperator.NEQ:
        return abs(val - f.value) >= 1e-10
    elif f.operator == FilterOperator.BETWEEN:
        return f.value <= val <= (f.value2 or f.value)
    elif f.operator == FilterOperator.IN:
        if isinstance(f.value, (list, tuple)):
            return val in [float(v) for v in f.value]
        return abs(val - f.value) < 1e-10

    return False


# ═══════════════════════════════════════════════════════════════════════════════
# ScreenerEngine
# ═══════════════════════════════════════════════════════════════════════════════


class ScreenerEngine:
    """Screener Engine — deep module with small interface.

    Interface (3 methods)::

        engine = ScreenerEngine()
        results = engine.screen(criteria, sort_by="pe_ratio", limit=20)
        results = engine.screen_natural("PE<20 消费股")
        templates = engine.get_templates()

    Implementation hides: filter compilation, stock ranking, template
    management, and LLM query parsing.
    """

    def __init__(self, data_center: DataCenter | None = None) -> None:
        self._data = data_center or DataCenter()
        self._templates = {t.id: t for t in PRESET_TEMPLATES}
        self._stock_pool: pd.DataFrame | None = None

    # ── Public interface ──────────────────────────────────────────────────

    def screen(
        self,
        criteria: list[Filter],
        sort_by: str | None = None,
        ascending: bool = False,
        limit: int = 50,
    ) -> list[ScreenerResult]:
        """Screen stocks using structured filter criteria.

        Args:
            criteria: List of Filter objects.
            sort_by: Field to sort results by.
            ascending: Sort direction.
            limit: Maximum number of results.

        Returns:
            List of ScreenerResult objects, sorted by score.
        """
        pool = self._get_stock_pool()
        if pool.empty:
            return []

        # Apply filters
        mask = pd.Series(True, index=pool.index)
        matched_counts = pd.Series(0, index=pool.index)

        for f in criteria:
            if f.field not in pool.columns:
                continue
            filter_mask = pool[f.field].apply(lambda v, flt=f: _apply_filter(v, flt))
            mask = mask & filter_mask
            matched_counts = matched_counts + filter_mask.astype(int)

        filtered = pool[mask].copy()
        if filtered.empty:
            return []

        # Add match counts
        filtered["_matched"] = matched_counts[mask]

        # Sort
        if sort_by and sort_by in filtered.columns:
            filtered = filtered.sort_values(sort_by, ascending=ascending)

        # Limit
        filtered = filtered.head(limit)

        # Convert to results
        results = []
        for _, row in filtered.iterrows():
            results.append(ScreenerResult(
                ticker=str(row.get("ticker", "")),
                name=str(row.get("name", "")),
                score=float(row.get("_matched", 0)) / len(criteria) * 100 if criteria else 0,
                matched_filters=int(row.get("_matched", 0)),
                data=row.to_dict(),
            ))

        return results

    def screen_natural(
        self,
        query: str,
        limit: int = 50,
    ) -> list[ScreenerResult]:
        """Screen stocks using natural language query (LLM-powered).

        Parses the query into structured filters, then runs screen().

        Args:
            query: Natural language query in Chinese/English.
            limit: Maximum number of results.

        Returns:
            List of ScreenerResult objects.
        """
        criteria = self._parse_query_with_llm(query)
        if not criteria:
            return []
        return self.screen(criteria, limit=limit)

    def get_templates(self) -> list[ScreenerTemplate]:
        """Get all preset screening templates.

        Returns:
            List of ScreenerTemplate objects.
        """
        return list(self._templates.values())

    def get_template(self, template_id: str) -> ScreenerTemplate | None:
        """Get a specific template by ID."""
        return self._templates.get(template_id)

    def run_template(
        self,
        template_id: str,
        sort_by: str | None = None,
        ascending: bool | None = None,
        limit: int = 50,
    ) -> list[ScreenerResult]:
        """Run a preset template.

        Args:
            template_id: Template ID (e.g., "value", "growth").
            sort_by: Override template's sort_by.
            ascending: Override template's ascending.
            limit: Maximum results.

        Returns:
            List of ScreenerResult objects.
        """
        template = self._templates.get(template_id)
        if template is None:
            return []

        return self.screen(
            template.filters,
            sort_by=sort_by or template.sort_by,
            ascending=ascending if ascending is not None else template.ascending,
            limit=limit,
        )

    # ── Private helpers ───────────────────────────────────────────────────

    def _get_stock_pool(self) -> pd.DataFrame:
        """Get the stock pool for screening.

        In a real implementation, this would fetch from a data source.
        For now, we return an empty DataFrame (callers should provide data).
        """
        if self._stock_pool is not None:
            return self._stock_pool

        # Try to get from A-stock hot stocks list
        try:
            from tradingagents.dataflows.a_stock.hot_stocks import get_hot_stocks
            result = get_hot_stocks()
            if result and isinstance(result, pd.DataFrame):
                self._stock_pool = result
                return self._stock_pool
        except Exception:
            pass

        return pd.DataFrame()

    def set_stock_pool(self, pool: pd.DataFrame) -> None:
        """Manually set the stock pool for screening."""
        self._stock_pool = pool

    def _parse_query_with_llm(self, query: str) -> list[Filter]:
        """Parse a natural language query into filter criteria using LLM.

        This is a simplified parser that handles common Chinese patterns.
        A full implementation would use the LLM client.
        """
        criteria: list[Filter] = []
        query_lower = query.lower()

        # Parse common patterns
        import re

        # PE pattern: PE<20, 市盈率<20
        pe_match = re.search(r"(?:pe|市盈率)\s*[<<=]\s*(\d+)", query_lower)
        if pe_match:
            criteria.append(Filter("pe_ratio", FilterOperator.LT, float(pe_match.group(1))))

        # PB pattern: PB<3, 市净率<3
        pb_match = re.search(r"(?:pb|市净率)\s*[<<=]\s*(\d+)", query_lower)
        if pb_match:
            criteria.append(Filter("pb_ratio", FilterOperator.LT, float(pb_match.group(1))))

        # ROE pattern: ROE>15, 净资产收益率>15
        roe_match = re.search(r"(?:roe|净资产收益率)\s*[>=>]\s*(\d+)", query_lower)
        if roe_match:
            criteria.append(Filter("roe", FilterOperator.GT, float(roe_match.group(1))))

        # Market cap pattern: 市值>100亿
        cap_match = re.search(r"市值\s*[>=>]\s*(\d+)\s*亿", query_lower)
        if cap_match:
            criteria.append(Filter("market_cap", FilterOperator.GT, float(cap_match.group(1)) * 100_000_000))

        # Change pct pattern: 涨幅>5%
        chg_match = re.search(r"涨幅?\s*[>=>]\s*(\d+)", query_lower)
        if chg_match:
            criteria.append(Filter("change_pct", FilterOperator.GT, float(chg_match.group(1))))

        # Dividend pattern: 股息率>3%
        div_match = re.search(r"股息率?\s*[>=>]\s*(\d+)", query_lower)
        if div_match:
            criteria.append(Filter("dividend_yield", FilterOperator.GT, float(div_match.group(1))))

        # Growth pattern: 增长>20%
        growth_match = re.search(r"增长\s*[>=>]\s*(\d+)", query_lower)
        if growth_match:
            criteria.append(Filter("profit_growth", FilterOperator.GT, float(growth_match.group(1))))

        # RSI pattern: RSI<30
        rsi_match = re.search(r"rsi\s*[<<=]\s*(\d+)", query_lower)
        if rsi_match:
            criteria.append(Filter("rsi_14", FilterOperator.LT, float(rsi_match.group(1))))

        # Industry pattern: 消费, 科技, 金融, 医药
        industry_keywords = {
            "消费": "消费",
            "科技": "科技",
            "金融": "金融",
            "医药": "医药",
            "新能源": "新能源",
            "半导体": "半导体",
        }
        for keyword, industry in industry_keywords.items():
            if keyword in query_lower:
                criteria.append(Filter("industry", FilterOperator.CONTAINS, industry))
                break

        # Northbound pattern: 北向, 外资
        if "北向" in query_lower or "外资" in query_lower:
            criteria.append(Filter("northbound_flow", FilterOperator.GT, 0))

        return criteria
