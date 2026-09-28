"""市场全景图数据模块（腾讯 API 版本）— 当东方财富 API 不可用时的替代方案。

数据源: 腾讯行情 API (qt.gtimg.cn)
特点: 免费、无需认证、国内访问稳定
局限: 无板块排行/市场宽度 API，仅提供指数行情和个股行情

Functions (与 market_overview.py 接口一致):
    get_index_trends()           — 三大指数分时数据
    get_stock_ranking()          — 上证/深证A股涨跌幅排行（精选成分股）
    get_board_ranking()          — 板块排行（腾讯无此 API，返回空）
    get_market_breadth()         — 市场宽度（腾讯无此 API，返回空）
    get_market_news()            — 市场资讯（复用现有模块）
    get_market_overview()        — 聚合全部数据
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ── Tencent API helpers ──────────────────────────────────────────────────────

_TENCENT_URL = "http://qt.gtimg.cn/q="
_TENCENT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "http://finance.qq.com/",
}

# 指数代码映射 (Tencent 格式: market.code)
# 返回 (short_format, full_format, name)
_INDEX_CODES = {
    "000001": ("s_sh000001", "sh000001", "上证指数"),
    "399001": ("s_sz399001", "sz399001", "深证成指"),
    "399006": ("s_sz399006", "sz399006", "创业板指"),
}

# 精选成分股列表（用于涨跌幅排行，Tencent 无排行 API）
# 上证精选
_SH_MAJOR = [
    "sh600519", "sh601398", "sh600036", "sh601166", "sh600276",
    "sh601012", "sh600900", "sh601857", "sh600031", "sh601318",
    "sh600887", "sh601328", "sh601288", "sh600050", "sh601688",
    "sh600104", "sh600585", "sh601111", "sh600000", "sh601390",
    "sh601989", "sh601800", "sh600028", "sh601766", "sh601211",
    "sh600809", "sh600309", "sh601088", "sh600196", "sh601601",
]

# 深证精选
_SZ_MAJOR = [
    "sz000858", "sz000333", "sz002714", "sz000725", "sz002475",
    "sz000651", "sz000002", "sz002594", "sz000568", "sz002352",
    "sz300750", "sz002304", "sz000538", "sz002142", "sz000001",
    "sz000100", "sz002027", "sz000063", "sz000338", "sz002230",
    "sz300059", "sz002415", "sz000661", "sz002032", "sz000876",
    "sz300015", "sz002049", "sz000625", "sz300122", "sz002241",
]


def _parse_tencent_line(line: str) -> dict | None:
    """Parse one Tencent quote line into a dict.

    Tencent format (short, s_ prefix):
        v_s_sh000001="1~上证指数~000001~3932.70~2.58~0.07~477375261~89790401~~697503.59~ZS~";
    Fields: market~name~code~price~change~changePct~volume~amount~~amount_yi~type~

    Tencent format (full, no prefix):
        v_sh000001="1~上证指数~000001~3932.70~3930.12~3942.51~477375261~...~";
    Fields: market~name~code~price~last_close~open~volume~...
    """
    match = re.search(r'v_\w+="(.+)"', line)
    if not match:
        return None
    vals = match.group(1).split("~")
    if len(vals) < 8:
        return None
    try:
        code = vals[2]
        price = float(vals[3]) if vals[3] else 0
        if price <= 0:
            return None
        return {
            "code": code,
            "name": vals[1],
            "price": price,
            "raw_fields": vals,
        }
    except (ValueError, IndexError):
        return None


def _fetch_tencent_quotes(codes: list[str], short: bool = True) -> dict[str, dict]:
    """Batch fetch quotes from Tencent API.

    Args:
        codes: list of Tencent-format codes like ["sh600519", "sz000858"]
        short: if True, use short format (s_ prefix) for faster parsing

    Returns:
        {code: {name, price, last_close, change_pct, volume, ...}}
    """
    if not codes:
        return {}

    prefix = "s_" if short else ""
    query_codes = [prefix + c for c in codes]
    url = _TENCENT_URL + ",".join(query_codes)

    try:
        r = requests.get(url, headers=_TENCENT_HEADERS, timeout=10)
        r.encoding = "gbk"
        results = {}
        for line in r.text.strip().split(";"):
            line = line.strip()
            if not line:
                continue
            match = re.search(r'v_\w+="(.+)"', line)
            if not match:
                continue
            vals = match.group(1).split("~")
            if len(vals) < 8:
                continue
            code = vals[2]
            price = float(vals[3]) if vals[3] else 0
            if price <= 0:
                continue

            if short:
                # Short format: market~name~code~price~change~changePct~volume~amount~~amount_yi~type~
                change = float(vals[4]) if vals[4] else 0
                change_pct = float(vals[5]) if vals[5] else 0
                volume = int(float(vals[6])) if vals[6] else 0
                amount_yi = float(vals[9]) if len(vals) > 9 and vals[9] else 0
                results[code] = {
                    "name": vals[1],
                    "code": code,
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": volume,
                    "amount_yi": amount_yi,
                }
            else:
                # Full format: market~name~code~price~pre_close~open~volume~...
                # Then at end: ...~change~changePct~...
                pre_close = float(vals[4]) if vals[4] else 0
                volume = int(float(vals[6])) if vals[6] else 0
                # change and changePct are at indices 31 and 32 in full format
                change = float(vals[31]) if len(vals) > 31 and vals[31] else 0
                change_pct = float(vals[32]) if len(vals) > 32 and vals[32] else 0
                results[code] = {
                    "name": vals[1],
                    "code": code,
                    "price": price,
                    "pre_close": pre_close,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": volume,
                }
        return results
    except Exception as e:
        logger.warning("Tencent quote fetch failed: %s", e)
        return {}


# ── index trends ──────────────────────────────────────────────────────────────

def get_index_trends() -> dict[str, dict]:
    """获取三大指数分时数据。

    Returns same format as market_overview.py:
        {
            "000001": { "name": "上证指数", "price": 3942.09,
                        "change_pct": 0.02, "pre_close": 3941.39,
                        "trends": [] },
            ...
        }
    """
    result = {}
    for code, (_, tcode_full, name) in _INDEX_CODES.items():
        try:
            quotes = _fetch_tencent_quotes([tcode_full], short=False)
            q = quotes.get(code, {})
            if not q:
                continue

            price = q.get("price", 0)
            pre_close = q.get("pre_close", 0)
            change_pct = q.get("change_pct", 0)

            result[code] = {
                "name": name,
                "price": round(price, 2),
                "pre_close": round(pre_close, 2),
                "change_pct": round(change_pct, 2),
                "trends": [],  # Tencent API doesn't provide intraday trends
            }
        except Exception as e:
            logger.warning("Index %s trends failed (tencent): %s", code, e)

    return result


# ── stock ranking ────────────────────────────────────────────────────────────

def get_stock_ranking(market: str = "sh", sort: str = "gain", limit: int = 10) -> list[dict]:
    """获取上证/深证A股涨跌幅排行（基于精选成分股）。

    Tencent 无排序 API，使用预设的成分股列表获取行情后本地排序。

    Returns same format as market_overview.py:
        [{ code, name, price, change_pct, change, volume, amount }, ...]
    """
    codes = _SH_MAJOR if market == "sh" else _SZ_MAJOR
    quotes = _fetch_tencent_quotes(codes, short=False)

    items = []
    for code, q in quotes.items():
        items.append({
            "code": q.get("code", code[-6:]),
            "name": q.get("name", ""),
            "price": round(q.get("price", 0), 2),
            "change_pct": round(q.get("change_pct", 0), 2),
            "change": round(q.get("change", 0), 2),
            "volume": q.get("volume", 0),
            "amount": 0,  # Tencent 不直接提供成交额（亿元）
        })

    # 本地排序
    if sort == "gain":
        items.sort(key=lambda x: x["change_pct"], reverse=True)
    else:
        items.sort(key=lambda x: x["change_pct"])

    return items[:limit]


# ── board ranking ────────────────────────────────────────────────────────────

def get_board_ranking(board_type: str = "industry", sort: str = "change_pct", limit: int = 50) -> list[dict]:
    """获取板块排行。

    腾讯 API 无板块排行接口，返回空列表。
    前端会显示"数据暂不可用"提示。
    """
    logger.debug("Board ranking not available via Tencent API")
    return []


# ── market breadth ──────────────────────────────────────────────────────────

def get_market_breadth() -> dict:
    """市场宽度统计。

    腾讯 API 无市场宽度接口，返回零值。
    前端会显示"数据暂不可用"提示。
    """
    return {
        "total": 0,
        "up_count": 0,
        "down_count": 0,
        "flat_count": 0,
        "total_amount_yi": 0.0,
    }


# ── market news ──────────────────────────────────────────────────────────────

def get_market_news(limit: int = 30) -> list[dict]:
    """获取市场资讯 — 尝试多个新闻源，全部不可用时返回空列表。

    注意: 财联社和东财快讯 API 在某些网络环境下可能被屏蔽，
    此时静默返回空列表，前端会显示"资讯暂不可用"。
    """
    news = []

    # 尝试财联社快讯
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.cls.cn/",
        }
        r = requests.get(
            "https://www.cls.cn/nodeapi/telegraphList",
            params={"rn": str(limit), "page": "1"},
            headers=headers,
            timeout=8,
        )
        d = r.json()
        for item in d.get("data", {}).get("roll_data", []):
            title = item.get("title", "") or item.get("brief", "")
            content = item.get("content", "") or item.get("brief", "")
            ctime = item.get("ctime", "")
            pub_time = ""
            if ctime:
                try:
                    pub_time = datetime.fromtimestamp(int(ctime)).strftime("%H:%M")
                except (ValueError, TypeError, OSError):
                    pub_time = str(ctime)
            news.append({
                "title": title[:80],
                "content": content[:200],
                "time": pub_time,
                "source": "财联社",
            })
        if news:
            return news[:limit]
    except Exception as e:
        logger.debug("CLS news unavailable (tencent_market): %s", e)

    # 尝试东财快讯
    try:
        em_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://kuaixun.eastmoney.com/",
        }
        r2 = requests.get(
            "https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
            params={
                "client": "web",
                "biz": "web_724",
                "fastColumn": "102",
                "pageSize": str(limit),
                "sortEnd": "9999999999999",
            },
            headers=em_headers,
            timeout=8,
        )
        d2 = r2.json()
        for item in d2.get("data", {}).get("fastNewsList", []):
            title = item.get("title", "")
            summary = item.get("summary", "")[:200]
            pub_time = item.get("showTime", "")
            news.append({
                "title": title[:80],
                "content": summary,
                "time": pub_time,
                "source": "东财快讯",
            })
        if news:
            return news[:limit]
    except Exception as e:
        logger.debug("Eastmoney news unavailable (tencent_market): %s", e)

    # 两个源都不可用，返回空列表
    return []


# ── market overview (aggregate) ─────────────────────────────────────────────

def get_market_overview() -> dict[str, Any]:
    """聚合市场全景图全部数据（腾讯 API 版本）。"""
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_gather_market_data())
    finally:
        loop.close()
    return result


def get_combined_market_overview() -> dict[str, Any]:
    """聚合市场全景图全部数据（三源互补版本）。

    数据源互补:
    - 腾讯: 实时行情 + 个股涨跌排行
    - 新浪: A 股全量排行 + 板块排行 + 市场宽度
    - 东财: 指数分时趋势 (241 点)
    """
    from .sina_market import (
        get_combined_stock_ranking,
        get_combined_board_ranking,
        get_combined_market_breadth,
    )
    from .eastmoney_client import get_index_trends_em

    # 指数分时 (东财)
    secids = {
        "000001": ("1.000001", "上证指数"),
        "399001": ("0.399001", "深证成指"),
        "399006": ("0.399006", "创业板指"),
    }
    indices = get_index_trends_em(secids)

    # 个股涨跌排行 (新浪全量)
    sh_gainers = get_combined_stock_ranking("sh", "gain", 10)
    sh_losers = get_combined_stock_ranking("sh", "loss", 10)
    sz_gainers = get_combined_stock_ranking("sz", "gain", 10)
    sz_losers = get_combined_stock_ranking("sz", "loss", 10)

    # 板块排行 (新浪)
    industry_boards = get_combined_board_ranking("industry", 50)
    concept_boards = get_combined_board_ranking("concept", 50)

    # 市场宽度 (新浪)
    breadth = get_combined_market_breadth()

    # 新闻 (尝试多个源)
    news = _get_news_unified(30)

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "indices": indices,
        "sh_gainers": sh_gainers,
        "sh_losers": sh_losers,
        "sz_gainers": sz_gainers,
        "sz_losers": sz_losers,
        "boards": {
            "industry": industry_boards,
            "concept": concept_boards,
        },
        "breadth": breadth,
        "news": news,
    }


def _get_news_unified(limit: int = 30) -> list[dict]:
    """获取市场资讯 — 尝试多个新闻源。"""
    news = []
    # 复用现有的新闻获取逻辑
    return get_market_news(limit)


async def _gather_market_data() -> dict[str, Any]:
    """Async gather all market data from Tencent API."""

    def _sync(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    indices, sh_gain, sh_loss, sz_gain, sz_loss, industry, concept, breadth, news = await asyncio.gather(
        asyncio.to_thread(_sync, get_index_trends),
        asyncio.to_thread(_sync, get_stock_ranking, "sh", "gain", 10),
        asyncio.to_thread(_sync, get_stock_ranking, "sh", "loss", 10),
        asyncio.to_thread(_sync, get_stock_ranking, "sz", "gain", 10),
        asyncio.to_thread(_sync, get_stock_ranking, "sz", "loss", 10),
        asyncio.to_thread(_sync, get_board_ranking, "industry", "change_pct", 50),
        asyncio.to_thread(_sync, get_board_ranking, "concept", "change_pct", 50),
        asyncio.to_thread(_sync, get_market_breadth),
        asyncio.to_thread(_sync, get_market_news, 30),
    )

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "indices": indices,
        "sh_gainers": sh_gain,
        "sh_losers": sh_loss,
        "sz_gainers": sz_gain,
        "sz_losers": sz_loss,
        "boards": {
            "industry": industry,
            "concept": concept,
        },
        "breadth": breadth,
        "news": news,
    }
