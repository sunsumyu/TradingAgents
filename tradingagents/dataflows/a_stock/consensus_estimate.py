"""机构一致预期（工单 17 余项，Phase 13 收尾）— 东财 RPT_WEB_RESPREDICT。

2026-09-28 实测核实（datacenter-web，curl_cffi chrome120）：

* 报表必须用**具名列组** ``columns=WEB_RESPREDICT``（``columns=ALL`` 会 9501），
  排序用 ``RATING_ORG_NUM``——此前工单 17 记录的 9701×3 根因即参数不符；
  同名报表 ``RPT_VALUEANALYSIS_DET``（带个股 SECURITY_CODE 过滤可达）实为
  **估值分析明细**（PE/PB/PS/PEG），并非一致预期，勿混用。
* 过滤支持三种（均 code=0）：无过滤=全市场（587 页）、
  ``INDUSTRY_BOARD="<行业>"``（29 页）、``SECURITY_CODE="<code>"``（个股 1 条）。
* 字段：评级机构分布（买入/增持/中性/减持/卖出）+ 四年 EPS 共识
  （YEAR1-4 搭配 YEAR_MARK：A=实际 / E=预测）+ 目标价区间（DEC_AIMPRICE MIN/MAX）
  + 行业/概念/地域板块归属。
  样本：600519 贵州茅台 43 家机构（34 买入 + 9 增持），
  2025A EPS 65.85 / 2026E 67.25 / 2027E 71.13。

输出为低频报表 markdown，走 PG 缓存（Phase 12 新规）；评级共识随研报
发布更新 → TTL 24h。
"""

from __future__ import annotations

import time
from datetime import datetime

from curl_cffi import requests as cf_requests

from .utils import normalize_ticker

_DC_WEB = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def _fetch(rows_filter: str, page_size: int) -> list[dict]:
    params: dict[str, str] = {
        "reportName": "RPT_WEB_RESPREDICT",
        "columns": "WEB_RESPREDICT",
        "pageNumber": "1",
        "pageSize": str(max(1, page_size)),
        "sortTypes": "-1",
        "sortColumns": "RATING_ORG_NUM",
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
        "source": "WEB",
        "client": "WEB",
    }
    if rows_filter:
        params["filter"] = rows_filter
    last_exc: Exception | None = None
    for attempt in range(1, 3):
        try:
            j = cf_requests.get(
                _DC_WEB, params=params, impersonate="chrome120", timeout=15
            ).json()
            if j.get("code") == 0 and j.get("result"):
                return j["result"].get("data") or []
            return []
        except Exception as exc:  # noqa: BLE001 - 网络层异常统一降级为空
            last_exc = exc
            if attempt < 2:
                time.sleep(attempt)
    if last_exc is not None:
        print(f"[consensus_estimate] RPT_WEB_RESPREDICT failed: {last_exc}")
    return []


def _year_mark(row: dict, idx: int) -> str:
    year = row.get(f"YEAR{idx}")
    mark = str(row.get(f"YEAR_MARK{idx}") or "")
    if year is None:
        return "-"
    return f"{int(year)}{mark}"


def _eps(row: dict, idx: int) -> str:
    v = row.get(f"EPS{idx}")
    if v is None:
        return "-"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "-"


def _price(row: dict, key: str) -> str:
    v = row.get(key)
    if v is None:
        return "-"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "-"


def _rating(row: dict, key: str) -> str:
    v = row.get(key)
    return "0" if v is None else str(int(v)) if isinstance(v, (int, float)) else str(v)


def get_consensus_estimate(ticker: str | None = None, page_size: int = 50) -> str:
    """机构一致预期（评级汇总 + EPS 共识 + 目标价区间）。

    Args:
        ticker: 6 位 A 股代码 → 个股模式（1 条最新共识）；
                None/空 → 市场模式（按评级机构数降序前 N）
        page_size: 市场模式返回条数
    """
    title = "机构一致预期"
    if ticker:
        code = normalize_ticker(ticker)
        rows = _fetch(f'(SECURITY_CODE="{code}")', page_size=1)
        title = f"{title} | {code}"
    else:
        rows = _fetch("", page_size=page_size)

    if not rows:
        return f"# {title}\n\n⚠️ 暂无一致预期数据（可稍后重试）。"

    lines = []
    for r in rows:
        lines.append(" | ".join([
            str(r.get("SECURITY_CODE", "-")),
            str(r.get("SECURITY_NAME_ABBR", "-")),
            _rating(r, "RATING_ORG_NUM"),
            _rating(r, "RATING_BUY_NUM"),
            _rating(r, "RATING_ADD_NUM"),
            _rating(r, "RATING_NEUTRAL_NUM"),
            _rating(r, "RATING_REDUCE_NUM"),
            _rating(r, "RATING_SALE_NUM"),
            _price(r, "DEC_AIMPRICEMIN"),
            _price(r, "DEC_AIMPRICEMAX"),
            _year_mark(r, 1),
            _eps(r, 1),
            _year_mark(r, 2),
            _eps(r, 2),
        ]))

    header = (
        "证券代码 | 证券简称 | 评级机构数 | 买入 | 增持 | 中性 | 减持 | 卖出 | "
        "目标价低(元) | 目标价高(元) | 年度1 | EPS1(元) | 年度2 | EPS2(元)"
    )
    return "\n".join([
        f"# {title}",
        f"# Source: 东财 datacenter RPT_WEB_RESPREDICT",
        f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        header,
        *lines,
    ])
