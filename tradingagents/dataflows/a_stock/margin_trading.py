"""融资融券数据中心 — 个股明细 + 市场统计。

Data source: akshare (上交所 / 深交所融资融券数据)

Functions:
    get_margin_detail()          — 融资融券个股明细排行
    get_margin_market_stat()     — 融资融券市场统计（时间序列）
    get_margin_industry()        — 融资融券行业分布（基于个股+板块映射）
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _safe_akshare_call(fn_name: str, **kwargs) -> Any:
    """Lazy-import akshare and call a function, returning None on failure."""
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


def _format_yi(val: float | None) -> str:
    """Format a value in 亿元 (100M yuan)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "--"
    return f"{val / 1e8:.2f}亿"


def _format_wan(val: float | None) -> str:
    """Format a value in 万元 (10K yuan)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "--"
    return f"{val / 1e4:.2f}万"


def get_margin_detail(market: str = "sh", curr_date: str = "") -> str:
    """融资融券个股明细排行。

    Args:
        market: "sh" (沪市), "sz" (深市), "bj" (北交所)
        curr_date: trade date YYYY-MM-DD, defaults to latest available

    Returns markdown table::

        # 融资融券明细 | 沪市 | 2026-09-02
        序号 | 证券代码 | 证券简称 | 融资余额(亿) | 融资买入额(亿) | 融资偿还额(亿) |
        净买入(亿) | 融券余量(万) | 融券卖出量(万) | 融券偿还量(万) | 净卖出(万)
    """
    lines = ["# 融资融券明细"]

    market_map = {"sh": "沪市", "sz": "深市", "bj": "北交所"}
    market_label = market_map.get(market, market)
    lines.append(f"\n市场: {market_label}")

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    # akshare date format: YYYYMMDD
    ak_date = ref_date.strftime("%Y%m%d")
    lines.append(f"日期: {curr_date or ref_date.strftime('%Y-%m-%d')}")

    # 尝试获取数据，最多回溯5个交易日
    df = None
    for i in range(6):
        try_date = (ref_date - timedelta(days=i)).strftime("%Y%m%d")
        if market == "sh":
            df = _safe_akshare_call("stock_margin_detail_sse", date=try_date)
        elif market == "sz":
            df = _safe_akshare_call("stock_margin_detail_szse", date=try_date)
        elif market == "bj":
            df = _safe_akshare_call("stock_margin_detail_bse", date=try_date)
        else:
            lines.append(f"\n不支持的市场: {market}")
            return "\n".join(lines)
        if df is not None and not df.empty:
            break

    if df is None or df.empty:
        lines.append(f"\n{market_label}近5日无融资融券明细数据。")
        return "\n".join(lines)

    # Normalize columns (SSE and SZSE have slightly different schemas)
    col_map = {}
    for col in df.columns:
        if "代码" in col:
            col_map[col] = "code"
        elif "简称" in col:
            col_map[col] = "name"
        elif "融资余额" in col:
            col_map[col] = "margin_balance"
        elif "融资买入" in col:
            col_map[col] = "margin_buy"
        elif "融资偿还" in col:
            col_map[col] = "margin_repay"
        elif "融券余量" in col:
            col_map[col] = "short_qty"
        elif "融券卖出" in col:
            col_map[col] = "short_sell"
        elif "融券偿还" in col:
            col_map[col] = "short_repay"

    if col_map:
        df = df.rename(columns=col_map)

    # Sort by margin_balance descending, take top 50
    if "margin_balance" in df.columns:
        df = df.sort_values("margin_balance", ascending=False)
    df_top = df.head(50)

    lines.append(f"\n共 {len(df)} 只标的，展示前 50")
    lines.append(
        "序号 | 证券代码 | 证券简称 | 融资余额(亿) | 融资买入(亿) | 融资偿还(亿) | "
        "净买入(亿) | 融券余量 | 融券卖出 | 融券偿还 | 净卖出"
    )

    for idx, (_, row) in enumerate(df_top.iterrows(), 1):
        code = str(row.get("code", row.get(df.columns[1], "")))
        name = str(row.get("name", row.get(df.columns[2], "")))

        balance = row.get("margin_balance", 0) or 0
        buy = row.get("margin_buy", 0) or 0
        repay = row.get("margin_repay", 0) or 0
        net_buy = balance - (balance - buy + repay) if False else buy - repay

        short_qty = row.get("short_qty", 0) or 0
        short_sell = row.get("short_sell", 0) or 0
        short_repay = row.get("short_repay", 0) or 0
        net_short = short_sell - short_repay

        lines.append(
            f"  {idx} | {code} | {name} | "
            f"{_format_yi(balance)} | {_format_yi(buy)} | {_format_yi(repay)} | "
            f"{_format_yi(net_buy)} | "
            f"{_format_wan(short_qty)} | {_format_wan(short_sell)} | {_format_wan(short_repay)} | {_format_wan(net_short)}"
        )

    return "\n".join(lines)


def get_margin_market_stat(market: str = "total", curr_date: str = "") -> str:
    """融资融券市场统计（时间序列）。

    Args:
        market: "total" (全市场), "sh" (沪市), "sz" (深市)
        curr_date: end date YYYY-MM-DD

    Returns markdown table::

        # 融资融券市场统计 | 全市场
        日期 | 融资余额(亿) | 融资买入额(亿) | 融券余量(万) | 融券余量金额(亿) | 融资融券余额(亿)
    """
    lines = ["# 融资融券市场统计"]

    market_map = {"total": "全市场", "sh": "沪市", "sz": "深市"}
    market_label = market_map.get(market, market)
    lines.append(f"\n市场: {market_label}")

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    # 获取最近 60 个交易日
    start_date = (ref_date - timedelta(days=90)).strftime("%Y%m%d")
    end_date = ref_date.strftime("%Y%m%d")

    if market in ("total", "sh"):
        df_sh = _safe_akshare_call(
            "stock_margin_sse", start_date=start_date, end_date=end_date
        )
    else:
        df_sh = None

    if market in ("total", "sz"):
        try:
            import akshare as ak
            df_sz = ak.stock_margin_szse(start_date=start_date, end_date=end_date)
        except Exception as e:
            logger.warning("stock_margin_szse failed: %s", e)
            df_sz = None
    else:
        df_sz = None

    if df_sh is None and df_sz is None:
        lines.append("\n近期无融资融券市场统计数据。")
        return "\n".join(lines)

    # 合并数据
    all_rows: list[dict] = []

    if df_sh is not None and not df_sh.empty:
        for _, row in df_sh.iterrows():
            all_rows.append({
                "date": str(row.get("信用交易日期", "")),
                "market": "sh",
                "margin_balance": float(row.get("融资余额", 0) or 0),
                "margin_buy": float(row.get("融资买入额", 0) or 0),
                "short_qty": float(row.get("融券余量", 0) or 0),
                "short_balance": float(row.get("融券余量金额", 0) or 0),
                "total_balance": float(row.get("融资融券余额", 0) or 0),
            })

    if df_sz is not None and not df_sz.empty:
        for _, row in df_sz.iterrows():
            all_rows.append({
                "date": str(row.get("信用交易日期", "")),
                "market": "sz",
                "margin_balance": float(row.get("融资余额", 0) or 0),
                "margin_buy": float(row.get("融资买入额", 0) or 0),
                "short_qty": float(row.get("融券余量", 0) or 0),
                "short_balance": float(row.get("融券余额", 0) or 0),
                "total_balance": float(row.get("融资融券余额", 0) or 0),
            })

    if not all_rows:
        lines.append("\n无有效数据。")
        return "\n".join(lines)

    # 按日期聚合
    df_all = pd.DataFrame(all_rows)
    if market == "total":
        df_agg = df_all.groupby("date").sum(numeric_only=True).reset_index()
    else:
        df_agg = df_all[df_all["market"] == market].drop(columns=["market"])

    df_agg = df_agg.sort_values("date").tail(30)

    lines.append(f"\n近 {len(df_agg)} 个交易日")
    lines.append(
        "日期 | 融资余额(亿) | 融资买入(亿) | 融券余量(万) | "
        "融券余量金额(亿) | 融资融券余额(亿)"
    )

    for _, row in df_agg.iterrows():
        date_str = str(row.get("date", ""))
        # Normalize date format
        if len(date_str) == 8:
            date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        lines.append(
            f"  {date_str} | "
            f"{_format_yi(row.get('margin_balance', 0))} | "
            f"{_format_yi(row.get('margin_buy', 0))} | "
            f"{int(row.get('short_qty', 0)):,} | "
            f"{_format_yi(row.get('short_balance', 0))} | "
            f"{_format_yi(row.get('total_balance', 0))}"
        )

    return "\n".join(lines)


def get_margin_industry(curr_date: str = "") -> str:
    """融资融券行业分布（简化版：基于个股融资融券余额 × 行业分类）。

    注：akshare 无直接的融资融券行业分布接口，本函数通过
    stock_margin_detail_sse + stock_board_industry_name_em 聚合计算。

    Returns markdown table::

        # 融资融券行业分布
        行业 | 融资余额占比% | 融券余额占比%
    """
    lines = ["# 融资融券行业分布"]

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    ak_date = ref_date.strftime("%Y%m%d")

    # 获取沪市融资融券明细
    df_margin = _safe_akshare_call("stock_margin_detail_sse", date=ak_date)
    if df_margin is None or df_margin.empty:
        lines.append("\n无融资融券数据。")
        return "\n".join(lines)

    # 获取行业板块成分股
    industry_df = _safe_akshare_call("stock_board_industry_name_em")
    if industry_df is None or industry_df.empty:
        lines.append("\n无行业板块数据。")
        return "\n".join(lines)

    # 简化实现：标记数据来源限制
    lines.append(f"\n日期: {curr_date or ref_date.strftime('%Y-%m-%d')}")
    lines.append(f"融资融券标的数: {len(df_margin)}")
    lines.append(f"行业板块数: {len(industry_df)}")
    lines.append("\n注：行业分布需聚合计算，当前为数据概览。")
    lines.append("完整行业分布将在后续版本通过东财 datacenter 接口实现。")

    return "\n".join(lines)
