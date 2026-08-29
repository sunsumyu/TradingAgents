"""Data models for the Screener Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FilterOperator(Enum):
    """Filter comparison operators."""

    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    EQ = "="
    NEQ = "!="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    BETWEEN = "between"


@dataclass
class Filter:
    """A single filter criterion."""

    field: str
    operator: FilterOperator
    value: Any
    value2: Any = None  # For BETWEEN operator


@dataclass
class ScreenerResult:
    """A single stock result from screening."""

    ticker: str
    name: str
    score: float = 0.0  # 0-100 match score
    matched_filters: int = 0
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreenerTemplate:
    """A preset screening template."""

    id: str
    name: str
    description: str
    category: str  # "value" | "growth" | "momentum" | "technical" | "fundamental"
    filters: list[Filter]
    sort_by: str | None = None
    ascending: bool = False
    tags: list[str] = field(default_factory=list)


# ── 50+ filterable fields ─────────────────────────────────────────────────

SCREEN_FIELDS: dict[str, str] = {
    # Technical
    "pe_ratio": "市盈率",
    "pb_ratio": "市净率",
    "ps_ratio": "市销率",
    "market_cap": "总市值",
    "circulating_cap": "流通市值",
    "change_pct": "涨跌幅",
    "volume_ratio": "量比",
    "turnover_rate": "换手率",
    "amplitude": "振幅",
    "ma5": "5日均线",
    "ma10": "10日均线",
    "ma20": "20日均线",
    "ma60": "60日均线",
    "rsi_14": "RSI(14)",
    "macd": "MACD",
    "kdj_k": "KDJ-K",
    "kdj_d": "KDJ-D",
    "boll_width": "布林带宽",
    "atr_14": "ATR(14)",

    # Fundamental
    "roe": "净资产收益率",
    "roa": "总资产收益率",
    "gross_margin": "毛利率",
    "net_margin": "净利率",
    "revenue_growth": "营收增长率",
    "profit_growth": "净利润增长率",
    "debt_ratio": "资产负债率",
    "current_ratio": "流动比率",
    "dividend_yield": "股息率",
    "eps": "每股收益",
    "bps": "每股净资产",

    # Capital flow
    "northbound_flow": "北向资金净流入",
    "main_force_flow": "主力资金净流入",
    "retail_flow": "散户资金净流入",
    "northbound_days": "北向连续流入天数",
    "volume_5d_avg": "5日平均成交量",
    "volume_20d_avg": "20日平均成交量",

    # A-share specific
    "hot_rank": "人气排名",
    "dragon_tiger": "龙虎榜净买入",
    "concept_count": "概念板块数量",
    "lockup_days": "距解禁天数",
    "profit_forecast_eps": "预测EPS",
    "profit_forecast_pe": "预测PE",

    # Market
    "beta": "Beta",
    "52w_high": "52周最高",
    "52w_low": "52周最低",
    "52w_change_pct": "52周涨跌幅",
    "ipo_date": "上市日期",
    "list_years": "上市年限",
    "industry": "行业",
    "region": "地区",
}
