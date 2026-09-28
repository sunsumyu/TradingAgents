"""基金数据模块 — 基金发行、基金公告、基金管理、基金规模。

Data source: akshare fund_*_em functions (东方财富天天基金)

Functions:
    get_fund_purchase()     — 基金发行列表（全部/发行中/将发行）
    get_fund_announcement() — 基金公告
    get_fund_scale()        — 基金规模统计
    get_fund_open_info()    — 开放式基金信息
    get_fund_data_overview() — 聚合全部基金数据
"""

from __future__ import annotations
import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


def _safe_call(fn, *args, **kwargs):
    """Safely call akshare function, return DataFrame or None."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning("akshare %s failed: %s", fn.__name__, e)
        return None


def get_fund_purchase() -> dict[str, Any]:
    """基金发行列表。

    Returns {
        "all": [...], "issuing": [...], "upcoming": [...]
    } where each item has: code, name, type, nav, nav_date, subscribe_status, redeem_status, next_open, min_buy, daily_limit, fee_rate
    """
    import akshare as ak

    df = _safe_call(ak.fund_purchase_em)
    if df is None or df.empty:
        return {"all": [], "issuing": [], "upcoming": [], "total": 0}

    all_items = []
    for _, row in df.iterrows():
        all_items.append({
            "code": str(row.get("基金代码", "")),
            "name": str(row.get("基金简称", "")),
            "type": str(row.get("基金类型", "")),
            "nav": row.get("最新净值/万份收益", None),
            "nav_date": str(row.get("最新净值/万份收益-报告时间", "")),
            "subscribe_status": str(row.get("申购状态", "")),
            "redeem_status": str(row.get("赎回状态", "")),
            "next_open": str(row.get("下一开放日", "")),
            "min_buy": float(row.get("购买起点", 0)) if row.get("购买起点") else 0,
            "daily_limit": float(row.get("日累计限定金额", 0)) if row.get("日累计限定金额") else 0,
            "fee_rate": float(row.get("手续费", 0)) if row.get("手续费") else 0,
        })

    # Filter by status
    issuing = [i for i in all_items if "暂停" in i["subscribe_status"] or "暂停" in i["redeem_status"]]
    upcoming = [i for i in all_items if i.get("next_open") and i["next_open"] != "NaT" and i["next_open"] != "nan" and i["next_open"] != ""]

    return {
        "total": len(all_items),
        "all": all_items[:200],  # Limit to 200 for performance
        "issuing": issuing[:100],
        "upcoming": upcoming[:100],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_fund_announcement() -> dict[str, Any]:
    """基金公告数据。

    Returns { "reports": [...], "dividends": [...], "personnel": [...] }
    """
    import akshare as ak

    reports = _safe_call(ak.fund_announcement_report_em)
    dividends = _safe_call(ak.fund_announcement_dividend_em)
    personnel = _safe_call(ak.fund_announcement_personnel_em)

    result = {"reports": [], "dividends": [], "personnel": []}

    for df, key in [(reports, "reports"), (dividends, "dividends"), (personnel, "personnel")]:
        if df is None or df.empty:
            continue
        items = []
        for _, row in df.head(50).iterrows():
            item = {}
            for col in df.columns:
                val = row.get(col, None)
                if val is not None and str(val) != "nan":
                    item[str(col)] = str(val)
            items.append(item)
        result[key] = items

    result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return result


def get_fund_scale() -> dict[str, Any]:
    """基金规模统计。

    Returns { "by_type": [...], "total_aum": ... }
    """
    import akshare as ak

    df = _safe_call(ak.fund_aum_em)
    if df is None or df.empty:
        return {"by_type": [], "total_aum": 0}

    by_type = []
    for _, row in df.iterrows():
        item = {}
        for col in df.columns:
            val = row.get(col, None)
            if val is not None and str(val) != "nan":
                item[str(col)] = str(val) if not isinstance(val, (int, float)) else val
        by_type.append(item)

    return {
        "by_type": by_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_fund_open_info() -> dict[str, Any]:
    """开放式基金信息。

    Returns { "items": [...] }
    """
    import akshare as ak

    df = _safe_call(ak.fund_open_fund_daily_em)
    if df is None or df.empty:
        return {"items": [], "total": 0}

    items = []
    for _, row in df.head(200).iterrows():
        item = {}
        for col in df.columns:
            val = row.get(col, None)
            if val is not None and str(val) != "nan":
                item[str(col)] = str(val) if not isinstance(val, (int, float)) else val
        items.append(item)

    return {
        "items": items,
        "total": len(items),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_fund_data_overview() -> dict[str, Any]:
    """聚合全部基金数据。

    Returns {
        "purchase": {...},
        "announcement": {...},
        "scale": {...},
        "open_info": {...},
    }
    """
    return {
        "purchase": get_fund_purchase(),
        "announcement": get_fund_announcement(),
        "scale": get_fund_scale(),
        "open_info": get_fund_open_info(),
    }
