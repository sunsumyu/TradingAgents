"""调研互动 & 备查资料数据模块。

Data source: 东方财富 datacenter-web API (复用 eastmoney 的 _em_get / _eastmoney_datacenter)

Functions:
    get_survey_interaction()      — 调研互动：机构调研统计 (按股票聚合近1月/3月/6月)
    get_company_name_changes()    — 备查资料：公司更名记录 (深交所-名称变更，仅深市)
    get_st_changes()              — 备查资料：实施/撤销ST (由深交所简称变更派生)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from .eastmoney import _DATACENTER_URL, _em_get

logger = logging.getLogger(__name__)


# ── 调研互动 (Institutional Research Survey) ──────────────────────────────────

def get_survey_interaction(
    curr_date: str | None = None,
    page_size: int = 50,
    page_number: int = 1,
) -> str:
    """获取调研互动数据 — 机构调研统计一览（按股票聚合）。

    数据源: RPT_ORG_SURVEYNEW (东财-数据中心-机构调研统计)
    - filter (NUMBERNEW="1")(IS_SOURCE="1") 去重调研公告
    - quoteColumns 附加 最新价(f2)/涨跌幅(f3)/行业(f100)
    - SUM 字段 = 单次调研活动的接待机构数量

    Args:
        curr_date: 参考日期 (YYYY-MM-DD)，默认今天
        page_size: 每页条数
        page_number: 页码

    Returns:
        Markdown 字符串
    """
    if curr_date is None:
        curr_date = datetime.now().strftime("%Y-%m-%d")

    ref_date = datetime.strptime(curr_date, "%Y-%m-%d")
    date_1m_ago = (ref_date - timedelta(days=30)).strftime("%Y-%m-%d")
    date_3m_ago = (ref_date - timedelta(days=90)).strftime("%Y-%m-%d")
    date_6m_ago = (ref_date - timedelta(days=180)).strftime("%Y-%m-%d")

    lines: list[str] = [
        f"# 调研互动 (机构调研统计) | {curr_date}",
        "",
        "序号 | 证券代码 | 证券简称 | 所属行业 | 最新调研日 | 近一月调研 | 近三月调研 | 近半年调研 | 近一月机构 | 近三月机构 | 近半年机构 | 最新价 | 涨跌幅%",
    ]

    try:
        params = {
            "sortColumns": "NOTICE_DATE,SUM,RECEIVE_START_DATE,SECURITY_CODE",
            "sortTypes": "-1,-1,-1,1",
            "pageSize": "500",
            "pageNumber": "1",
            "reportName": "RPT_ORG_SURVEYNEW",
            "columns": "ALL",
            "quoteColumns": (
                "f2~01~SECURITY_CODE~CLOSE_PRICE,"
                "f3~01~SECURITY_CODE~CHANGE_RATE,"
                "f100~01~SECURITY_CODE~INDUSTRY"
            ),
            "quoteType": "0",
            "source": "WEB",
            "client": "WEB",
            "filter": f'(NUMBERNEW="1")(IS_SOURCE="1")(NOTICE_DATE>\'{date_6m_ago}\')',
        }

        # 最多取 3 页 (1500 条调研公告)
        records: list[dict] = []
        for page in range(1, 4):
            params["pageNumber"] = str(page)
            r = _em_get(_DATACENTER_URL, params=params, timeout=15)
            d = r.json()
            result = d.get("result") or {}
            rows = result.get("data") or []
            records.extend(rows)
            total_pages = int(result.get("pages") or 1)
            if page >= total_pages or not rows:
                break

        if not records:
            lines.append("")
            lines.append(f"近半年（{date_6m_ago} 之后）暂无调研数据。")
            return "\n".join(lines)

        # 按股票聚合
        stock_stats: dict[str, dict] = defaultdict(lambda: {
            "name": "", "industry": "", "close": "", "chg": "",
            "latest_date": "",
            "events_1m": 0, "events_3m": 0, "events_6m": 0,
            "orgs_1m": 0, "orgs_3m": 0, "orgs_6m": 0,
        })

        for row in records:
            code = str(row.get("SECURITY_CODE") or "")
            if not code:
                continue
            notice = str(row.get("NOTICE_DATE") or "")
            notice_day = notice.split(" ")[0] if notice else ""
            try:
                n_date = datetime.strptime(notice_day, "%Y-%m-%d")
            except ValueError:
                continue

            stats = stock_stats[code]
            stats["name"] = str(row.get("SECURITY_NAME_ABBR") or "")
            stats["industry"] = str(row.get("INDUSTRY") or "")
            if row.get("CLOSE_PRICE") is not None:
                stats["close"] = str(row.get("CLOSE_PRICE"))
            if row.get("CHANGE_RATE") is not None:
                stats["chg"] = str(row.get("CHANGE_RATE"))
            if notice_day > stats["latest_date"]:
                stats["latest_date"] = notice_day

            # SUM = 接待机构数量
            try:
                orgs = int(float(row.get("SUM") or 1))
            except (ValueError, TypeError):
                orgs = 1

            if n_date >= ref_date - timedelta(days=30):
                stats["events_1m"] += 1
                stats["orgs_1m"] += orgs
            if n_date >= ref_date - timedelta(days=90):
                stats["events_3m"] += 1
                stats["orgs_3m"] += orgs
            if n_date >= ref_date - timedelta(days=180):
                stats["events_6m"] += 1
                stats["orgs_6m"] += orgs

        # 按最新调研日排序
        sorted_stocks = sorted(
            stock_stats.items(), key=lambda kv: kv[1]["latest_date"], reverse=True
        )

        start_idx = (page_number - 1) * page_size
        end_idx = page_number * page_size
        for i, (code, s) in enumerate(sorted_stocks[start_idx:end_idx], start_idx + 1):
            lines.append(
                f"  {i} | {code} | {s['name']} | {s['industry'] or '--'} | "
                f"{s['latest_date']} | {s['events_1m']} | {s['events_3m']} | {s['events_6m']} | "
                f"{s['orgs_1m']} | {s['orgs_3m']} | {s['orgs_6m']} | "
                f"{s['close'] or '--'} | {s['chg'] or '--'}"
            )

    except Exception as exc:
        logger.warning("Survey interaction fetch failed: %s", exc)
        lines.append("")
        lines.append(f"获取调研互动数据失败: {exc}")

    return "\n".join(lines)


# ── 备查资料 — 公司更名 (Company Name Changes) ────────────────────────────────

def get_company_name_changes(
    start_date: str | None = None,
    end_date: str | None = None,
    page_size: int = 50,
    page_number: int = 1,
    symbol: str = "简称变更",
) -> str:
    """获取备查资料 — 公司更名记录一览（真源：深交所-名称变更）。

    数据源: akshare stock_info_sz_change_name（深证证券交易所-市场数据-股票数据-名称变更）
    本会话实测: 简称变更 7482 行 / 全称变更 1762 行，
    列: 变更日期 | 证券代码 | 证券简称 | 变更前简称(全称) | 变更后简称(全称)。

    覆盖范围：仅深市证券（沪市更名不在该源中）。

    Args:
        start_date: 开始日期 (YYYY-MM-DD)，默认90天前
        end_date: 结束日期 (YYYY-MM-DD)，默认今天
        page_size: 每页条数
        page_number: 页码
        symbol: "简称变更" 或 "全称变更"

    Returns:
        Markdown 字符串
    """
    today = datetime.now()
    if end_date is None:
        end_date = today.strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")

    lines: list[str] = [
        f"# 备查资料 (公司更名) | {start_date} ~ {end_date}",
        "",
        f"数据源: 深交所-名称变更（{symbol}，仅覆盖深市证券）",
    ]

    try:
        import akshare as ak

        df = ak.stock_info_sz_change_name(symbol=symbol)
        if df is None or df.empty:
            lines.extend(["", "深交所名称变更数据为空。"])
            return "\n".join(lines)

        date_col = "变更日期"
        before_col = "变更前简称" if "简称" in symbol else "变更前全称"
        after_col = "变更后简称" if "简称" in symbol else "变更后全称"

        rows = []
        for _, row in df.iterrows():
            change_date = str(row.get(date_col, ""))[:10]
            if change_date < start_date or change_date > end_date:
                continue
            rows.append((
                change_date,
                str(row.get("证券代码", "")),
                str(row.get("证券简称", "")),
                str(row.get(before_col, "")),
                str(row.get(after_col, "")),
            ))
        rows.sort(reverse=True)

        lines.append(f"共 {len(rows)} 条更名记录（第 {page_number} 页，每页 {page_size} 条）")
        lines.append("")
        lines.append("序号 | 变更日期 | 证券代码 | 证券简称 | 变更前 | 变更后")

        start_idx = (page_number - 1) * page_size
        for i, (change_date, code, name, before, after) in enumerate(
            rows[start_idx:start_idx + page_size], start_idx + 1
        ):
            lines.append(f"  {i} | {change_date} | {code} | {name} | {before} | {after}")

    except ImportError:
        lines.extend(["", "⚠️ akshare 未安装，无法获取公司更名数据。请运行: pip install akshare"])
    except Exception as exc:
        logger.warning("Company name changes fetch failed: %s", exc)
        lines.extend(["", f"获取公司更名数据失败: {exc}"])

    return "\n".join(lines)


# ── 备查资料 — 实施ST / 撤销ST (ST Changes) ───────────────────────────────────

def get_st_changes(
    start_date: str | None = None,
    end_date: str | None = None,
    page_size: int = 50,
    page_number: int = 1,
) -> str:
    """获取备查资料 — 实施/撤销ST 记录（由深交所简称变更派生）。

    派生规则：变更后简称含 ST（含 *ST）而变更前不含 → 实施；
    变更前含而变更后不含 → 撤销；两者都含 → 调整（风险警示类型变化）。

    覆盖范围：仅深市证券；沪市 ST 变更不在该源中。

    Returns:
        Markdown 字符串
    """
    today = datetime.now()
    if end_date is None:
        end_date = today.strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")

    lines: list[str] = [
        f"# 备查资料 (ST变更) | {start_date} ~ {end_date}",
        "",
        "数据源: 深交所-简称变更派生（实施/撤销ST，仅覆盖深市证券）",
    ]

    try:
        import akshare as ak

        df = ak.stock_info_sz_change_name(symbol="简称变更")
        if df is None or df.empty:
            lines.extend(["", "深交所名称变更数据为空，无法派生 ST 变更。"])
            return "\n".join(lines)

        rows = []
        for _, row in df.iterrows():
            change_date = str(row.get("变更日期", ""))[:10]
            if change_date < start_date or change_date > end_date:
                continue
            before = str(row.get("变更前简称", ""))
            after = str(row.get("变更后简称", ""))
            before_st = "ST" in before.upper()
            after_st = "ST" in after.upper()
            if after_st and not before_st:
                direction = "实施ST"
            elif before_st and not after_st:
                direction = "撤销ST"
            elif before_st and after_st:
                direction = "调整"
            else:
                continue
            rows.append((
                change_date,
                str(row.get("证券代码", "")),
                str(row.get("证券简称", "")),
                before,
                after,
                direction,
            ))
        rows.sort(reverse=True)

        lines.append(f"共 {len(rows)} 条ST变更记录（第 {page_number} 页，每页 {page_size} 条）")
        lines.append("")
        lines.append("序号 | 变更日期 | 证券代码 | 证券简称 | 变更前简称 | 变更后简称 | 方向")

        start_idx = (page_number - 1) * page_size
        for i, (change_date, code, name, before, after, direction) in enumerate(
            rows[start_idx:start_idx + page_size], start_idx + 1
        ):
            lines.append(f"  {i} | {change_date} | {code} | {name} | {before} | {after} | {direction}")

    except ImportError:
        lines.extend(["", "⚠️ akshare 未安装，无法派生 ST 变更数据。请运行: pip install akshare"])
    except Exception as exc:
        logger.warning("ST changes fetch failed: %s", exc)
        lines.extend(["", f"获取 ST 变更数据失败: {exc}"])

    return "\n".join(lines)
