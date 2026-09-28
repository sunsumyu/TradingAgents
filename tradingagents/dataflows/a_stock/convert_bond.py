"""可转债列表（Phase 12.06）— 东财 RPT_BOND_CB_LIST。

数据源（东财 datacenter-web，2026-09-27 实测核实，1059 只转债全量）：
reportName 由 data.eastmoney.com/kzz/ 页面源提取（与 efinance 库使用的同名报表互证）。

已核验字段（新发行样例 莱特转债/隆新转债 + 退市样例 普利退债）：
* ``SECURITY_CODE``/``SECURITY_NAME_ABBR`` 转债代码/简称
* ``CONVERT_STOCK_CODE``/``SECURITY_SHORT_NAME`` 正股代码/简称
* ``BOND_EXPIRE`` 期限（年，字符串 "6"）
* ``RATING`` 评级（新发有值，退市债为 null）
* ``ACTUAL_ISSUE_SCALE`` 发行规模（亿元：5.25/9.6 与公告一致）
* ``INITIAL_TRANSFER_PRICE`` 初始转股价（元）
* ``CURRENT_BOND_PRICENEW`` 最新价（新发=面值 100，已上市为行情价）
* ``PUBLIC_START_DATE`` 申购日 / ``LISTING_DATE`` 上市日 / ``EXPIRE_DATE`` 到期日
* 市场：从 ``SECUCODE`` 后缀取 .SH/.SZ（118077.SH / 123288.SZ 已互证）

排序注意：``LISTING_DATE`` 降序会把 null（未上市）排在前面（实测普利退债置顶），
故默认按 ``PUBLIC_START_DATE``（申购日，恒有值）降序。
"""

from __future__ import annotations

import time
from datetime import datetime

from curl_cffi import requests as cf_requests

_DC_WEB = "https://datacenter-web.eastmoney.com/api/data/v1/get"

# 允许的排序列（白名单，防注入/防拼错）
_SORTABLE = {
    "public_start_date": "PUBLIC_START_DATE",
    "listing_date": "LISTING_DATE",
    "expire_date": "EXPIRE_DATE",
}


def _dc_get(report_name: str, *, sort_columns: str = "", page_size: int = 50,
            timeout: int = 15, retries: int = 2) -> list[dict]:
    params = {
        "reportName": report_name,
        "columns": "ALL",
        "sortColumns": sort_columns,
        "sortTypes": "-1" if sort_columns else "",
        "pageNumber": "1",
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
        print(f"[convert_bond] {report_name} failed: {last_exc}")
    return []


def _fmt(value, fmt: str = "raw") -> str:
    if value is None or value == "":
        return "-"
    try:
        if fmt == "num2":
            return f"{float(value):.2f}"
        if fmt == "date":
            return str(value)[:10]
        return str(value)
    except (TypeError, ValueError):
        return str(value)


def get_convert_bond_list(page_size: int = 50, sort_by: str = "public_start_date") -> str:
    """可转债列表（最新申购优先）。

    Args:
        page_size: 返回前 N 只
        sort_by: ``public_start_date``（默认）/ ``listing_date`` / ``expire_date``
            （后两者降序时未上市/未到期者按 API 排序行为，null 排前）
    """
    col = _SORTABLE.get(sort_by, "PUBLIC_START_DATE")
    rows = _dc_get("RPT_BOND_CB_LIST", sort_columns=col, page_size=max(1, page_size))
    if not rows:
        return "# 可转债列表 | 暂无数据\n\n⚠️ 东财 RPT_BOND_CB_LIST 无数据（可稍后重试）。"

    lines = []
    for r in rows:
        secucode = str(r.get("SECUCODE", "") or "")
        market = "沪" if secucode.endswith(".SH") else ("深" if secucode.endswith(".SZ") else "-")
        lines.append(" | ".join([
            str(r.get("SECURITY_CODE", "-")),
            str(r.get("SECURITY_NAME_ABBR", "-")),
            market,
            str(r.get("CONVERT_STOCK_CODE", "-") or "-"),
            str(r.get("SECURITY_SHORT_NAME", "-") or "-"),
            str(r.get("RATING", "-") or "-"),
            _fmt(r.get("ACTUAL_ISSUE_SCALE"), "num2"),
            _fmt(r.get("INITIAL_TRANSFER_PRICE"), "num2"),
            _fmt(r.get("CURRENT_BOND_PRICENEW"), "num2"),
            _fmt(r.get("PUBLIC_START_DATE"), "date"),
            _fmt(r.get("LISTING_DATE"), "date"),
            _fmt(r.get("EXPIRE_DATE"), "date"),
        ]))
    return "\n".join([
        "# 可转债列表",
        "# Source: 东财 datacenter RPT_BOND_CB_LIST",
        f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "转债代码 | 转债简称 | 市场 | 正股代码 | 正股简称 | 评级 | 规模(亿元) | 转股价 | 最新价 | 申购日 | 上市日 | 到期日",
        *lines,
    ])
