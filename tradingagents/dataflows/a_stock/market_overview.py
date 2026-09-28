"""市场全景图数据模块 — 指数分时 / 涨跌幅排行 / 板块排行 / 市场宽度。

Data source: 东方财富 push2 HTTP API（默认）或 腾讯行情 API（回退）

切换方式:
    - 环境变量: TRADINGAGENTS_MARKET_DATA_VENDOR=tencent|eastmoney
    - 配置文件: market_data_vendor: "tencent" | "eastmoney"

Functions:
    get_index_trends()           — 三大指数分时数据
    get_stock_ranking()          — 上证/深证A股涨跌幅排行
    get_board_ranking()          — 行业/概念/风格/地区板块排行
    get_market_breadth()         — 市场宽度（涨跌家数 + 成交额）
    get_market_news()            — 市场资讯（复用现有新闻模块）
    get_market_overview()        — 聚合全部数据（单一入口）
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Any

from .http_client import default_client
logger = logging.getLogger(__name__)

# ── Vendor dispatch ──────────────────────────────────────────────────────────

def _get_vendor() -> str:
    """Get the configured market data vendor.

    Priority: env var > config file > default ("combined")
    Options: tencent | eastmoney | sina | combined
    """
    env_vendor = os.environ.get("TRADINGAGENTS_MARKET_DATA_VENDOR", "").strip().lower()
    if env_vendor:
        return env_vendor
    try:
        from tradingagents.default_config import DEFAULT_CONFIG
        return DEFAULT_CONFIG.get("market_data_vendor", "combined").lower()
    except Exception:
        return "combined"

# Module-level vendor selection
_VENDOR = _get_vendor()
logger.info("Market overview vendor: %s", _VENDOR)
logger.info("  env TRADINGAGENTS_MARKET_DATA_VENDOR=%s", os.environ.get("TRADINGAGENTS_MARKET_DATA_VENDOR", "(unset)"))

# Vendor functions cache
_tencent_funcs = None
_combined_funcs = None


def _get_tencent_funcs():
    """Lazy import tencent_market to avoid circular import."""
    global _tencent_funcs
    if _tencent_funcs is None:
        from . import tencent_market
        _tencent_funcs = {
            "get_index_trends": tencent_market.get_index_trends,
            "get_stock_ranking": tencent_market.get_stock_ranking,
            "get_board_ranking": tencent_market.get_board_ranking,
            "get_market_breadth": tencent_market.get_market_breadth,
            "get_market_news": tencent_market.get_market_news,
            "get_market_overview": tencent_market.get_market_overview,
        }
    return _tencent_funcs


def _get_combined_funcs():
    """Lazy import combined market functions."""
    global _combined_funcs
    if _combined_funcs is None:
        from . import tencent_market
        _combined_funcs = {
            "get_market_overview": tencent_market.get_combined_market_overview,
        }
    return _combined_funcs


# Public API — dispatches to the configured vendor at call time
def get_index_trends(*args, **kwargs):
    """获取三大指数分时数据 (auto-dispatches to configured vendor)."""
    vendor = _get_vendor()
    if vendor == "tencent":
        return _get_tencent_funcs()["get_index_trends"](*args, **kwargs)
    if vendor == "combined":
        # Primary: Eastmoney push2 (241 intraday points)
        from .eastmoney_client import get_index_trends_em
        secids = {
            "000001": ("1.000001", "上证指数"),
            "399001": ("0.399001", "深证成指"),
            "399006": ("0.399006", "创业板指"),
        }
        result = get_index_trends_em(secids)
        if result:
            return result
        # Fallback: Tencent (quotes only, no intraday trends)
        logger.info("Eastmoney index trends unavailable, falling back to Tencent")
        return _get_tencent_funcs()["get_index_trends"](*args, **kwargs)
    return _em_get_index_trends(*args, **kwargs)


def get_stock_ranking(*args, **kwargs):
    """获取涨跌幅排行 (auto-dispatches to configured vendor)."""
    vendor = _get_vendor()
    if vendor == "tencent":
        return _get_tencent_funcs()["get_stock_ranking"](*args, **kwargs)
    if vendor == "combined":
        # Primary: Eastmoney push2 (full market-filtered lists)
        result = _em_get_stock_ranking(*args, **kwargs)
        if result:
            return result
        # Fallback: Tencent (preset 30 stocks, locally sorted)
        logger.info("Eastmoney stock ranking unavailable, falling back to Tencent")
        return _get_tencent_funcs()["get_stock_ranking"](*args, **kwargs)
    return _em_get_stock_ranking(*args, **kwargs)


def get_board_ranking(board_type: str = "industry", *args, **kwargs):
    """获取板块排行 (auto-dispatches to configured vendor)."""
    vendor = _get_vendor()
    if vendor == "tencent":
        return _get_tencent_funcs()["get_board_ranking"](board_type, *args, **kwargs)
    if vendor == "combined":
        # Primary: Eastmoney push2 (proper industry/concept distinction)
        result = _em_get_board_ranking(board_type, *args, **kwargs)
        if result:
            return result
        # Fallback: Sina hs_s (index-style boards only, no concept sectors)
        logger.info("Eastmoney board ranking unavailable, falling back to Sina")
        from .sina_market import get_sina_index_boards
        return get_sina_index_boards(node="hs_s", num=kwargs.get("limit", 50))
    return _em_get_board_ranking(board_type, *args, **kwargs)


def get_market_breadth(*args, **kwargs):
    """市场宽度 (auto-dispatches to configured vendor)."""
    vendor = _get_vendor()
    if vendor == "tencent":
        return _get_tencent_funcs()["get_market_breadth"](*args, **kwargs)
    if vendor == "combined":
        # Full breadth via Sina pagination (5500+ stocks counted)
        from .sina_market import get_combined_market_breadth
        return get_combined_market_breadth()
    return _em_get_market_breadth(*args, **kwargs)


def get_market_news(*args, **kwargs):
    """市场资讯 (auto-dispatches to configured vendor)."""
    vendor = _get_vendor()
    if vendor == "tencent":
        return _get_tencent_funcs()["get_market_news"](*args, **kwargs)
    return _em_get_market_news(*args, **kwargs)

# 东财 push2 通用参数
_UT = "bd1d9ddb04089700cf9c27f6f7426281"

# 指数代码映射 (secid 格式: market.code)
_INDEX_SECIDS = {
    "000001": ("1.000001", "上证指数"),
    "399001": ("0.399001", "深证成指"),
    "399006": ("0.399006", "创业板指"),
}

# 板块类型 → push2 fs 参数
_BOARD_FS = {
    "industry": "m:90 t:2 f:!50",
    "concept": "m:90 t:3 f:!50",
    "style": "m:90 t:4 f:!50",
    "region": "m:90 t:5 f:!50",
}

# 市场 → push2 fs 参数
_MARKET_FS = {
    "sh": "m:1 t:2,m:1 t:23",    # 上证主板 + 科创板
    "sz": "m:0 t:6,m:0 t:80",    # 深证主板 + 创业板
}


# ── helpers ────────────────────────────────────────────────────────────────────

def _push2_get(url: str, params: dict, timeout: int = 10) -> dict:
    """Call push2 API via IP direct bypass and return parsed JSON.

    Routes through eastmoney_client._push2_get_via_ip() which connects
    directly to push2 CDN IPs with Host header to bypass TLS fingerprint detection.
    """
    from .eastmoney_client import push2_get_list
    path = url.replace("https://push2.eastmoney.com", "")
    result = push2_get_list(path, params=params, timeout=timeout)
    if result is None:
        return {}
    return result


def _safe_div100(v: Any) -> float:
    """Safely divide by 100 (push2 prices are in cents)."""
    try:
        return float(v) / 100 if v not in (None, "-", "") else 0.0
    except (ValueError, TypeError):
        return 0.0


# ── index trends ──────────────────────────────────────────────────────────────

def _em_get_index_trends() -> dict[str, dict]:
    """获取三大指数分时数据 (东方财富)。

    使用 eastmoney_client (IP 直连绕过 TLS 指纹检测)。
    """
    from .eastmoney_client import get_index_trends_em
    return get_index_trends_em(_INDEX_SECIDS)


# ── stock ranking ─────────────────────────────────────────────────────────────

def _em_get_stock_ranking(market: str = "sh", sort: str = "gain", limit: int = 10) -> list[dict]:
    """获取上证/深证A股涨跌幅排行 (东方财富)。

    Args:
        market: "sh" (上证A股) | "sz" (深证A股)
        sort: "gain" (涨幅降序) | "loss" (涨幅升序)
        limit: 返回条数

    Returns:
        [{ code, name, price, change_pct, change, volume, amount }, ...]
    """
    fs = _MARKET_FS.get(market, _MARKET_FS["sh"])
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": str(limit),
        "po": "1" if sort == "gain" else "0",
        "np": "1",
        "ut": _UT,
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": fs,
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14",
    }

    try:
        d = _push2_get(url, params)
        if not d.get("data") or not d["data"].get("diff"):
            return []
        items = []
        for row in d["data"]["diff"]:
            items.append({
                "code": str(row.get("f12", "")),
                "name": str(row.get("f14", "")),
                "price": round(_safe_div100(row.get("f2")), 2),
                "change_pct": round(_safe_div100(row.get("f3")), 2),
                "change": round(_safe_div100(row.get("f4")), 2),
                "volume": int(row.get("f5") or 0),
                "amount": round(_safe_div100(row.get("f6")) / 10000, 2),  # 转亿
            })
        return items
    except Exception as e:
        logger.warning("Stock ranking (%s %s) failed: %s", market, sort, e)
        return []


# ─ board ranking ─────────────────────────────────────────────────────────────

def _em_get_board_ranking(board_type: str = "industry", sort: str = "change_pct", limit: int = 50) -> list[dict]:
    """获取板块排行 (东方财富)。

    Args:
        board_type: "industry" | "concept" | "style" | "region"
        sort: "change_pct" | "price" | "volume_ratio"
        limit: 返回条数

    Returns:
        [{ code, name, change_pct, price, change, volume_ratio,
           up_count, down_count, limit_up_count }, ...]
    """
    fs = _BOARD_FS.get(board_type, _BOARD_FS["industry"])
    url = "https://push2.eastmoney.com/api/qt/clist/get"

    sort_field_map = {"change_pct": "f3", "price": "f2", "volume_ratio": "f10"}
    fid = sort_field_map.get(sort, "f3")

    params = {
        "pn": "1",
        "pz": str(limit),
        "po": "1",
        "np": "1",
        "ut": _UT,
        "fltt": "2",
        "invt": "2",
        "fid": fid,
        "fs": fs,
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f104,f105",
    }

    try:
        d = _push2_get(url, params)
        if not d.get("data") or not d["data"].get("diff"):
            return []
        items = []
        for row in d["data"]["diff"]:
            items.append({
                "code": str(row.get("f12", "")),
                "name": str(row.get("f14", "")),
                "change_pct": round(_safe_div100(row.get("f3")), 2),
                "price": round(_safe_div100(row.get("f2")), 2),
                "change": round(_safe_div100(row.get("f4")), 2),
                "volume_ratio": round(float(row.get("f10") or 0) / 100, 2),
                "up_count": int(row.get("f104") or 0),
                "down_count": int(row.get("f105") or 0),
                "limit_up_count": 0,  # 需要额外接口获取
            })
        return items
    except Exception as e:
        logger.warning("Board ranking (%s) failed: %s", board_type, e)
        return []


# ── market breadth ───────────────────────────────────────────────────────────

def _em_get_market_breadth() -> dict:
    """市场宽度统计 — 涨跌家数 + 总成交额 (东方财富)。

    策略：分别从涨幅和跌幅两端各取 3000 条，统计正负数量。
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    fs_all = "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23"

    up_count = 0
    down_count = 0
    flat_count = 0
    total_amount = 0.0
    total = 0
    seen_codes: set[str] = set()

    for sort_order in ("1", "0"):  # gain desc, loss desc
        params = {
            "pn": "1", "pz": "3000", "po": sort_order, "np": "1",
            "ut": _UT, "fltt": "2", "invt": "2", "fid": "f3",
            "fs": fs_all, "fields": "f3,f6,f12",
        }
        try:
            d = _push2_get(url, params)
            if not total:
                total = d.get("data", {}).get("total", 0)
            items = d.get("data", {}).get("diff") or []
            for row in items:
                code = str(row.get("f12", ""))
                if code in seen_codes:
                    continue
                seen_codes.add(code)
                pct = _safe_div100(row.get("f3"))
                if pct > 0.005:  # > 0.005% 算上涨（避免精度问题）
                    up_count += 1
                elif pct < -0.005:
                    down_count += 1
                else:
                    flat_count += 1
                total_amount += float(row.get("f6") or 0)
        except Exception as e:
            logger.warning("Market breadth sort=%s failed: %s", sort_order, e)

    # 如果没覆盖全部，用总数补齐平盘
    covered = up_count + down_count + flat_count
    if covered < total:
        flat_count += total - covered

    total_amount_yi = round(total_amount / 1e8, 2)

    return {
        "total": total,
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "total_amount_yi": total_amount_yi,
    }


# ── market news ──────────────────────────────────────────────────────────────

def _em_get_market_news(limit: int = 30) -> list[dict]:
    """获取市场资讯 — 从财联社/东财快讯获取 (东方财富)。"""
    news = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.cls.cn/",
    }

    # 财联社快讯
    try:
        r = default_client.get(
            "https://www.cls.cn/nodeapi/telegraphList",
            params={"rn": str(limit), "page": "1"},
            headers=headers,
            timeout=10,
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
    except Exception as e:
        logger.warning("CLS news failed: %s", e)

    # 东财快讯
    if len(news) < limit:
        try:
            em_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://kuaixun.eastmoney.com/",
            }
            r2 = default_client.get(
                "https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
                params={
                    "client": "web",
                    "biz": "web_724",
                    "fastColumn": "102",
                    "pageSize": str(limit - len(news)),
                },
                headers=em_headers,
                timeout=10,
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
        except Exception as e:
            logger.warning("Eastmoney news failed: %s", e)

    return news[:limit]


# ── market overview (aggregate) ──────────────────────────────────────────────

def get_market_overview() -> dict[str, Any]:
    """聚合市场全景图全部数据。

    使用 asyncio.gather 并行请求各数据源，总延迟 = 最慢的一个接口。

    Returns:
        {
            "timestamp": "2026-09-03 18:22",
            "indices": { "000001": {...}, "399001": {...}, "399006": {...} },
            "sh_gainers": [...], "sh_losers": [...],
            "sz_gainers": [...], "sz_losers": [...],
            "boards": { "industry": [...], "concept": [...] },
            "breadth": { "total": 5556, "up": 920, "down": 1937, ... },
            "news": [...]
        }
    """
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_gather_market_data())
    finally:
        loop.close()
    return result


async def _gather_market_data() -> dict[str, Any]:
    """Async gather all market data."""

    def _sync(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    # 并行请求
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
