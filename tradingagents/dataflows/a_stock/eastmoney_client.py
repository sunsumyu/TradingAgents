"""东方财富 HTTP 客户端 — 分策略绕过 TLS 指纹检测。

东财各子域名封锁程度不同:
- push2.eastmoney.com: TLS 指纹检测，域名访问被拒，IP 直连可用
- datacenter-web.eastmoney.com: curl_cffi 模拟 Chrome 可用
- np-anotice-stock.eastmoney.com: curl_cffi 模拟 Chrome 可用
- np-weblist.eastmoney.com: 需要额外参数，部分可用

策略:
1. push2 → requests + IP 直连 + Host 头
2. datacenter-web / np-anotice → curl_cffi impersonate=chrome
3. 失败时自动降级
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests as std_requests

logger = logging.getLogger(__name__)

# ── IP 池 (push2 CDN 节点，定期更新) ─────────────────────────────────────
_PUSH2_IPS = [
    "47.112.165.11",   # 阿里云
    "43.144.251.121",  # 腾讯云
]

# ── curl_cffi 可用性 ──────────────────────────────────────────────────────
_CURL_CFFI_AVAILABLE = False
try:
    from curl_cffi import requests as cf_requests  # noqa: F401
    _CURL_CFFI_AVAILABLE = True
except ImportError:
    logger.warning("curl_cffi not installed; datacenter-web/np-anotice unavailable")


def _push2_get_via_ip(path: str, params: dict | None = None, timeout: float = 8) -> dict | None:
    """通过 IP 直连访问 push2 API (绕过 TLS 指纹检测)。"""
    for ip in _PUSH2_IPS:
        try:
            r = std_requests.get(
                f"https://{ip}{path}",
                params=params,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://finance.eastmoney.com/",
                    "Host": "push2.eastmoney.com",
                },
                timeout=timeout,
                verify=False,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.debug("push2 IP %s failed: %s", ip, e)
            continue
    return None


def _datacenter_get(report_name: str, params: dict | None = None, timeout: float = 10) -> dict | None:
    """通过 curl_cffi 访问 datacenter-web API。"""
    if not _CURL_CFFI_AVAILABLE:
        return None
    from curl_cffi import requests as cf_requests

    base_params = {
        "reportName": report_name,
        "source": "WEB",
        "client": "WEB",
    }
    if params:
        base_params.update(params)
    try:
        r = cf_requests.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params=base_params,
            impersonate="chrome120",
            timeout=timeout,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug("datacenter-web %s failed: %s", report_name, e)
    return None


def _np_notice_get(params: dict | None = None, timeout: float = 10) -> dict | None:
    """通过 curl_cffi 访问 np-anotice 公告 API。"""
    if not _CURL_CFFI_AVAILABLE:
        return None
    from curl_cffi import requests as cf_requests

    try:
        r = cf_requests.get(
            "https://np-anotice-stock.eastmoney.com/api/security/ann",
            params=params,
            impersonate="chrome120",
            timeout=timeout,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug("np-anotice failed: %s", e)
    return None


# ── 公开接口 ──────────────────────────────────────────────────────────────

def push2_get_stock_trends(secid: str, ndays: int = 1) -> dict | None:
    """获取个股/指数分时趋势 (push2 via IP)。"""
    return _push2_get_via_ip(
        "/api/qt/stock/trends2/get",
        params={
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "iscr": "0",
            "ndays": str(ndays),
        },
    )


def push2_get_stock_quote(secid: str) -> dict | None:
    """获取实时报价 (push2 via IP)。"""
    return _push2_get_via_ip(
        "/api/qt/stock/get",
        params={
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f60,f116,f117,f162,f167,f170",
        },
    )


def push2_get_kline(secid: str, klt: int = 101, limit: int = 120) -> dict | None:
    """获取 K 线数据 (push2 via IP)。"""
    return _push2_get_via_ip(
        "/api/qt/stock/kline/get",
        params={
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": str(klt),
            "fqt": "1",
            "end": "20500101",
            "lmt": str(limit),
        },
    )


def datacenter_get_report(report_name: str, page_size: int = 20,
                          sort_columns: str | None = None,
                          sort_types: str = "-1",
                          extra_params: dict | None = None) -> list[dict]:
    """获取 datacenter-web 报表数据 (curl_cffi)。"""
    params: dict[str, Any] = {"pageSize": str(page_size), "sortTypes": sort_types}
    if sort_columns:
        params["sortColumns"] = sort_columns
    if extra_params:
        params.update(extra_params)

    d = _datacenter_get(report_name, params=params)
    if d and d.get("success") and d.get("result"):
        return d["result"].get("data", [])
    return []


def get_notices(ann_type: str = "A", page_size: int = 20, page_index: int = 1) -> list[dict]:
    """获取公司公告 (curl_cffi)。"""
    d = _np_notice_get(params={
        "sr": "-1",
        "page_size": str(page_size),
        "page_index": str(page_index),
        "ann_type": ann_type,
        "client_source": "web",
        "f_node": "0",
        "s_node": "0",
    })
    if d and d.get("data"):
        return d["data"].get("list", [])
    return []


# ── 便捷函数 ──────────────────────────────────────────────────────────────

def get_index_trends_em(secids: dict[str, tuple[str, str]]) -> dict[str, dict]:
    """获取多只指数分时数据 (东方财富 push2 via IP)。

    Args:
        secids: {code: (secid, name)}  e.g. {"000001": ("1.000001", "上证指数")}

    Returns:
        {code: {name, price, pre_close, change_pct, trends}}
    """
    result = {}
    for code, (secid, name) in secids.items():
        d = push2_get_stock_trends(secid)
        if not d or not d.get("data") or not d["data"].get("trends"):
            continue
        trends_raw = d["data"]["trends"]
        pre_close = float(d["data"].get("preClose", 0))
        trends = []
        latest_price = 0.0
        for t in trends_raw:
            parts = t.split(",")
            if len(parts) < 7:
                continue
            time_str = parts[0].split(" ", 1)[-1] if " " in parts[0] else parts[0]
            price = float(parts[1])
            avg_price = float(parts[2])
            volume = int(float(parts[3]))
            latest_price = price
            trends.append({
                "time": time_str,
                "price": round(price, 2),
                "avg_price": round(avg_price, 2),
                "volume": volume,
            })
        change_pct = round((latest_price - pre_close) / pre_close * 100, 2) if pre_close > 0 else 0.0
        result[code] = {
            "name": name,
            "price": round(latest_price, 2),
            "pre_close": round(pre_close, 2),
            "change_pct": change_pct,
            "trends": trends,
        }
    return result


def get_stock_quote_em(secid: str) -> dict | None:
    """获取实时报价 (东方财富 push2 via IP)。"""
    d = push2_get_stock_quote(secid)
    if not d or not d.get("data"):
        return None
    q = d["data"]
    # f43 价格是乘以 100 的整数，需要除以 100
    price = q.get("f43", 0) / 100 if q.get("f43") else 0
    pre_close = q.get("f60", 0) / 100 if q.get("f60") else 0
    change_pct = q.get("f170", 0) / 100 if q.get("f170") else 0
    return {
        "code": q.get("f57", ""),
        "name": q.get("f58", ""),
        "price": price,
        "high": q.get("f44", 0) / 100 if q.get("f44") else 0,
        "low": q.get("f45", 0) / 100 if q.get("f45") else 0,
        "open": q.get("f46", 0) / 100 if q.get("f46") else 0,
        "pre_close": pre_close,
        "volume": q.get("f47", 0),
        "amount": q.get("f48", 0),
        "change_pct": change_pct,
    }


def get_kline_em(secid: str, klt: int = 101, limit: int = 120) -> list[dict]:
    """获取 K 线数据 (东方财富 push2 via IP)。"""
    d = push2_get_kline(secid, klt=klt, limit=limit)
    if not d or not d.get("data") or not d["data"].get("klines"):
        return []
    klines = []
    for line in d["data"]["klines"]:
        parts = line.split(",")
        if len(parts) < 7:
            continue
        klines.append({
            "date": parts[0],
            "open": float(parts[1]),
            "close": float(parts[2]),
            "high": float(parts[3]),
            "low": float(parts[4]),
            "volume": int(float(parts[5])),
            "amount": float(parts[6]) if parts[6] else 0,
        })
    return klines


def push2_get_list(path: str, params: dict | None = None, timeout: float = 10) -> dict | None:
    """Generic push2 list query via IP direct (boards, breadth, etc.)."""
    return _push2_get_via_ip(path, params=params, timeout=timeout)
