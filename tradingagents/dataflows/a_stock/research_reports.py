"""研报流（Phase 12.05）— 东财 reportapi 研究报告列表。

数据源（2026-09-27 实测核实，reportapi.eastmoney.com/report/list）：
方案文档列为「已验证开放端点」。实测：

* 全市场（qType=0，无 code）→ total=7197，字段含
  ``title``/``orgSName``(券商)/``publishDate``/``emRatingName``(评级)/
  ``researcher``(分析师)/``stockName``/``stockCode``。
* 个股过滤 ``code=600519`` ✅ → total=40（近 180 天），
  首条「贵州茅台公司跟踪报告…」诚通证券 2026-09-21 买入 陈文倩。

日期窗口 ``beginTime``/``endTime``（YYYY-MM-DD）为必填（缺省报错），调用方必须给窗口。
评级为券商观点，非本平台结论；缓存走默认 TTL（研报按日发布，4h/24h 足够）。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from curl_cffi import requests as cf_requests

from .utils import normalize_ticker

_REPORT_URL = "https://reportapi.eastmoney.com/report/list"


def _is_astock_code(ticker: str) -> bool:
    """与 astock_features.is_astock_code 同规则：规范化后恰为 6 位数字。"""
    try:
        code = normalize_ticker(ticker)
    except Exception:  # noqa: BLE001 - 非常规输入按非个股处理
        return False
    return len(code) == 6 and code.isdigit()


def _get_reports(
    code: str | None, begin: str, end: str, page_size: int, timeout: int = 15
) -> list[dict]:
    """reportapi 研报查询（curl_cffi，两次退避重试，失败返回空列表）。"""
    params: dict[str, str] = {
        "industryCode": "*",
        "pageSize": str(max(1, page_size)),
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "beginTime": begin,
        "endTime": end,
        "pageNo": "1",
        "fields": "",
        "qType": "0",
        "orgCode": "",
        "rcode": "",
    }
    if code:
        params["code"] = code
    last_exc: Exception | None = None
    for attempt in range(1, 3):
        try:
            j = cf_requests.get(
                _REPORT_URL, params=params, impersonate="chrome120", timeout=timeout
            ).json()
            return j.get("data") or []
        except Exception as exc:  # noqa: BLE001 - 网络层异常统一降级为空
            last_exc = exc
            if attempt < 2:
                time.sleep(attempt)
    if last_exc is not None:
        print(f"[research_reports] failed: {last_exc}")
    return []


def _esc(text: object) -> str:
    out = str(text or "-").replace("|", "／").strip()
    return out or "-"


def _fmt_date(value: object) -> str:
    return str(value or "-")[:10]


def get_research_reports(
    ticker: str | None = None,
    date: str | None = None,
    page_size: int = 30,
    window_days: int = 180,
) -> str:
    """研报流（个股或全市场，最新在前）。

    Args:
        ticker: 6 位 A 股代码 → 个股研报；None/非 A 股 → 全市场最新研报
        date: 分析日期 YYYY-MM-DD；窗口取其前 ``window_days`` 天（默认 180）
        page_size: 返回条数
        window_days: 日期窗口长度
    """
    if date:
        end_dt = datetime.strptime(date[:10], "%Y-%m-%d")
    else:
        end_dt = datetime.now()
    begin = (end_dt - timedelta(days=window_days)).strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")

    per_stock = bool(ticker and _is_astock_code(ticker))
    code = normalize_ticker(ticker) if per_stock else None
    rows = _get_reports(code, begin, end, max(1, page_size))
    if not rows:
        return (
            f"# 研报流 | {code or '全市场'}\n\n"
            f"⚠️ 近 {window_days} 天无研报数据（或接口繁忙，可稍后重试）。"
        )

    lines = []
    for r in rows:
        cells = [
            _fmt_date(r.get("publishDate")),
            _esc(r.get("orgSName")),
            _esc(r.get("emRatingName")),
            _esc(r.get("researcher")),
        ]
        if not per_stock:
            cells += [_esc(r.get("stockCode")), _esc(r.get("stockName"))]
        cells.append(_esc(r.get("title")))
        lines.append(" | ".join(cells))

    header = (
        "研报日期 | 券商 | 评级 | 分析师 | "
        + ("正股代码 | 正股简称 | " if not per_stock else "")
        + "标题"
    )
    return "\n".join([
        f"# 研报流 | {code or '全市场'} | {begin} ~ {end}",
        "# Source: 东财 reportapi（研究报告）",
        f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        header,
        *lines,
    ])
