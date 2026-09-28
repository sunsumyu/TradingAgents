"""投资日历 — 聚合当日所有市场事件。

Data sources:
- 新股上市/发行: ipo_center (akshare)
- 停复牌: eastmoney datacenter
- 特别处理: eastmoney datacenter
- 解禁: eastmoney datacenter (get_lockup_expiry)

Function:
    get_investment_calendar(curr_date) — 聚合日历
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


def _eastmoney_datacenter(
    report_name: str,
    columns: str = "ALL",
    filter_str: str = "",
    page_size: int = 50,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> list[dict]:
    """东财数据中心统一查询（从 eastmoney 模块复用）。"""
    from tradingagents.dataflows.a_stock.eastmoney import _eastmoney_datacenter as _em_dc
    return _em_dc(
        report_name=report_name,
        columns=columns,
        filter_str=filter_str,
        page_size=page_size,
        sort_columns=sort_columns,
        sort_types=sort_types,
    )


def get_investment_calendar(curr_date: str = "") -> str:
    """投资日历 — 聚合当日所有市场事件。

    子事件：
    - 首发新股上市
    - 首发新股发行
    - 沪深停复牌
    - 特别处理（ST/摘帽）
    - 限售解禁

    Returns markdown grouped by event type.
    """
    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    date_str = ref_date.strftime("%Y-%m-%d")
    lines = [f"# 投资日历 | {date_str}"]

    # ── 1. 首发新股上市 ─
    ipo_listing_lines = []
    try:
        df = _safe_akshare_call("stock_new_ipo_cninfo")
        if df is not None and not df.empty and "上市日期" in df.columns:
            df["_ld"] = pd.to_datetime(df["上市日期"], errors="coerce")
            df_day = df[df["_ld"].dt.date == ref_date.date()]
            if not df_day.empty:
                ipo_listing_lines.append(f"\n首发新股上市（共 {len(df_day)} 条记录）")
                ipo_listing_lines.append("证券代码 | 证券简称 | 说明")
                for _, row in df_day.iterrows():
                    code = str(row.get("证劵代码", row.get("证券代码", "")))
                    name = str(row.get("证券简称", ""))
                    price = row.get("发行价")
                    price_str = f"发行价格{float(price):.2f}元/股" if price and not (isinstance(price, float) and pd.isna(price)) else ""
                    volume = row.get("总发行数量")
                    vol_str = f"{float(volume):.0f}万股" if volume and not (isinstance(volume, float) and pd.isna(volume)) else ""
                    pe = row.get("发行市盈率")
                    pe_str = f"，发行市盈率{float(pe):.1f}" if pe and not (isinstance(pe, float) and pd.isna(pe)) else ""
                    desc = f"首发新股上市日{f'，{price_str}' if price_str else ''}{f'，{vol_str}' if vol_str else ''}{pe_str}..."
                    ipo_listing_lines.append(f"  {code} | {name} | {desc}")
    except Exception as e:
        logger.warning("IPO listing calendar failed: %s", e)

    # ── 2. 首发新股发行 ──
    ipo_decl_lines = []
    try:
        df = _safe_akshare_call("stock_ipo_ths")
        if df is not None and not df.empty and "申购日期" in df.columns:
            import re
            def _parse_date(val: str) -> datetime | None:
                if pd.isna(val):
                    return None
                s = re.sub(r"\s*[周][一二三四五六日]", "", str(val).strip())
                for fmt in ("%Y-%m-%d", "%m-%d"):
                    try:
                        d = datetime.strptime(s, fmt)
                        if d.year == 1900:
                            d = d.replace(year=ref_date.year)
                        return d
                    except ValueError:
                        continue
                return None

            df["_sd"] = df["申购日期"].apply(_parse_date)
            df_day = df[df["_sd"].dt.date == ref_date.date()]
            if not df_day.empty:
                ipo_decl_lines.append(f"\n首发新股发行（共 {len(df_day)} 条记录）")
                ipo_decl_lines.append("证券代码 | 证券简称 | 说明")
                for _, row in df_day.iterrows():
                    code = str(row.get("股票代码", ""))
                    name = str(row.get("股票简称", ""))
                    sub_code = str(row.get("申购代码", ""))
                    price = row.get("发行价格")
                    volume = row.get("发行总数（万股）")
                    price_str = f"发行价格{float(price):.2f}元/股" if price and str(price) != "-" and not (isinstance(price, float) and pd.isna(price)) else ""
                    vol_str = f"{float(volume):.2f}万股" if volume and str(volume) != "-" and not (isinstance(volume, float) and pd.isna(volume)) else ""
                    desc = f"申购代码{sub_code}，{price_str}，发行数量{vol_str}..."
                    ipo_decl_lines.append(f"  {code} | {name} | {desc}")

            # 也检查中签率公告日
            if "中签率公告日" in df.columns or "中签号" in df.columns:
                # Use 中签缴款日期 as proxy
                if "中签缴款日期" in df.columns:
                    df["_ld2"] = df["中签缴款日期"].apply(lambda x: _parse_date(str(x)) if x and str(x) != "-" else None)
                    df_lottery = df[df["_ld2"].notna() & (df["_ld2"].dt.date == ref_date.date())]
                    if not df_lottery.empty:
                        for _, row in df_lottery.iterrows():
                            if row["股票代码"] not in df_day["股票代码"].values:
                                code = str(row.get("股票代码", ""))
                                name = str(row.get("股票简称", ""))
                                ipo_decl_lines.append(f"  {code} | {name} | 中签率公告日")
    except Exception as e:
        logger.warning("IPO declaration calendar failed: %s", e)

    # ── 3. 沪深停复牌 ──
    susp_lines = []
    try:
        susp_data = _eastmoney_datacenter(
            "RPT_LICO_FN_CPD",
            filter_str=f"(TRADE_DATE='{date_str}')",
            page_size=50,
        )
        if susp_data:
            susp_lines.append(f"\n沪深停复牌（共 {len(susp_data)} 条记录）")
            susp_lines.append("证券代码 | 证券简称 | 停牌时间 | 复牌时间 | 说明 | 原因")
            for row in susp_data:
                code = str(row.get("SECURITY_CODE", ""))
                name = str(row.get("SECURITY_NAME_ABBR", ""))
                susp_time = str(row.get("SUSPEND_DATE", ""))[:10]
                res_time = str(row.get("RESUME_DATE", ""))[:10]
                reason = str(row.get("REASON", row.get("EXPLANATION", "")))
                susp_lines.append(f"  {code} | {name} | {susp_time} | {res_time} | 停牌 | {reason}")
    except Exception as e:
        logger.warning("Suspension calendar failed: %s", e)

    if not susp_lines:
        # 尝试备用报表
        try:
            susp_data2 = _eastmoney_datacenter(
                "RPT_STOCKMARKET_STA_STOCKNEW",
                filter_str=f"(TRADE_DATE='{date_str}')",
                page_size=20,
            )
            if susp_data2:
                susp_lines.append(f"\n沪深停复牌（共 {len(susp_data2)} 条记录）")
                susp_lines.append("证券代码 | 证券简称 | 停牌时间 | 复牌时间 | 说明 | 原因")
                for row in susp_data2:
                    code = str(row.get("SECURITY_CODE", row.get("CODE", "")))
                    name = str(row.get("SECURITY_NAME_ABBR", row.get("NAME", "")))
                    susp_lines.append(f"  {code} | {name} | {date_str} | {date_str} | 停牌/复牌 |")
        except Exception as e:
            logger.warning("Suspension calendar (backup) failed: %s", e)

    # ── 4. 特别处理 ──
    st_lines = []
    try:
        st_data = _eastmoney_datacenter(
            "RPT_STOCKMARKET_STA_SPECIAL",
            filter_str=f"(TRADE_DATE='{date_str}')",
            page_size=20,
        )
        if st_data:
            st_lines.append(f"\n特别处理（共 {len(st_data)} 条记录）")
            st_lines.append("证券代码 | 证券简称 | 说明")
            for row in st_data:
                code = str(row.get("SECURITY_CODE", ""))
                name = str(row.get("SECURITY_NAME_ABBR", ""))
                reason = str(row.get("REASON", row.get("EXPLANATION", "")))
                st_lines.append(f"  {code} | {name} | {reason}")
    except Exception as e:
        logger.warning("Special treatment calendar failed: %s", e)

    # ── 5. 限售解禁 ─
    lockup_lines = []
    try:
        lockup_data = _eastmoney_datacenter(
            "RPT_LOCKUP_DETAIL",
            filter_str=f"(LISTING_DATE='{date_str}')",
            page_size=100,
        )
        if lockup_data:
            lockup_lines.append(f"\n限售解禁（共 {len(lockup_data)} 条记录）")
            lockup_lines.append("证券代码 | 证券简称 | 解禁日期 | 解禁数量(万) | 占总股本% | 解禁原因")
            for row in lockup_data:
                code = str(row.get("SECURITY_CODE", ""))
                name = str(row.get("SECURITY_NAME_ABBR", ""))
                qty = row.get("LOCKUP_SHARES", 0) or 0
                ratio = row.get("RATIO", 0) or 0
                reason = str(row.get("REASON", row.get("LOCKUP_TYPE", "")))
                lockup_lines.append(
                    f"  {code} | {name} | {date_str} | {float(qty) / 10000:.2f} | {float(ratio) * 100:.2f} | {reason}"
                )
    except Exception as e:
        logger.warning("Lockup calendar failed: %s", e)

    # ── 汇总 ──
    sections = []
    if ipo_listing_lines:
        sections.append("\n".join(ipo_listing_lines))
    if ipo_decl_lines:
        sections.append("\n".join(ipo_decl_lines))
    if susp_lines:
        sections.append("\n".join(susp_lines))
    if st_lines:
        sections.append("\n".join(st_lines))
    if lockup_lines:
        sections.append("\n".join(lockup_lines))

    if not sections:
        lines.append(f"\n{date_str} 无特别市场事件。")
    else:
        lines.append("\n".join(sections))

    return "\n".join(lines)
