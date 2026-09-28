"""持仓股东报表（Phase 12.02）— 股东户数 / 十大流通股东 / 股东增减持。

数据源（东财，2026-09-27 实测核实）：

* ``RPT_HOLDERNUM_DET``（datacenter-web）— 股东户数**历史各期**（2026-09-28 换源）。
  原 ``RPT_HOLDERNUMLATEST`` 每股仅最新一期，已弃用（函数保留不删）。
  支持个股过滤 ``(SECURITY_CODE="600519")``，按 ``END_DATE`` 降序取披露历史
  （600519 实测 30 期）；扩展字段（户均持股数 AVG_HOLD_NUM / 户均市值
  AVG_MARKET_CAP / 区间涨跌幅 INTERVAL_CHRATE）已核验但暂不展示。
  已核验：贵州茅台 296,404 户，较上期 +21.90%。
* ``RPT_F10_EH_FREEHOLDERS``（datacenter.eastmoney.com/securities，F10 通路）—
  十大流通股东，按 ``SECUCODE`` 过滤。已核验：茅台集团 68,128.29 万股、
  占流通股 54.50%（2026-06-30 期）。
* ``RPT_SHARE_HOLDER_INCREASE``（datacenter-web）— 股东增减持。
  已核验单位语义（茅台集团案例）：``CHANGE_NUM`` 为万股（带符号取
  ``CHANGE_NUM_SYMBOL``），``HOLD_RATIO`` 为百分比（54.4 ↔ 十大流通 54.49% 一致）。

请求走 curl_cffi（impersonate=chrome120，与本仓 eastmoney_client 同一反爬策略）；
输出为低频报表 markdown，经 PG 缓存（Phase 12 新规，不进 TDengine）。

字段口径备注（不确定者一律不展示，宁缺勿错）：
``CHANGE_RATE`` / ``AFTER_CHANGE_RATE`` 的符号与量纲在不同行间不一致，不采用。
"""

from __future__ import annotations

import time
from datetime import datetime

from curl_cffi import requests as cf_requests

from .utils import normalize_ticker

_DC_WEB = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_DC_SECURITIES = "https://datacenter.eastmoney.com/securities/api/data/v1/get"

# 股东户数披露历史每行一字段期，50 期足够个股页展示
_HISTORY_ROWS = 50


def _secucode(ticker: str) -> str:
    """600519 → 600519.SH；000001 → 000001.SZ；8/4/9 开头 → BJ。"""
    code = normalize_ticker(ticker)
    suffix = "BJ" if code.startswith(("4", "8", "9")) else (
        "SH" if code.startswith("6") else "SZ"
    )
    return f"{code}.{suffix}"


def _dc_get(
    report_name: str,
    *,
    host: str = "web",
    filter_str: str = "",
    sort_columns: str = "",
    page_size: int = 50,
    page_number: int = 1,
    timeout: int = 15,
    retries: int = 2,
) -> list[dict]:
    """东财 datacenter 查询（curl_cffi，两次退避重试，失败返回空列表）。"""
    url = _DC_SECURITIES if host == "securities" else _DC_WEB
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
            j = cf_requests.get(url, params=params, impersonate="chrome120", timeout=timeout).json()
            if j.get("code") == 0 and j.get("result"):
                return j["result"].get("data") or []
            return []
        except Exception as exc:  # noqa: BLE001 - 网络层异常统一降级为空
            last_exc = exc
            if attempt < retries:
                time.sleep(attempt)
    if last_exc is not None:
        print(f"[holder_structure] {report_name} failed: {last_exc}")
    return []


def _fmt(value, fmt: str = "raw") -> str:
    if value is None or value == "":
        return "-"
    try:
        if fmt == "pct2":
            return f"{float(value):.2f}"
        if fmt == "wan2":
            return f"{float(value) / 1e4:,.2f}"
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


def get_holder_num(ticker: str, page_size: int = _HISTORY_ROWS) -> str:
    """个股股东户数历史披露（RPT_HOLDERNUM_DET，按报告期降序）。

    2026-09-28 实测换源：原 ``RPT_HOLDERNUMLATEST`` 每股仅含最新一期；
    ``RPT_HOLDERNUM_DET`` 为历史各期明细（600519 实测 30 期，含户均持股数/
    户均市值/区间涨跌幅等扩展字段），markdown 输出保持原 5 列结构不变
    （报告期|股东户数|较上期增减|环比增幅%|公告日期），parser/面板零改动。
    """
    rows = _dc_get(
        "RPT_HOLDERNUM_DET",
        filter_str=f'(SECURITY_CODE="{normalize_ticker(ticker)}")',
        sort_columns="END_DATE",
        page_size=max(1, page_size),
    )
    if not rows:
        return f"# 股东户数 | {normalize_ticker(ticker)}\n\n⚠️ 暂无股东户数数据（可能为非披露期或接口繁忙，可稍后重试）。"

    lines = []
    for r in rows:
        lines.append(" | ".join([
            str(r.get("END_DATE", "-"))[:10],
            _fmt(r.get("HOLDER_NUM"), "int"),
            _fmt(r.get("HOLDER_NUM_CHANGE"), "int"),
            _fmt(r.get("HOLDER_NUM_RATIO"), "pct2"),
            str(r.get("HOLD_NOTICE_DATE", "-"))[:10],
        ]))
    return _table(
        f"# 股东户数 | {normalize_ticker(ticker)}",
        "datacenter RPT_HOLDERNUM_DET",
        "报告期 | 股东户数 | 较上期增减 | 环比增幅% | 公告日期",
        lines,
    )


def get_free_holders(ticker: str) -> str:
    """个股十大流通股东（RPT_F10_EH_FREEHOLDERS，最新披露期）。"""
    secucode = _secucode(ticker)
    rows = _dc_get(
        "RPT_F10_EH_FREEHOLDERS",
        host="securities",
        filter_str=f'(SECUCODE="{secucode}")',
        sort_columns="END_DATE",
        page_size=50,
    )
    if not rows:
        return f"# 十大流通股东 | {secucode}\n\n⚠️ 暂无十大流通股东数据。"

    latest = max(str(r.get("END_DATE", ""))[:10] for r in rows)
    day = [r for r in rows if str(r.get("END_DATE", ""))[:10] == latest]

    def rank(r: dict) -> float:
        try:
            return float(r.get("HOLDER_RANK") or 99)
        except (TypeError, ValueError):
            return 99.0

    day.sort(key=rank)
    lines = []
    for r in day:
        lines.append(" | ".join([
            latest,
            _fmt(r.get("HOLDER_RANK"), "int"),
            str(r.get("HOLDER_NAME", "-")),
            _fmt(r.get("HOLD_NUM"), "wan2"),
            _fmt(r.get("FREE_HOLDNUM_RATIO"), "pct2"),
        ]))
    return _table(
        f"# 十大流通股东 | {secucode} | {latest}",
        "securities RPT_F10_EH_FREEHOLDERS",
        "报告期 | 排名 | 股东名称 | 持股数量(万股) | 占流通股比%",
        lines,
    )


def get_holder_increase(ticker: str, page_size: int = 30) -> str:
    """个股股东增减持记录（RPT_SHARE_HOLDER_INCREASE，按公告日降序）。"""
    rows = _dc_get(
        "RPT_SHARE_HOLDER_INCREASE",
        filter_str=f'(SECURITY_CODE="{normalize_ticker(ticker)}")',
        sort_columns="NOTICE_DATE",
        page_size=max(1, page_size),
    )
    if not rows:
        return f"# 股东增减持 | {normalize_ticker(ticker)}\n\n⚠️ 暂无股东增减持记录。"

    lines = []
    for r in rows:
        lines.append(" | ".join([
            str(r.get("NOTICE_DATE", "-"))[:10],
            str(r.get("HOLDER_NAME", "-")),
            str(r.get("DIRECTION", "-") or "-"),
            _fmt(r.get("CHANGE_NUM_SYMBOL"), "raw"),
            _fmt(r.get("HOLD_RATIO"), "pct2"),
        ]))
    return _table(
        f"# 股东增减持 | {normalize_ticker(ticker)}",
        "datacenter RPT_SHARE_HOLDER_INCREASE",
        "公告日 | 股东名称 | 方向 | 变动股数(万股) | 变动后持股比例%",
        lines,
    )
