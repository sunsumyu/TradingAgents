"""新股数据中心 — 发行预告 + 上市预告。

Data source: akshare (同花顺新股数据 / 巨潮新股数据)

Functions:
    get_ipo_declaration()  — 新股发行预告（待申购 + 已申购未上市）
    get_ipo_listing()      — 新股上市预告（近期上市）
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

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


def get_ipo_declaration(curr_date: str = "") -> str:
    """新股发行预告 — 近期待申购 / 已申购未上市的新股。

    Returns markdown table matching 通达信 新股发行预告 format::

        # 新股发行预告
        序号 | 证券代码 | 证券简称 | 申购日期 | 申购代码 | 申购价(元) |
        发行量(万) | 网上发行量(万) | 申购上限(万) | 市盈率(摊薄) | 中签号公布日
    """
    import pandas as pd

    lines = ["# 新股发行预告"]

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    date_str = ref_date.strftime("%Y-%m-%d")
    lines.append(f"\n查询日期: {date_str}")

    df = _safe_akshare_call("stock_ipo_ths")
    if df is None or df.empty:
        lines.append("\n暂无新股发行预告数据。")
        return "\n".join(lines)

    # stock_ipo_ths columns:
    # 股票代码, 股票简称, 申购代码, 发行总数（万股）, 网上发行（万股）,
    # 申购上限（万股）, 顶格申购需配市值（万元）, 发行价格, 发行市盈率,
    # 行业市盈率, 申购日期, 中签率（%）, 中签号, 中签缴款日期, 上市日期, ...

    # 筛选近期（前后30天）的新股
    if "申购日期" in df.columns:
        # 申购日期格式可能是 "09-03 周四" 或 "2026-09-03"
        def _parse_subscribe_date(val: str) -> datetime | None:
            if pd.isna(val):
                return None
            s = str(val).strip()
            # Strip Chinese weekday suffix (周一~周日)
            import re
            s_clean = re.sub(r"\s*[周][一二三四五六日]", "", s).strip()
            for fmt in ("%Y-%m-%d", "%m-%d"):
                try:
                    parsed = datetime.strptime(s_clean, fmt)
                    if parsed.year == 1900:
                        parsed = parsed.replace(year=ref_date.year)
                    return parsed
                except ValueError:
                    continue
            return None

        df["_parsed_date"] = df["申购日期"].apply(_parse_subscribe_date)
        df_valid = df[df["_parsed_date"].notna()].copy()

        # 筛选前后30天
        window_start = ref_date - timedelta(days=7)
        window_end = ref_date + timedelta(days=30)
        df_window = df_valid[
            (df_valid["_parsed_date"] >= window_start)
            & (df_valid["_parsed_date"] <= window_end)
        ]
    else:
        df_window = df.head(20)

    if df_window.empty:
        lines.append("\n近30天无新股发行预告。")
        return "\n".join(lines)

    # 排序：按申购日期
    if "_parsed_date" in df_window.columns:
        df_window = df_window.sort_values("_parsed_date")

    lines.append(f"\n共 {len(df_window)} 只新股")
    lines.append(
        "序号 | 证券代码 | 证券简称 | 申购日期 | 申购代码 | 申购价(元) | "
        "发行量(万) | 网上发行量(万) | 申购上限(万) | 市盈率(摊薄) | 中签号公布日"
    )

    for idx, (_, row) in enumerate(df_window.iterrows(), 1):
        code = str(row.get("股票代码", ""))
        name = str(row.get("股票简称", ""))
        sub_code = str(row.get("申购代码", ""))
        sub_date = str(row.get("申购日期", ""))
        price = row.get("发行价格")
        volume = row.get("发行总数（万股）")
        online_vol = row.get("网上发行（万股）")
        sub_limit = row.get("申购上限（万股）")
        pe = row.get("发行市盈率")
        lottery_date = str(row.get("中签缴款日期", ""))

        price_str = f"{float(price):.2f}" if price and str(price) != "-" and not (isinstance(price, float) and pd.isna(price)) else "--"
        vol_str = f"{float(volume):.2f}" if volume and str(volume) != "-" and not (isinstance(volume, float) and pd.isna(volume)) else "--"
        online_str = f"{float(online_vol):.2f}" if online_vol and str(online_vol) != "-" and not (isinstance(online_vol, float) and pd.isna(online_vol)) else "--"
        limit_str = f"{float(sub_limit):.2f}" if sub_limit and str(sub_limit) != "-" and not (isinstance(sub_limit, float) and pd.isna(sub_limit)) else "--"
        pe_str = f"{float(pe):.2f}" if pe and str(pe) != "-" and not (isinstance(pe, float) and pd.isna(pe)) else "--"

        lines.append(
            f"  {idx} | {code} | {name} | {sub_date} | {sub_code} | {price_str} | "
            f"{vol_str} | {online_str} | {limit_str} | {pe_str} | {lottery_date}"
        )

    return "\n".join(lines)


def get_ipo_listing(curr_date: str = "") -> str:
    """新股上市预告 — 近期已上市 / 待上市的新股。

    Returns markdown table matching 通达信 新股上市预告 format::

        # 新股上市预告
        序号 | 证券代码 | 证券简称 | 上市日期 | 发行价(元) | 发行量(万) |
        网上发行量(万) | 市盈率(摊薄) | 申购日期 | 中签率%
    """
    import pandas as pd

    lines = ["# 新股上市预告"]

    if curr_date:
        ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    else:
        ref_date = datetime.now()

    date_str = ref_date.strftime("%Y-%m-%d")
    lines.append(f"\n查询日期: {date_str}")

    df = _safe_akshare_call("stock_new_ipo_cninfo")
    if df is None or df.empty:
        lines.append("\n暂无新股上市预告数据。")
        return "\n".join(lines)

    # stock_new_ipo_cninfo columns:
    # 证劵代码, 证券简称, 上市日期, 申购日期, 发行价, 总发行数量,
    # 发行市盈率, 上网发行中签率, 摇号结果公告日, 中签公告日,
    # 中签缴款日, 网上申购上限, 上网发行数量

    # 筛选近期（前后30天）上市的新股
    if "上市日期" in df.columns:
        df["_listing_date"] = pd.to_datetime(df["上市日期"], errors="coerce")
        df_valid = df[df["_listing_date"].notna()].copy()

        window_start = ref_date - timedelta(days=7)
        window_end = ref_date + timedelta(days=30)
        df_window = df_valid[
            (df_valid["_listing_date"] >= window_start)
            & (df_valid["_listing_date"] <= window_end)
        ]
    else:
        df_window = df.head(20)

    if df_window.empty:
        lines.append("\n近30天无新股上市预告。")
        return "\n".join(lines)

    # 排序：按上市日期
    if "_listing_date" in df_window.columns:
        df_window = df_window.sort_values("_listing_date")

    lines.append(f"\n共 {len(df_window)} 只新股")
    lines.append(
        "序号 | 证券代码 | 证券简称 | 上市日期 | 发行价(元) | 发行量(万) | "
        "网上发行量(万) | 市盈率(摊薄) | 申购日期 | 中签率%"
    )

    for idx, (_, row) in enumerate(df_window.iterrows(), 1):
        code = str(row.get("证劵代码", row.get("证券代码", "")))
        name = str(row.get("证券简称", ""))
        listing_date = str(row.get("上市日期", ""))[:10]
        price = row.get("发行价")
        volume = row.get("总发行数量")
        online_vol = row.get("上网发行数量")
        pe = row.get("发行市盈率")
        sub_date = str(row.get("申购日期", ""))[:10]
        win_rate = row.get("上网发行中签率")

        price_str = f"{float(price):.2f}" if price and not (isinstance(price, float) and pd.isna(price)) else "--"
        vol_str = f"{float(volume):.2f}" if volume and not (isinstance(volume, float) and pd.isna(volume)) else "--"
        online_str = f"{float(online_vol):.2f}" if online_vol and not (isinstance(online_vol, float) and pd.isna(online_vol)) else "--"
        pe_str = f"{float(pe):.2f}" if pe and not (isinstance(pe, float) and pd.isna(pe)) else "--"
        rate_str = f"{float(win_rate) * 100:.4f}" if win_rate and not (isinstance(win_rate, float) and pd.isna(win_rate)) else "--"

        lines.append(
            f"  {idx} | {code} | {name} | {listing_date} | {price_str} | {vol_str} | "
            f"{online_str} | {pe_str} | {sub_date} | {rate_str}"
        )

    return "\n".join(lines)
