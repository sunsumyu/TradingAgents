"""大宗交易数据中心 — 个股明细 + 行业分布 + 大盘统计。

Data source: akshare (东方财富大宗交易数据)

Functions:
    get_block_trade_detail()       — 个股大宗交易明细
    get_block_trade_industry()     — 大宗交易行业分布
    get_block_trade_market_stat()  — 大盘大宗交易统计
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


def get_block_trade_detail(curr_date: str = "", market: str = "all") -> str:
    """个股大宗交易明细。

    Returns markdown table::

        # 个股大宗交易 | 2026-09-03
        序号 | 证券代码 | 证券简称 | 成交价 | 收盘价 | 溢折价率(%) | 成交额(万) | 成交量(万) | 买方营业部 | 卖方营业部
    """
    import pandas as pd

    lines = ["# 个股大宗交易"]

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    date_str = ref_date.strftime("%Y%m%d")
    lines.append(f"\n日期: {ref_date.strftime('%Y-%m-%d')}")

    df = _safe_akshare_call("stock_dzjy_mrmx", start_date=date_str, end_date=date_str)
    if df is None or df.empty:
        lines.append(f"\n{ref_date.strftime('%Y-%m-%d')} 无大宗交易数据。")
        return "\n".join(lines)

    lines.append(f"\n共 {len(df)} 条记录")
    lines.append(
        "序号 | 证券代码 | 证券简称 | 成交价 | 收盘价 | 溢折价率(%) | "
        "成交额(万) | 成交量(万) | 买方营业部 | 卖方营业部"
    )

    for idx, (_, row) in enumerate(df.head(50).iterrows(), 1):
        code = str(row.get("证券代码", row.get("代码", "")))
        name = str(row.get("证券简称", row.get("名称", "")))
        price = row.get("成交价", 0) or 0
        close = row.get("收盘价", 0) or 0
        premium = row.get("溢折价率", 0) or 0
        amount = row.get("成交额", 0) or 0
        volume = row.get("成交量", 0) or 0
        buyer = str(row.get("买方营业部", row.get("买入营业部", "")))
        seller = str(row.get("卖方营业部", row.get("卖出营业部", "")))

        lines.append(
            f"  {idx} | {code} | {name} | {float(price):.2f} | {float(close):.2f} | "
            f"{float(premium):.2f} | {float(amount):.2f} | {float(volume):.2f} | "
            f"{buyer} | {seller}"
        )

    return "\n".join(lines)


def get_block_trade_industry(month: str = "") -> str:
    """大宗交易行业分布（溢价/折价率 + 成交金额 + 成交次数）。

    Returns markdown table::

        # 大宗交易行业分布 | 2026-09
        行业 | 溢折价率(%) | 成交金额(万) | 成交次数
    """
    lines = ["# 大宗交易行业分布"]

    if month:
        month_str = month
    else:
        month_str = datetime.now().strftime("%Y-%m")

    lines.append(f"\n统计月度: {month_str}")

    # 近三月/近六月/近一年
    period_map = {"近三月": "近三月", "近六月": "近六月", "近一年": "近一年"}
    symbol = period_map.get(month_str, "近三月")
    df = _safe_akshare_call("stock_dzjy_hygtj", symbol=symbol)
    if df is None or df.empty:
        lines.append(f"\n{month_str} 无大宗交易行业数据。")
        return "\n".join(lines)

    lines.append(f"\n共 {len(df)} 个行业")
    lines.append("行业 | 溢折价率(%) | 成交金额(万) | 成交次数")

    for _, row in df.iterrows():
        industry = str(row.get("行业", row.get("名称", "")))
        premium = row.get("溢折价率", row.get("溢价率", 0)) or 0
        amount = row.get("成交金额", row.get("总金额", 0)) or 0
        count = row.get("成交次数", row.get("总次数", 0)) or 0

        lines.append(
            f"  {industry} | {float(premium):.2f} | {float(amount):.2f} | {int(count)}"
        )

    return "\n".join(lines)


def get_block_trade_market_stat(month: str = "") -> str:
    """大盘大宗交易统计（月度趋势）。

    Returns markdown table::

        # 大盘大宗交易统计 | 2026-09
        日期 | 溢折价率(%) | 成交金额(万) | 成交次数
    """
    lines = ["# 大盘大宗交易统计"]

    if month:
        month_str = month
    else:
        month_str = datetime.now().strftime("%Y-%m")

    lines.append(f"\n统计月度: {month_str}")

    df = _safe_akshare_call("stock_dzjy_sctj")
    if df is None or df.empty:
        lines.append(f"\n{month_str} 无大宗交易统计数据。")
        return "\n".join(lines)

    lines.append(f"\n共 {len(df)} 个交易日")
    lines.append("日期 | 溢折价率(%) | 成交金额(万) | 成交次数")

    for _, row in df.iterrows():
        date = str(row.get("日期", row.get("交易日期", "")))
        premium = row.get("溢折价率", row.get("溢价率", 0)) or 0
        amount = row.get("成交金额", row.get("总金额", 0)) or 0
        count = row.get("成交次数", row.get("总次数", 0)) or 0

        lines.append(
            f"  {date} | {float(premium):.2f} | {float(amount):.2f} | {int(count)}"
        )

    return "\n".join(lines)
