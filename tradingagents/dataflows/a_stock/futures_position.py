"""股指期货持仓数据模块 — 中金所会员持仓排名龙虎榜。

Data source: 中金所官网 ccpm (via akshare get_cffex_rank_table)

通达信「股指期货」菜单对应功能：成交持仓 / 多单持仓 / 空单持仓 龙虎榜。
数据验证：IF2609 2026-09-04 中信期货 vol=29843(+6043) 与通达信终端一致。

Functions:
    get_futures_position()  — 股指期货持仓龙虎榜 (成交量/多头/空头 三榜)
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd

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


def _fmt_chg(val: Any) -> str:
    """格式化增减数字，保留符号。"""
    try:
        v = int(float(val))
        return f"+{v}" if v > 0 else str(v)
    except (ValueError, TypeError):
        return "--"


def _clean_member(name: Any) -> str:
    """清理会员简称：去掉 (代客) 后缀，None → 本日合计。"""
    if name is None or str(name).strip().lower() in ("none", "nan", ""):
        return "本日合计"
    return str(name).replace("(代客)", "").strip()


def _split_total(df):
    """把合计行 (party name 为空) 从排名表中分离。"""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df, None
    name_col = "vol_party_name"
    if name_col not in df.columns:
        return df, None
    is_total = df[name_col].isna() | (df[name_col].astype(str).str.strip().isin(["", "None", "nan"]))
    if not is_total.any():
        return df, None
    return df[~is_total], df[is_total].iloc[0]


def _find_recent_trade_date(curr_date: str) -> str:
    """若当日无数据（非交易日/数据未更新），回退到最近 5 天内最近一个有数据的日期。"""
    from datetime import timedelta

    ref = datetime.strptime(curr_date, "%Y-%m-%d")
    for offset in range(0, 6):
        probe = (ref - timedelta(days=offset)).strftime("%Y%m%d")
        result = _safe_akshare_call("get_cffex_rank_table", date=probe, vars_list=["IF"])
        if isinstance(result, dict) and result:
            return probe
    return ref.strftime("%Y%m%d")


def get_futures_position(
    contract: str = "IF",
    curr_date: str | None = None,
    page_size: int = 20,
    page_number: int = 1,
) -> str:
    """获取股指期货持仓龙虎榜数据（成交量/多头/空头）。

    Args:
        contract: 品种代码 (IF/IC/IH/IM)，自动选取该品种主力+次主力合约
        curr_date: 数据日期 (YYYY-MM-DD)，默认今天；非交易日自动回退
        page_size: 每榜显示行数
        page_number: 页码（保留接口一致性，实际显示 top N）

    Returns:
        Markdown 字符串，每个合约三个榜单：成交量 / 多头持仓 / 空头持仓
    """
    if curr_date is None:
        curr_date = datetime.now().strftime("%Y-%m-%d")

    date_str = _find_recent_trade_date(curr_date)
    date_disp = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    lines: list[str] = [
        f"# 股指期货持仓龙虎榜 | 品种: {contract} | {date_disp}",
        "",
        "数据来源: 中金所前20会员持仓排名 (ccpm)",
    ]

    result = _safe_akshare_call("get_cffex_rank_table", date=date_str, vars_list=[contract])
    if not isinstance(result, dict) or not result:
        lines.append("")
        lines.append(f"{date_disp} 无 {contract} 持仓排名数据。")
        return "\n".join(lines)

    # 合约排序：按成交量合计降序（主力合约在前）
    def _contract_total(df) -> float:
        try:
            return float(pd.to_numeric(df["vol"], errors="coerce").sum())
        except Exception:
            return 0.0

    sorted_contracts = sorted(result.items(), key=lambda kv: _contract_total(kv[1]), reverse=True)

    for symbol, raw_df in sorted_contracts:
        if not isinstance(raw_df, pd.DataFrame) or raw_df.empty:
            continue
        df, total_row = _split_total(raw_df)

        lines.append("")
        lines.append(f"## 合约 {symbol}")
        lines.append("")

        # ── 成交量龙虎榜 ──
        lines.append("### 成交量龙虎榜")
        lines.append("")
        lines.append("名次 | 会员简称 | 成交量 | 增减")
        try:
            ranked = df.sort_values("vol", ascending=False).head(page_size)
            for i, (_, row) in enumerate(ranked.iterrows(), 1):
                lines.append(
                    f"  {i} | {_clean_member(row.get('vol_party_name'))} | "
                    f"{row.get('vol', '--')} | {_fmt_chg(row.get('vol_chg'))}"
                )
            if total_row is not None:
                lines.append(
                    f"  本日合计 | — | {total_row.get('vol', '--')} | {_fmt_chg(total_row.get('vol_chg'))}"
                )
        except Exception as exc:
            logger.warning("vol ranking failed for %s: %s", symbol, exc)
            lines.append("  数据解析失败。")

        # ── 多头持仓龙虎榜 ──
        lines.append("")
        lines.append("### 多头持仓龙虎榜")
        lines.append("")
        lines.append("名次 | 会员简称 | 多单持仓 | 增减")
        try:
            ranked = df.sort_values("long_open_interest", ascending=False).head(page_size)
            for i, (_, row) in enumerate(ranked.iterrows(), 1):
                lines.append(
                    f"  {i} | {_clean_member(row.get('long_party_name'))} | "
                    f"{row.get('long_open_interest', '--')} | {_fmt_chg(row.get('long_open_interest_chg'))}"
                )
            if total_row is not None:
                lines.append(
                    f"  本日合计 | — | {total_row.get('long_open_interest', '--')} | {_fmt_chg(total_row.get('long_open_interest_chg'))}"
                )
        except Exception as exc:
            logger.warning("long ranking failed for %s: %s", symbol, exc)
            lines.append("  数据解析失败。")

        # ── 空头持仓龙虎榜 ──
        lines.append("")
        lines.append("### 空头持仓龙虎榜")
        lines.append("")
        lines.append("名次 | 会员简称 | 空单持仓 | 增减")
        try:
            ranked = df.sort_values("short_open_interest", ascending=False).head(page_size)
            for i, (_, row) in enumerate(ranked.iterrows(), 1):
                lines.append(
                    f"  {i} | {_clean_member(row.get('short_party_name'))} | "
                    f"{row.get('short_open_interest', '--')} | {_fmt_chg(row.get('short_open_interest_chg'))}"
                )
            if total_row is not None:
                lines.append(
                    f"  本日合计 | — | {total_row.get('short_open_interest', '--')} | {_fmt_chg(total_row.get('short_open_interest_chg'))}"
                )
        except Exception as exc:
            logger.warning("short ranking failed for %s: %s", symbol, exc)
            lines.append("  数据解析失败。")

    return "\n".join(lines)
