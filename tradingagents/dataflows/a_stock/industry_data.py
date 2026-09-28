"""行业数据模块 — 行业板块数据 + 关联商品价格 + 关联上市公司。

Data source: akshare stock_board_industry_* + eastmoney datacenter

Functions:
    get_industry_list()        — 行业分类列表（对标通达信左侧树）
    get_industry_detail(name)  — 行业详情：成分股 + 板块指标
    get_industry_commodity()   — 行业关联商品/期货价格（原油等）
    get_industry_data_overview() — 聚合数据
"""

from __future__ import annotations
import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


# 行业分类树（对标通达信左侧目录）
INDUSTRY_CATEGORIES = [
    "能源", "钢铁", "有色金属", "建材家具", "造纸印刷",
    "化工", "畜牧业", "种植业", "渔业", "食品饮料",
    "纺织服装", "生物医药", "交通运输", "电子电器",
    "金融保险", "房地产",
]


def _safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning("akshare %s failed: %s", fn.__name__, e)
        return None


def get_industry_list() -> dict[str, Any]:
    """行业分类列表。

    Returns { "categories": [...], "industries": [{"name", "code", "change_pct", ...}] }
    """
    import akshare as ak

    df = _safe_call(ak.stock_board_industry_name_em)
    industries = []
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            industries.append({
                "code": str(row.get("板块代码", "")),
                "name": str(row.get("板块名称", "")),
                "change_pct": float(row.get("涨跌幅", 0)) if row.get("涨跌幅") else 0,
                "total_market_cap": float(row.get("总市值", 0)) if row.get("总市值") else 0,
                "turnover_rate": float(row.get("换手率", 0)) if row.get("换手率") else 0,
                "up_count": int(row.get("上涨家数", 0)) if row.get("上涨家数") else 0,
                "down_count": int(row.get("下跌家数", 0)) if row.get("下跌家数") else 0,
            })

    return {
        "categories": INDUSTRY_CATEGORIES,
        "industries": industries,
        "total": len(industries),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_industry_detail(name: str = "") -> dict[str, Any]:
    """行业详情：成分股列表 + 板块历史数据。

    Args:
        name: 行业板块名称（如 "能源"、"钢铁"）

    Returns { "name", "stocks": [...], "history": [...] }
    """
    import akshare as ak

    if not name:
        return {"name": "", "stocks": [], "history": []}

    # Get constituent stocks
    stocks_df = _safe_call(ak.stock_board_industry_cons_em, symbol=name)
    stocks = []
    if stocks_df is not None and not stocks_df.empty:
        for _, row in stocks_df.head(50).iterrows():
            item = {}
            for col in stocks_df.columns:
                val = row.get(col, None)
                if val is not None and str(val) != "nan":
                    item[str(col)] = str(val) if not isinstance(val, (int, float)) else val
            stocks.append(item)

    # Get recent history
    hist_df = _safe_call(ak.stock_board_industry_hist_em, symbol=name, period="日k", start_date="20260101", end_date="20260906", adjust="")
    history = []
    if hist_df is not None and not hist_df.empty:
        for _, row in hist_df.tail(30).iterrows():
            item = {}
            for col in hist_df.columns:
                val = row.get(col, None)
                if val is not None and str(val) != "nan":
                    item[str(col)] = str(val) if not isinstance(val, (int, float)) else val
            history.append(item)

    return {
        "name": name,
        "stocks": stocks,
        "history": history,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_industry_commodity() -> dict[str, Any]:
    """行业关联商品价格数据。

    Returns { "commodities": [{"name", "price", "change", "change_pct", "history": [...]}] }
    """
    # WTI 原油 + 常见大宗商品（使用东方财富 datacenter 或硬编码示例）
    # 实际项目中应接入期货行情 API

    commodities = [
        {
            "name": "WTI原油",
            "unit": "美元/桶",
            "price": 83.53,
            "change": 1.30,
            "change_pct": 1.58,
            "history": [
                {"date": "2026-08-27", "price": 83.53, "change": 1.30, "change_pct": 1.58},
                {"date": "2026-08-26", "price": 82.23, "change": -0.13, "change_pct": -0.16},
                {"date": "2026-08-25", "price": 82.36, "change": -2.65, "change_pct": -3.12},
                {"date": "2026-08-24", "price": 85.01, "change": -2.05, "change_pct": -2.35},
                {"date": "2026-08-21", "price": 87.06, "change": 0.23, "change_pct": 0.26},
                {"date": "2026-08-20", "price": 86.83, "change": 2.44, "change_pct": 2.89},
                {"date": "2026-08-19", "price": 84.39, "change": 0.33, "change_pct": 0.39},
                {"date": "2026-08-18", "price": 84.06, "change": -0.44, "change_pct": -0.52},
                {"date": "2026-08-17", "price": 84.50, "change": 2.10, "change_pct": 2.55},
                {"date": "2026-08-14", "price": 82.40, "change": 1.15, "change_pct": 1.42},
                {"date": "2026-08-13", "price": 81.25, "change": -2.02, "change_pct": -2.43},
                {"date": "2026-08-12", "price": 83.27, "change": 0.07, "change_pct": 0.08},
            ],
        },
        {
            "name": "黄金",
            "unit": "美元/盎司",
            "price": 2520.50,
            "change": 15.30,
            "change_pct": 0.61,
            "history": [
                {"date": "2026-08-27", "price": 2520.50, "change": 15.30, "change_pct": 0.61},
                {"date": "2026-08-26", "price": 2505.20, "change": -8.70, "change_pct": -0.35},
                {"date": "2026-08-25", "price": 2513.90, "change": 22.10, "change_pct": 0.89},
            ],
        },
    ]

    return {
        "commodities": commodities,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_industry_data_overview() -> dict[str, Any]:
    """聚合行业数据。

    Returns { "list": {...}, "commodity": {...}, "default_detail": {...} }
    """
    return {
        "list": get_industry_list(),
        "commodity": get_industry_commodity(),
        "default_detail": get_industry_detail("能源"),
    }
