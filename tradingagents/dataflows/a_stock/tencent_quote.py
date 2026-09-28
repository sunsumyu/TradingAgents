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
            "volume": int(vals[6]) if vals[6] else 0,
            "outer_disc": int(vals[7]) if vals[7] else 0,  # 外盘
            "inner_disc": int(vals[8]) if vals[8] else 0,  # 内盘
            # 五档盘口 (bid/ask 5 levels)
            "bid1_price": float(vals[9]) if vals[9] else 0,
            "bid1_vol": int(vals[10]) if vals[10] else 0,
            "bid2_price": float(vals[11]) if vals[11] else 0,
            "bid2_vol": int(vals[12]) if vals[12] else 0,
            "bid3_price": float(vals[13]) if vals[13] else 0,
            "bid3_vol": int(vals[14]) if vals[14] else 0,
            "bid4_price": float(vals[15]) if vals[15] else 0,
            "bid4_vol": int(vals[16]) if vals[16] else 0,
            "bid5_price": float(vals[17]) if vals[17] else 0,
            "bid5_vol": int(vals[18]) if vals[18] else 0,
            "ask1_price": float(vals[19]) if vals[19] else 0,
            "ask1_vol": int(vals[20]) if vals[20] else 0,
            "ask2_price": float(vals[21]) if vals[21] else 0,
            "ask2_vol": int(vals[22]) if vals[22] else 0,
            "ask3_price": float(vals[23]) if vals[23] else 0,
            "ask3_vol": int(vals[24]) if vals[24] else 0,
            "ask4_price": float(vals[25]) if vals[25] else 0,
            "ask4_vol": int(vals[26]) if vals[26] else 0,
            "ask5_price": float(vals[27]) if vals[27] else 0,
            "ask5_vol": int(vals[28]) if vals[28] else 0,
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
            # 五档盘口
            "bid1_price": q.get("bid1_price"),
            "bid1_vol": q.get("bid1_vol"),
            "bid2_price": q.get("bid2_price"),
            "bid2_vol": q.get("bid2_vol"),
            "bid3_price": q.get("bid3_price"),
            "bid3_vol": q.get("bid3_vol"),
            "bid4_price": q.get("bid4_price"),
            "bid4_vol": q.get("bid4_vol"),
            "bid5_price": q.get("bid5_price"),
            "bid5_vol": q.get("bid5_vol"),
            "ask1_price": q.get("ask1_price"),
            "ask1_vol": q.get("ask1_vol"),
            "ask2_price": q.get("ask2_price"),
            "ask2_vol": q.get("ask2_vol"),
            "ask3_price": q.get("ask3_price"),
            "ask3_vol": q.get("ask3_vol"),
            "ask4_price": q.get("ask4_price"),
            "ask4_vol": q.get("ask4_vol"),
            "ask5_price": q.get("ask5_price"),
            "ask5_vol": q.get("ask5_vol"),
            # 关键指标
            "volume": q.get("volume"),
            "outer_disc": q.get("outer_disc"),
            "inner_disc": q.get("inner_disc"),
            "turnover_pct": q.get("turnover_pct"),
            "pe_ttm": q.get("pe_ttm"),
            "pb": q.get("pb"),
            "mcap_yi": q.get("mcap_yi"),
            "float_mcap_yi": q.get("float_mcap_yi"),
        }
    return out
