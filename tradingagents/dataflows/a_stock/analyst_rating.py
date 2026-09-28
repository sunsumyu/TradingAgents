"""分析师评级数据中心 — 个股投资评级 + EPS 预测 + 目标价。

Data source: akshare (东方财富分析师评级数据)

Functions:
    get_analyst_rating() — 分析师评级/目标价/EPS预测
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _safe_akshare_call(fn_name: str, **kwargs) -> Any:
    try:
        import akshare as ak
        fn = getattr(ak, fn_name)
        return fn(**kwargs)
    except ImportError:
        logger.warning("akshare not installed; %s unavailable", fn_name)
        return None
    except Exception as e:
        logger.warning("akshare.%s failed: %s", fn_name, e)
        return None


def get_analyst_rating(curr_date: str = "", period: str = "一月内") -> str:
    """分析师评级（个股投资评级）。

    Args:
        curr_date: 报告日期 yyyy-mm-dd
        period: "一月内" | "三月内" | "六月内" | "一年内"

    Returns markdown table::

        # 价值分析 - 个股投资评级 | 2026-09-03
        序号 | 报告日期 | 证券代码 | 证券简称 | 评级 | 评级变化 | 目标价 |
        EPS实际值 | T年度 | T+1年 | T+2年 | 标题 | 研究机构
    """
    import pandas as pd

    lines = ["# 价值分析 - 个股投资评级"]

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    lines.append(f"\n数据日期: {ref_date.strftime('%Y-%m-%d')}")
    lines.append(f"统计周期: {period}")

    # 东方财富分析师评级
    df = _safe_akshare_call("stock_profit_forecast_em", symbol="")
    if df is None or df.empty:
        lines.append(f"\n{ref_date.strftime('%Y-%m-%d')} 无分析师评级数据。")
        return "\n".join(lines)

    lines.append(f"\n共 {len(df)} 条记录")
    lines.append(
        "序号 | 报告日期 | 证券代码 | 证券简称 | 评级 | 评级变化 | 目标价 | "
        "EPS实际值 | T年度 | T+1年 | T+2年 | 标题 | 研究机构"
    )

    for idx, (_, row) in enumerate(df.head(100).iterrows(), 1):
        report_date = str(row.get("报告日期", ""))[:10]
        code = str(row.get("证券代码", ""))
        name = str(row.get("证券简称", ""))
        rating = str(row.get("评级", row.get("投资评级", "")))
        rating_change = str(row.get("评级变化", ""))
        target_price = row.get("目标价", 0) or 0
        eps_actual = row.get("EPS实际值", row.get("EPS", 0)) or 0
        eps_t = row.get("T年度", row.get("预测EPS1", 0)) or 0
        eps_t1 = row.get("T+1年", row.get("预测EPS2", 0)) or 0
        eps_t2 = row.get("T+2年", row.get("预测EPS3", 0)) or 0
        title = str(row.get("标题", row.get("研究报告", "")))
        institution = str(row.get("研究机构", row.get("机构", "")))

        lines.append(
            f"  {idx} | {report_date} | {code} | {name} | {rating} | {rating_change} | "
            f"{float(target_price):.2f} | {float(eps_actual):.2f} | {float(eps_t):.2f} | "
            f"{float(eps_t1):.2f} | {float(eps_t2):.2f} | {title[:50]} | {institution}"
        )

    return "\n".join(lines)
