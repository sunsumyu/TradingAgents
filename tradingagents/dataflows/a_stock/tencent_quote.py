"""Tencent Finance batch realtime quotes (qt.gtimg.cn).

Single HTTP request for all A-share codes; returns PE/PB/market cap/price.
"""

from __future__ import annotations

import logging
import urllib.request

from .utils import get_prefix, normalize_ticker

logger = logging.getLogger(__name__)


def _tencent_quote(codes: list[str]) -> dict[str, dict]:
    """Batch real-time quotes from Tencent Finance (qt.gtimg.cn).

    Returns dict[code] -> {name, price, pe_ttm, pb, mcap_yi, ...}
    """
    prefixed = [f"{get_prefix(c)}{c}" for c in codes]
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    raw = resp.read().decode("gbk")

    result = {}
    for line in raw.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]  # strip sh/sz/bj prefix
        result[code] = {
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "open": float(vals[5]) if vals[5] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "limit_up": float(vals[47]) if vals[47] else 0,
            "limit_down": float(vals[48]) if vals[48] else 0,
            "pe_static": float(vals[52]) if vals[52] else 0,
        }
    return result


def get_realtime_quotes(codes: list[str]) -> dict[str, dict]:
    """批量实时行情（公开入口，Watchlist 轮询用）。

    一次 Tencent HTTP 请求查询全部代码；返回 {原始输入代码: {...}}，键与
    传入的代码一致。查不到数据的代码不会出现在结果里，单个代码失败不影响其他代码。
    """
    normalized: dict[str, str] = {}
    for original in codes:
        if not original or not str(original).strip():
            continue
        try:
            code = normalize_ticker(str(original))
        except Exception:
            continue
        normalized.setdefault(code, str(original).strip())

    if not normalized:
        return {}

    try:
        quotes = _tencent_quote(list(normalized.keys()))
    except Exception:
        return {}

    out: dict[str, dict] = {}
    for code, q in quotes.items():
        price = q.get("price") or 0
        last_close = q.get("last_close") or 0
        if price <= 0:
            continue
        original = normalized.get(code)
        if not original:
            continue
        out[original] = {
            "name": q.get("name"),
            "price": price,
            "change": round(price - last_close, 4),
            "change_pct": q.get("change_pct") or 0.0,
            "high": q.get("high") or 0.0,
            "low": q.get("low") or 0.0,
        }
    return out
