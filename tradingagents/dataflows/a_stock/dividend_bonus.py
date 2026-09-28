"""增发送配数据中心 — 分红送转方案明细。

Data source: akshare (东方财富分红送转数据)

Functions:
    get_dividend_bonus() — 分红送转方案明细
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


def get_dividend_bonus(curr_date: str = "", market: str = "all", status: str = "all") -> str:
    """分红送转方案明细。

    Args:
        curr_date: 除权日 or 公告日 yyyy-mm-dd
        market: "all" | "sh" | "sz" | "bj"
        status: "all" | "plan" (预案) | "implemented" (已实施)

    Returns markdown table::

        # 增发送配 | 2026-09-04
        序号 | 证券代码 | 证券简称 | 送股 | 转股 | 派息(元) | 收益 | 净资产 |
        公积金 | 未分配利润 | 预案公告日 | 股权登记日 | 除权除息日 | 方案进度
    """
    import pandas as pd

    lines = ["# 增发送配"]

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    lines.append(f"\n数据日期: {ref_date.strftime('%Y-%m-%d')}")

    # 东方财富分红送转
    df = _safe_akshare_call("stock_fhps_em", date=ref_date.strftime("%Y%m%d"))
    if df is None or df.empty:
        lines.append(f"\n{ref_date.strftime('%Y-%m-%d')} 无分红送转数据。")
        return "\n".join(lines)

    # 市场筛选
    if market != "all":
        market_prefix = {"sh": "6", "sz": "03", "bj": "8"}.get(market, "")
        if market_prefix:
            df = df[df["证券代码"].astype(str).str.startswith(market_prefix)]

    lines.append(f"\n共 {len(df)} 条记录")
    lines.append(
        "序号 | 证券代码 | 证券简称 | 送股 | 转股 | 送转总数 | 派息(元) | "
        "收益 | 净资产 | 公积金 | 未分配利润 | 预案公告日 | 股权登记日 | "
        "除权除息日 | 方案进度"
    )

    for idx, (_, row) in enumerate(df.head(100).iterrows(), 1):
        code = str(row.get("证券代码", ""))
        name = str(row.get("证券简称", ""))
        bonus = row.get("送股", 0) or 0
        transfer = row.get("转股", 0) or 0
        total = row.get("送转总数", 0) or 0
        dividend = row.get("派息", row.get("派息(元)", 0)) or 0
        earnings = row.get("收益", 0) or 0
        net_asset = row.get("净资产", 0) or 0
        reserve = row.get("公积金", 0) or 0
        retained = row.get("未分配利润", 0) or 0
        announce_date = str(row.get("预案公告日", ""))[:10]
        reg_date = str(row.get("股权登记日", ""))[:10]
        ex_date = str(row.get("除权除息日", ""))[:10]
        progress = str(row.get("方案进度", ""))

        lines.append(
            f"  {idx} | {code} | {name} | {float(bonus):.2f} | {float(transfer):.2f} | "
            f"{float(total):.2f} | {float(dividend):.2f} | {float(earnings):.2f} | "
            f"{float(net_asset):.2f} | {float(reserve):.2f} | {float(retained):.2f} | "
            f"{announce_date} | {reg_date} | {ex_date} | {progress}"
        )

    return "\n".join(lines)
