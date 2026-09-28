"""三板 / 港股 / 美股 数据模块。

Data source: 东方财富 datacenter-web API (复用 eastmoney 的 _em_get / _eastmoney_datacenter)

注：以下功能的 ReportName 尚未确认，暂时返回提示信息。
待找到正确的 ReportName 后更新。

Functions:
    get_neeq_abnormal_trade()  — 三板异常交易
    get_hk_ipo()               — 港股 IPO 一览
    get_us_ipo()               — 美股 IPO 申请
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ── 三板异常交易 (NEEQ Abnormal Trading) ─────────────────────────────────────

def get_neeq_abnormal_trade(
    curr_date: str | None = None,
    page_size: int = 50,
    page_number: int = 1,
) -> str:
    """获取三板异常交易数据。

    注：三板异常交易数据没有公开的 API 数据源。
    建议参考以下替代方案：
    1. 全国中小企业股份转让系统官网 (www.neeq.com.cn)
    2. 东方财富新三板频道
    3. 同花顺新三板数据

    Args:
        curr_date: 参考日期 (YYYY-MM-DD)，默认今天
        page_size: 每页条数
        page_number: 页码

    Returns:
        Markdown 字符串
    """
    if curr_date is None:
        curr_date = datetime.now().strftime("%Y-%m-%d")

    lines: list[str] = [
        f"# 三板异常交易 | {curr_date}",
        "",
        "序号 | 证券代码 | 证券简称 | 交易方式 | 收盘价 | 涨跌幅% | 成交数量(股) | 成交金额(万元) | 涉及事项 | 披露原因",
        "",
        "⚠️ 三板异常交易数据暂无公开 API 数据源。",
        "",
        "## 替代方案",
        "",
        "1. **全国中小企业股份转让系统官网**",
        "   - 网址: www.neeq.com.cn",
        "   - 路径: 信息披露 → 异常交易",
        "",
        "2. **东方财富新三板频道**",
        "   - 网址: data.eastmoney.com/neeq/",
        "",
        "3. **同花顺新三板数据**",
        "   - 在通达信/同花顺终端查看",
        "",
        "如需实时数据，建议直接访问上述网站或使用终端软件。",
    ]

    return "\n".join(lines)


# ── 港股 IPO 一览 (Hong Kong IPO) ────────────────────────────────────────────

_AASTOCKS_IPO_URL = "https://www.aastocks.com/sc/stocks/market/ipo/mainpage.aspx"


def _strip_tags(fragment: str) -> str:
    import re

    txt = re.sub(r"<[^>]+>", " ", fragment)
    txt = txt.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", txt).strip()


def _norm_hk_date(value: str) -> str:
    """``2026/10/06`` → ``2026-10-06``；不可解析时原样返回。"""
    import re

    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", value.strip())
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return value.strip()


def _aastocks_tables(html: str) -> list[str]:
    import re

    return re.findall(r"<table[^>]*>.*?</table>", html, re.DOTALL)


def _parse_subscribing_table(table_html: str) -> list[tuple[str, ...]]:
    """「正在招股」表 → (代码, 名称, 行业, 招股价, 每手, 入场费, 截止日, 上市日)。"""
    import re

    out: list[tuple[str, ...]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL):
        cells = [
            _strip_tags(c)
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.DOTALL)
        ]
        cells = [c for c in cells if c]
        if len(cells) < 7:
            continue
        first = cells[0]
        m = re.search(r"^(.*?)(0\d{4})\.HK(.*)$", first)
        if not m:
            continue
        name = m.group(1).strip()
        code = m.group(2)
        note = m.group(3).strip()  # 如 "7日后截止招股"
        out.append((
            code,
            name,
            cells[1],
            cells[2],
            cells[3].replace(",", ""),
            cells[4].replace(",", ""),
            _norm_hk_date(cells[5]),
            _norm_hk_date(cells[6]),
            note,
        ))
    return out


def _parse_listed_table(table_html: str, limit: int) -> list[tuple[str, ...]]:
    """半新股「已上市」表 → (上市日, 代码, 名称, 上市价, 超额倍数)。

    过滤衍生品行（名称带 @ 标记的权证/牛熊证）；剥离「跌穿上市价」状态后缀
    （现价/上市价可自行比较得出，语义归解析器/展示层）。
    """
    import re

    out: list[tuple[str, ...]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL):
        cells = [
            _strip_tags(c)
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.DOTALL)
        ]
        cells = [c for c in cells if c]
        if len(cells) < 5:
            continue
        code_m = re.fullmatch(r"(0\d{4})\.HK", cells[1].strip())
        if not code_m:
            continue  # 表头或非代码行
        name = cells[2].strip()
        if "@" in name:
            continue  # 衍生权证 / 牛熊证，非股票 IPO
        name = name.replace("跌穿上市价", "").strip()
        out.append((
            _norm_hk_date(cells[0]),
            code_m.group(1),
            name,
            cells[3].replace(",", ""),
            cells[4].replace(",", ""),
        ))
        if len(out) >= limit:
            break
    return out


def get_hk_ipo(
    curr_date: str | None = None,
    page_size: int = 50,
    page_number: int = 1,
) -> str:
    """获取港股 IPO 一览数据（真源：阿斯达克 aastocks 新股频道）。

    2026-09-28 实测换源修复工单 08 错标：原 akshare ``stock_ipo_hk_ths``
    返回的是 A 股数据；东财港股新股页已 404 下线且 datacenter 无对应报表
    （详见工单 08）。本函数抓取 aastocks 新股主页两张表：

    * 「正在招股」：代码/名称/行业/招股价区间/每手股数/入场费/截止日/上市日
    * 半新股「已上市」：上市日/代码/名称/上市价/超额倍数
      （过滤 ``@`` 衍生品行；``跌穿上市价`` 状态后缀剥离）

    覆盖范围：aastocks 首页概览（招股中通常 0-10 只、已上市近 20 只），
    非完整招股书数据。

    Args:
        curr_date: 参考日期（仅用于标题），默认今天
        page_size: 已上市列表条数上限
        page_number: 保留接口一致性（本功能为概览快照，不支持分页）

    Returns:
        Markdown 字符串
    """
    if curr_date is None:
        curr_date = datetime.now().strftime("%Y-%m-%d")

    lines: list[str] = [
        f"# 港股新股（IPO） | {curr_date}",
        "# Source: 阿斯达克 aastocks 新股频道",
        f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    try:
        from curl_cffi import requests as cf_requests

        r = cf_requests.get(
            _AASTOCKS_IPO_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            impersonate="chrome120",
            timeout=15,
        )
        r.raise_for_status()
        tables = _aastocks_tables(r.text)

        # 「正在招股」表：紧跟该标题后的第一张表
        subscribing: list[tuple[str, ...]] = []
        anchor = r.text.find("正在招股")
        if anchor >= 0:
            for t_html in _aastocks_tables(r.text[anchor:]):
                subscribing = _parse_subscribing_table(t_html)
                if subscribing:
                    break

        # 「已上市」表：表头含 上市日期+代号+上市价 的第一张表
        listed: list[tuple[str, ...]] = []
        for t_html in tables:
            head_txt = _strip_tags(t_html[:600])
            if "上市日期" in head_txt and "代号" in head_txt and "上市价" in head_txt:
                listed = _parse_listed_table(t_html, limit=max(1, page_size))
                if listed:
                    break

        if not subscribing and not listed:
            lines.append("⚠️ 暂无港股新股数据（页面结构可能已变化，可稍后重试）。")
            return "\n".join(lines)

        lines.append("## 招股中")
        lines.append("")
        lines.append("代码 | 名称 | 行业 | 招股价 | 每手股数 | 入场费(港元) | 招股截止日 | 上市日期")
        for code, name, industry, price, lot, fee, deadline, listing, _note in subscribing:
            lines.append(f"{code} | {name} | {industry} | {price} | {lot} | {fee} | {deadline} | {listing}")

        lines.append("")
        lines.append("## 已上市（半新股）")
        lines.append("")
        lines.append("上市日期 | 代码 | 名称 | 上市价 | 超额倍数")
        for listing_date, code, name, offer, oversub in listed:
            lines.append(f"{listing_date} | {code} | {name} | {offer} | {oversub}")

    except ImportError:
        lines.extend(["", "⚠️ curl_cffi 未安装，无法获取港股新股数据。请运行: pip install curl_cffi"])
    except Exception as exc:
        logger.warning("HK IPO fetch failed: %s", exc)
        lines.extend(["", f"获取港股新股数据失败: {exc}"])

    return "\n".join(lines)


# ── 美股 IPO 申请 (US IPO Applications) ──────────────────────────────────────

def get_us_ipo(
    curr_date: str | None = None,
    page_size: int = 50,
    page_number: int = 1,
) -> str:
    """获取美股 IPO 申请数据。

    注：美股 IPO 数据没有公开的 API 数据源。
    建议参考以下替代方案：
    1. SEC EDGAR 数据库 (www.sec.gov/edgar)
    2. Nasdaq IPO Calendar
    3. NYSE IPO Calendar

    Args:
        curr_date: 参考日期 (YYYY-MM-DD)，默认今天
        page_size: 每页条数
        page_number: 页码

    Returns:
        Markdown 字符串
    """
    if curr_date is None:
        curr_date = datetime.now().strftime("%Y-%m-%d")

    lines: list[str] = [
        f"# 美股数据 (IPO申请) | {curr_date}",
        "",
        "序号 | 股票代码 | 公司名称 | 申请日期 | 行业 | 承销簿记人 | 交易所 | 发行总额(百万美元) | 发行股份数量(百万) | 计划发售价范围(美元)",
        "",
        "⚠️ 美股 IPO 数据暂无公开 API 数据源。",
        "",
        "## 替代方案",
        "",
        "1. **SEC EDGAR 数据库**",
        "   - 网址: www.sec.gov/edgar",
        "   - 搜索: S-1 表格 (IPO注册声明)",
        "",
        "2. **Nasdaq IPO Calendar**",
        "   - 网址: www.nasdaq.com/market-activity/ipos",
        "",
        "3. **NYSE IPO Calendar**",
        "   - 网址: www.nyse.com/listings/ipos",
        "",
        "4. **东方财富美股频道**",
        "   - 网址: data.eastmoney.com/xg/us/",
        "",
        "如需实时数据，建议直接访问上述网站或使用终端软件。",
    ]

    return "\n".join(lines)
