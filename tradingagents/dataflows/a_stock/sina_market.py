"""新浪财经数据模块 — 补充腾讯/东财的缺失数据。

数据源: 新浪财经 API (vip.stock.finance.sina.com.cn)
特点: 免费、无需认证、国内访问稳定
提供:
    - A 股全量涨跌幅排行 (沪深合并)
    - 指数板块排行 (hs_s 行业指数、hs_z 概念指数)
    - 市场宽度 (总家数)

与 tencent_market.py 互补:
    - 腾讯: 实时行情 + 个股涨跌排行
    - 新浪: A 股全量排行 + 板块排行
    - 东财: 指数分时趋势 (241 点)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_SINA_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php"
_SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn/",
}


def _sina_get(path: str, params: dict | None = None, timeout: float = 8) -> list | None:
    """调用新浪 API (禁用系统代理)。"""
    try:
        # 使用独立 session 绕过系统代理 (Clash Verge 等)
        if not hasattr(_sina_get, '_session'):
            _sina_get._session = requests.Session()
            _sina_get._session.trust_env = False
        r = _sina_get._session.get(
            f"{_SINA_URL}/{path}",
            params=params,
            headers=_SINA_HEADERS,
            timeout=timeout,
        )
        if r.status_code == 200 and r.text.strip():
            return json.loads(r.text)
    except Exception as e:
        logger.debug("Sina API %s failed: %s", path, e)
    return None


def get_sina_stock_ranking(node: str = "hs_a", page: int = 1, num: int = 50,
                            sort: str = "changepercent", asc: int = 0) -> list[dict]:
    """获取 A 股涨跌幅排行 (新浪全量数据)。

    Args:
        node: hs_a (沪深A股), hs_s (上海A股), hs_z (深圳A股)
        page: 页码
        num: 每页条数
        sort: 排序字段
        asc: 0=降序, 1=升序

    Returns:
        [{ code, name, price, change_pct, change, volume, amount }, ...]
    """
    items = _sina_get(
        "Market_Center.getHQNodeData",
        params={
            "page": str(page),
            "num": str(num),
            "sort": sort,
            "asc": str(asc),
            "node": node,
            "symbol": "",
            "_s_r_a": "page",
        },
    )
    if not items:
        return []

    result = []
    for i in items:
        price = float(i.get("trade", 0))
        change = float(i.get("pricechange", 0)) if i.get("pricechange") else 0
        change_pct = float(i.get("changepercent", 0)) if i.get("changepercent") else 0
        volume = int(float(i.get("volume", 0)))
        amount = float(i.get("amount", 0)) / 1e8 if i.get("amount") else 0  # 转为亿元
        result.append({
            "code": i.get("code", ""),
            "name": i.get("name", ""),
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": volume,
            "amount": round(amount, 2),
        })
    return result


def get_sina_index_boards(node: str = "hs_s", num: int = 50) -> list[dict]:
    """获取指数板块排行 (新浪)。

    Args:
        node: hs_s (行业指数), hs_z (概念指数)
        num: 返回条数

    Returns:
        [{ code, name, price, change_pct, change, volume, amount }, ...]
    """
    items = _sina_get(
        "Market_Center.getHQNodeData",
        params={
            "page": "1",
            "num": str(num),
            "sort": "changepercent",
            "asc": "0",
            "node": node,
            "symbol": "",
            "_s_r_a": "page",
        },
    )
    if not items:
        return []

    result = []
    for i in items:
        price = float(i.get("trade", 0))
        change = float(i.get("pricechange", 0)) if i.get("pricechange") else 0
        change_pct = float(i.get("changepercent", 0)) if i.get("changepercent") else 0
        volume = int(float(i.get("volume", 0)))
        amount = float(i.get("amount", 0)) / 1e8 if i.get("amount") else 0
        result.append({
            "code": i.get("code", ""),
            "name": i.get("name", ""),
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "volume": volume,
            "amount": round(amount, 2),
        })
    return result


def get_sina_market_stats() -> dict:
    """获取市场统计 (总家数)。"""
    total = _sina_get(
        "Market_Center.getHQNodeStockCount",
        params={"node": "hs_a"},
    )
    if total and isinstance(total, str):
        try:
            return {"total": int(total.strip('"'))}
        except ValueError:
            pass
    return {"total": 0}


def get_combined_stock_ranking(market: str = "sh", sort: str = "gain", limit: int = 10) -> list[dict]:  # noqa: F811
    """获取全量 A 股涨跌幅排行 (沪深合并后筛选)。

    使用新浪全量数据，按市场筛选。

    Args:
        market: "sh" (上证A股) | "sz" (深证A股)
        sort: "gain" (涨幅降序) | "loss" (涨幅升序)
        limit: 返回条数

    Returns:
        [{ code, name, price, change_pct, change, volume, amount }, ...]
    """
    # 获取全量 A 股 (新浪一次最多返回 50 条)
    all_stocks = get_sina_stock_ranking(node="hs_a", num=50, sort="changepercent", asc=0)
    if not all_stocks:
        return []

    # 按市场筛选
    if market == "sh":
        # 上证 A 股: 60xxxx, 68xxxx (科创板)
        filtered = [s for s in all_stocks if s["code"].startswith(("60", "68"))]
    else:
        # 深证 A 股: 00xxxx, 30xxxx (创业板)
        filtered = [s for s in all_stocks if s["code"].startswith(("00", "30"))]

    # 排序
    if sort == "gain":
        filtered.sort(key=lambda x: x["change_pct"], reverse=True)
    else:
        filtered.sort(key=lambda x: x["change_pct"])

    return filtered[:limit]


def get_combined_board_ranking(board_type: str = "industry", sort: str = "change_pct", limit: int = 50) -> list[dict]:
    """获取板块排行 (新浪指数板块)。

    Args:
        board_type: "industry" (行业指数) | "concept" (概念指数)
        sort: 排序字段 (未使用，保留接口兼容)
        limit: 返回条数

    Returns:
        [{ code, name, price, change_pct, change, volume, amount }, ...]
    """
    if board_type == "industry":
        return get_sina_index_boards(node="hs_s", num=limit)
    else:
        return get_sina_index_boards(node="hs_z", num=limit)


def get_combined_market_breadth() -> dict:
    """获取市场宽度 (新浪全量 A 股涨跌统计)。

    通过新浪分页接口遍历全量 A 股，统计涨跌家数。
    新浪每次最多返回 100 条，需分页遍历 (~56 页)。

    优化: 数据按 changepercent 降序排列，一旦遇到 pct <= 0 的行，
    后续所有行均为下跌或平盘，可直接用总数减去已统计数。
    """
    url = f"{_SINA_URL}/Market_Center.getHQNodeData"
    up_count = 0
    down_count = 0
    flat_count = 0
    total_counted = 0
    total_amount = 0.0
    total = 5557  # Fallback if count API unavailable

    # Get accurate total count
    try:
        resp = _sina_get("Market_Center.getHQNodeStockCount", params={"node": "hs_a"})
        if resp and isinstance(resp, str):
            total = int(resp.strip('"'))
    except Exception:
        pass

    if not hasattr(_sina_get, '_session'):
        _sina_get._session = requests.Session()
        _sina_get._session.trust_env = False
    session = _sina_get._session

    for page in range(1, 60):  # 最多 60 页 * 100 = 6000 条
        try:
            resp = session.get(
                url,
                params={"page": page, "num": 100, "sort": "changepercent", "asc": 0, "node": "hs_a"},
                headers=_SINA_HEADERS,
                timeout=10,
            )
            if resp.status_code != 200 or not resp.text.strip():
                break
            data = json.loads(resp.text)
            if not data:
                break

            has_negative = False
            for stock in data:
                total_counted += 1
                pct = float(stock.get("changepercent", 0))
                if pct > 0:
                    up_count += 1
                elif pct < 0:
                    down_count += 1
                    has_negative = True
                else:
                    flat_count += 1
                total_amount += float(stock.get("amount", 0))

            # Optimization: once we hit negative, remaining stocks are all down/flat
            if has_negative:
                # Remaining stocks (total - counted) are all down or flat
                # We already counted the negatives in this page, remaining are down
                remaining = total - total_counted
                down_count += remaining
                total_counted = total
                break

        except Exception as e:
            logger.debug("Breadth page %d failed: %s", page, e)
            break

    return {
        "total": total,
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "total_amount_yi": round(total_amount / 1e8, 2),
    }
