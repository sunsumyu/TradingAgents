"""财报数据中心 — 业绩预告 + 业绩快报。

Data source: akshare (东方财富业绩预告/快报)

Functions:
    get_earnings_forecast() — 业绩预告
    get_earnings_express()  — 业绩快报
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


def get_earnings_forecast(curr_date: str = "", forecast_type: str = "all") -> str:
    """业绩预告。

    Args:
        curr_date: 报告期末日 yyyy-mm-dd (如 2026-09-30)
        forecast_type: "all" | "rise" (大幅上升) | "fall" (大幅下降) |
                       "pre_increase" (预增) | "pre_decrease" (预减) |
                       "pre_profit" (预盈) | "pre_loss" (预亏) |
                       "uncertain" (不确定) | "no_big_change" (无大幅变动)

    Returns markdown table::

        # 业绩预告 | 2026-09-30
        序号 | 证券代码 | 证券简称 | 报告期 | 预告类型 | 预告内容 | 预告日期
    """
    import pandas as pd

    lines = ["# 业绩预告"]

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    lines.append(f"\n数据日期: {ref_date.strftime('%Y-%m-%d')}")

    # 业绩预告
    df = _safe_akshare_call("stock_yjbb_em", date=ref_date.strftime("%Y%m%d"))
    if df is None or df.empty:
        lines.append(f"\n{ref_date.strftime('%Y-%m-%d')} 无业绩预告数据。")
        return "\n".join(lines)

    # 预告类型筛选
    if forecast_type != "all":
        type_map = {
            "rise": "业绩大幅上升",
            "fall": "业绩大幅下降",
            "pre_increase": "业绩预增",
            "pre_decrease": "业绩预减",
            "pre_profit": "业绩预盈",
            "pre_loss": "业绩预亏",
            "uncertain": "不确定",
            "no_big_change": "无大幅变动",
        }
        type_name = type_map.get(forecast_type, "")
        if type_name:
            df = df[df.get("预告类型", pd.Series()) == type_name]

    lines.append(f"\n共 {len(df)} 条记录")
    lines.append(
        "序号 | 证券代码 | 证券简称 | 报告期 | 预告类型 | 预告内容 | 预告日期"
    )

    for idx, (_, row) in enumerate(df.head(100).iterrows(), 1):
        code = str(row.get("证券代码", ""))
        name = str(row.get("证券简称", ""))
        report_period = str(row.get("报告期", ""))[:10]
        forecast_type_name = str(row.get("预告类型", ""))
        content = str(row.get("预告内容", row.get("业绩预告摘要", "")))
        forecast_date = str(row.get("预告日期", ""))[:10]

        lines.append(
            f"  {idx} | {code} | {name} | {report_period} | {forecast_type_name} | "
            f"{content[:80]} | {forecast_date}"
        )

    return "\n".join(lines)


def get_earnings_express(curr_date: str = "") -> str:
    """业绩快报。

    Returns markdown table::

        # 业绩快报 | 2026-09-30
        序号 | 证券代码 | 证券简称 | 报告期 | 每股收益 | 净资产收益率 |
        营业收入(万) | 净利润(万) | 总资产(万) | 披露日期
    """
    import pandas as pd

    lines = ["# 业绩快报"]

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    lines.append(f"\n数据日期: {ref_date.strftime('%Y-%m-%d')}")

    # 业绩快报
    df = _safe_akshare_call("stock_yjkb_em", date=ref_date.strftime("%Y%m%d"))
    if df is None or df.empty:
        lines.append(f"\n{ref_date.strftime('%Y-%m-%d')} 无业绩快报数据。")
        return "\n".join(lines)

    lines.append(f"\n共 {len(df)} 条记录")
    lines.append(
        "序号 | 证券代码 | 证券简称 | 报告期 | 每股收益 | 净资产收益率 | "
        "营业收入(万) | 净利润(万) | 总资产(万) | 披露日期"
    )

    for idx, (_, row) in enumerate(df.head(100).iterrows(), 1):
        code = str(row.get("证券代码", ""))
        name = str(row.get("证券简称", ""))
        report_period = str(row.get("报告期", ""))[:10]
        eps = row.get("每股收益", 0) or 0
        roe = row.get("净资产收益率", 0) or 0
        revenue = row.get("营业收入", row.get("营业总收入", 0)) or 0
        net_profit = row.get("净利润", 0) or 0
        total_asset = row.get("总资产", 0) or 0
        disclose_date = str(row.get("披露日期", ""))[:10]

        lines.append(
            f"  {idx} | {code} | {name} | {report_period} | {float(eps):.2f} | "
            f"{float(roe):.2f} | {float(revenue):.2f} | {float(net_profit):.2f} | "
            f"{float(total_asset):.2f} | {disclose_date}"
        )

    return "\n".join(lines)
