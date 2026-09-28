"""机构持股数据中心 — 机构持仓明细 + 仓位类型。

Data source: akshare (东方财富机构持股数据)

Functions:
    get_institutional_hold() — 机构持股明细
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


def get_institutional_hold(
    report_date: str = "", inst_type: str = "all", position_type: str = "all"
) -> str:
    """机构持股明细。

    Args:
        report_date: 报告期末日 yyyy-mm-dd (如 2026-06-30)
        inst_type: "all" | "northbound" (北上资金) | "fund" (基金) |
                   "insurance" (保险) | "qfii" (QFII) | "social_security" (社保) |
                   "broker" (券商) | "private" (私募) | "trust" (信托) |
                   "finance" (财务公司) | "annuity" (年金) | "bank" (银行) |
                   "general_legal" (一般法人) | "special_legal" (特殊法人)
        position_type: "all" | "heavy" (重仓) | "increase" (增仓) |
                       "decrease" (减仓) | "new" (新进) | "unchanged" (不变)

    Returns markdown table::

        # 机构持股 | 2026-06-30
        序号 | 证券代码 | 证券简称 | 所属行业 | 持股机构数 | 持仓数量(万股) |
        持仓市值(万元) | 占总股本比例(%) | 占已流通A股比例(%) | 较上期增减(万股) |
        仓位类型
    """
    import pandas as pd

    lines = ["# 机构持股"]

    if report_date:
        ref_date = datetime.strptime(report_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    lines.append(f"\n数据日期: {ref_date.strftime('%Y-%m-%d')}")

    # 机构持股明细
    df = _safe_akshare_call(
        "stock_jgdy_detail_em", date=ref_date.strftime("%Y%m%d")
    )
    if df is None or df.empty:
        lines.append(f"\n{ref_date.strftime('%Y-%m-%d')} 无机构持股数据。")
        return "\n".join(lines)

    lines.append(f"\n共 {len(df)} 条记录")
    lines.append(
        "序号 | 证券代码 | 证券简称 | 所属行业 | 持股机构数 | 持仓数量(万股) | "
        "持仓市值(万元) | 占总股本比例(%) | 占已流通A股比例(%) | "
        "较上期增减(万股) | 仓位类型"
    )

    for idx, (_, row) in enumerate(df.head(100).iterrows(), 1):
        code = str(row.get("证券代码", ""))
        name = str(row.get("证券简称", ""))
        industry = str(row.get("所属行业", ""))
        inst_count = row.get("持股机构数", 0) or 0
        shares = row.get("持仓数量", row.get("持股数量", 0)) or 0
        market_value = row.get("持仓市值", 0) or 0
        total_ratio = row.get("占总股本比例", 0) or 0
        float_ratio = row.get("占已流通A股比例", 0) or 0
        change = row.get("较上期增减", 0) or 0
        position_type_name = str(row.get("仓位类型", ""))

        lines.append(
            f"  {idx} | {code} | {name} | {industry} | {int(inst_count)} | "
            f"{float(shares):.2f} | {float(market_value):.2f} | "
            f"{float(total_ratio):.2f} | {float(float_ratio):.2f} | "
            f"{float(change):.2f} | {position_type_name}"
        )

    return "\n".join(lines)
