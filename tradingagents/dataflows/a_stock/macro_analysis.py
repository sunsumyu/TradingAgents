"""宏观分析模块 — 宏观经济指标（GDP/CPI/PMI/财政收支等）。

Data source: akshare macro_china_* functions (国家统计局)

Functions:
    get_macro_gdp()         — 国内生产总值趋势 + 结构
    get_macro_cpi()         — 消费者物价指数
    get_macro_pmi()         — 采购经理人指数
    get_macro_list()        — 宏观指标分类目录
    get_macro_overview()    — 聚合数据
"""

from __future__ import annotations
import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


# 宏观指标分类（对标通达信左侧目录）
MACRO_CATEGORIES = [
    "GDP", "就业保障", "居民生活", "财政收支", "物价指数",
    "景气指数", "工业经济", "消费", "投资", "对外经济",
    "银行货币", "证券保险", "运输邮电", "能源生产",
    "世界经济", "初级产品",
]


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning("akshare %s failed: %s", fn.__name__, e)
        return None


def _df_to_records(df, limit: int = 20) -> list[dict]:
    """Convert DataFrame rows to list of dicts."""
    if df is None or df.empty:
        return []
    records = []
    for _, row in df.head(limit).iterrows():
        item = {}
        for col in df.columns:
            val = row.get(col, None)
            if val is not None:
                try:
                    if str(val) == "nan":
                        continue
                except Exception:
                    pass
                if isinstance(val, (int, float)):
                    item[str(col)] = val
                else:
                    item[str(col)] = str(val)
        records.append(item)
    return records


def get_macro_gdp() -> dict[str, Any]:
    """GDP 数据：绝对值趋势 + 产业结构占比。

    Returns {
        "trend": [{"季度", "全国(亿元)", "第一产业(亿元)", "第二产业(亿元)", "第三产业(亿元)"}],
        "growth": [{"季度", "同比增长"}],
        "structure": [{"季度", "第一产业占比%", "第二产业占比%", "第三产业占比%"}],
    }
    """
    import akshare as ak

    df = _safe_call(ak.macro_china_gdp)
    trend = []
    growth = []
    structure = []

    if df is not None and not df.empty:
        # Trend data (absolute values)
        for _, row in df.head(12).iterrows():
            quarter = str(row.get("季度", ""))
            trend.append({
                "quarter": quarter,
                "gdp": float(row.get("国内生产总值-绝对值", 0)) if row.get("国内生产总值-绝对值") else 0,
                "primary": float(row.get("第一产业-绝对值", 0)) if row.get("第一产业-绝对值") else 0,
                "secondary": float(row.get("第二产业-绝对值", 0)) if row.get("第二产业-绝对值") else 0,
                "tertiary": float(row.get("第三产业-绝对值", 0)) if row.get("第三产业-绝对值") else 0,
            })
            growth.append({
                "quarter": quarter,
                "gdp_growth": float(row.get("国内生产总值-同比增长", 0)) if row.get("国内生产总值-同比增长") else 0,
            })

            gdp_val = float(row.get("国内生产总值-绝对值", 1)) if row.get("国内生产总值-绝对值") else 1
            structure.append({
                "quarter": quarter,
                "primary_pct": round(float(row.get("第一产业-绝对值", 0)) / gdp_val * 100, 2) if row.get("第一产业-绝对值") else 0,
                "secondary_pct": round(float(row.get("第二产业-绝对值", 0)) / gdp_val * 100, 2) if row.get("第二产业-绝对值") else 0,
                "tertiary_pct": round(float(row.get("第三产业-绝对值", 0)) / gdp_val * 100, 2) if row.get("第三产业-绝对值") else 0,
            })

    return {
        "trend": trend,
        "growth": growth,
        "structure": structure,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_macro_cpi() -> dict[str, Any]:
    """CPI 消费者物价指数。

    Returns { "monthly": [...], "yearly": [...] }
    """
    import akshare as ak

    monthly = _safe_call(ak.macro_china_cpi_monthly)
    yearly = _safe_call(ak.macro_china_cpi_yearly)

    return {
        "monthly": _df_to_records(monthly),
        "yearly": _df_to_records(yearly),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_macro_pmi() -> dict[str, Any]:
    """PMI 采购经理人指数。

    Returns { "data": [...] }
    """
    # PMI data — use enterprise boom index as proxy
    import akshare as ak

    df = _safe_call(ak.macro_china_enterprise_boom_index)
    if df is None or df.empty:
        # Fallback: try PMI yearly
        df = _safe_call(ak.macro_china_cx_pmi_yearly)

    return {
        "data": _df_to_records(df),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_macro_list() -> dict[str, Any]:
    """宏观指标分类目录。

    Returns { "categories": [...], "available": [...] }
    """
    available = []
    import akshare as ak

    # Check which macro functions exist
    macro_funcs = [
        "macro_china_gdp", "macro_china_cpi", "macro_china_pmi",
        "macro_china_exports_yoy", "macro_china_fdi",
    ]
    for name in macro_funcs:
        if hasattr(ak, name):
            available.append(name)

    return {
        "categories": MACRO_CATEGORIES,
        "available": available,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_macro_overview() -> dict[str, Any]:
    """聚合宏观分析数据。

    Returns { "gdp": {...}, "cpi": {...}, "pmi": {...}, "categories": [...] }
    """
    return {
        "gdp": get_macro_gdp(),
        "cpi": get_macro_cpi(),
        "pmi": get_macro_pmi(),
        "categories": get_macro_list(),
    }
