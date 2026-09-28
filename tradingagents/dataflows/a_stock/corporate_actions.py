"""公司行动报表（Phase 12.03）— 股权质押 / 股票回购。

数据源（东财 datacenter-web，2026-09-27 实测核实；reportName 均提取自
data.eastmoney.com 真实页面/JS，非猜测）：

* ``RPT_CSDC_STATISTICS``          市场质押统计（641 期，万股/万元）
* ``RPT_CSDC_INDUSTRY_STATISTICS`` 行业质押统计（128 行）
* ``RPT_CSDC_LIST_NEWEST``         个股质押最新（4216 只，支持 SECURITY_CODE 过滤）
* ``RPTA_WEB_GPHG``                股票回购（3094 条）

已核验单位（row0 交叉验算）：
* 回购 中创智领 HGSL=290,000 股 × HGZDJ 13.38 元 ≈ HGJE 3,891,257 元 →
  ``HGSL``=股、``HGJE``=元、``JLBZ``=币种（CNY）、``GGRQ``/``TDATE``=公告日、
  ``HGFS`` 为方式编码（映射未知，不展示）。
* 质押市场 TOTAL_PLEDGED_SHARES=28,122,603.04 万股（≈2812 亿股）、
  PLEDGE_MARKET_VALUE=260,789,141.98 万元（≈2.61 万亿元）→ 万股/万元。
* ``PM_RATIO``（273.27）与市场质押比例口径不符，``REPURCHASE_*`` 余额口径
  不确定 → 一律不展示（宁缺勿错）。

商誉 / 增发：目标页（data.eastmoney.com/syyw、/zengfa）为 591 字节 SPA 壳，
12 个猜测 reportName 均 9501，未获可核实端点 → 见工单 15，不在本模块。
"""

from __future__ import annotations

import time
from datetime import datetime

from curl_cffi import requests as cf_requests

from .utils import normalize_ticker

_DC_WEB = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def _dc_get(
    report_name: str,
    *,
    filter_str: str = "",
    sort_columns: str = "",
    page_size: int = 50,
    page_number: int = 1,
    timeout: int = 15,
    retries: int = 2,
) -> list[dict]:
    """东财 datacenter 查询（curl_cffi，两次退避重试，失败返回空列表）。"""
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "filter": filter_str,
        "sortColumns": sort_columns,
        "sortTypes": "-1" if sort_columns else "",
        "pageNumber": str(page_number),
        "pageSize": str(page_size),
        "source": "WEB",
        "client": "WEB",
    }
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            j = cf_requests.get(_DC_WEB, params=params, impersonate="chrome120", timeout=timeout).json()
            if j.get("code") == 0 and j.get("result"):
                return j["result"].get("data") or []
            return []
        except Exception as exc:  # noqa: BLE001 - 网络层异常统一降级为空
            last_exc = exc
            if attempt < retries:
                time.sleep(attempt)
    if last_exc is not None:
        print(f"[corporate_actions] {report_name} failed: {last_exc}")
    return []


def _fmt(value, fmt: str = "raw") -> str:
    if value is None or value == "":
        return "-"
    try:
        if fmt == "yi2":      # 万元/股 → 亿
            return f"{float(value) / 1e4:,.2f}"
        if fmt == "wan2":     # 股 → 万
            return f"{float(value) / 1e4:,.2f}"
        if fmt == "pct2":
            return f"{float(value):.2f}"
        if fmt == "yuan2":
            return f"{float(value):,.2f}"
        if fmt == "int":
            return f"{int(value):,}"
        return str(value)
    except (TypeError, ValueError):
        return str(value)


def _table(title: str, source: str, header: str, lines: list[str]) -> str:
    return "\n".join([
        title,
        f"# Source: 东财 {source}",
        f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        header,
        *lines,
    ])


def _latest_day(rows: list[dict], key: str = "TRADE_DATE") -> tuple[str, list[dict]]:
    """取排序结果第一页中最新交易日的整日数据。"""
    latest = max(str(r.get(key, ""))[:10] for r in rows)
    return latest, [r for r in rows if str(r.get(key, ""))[:10] == latest]


# ── 股权质押 ──────────────────────────────────────────────────────────────

def get_pledge_market() -> str:
    """市场质押统计（最新一期，RPT_CSDC_STATISTICS）。"""
    rows = _dc_get("RPT_CSDC_STATISTICS", sort_columns="TRADE_DATE", page_size=5)
    if not rows:
        return "# 市场质押统计 | 暂无数据\n\n⚠️ 东财 RPT_CSDC_STATISTICS 无数据（可稍后重试）。"
    r = rows[0]
    return _table(
        "# 市场质押统计",
        "datacenter RPT_CSDC_STATISTICS",
        "日期 | 质押公司数 | 质押股数(亿股) | 质押市值(亿元) | 沪深300指数 | 沪深300涨跌幅%",
        [" | ".join([
            str(r.get("TRADE_DATE", "-"))[:10],
            _fmt(r.get("PLEDGE_CO_NUM"), "int"),
            _fmt(r.get("TOTAL_PLEDGED_SHARES"), "yi2"),
            _fmt(r.get("PLEDGE_MARKET_VALUE"), "yi2"),
            _fmt(r.get("CSI_300_INDEX"), "yuan2"),
            _fmt(r.get("CSI_300_CHG"), "pct2"),
        ])],
    )


def get_pledge_industry(page_size: int = 50) -> str:
    """行业质押统计（最新一期，按平均质押比例降序，RPT_CSDC_INDUSTRY_STATISTICS）。"""
    rows = _dc_get(
        "RPT_CSDC_INDUSTRY_STATISTICS",
        sort_columns="TRADE_DATE",
        page_size=max(130, page_size),  # 行业全集 ~128 行
    )
    if not rows:
        return "# 行业质押统计 | 暂无数据\n\n⚠️ 东财 RPT_CSDC_INDUSTRY_STATISTICS 无数据。"

    _, day = _latest_day(rows)

    def ratio(r: dict) -> float:
        try:
            return float(r.get("AVERAGE_PLEDGE_RATIO") or 0)
        except (TypeError, ValueError):
            return 0.0

    day.sort(key=ratio, reverse=True)
    day = day[: max(1, page_size)]
    lines = [
        " | ".join([
            str(r.get("INDUSTRY", "-")),
            _fmt(r.get("AVERAGE_PLEDGE_RATIO"), "pct2"),
            _fmt(r.get("PLEDGE_TOTAL_MARKETCAP"), "yi2"),
            _fmt(r.get("TOTAL_PLEDGE_SHARES"), "yi2"),
        ])
        for r in day
    ]
    return _table(
        "# 行业质押统计",
        "datacenter RPT_CSDC_INDUSTRY_STATISTICS",
        "行业 | 平均质押比例% | 质押市值(亿元) | 质押股数(亿股)",
        lines,
    )


def get_pledge_stock(ticker: str | None = None, page_size: int = 50) -> str:
    """个股质押最新（RPT_CSDC_LIST_NEWEST）。

    ``ticker`` 为 6 位代码时取该股最新记录；否则取全市场按质押比例降序前 N。
    """
    filter_str = ""
    if ticker and len(normalize_ticker(ticker)) == 6:
        filter_str = f'(SECURITY_CODE="{normalize_ticker(ticker)}")'
        rows = _dc_get(
            "RPT_CSDC_LIST_NEWEST",
            filter_str=filter_str,
            sort_columns="TRADE_DATE",
            page_size=5,
        )
    else:
        rows = _dc_get(
            "RPT_CSDC_LIST_NEWEST",
            sort_columns="PLEDGE_RATIO",
            page_size=max(1, page_size),
        )
    if not rows:
        return "# 个股质押 | 暂无数据\n\n⚠️ 东财 RPT_CSDC_LIST_NEWEST 无数据。"

    lines = [
        " | ".join([
            str(r.get("TRADE_DATE", "-"))[:10],
            str(r.get("SECURITY_CODE", "-")),
            str(r.get("SECURITY_NAME_ABBR", "-")),
            str(r.get("INDUSTRY", "-") or "-"),
            _fmt(r.get("PLEDGE_RATIO"), "pct2"),
            _fmt(r.get("PLEDGE_DEAL_NUM"), "int"),
            _fmt(r.get("PLEDGE_MARKET_CAP"), "yi2"),
        ])
        for r in rows[: max(1, page_size)]
    ]
    return _table(
        "# 个股质押",
        "datacenter RPT_CSDC_LIST_NEWEST",
        "日期 | 代码 | 简称 | 行业 | 质押比例% | 质押笔数 | 质押市值(亿元)",
        lines,
    )


# ── 股票回购 ──────────────────────────────────────────────────────────────

def get_buyback(page_size: int = 50) -> str:
    """股票回购（最新公告一批，按回购金额降序，RPTA_WEB_GPHG）。"""
    rows = _dc_get("RPTA_WEB_GPHG", sort_columns="TDATE", page_size=500)
    if not rows:
        return "# 股票回购 | 暂无数据\n\n⚠️ 东财 RPTA_WEB_GPHG 无数据。"

    _, day = _latest_day(rows, key="TDATE")

    def amount(r: dict) -> float:
        try:
            return float(r.get("HGJE") or 0)
        except (TypeError, ValueError):
            return 0.0

    day.sort(key=amount, reverse=True)
    day = day[: max(1, page_size)]
    lines = [
        " | ".join([
            str(r.get("GGRQ", "-"))[:10],
            str(r.get("SCODE", "-")),
            str(r.get("SNAME", "-")),
            _fmt(r.get("HGJE"), "wan2"),
            _fmt(r.get("HGSL"), "wan2"),
            _fmt(r.get("HGZDJ"), "yuan2"),
            _fmt(r.get("HGZGJ"), "yuan2"),
            _fmt(r.get("SPJ"), "yuan2"),
            _fmt(r.get("ZDF"), "pct2"),
        ])
        for r in day
    ]
    return _table(
        "# 股票回购",
        "datacenter RPTA_WEB_GPHG",
        "公告日 | 代码 | 简称 | 回购金额(万元) | 回购数量(万股) | 回购最低价 | 回购最高价 | 市价 | 涨跌幅%",
        lines,
    )
