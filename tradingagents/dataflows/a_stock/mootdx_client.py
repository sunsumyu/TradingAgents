"""mootdx TCP client singleton for A-stock OHLCV data.

Handles server selection, TCP probing, negative caching, and health checks.
The client is lazily initialized and reused across calls.
"""

from __future__ import annotations

import contextlib
import logging
import socket
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_mootdx_client = None

_TDX_SERVERS = [
    ("119.97.185.59", 7709), ("124.70.133.119", 7709), ("116.205.183.150", 7709),
    ("123.60.73.44", 7709), ("116.205.163.254", 7709), ("121.36.225.169", 7709),
    ("123.60.70.228", 7709), ("124.71.9.153", 7709), ("110.41.147.114", 7709),
    ("124.71.187.122", 7709),
]

_TDX_CANARY_SYMBOL = "600519"
_MOOTDX_RETRY_AFTER_S = 300.0
_mootdx_unavailable_until = 0.0


# ---------------------------------------------------------------------------
# Server probing
# ---------------------------------------------------------------------------

def _candidate_tdx_servers() -> list[tuple[str, int]]:
    """待试的通达信服务器：先用实测精选的，再补 mootdx 自带的完整主机表。"""
    servers = list(_TDX_SERVERS)
    seen = set(servers)
    try:
        from mootdx.consts import HQ_HOSTS
        for entry in HQ_HOSTS:
            host = (entry[1], entry[2]) if len(entry) >= 3 else None
            if host and host not in seen:
                seen.add(host)
                servers.append(host)
    except Exception as e:
        logger.debug("读取 mootdx HQ_HOSTS 失败，仅使用内置精选表：%s", e)
    return servers


def _probe_tdx(ip: str, port: int, timeout: float = 1.0) -> bool:
    """TCP 握手探测通达信服务器端口是否开着。"""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _reachable_tdx_servers(servers, timeout: float = 1.0, max_probe: int = 15):
    """并发做 TCP 预筛，返回可连的那些（保持原顺序）。"""
    from concurrent.futures import ThreadPoolExecutor

    if not servers:
        return []
    to_probe = servers[:max_probe]
    with ThreadPoolExecutor(max_workers=min(16, len(to_probe))) as pool:
        flags = list(pool.map(lambda s: _probe_tdx(s[0], s[1], timeout), to_probe))
    return [srv for srv, ok in zip(to_probe, flags) if ok]


def _tdx_client_works(client) -> bool:
    """真实拉一根 K 线来验证这个 client 确实能取数。"""
    try:
        df = client.bars(symbol=_TDX_CANARY_SYMBOL, category=4, offset=1)
        return df is not None and not df.empty
    except Exception:
        return False


# ---------------------------------------------------------------------------
# BestIP protection
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _preserve_mootdx_bestip():
    """探测期间保护 mootdx 的持久化服务器配置，退出时按需还原。"""
    saved = None
    try:
        from mootdx import config as _cfg
        _cfg.setup()
        saved = _cfg.get("BESTIP")
        if isinstance(saved, dict):
            saved = dict(saved)
    except Exception as e:
        logger.debug("读取 mootdx BESTIP 失败，本次探测不做保护：%s", e)

    keep = {"flag": False}
    try:
        yield lambda: keep.__setitem__("flag", True)
    finally:
        if saved is not None and not keep["flag"]:
            try:
                from mootdx import config as _cfg2
                _cfg2.set("BESTIP", saved)
            except Exception as e:
                logger.debug("恢复 mootdx BESTIP 失败：%s", e)


# ---------------------------------------------------------------------------
# Client initialization
# ---------------------------------------------------------------------------

def _get_mootdx_client():
    """Lazy-init 健壮版 mootdx Quotes client（TCP 连接，可复用）。"""
    global _mootdx_client, _mootdx_unavailable_until
    if _mootdx_client is not None:
        return _mootdx_client

    now = time.time()
    if now < _mootdx_unavailable_until:
        raise RuntimeError(
            "mootdx 通达信服务器暂不可用（%.0f 秒内不再重试）。"
            "已尝试全部内置服务器：端口能连上的也没能完成通达信协议取数。"
            "请检查网络环境（代理/防火墙/公司网络常拦 TCP 7709），"
            "或改用 6 位股票代码直接查询。" % (_mootdx_unavailable_until - now)
        )

    from mootdx.quotes import Quotes

    _MOOTDX_PROBE_DEADLINE_S = 8.0
    probe_start = time.time()

    tcp_ok_but_dead = 0
    with _preserve_mootdx_bestip() as keep_bestip:
        reachable = _reachable_tdx_servers(_candidate_tdx_servers())

        for ip, port in reachable:
            if time.time() - probe_start > _MOOTDX_PROBE_DEADLINE_S:
                logger.warning(
                    "mootdx probe exceeded %.1fs deadline after checking %d servers; "
                    "aborting and falling back to Sina HTTP.",
                    _MOOTDX_PROBE_DEADLINE_S, tcp_ok_but_dead,
                )
                break

            try:
                candidate = Quotes.factory(market="std", server=(ip, port))
            except Exception as e:
                tcp_ok_but_dead += 1
                logger.debug("mootdx %s:%s 握手失败（%s），换下一台", ip, port, type(e).__name__)
            else:
                if _tdx_client_works(candidate):
                    logger.info("mootdx server selected: %s:%s", ip, port)
                    keep_bestip()
                    _mootdx_client = candidate
                    return _mootdx_client
                tcp_ok_but_dead += 1
                logger.debug("mootdx %s:%s 建连成功但取不到数，换下一台", ip, port)

    try:
        candidate = Quotes.factory(market="std")
    except Exception as e:
        logger.debug("mootdx 裸 factory 失败 — %s", e)
    else:
        if _tdx_client_works(candidate):
            logger.info("mootdx client from 裸 factory（用户已有配置）")
            _mootdx_client = candidate
            return _mootdx_client

    _mootdx_unavailable_until = time.time() + _MOOTDX_RETRY_AFTER_S
    if tcp_ok_but_dead:
        cause = (
            "%d 台服务器端口能连上，但通达信协议握手/取数被拒。"
            "这通常是协议层被拦（代理、防火墙、公司网络对 TCP 7709 的策略），"
            "换服务器解决不了。" % tcp_ok_but_dead
        )
    else:
        cause = "内置服务器表里没有一台的 TCP 7709 能连上，请检查网络连通性。"
    raise RuntimeError(
        "mootdx 通达信服务器不可用：%s"
        "可改用 6 位股票代码直接查询。%.0f 秒内将直接快速失败、不再逐台重探。"
        % (cause, _MOOTDX_RETRY_AFTER_S)
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def reset_mootdx_client() -> None:
    """丢弃缓存的 client，让下一次调用重新选服务器。"""
    global _mootdx_client, _mootdx_unavailable_until
    _mootdx_client = None
    _mootdx_unavailable_until = 0.0


def mootdx_call(method: str, timeout: float = 8.0, **kwargs):
    """调用 mootdx 的某个方法，失败就弃用当前服务器。

    Parameters
    ----------
    timeout:
        Maximum seconds to wait for the actual TCP data fetch.
    """
    import threading

    client = _get_mootdx_client()

    result_holder: list = [None]
    error_holder: list = [None]

    def _do_call():
        try:
            result_holder[0] = getattr(client, method)(**kwargs)
        except Exception as e:
            error_holder[0] = e

    t = threading.Thread(target=_do_call, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        reset_mootdx_client()
        raise TimeoutError(
            f"mootdx {method} timed out after {timeout}s — server may be unresponsive"
        )

    if error_holder[0] is not None:
        reset_mootdx_client()
        raise error_holder[0]

    return result_holder[0]


def get_insider_transactions(
    ticker: str,
) -> str:
    """Get shareholder/insider activity via mootdx F10.

    Note: A-stock insider transaction data differs from US markets.
    Uses mootdx F10 shareholder research as the closest equivalent.
    """
    import re as _re
    from datetime import datetime
    from .utils import normalize_ticker

    code = normalize_ticker(ticker)

    try:
        text = mootdx_call("F10", symbol=code, name="股东研究")

        if not text or not text.strip():
            return f"No insider/shareholder data found for A-stock '{code}'"

        header = f"# Shareholder Research for {code} (A-stock)\n"
        header += "# Note: A-stock equivalent of insider transactions\n"
        header += "# Data source: mootdx F10\n"
        header += (
            f"# Data retrieved on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        sec4_hits = list(_re.finditer(r"\r?\n【4\.股东变化】\r?\n", text))
        if sec4_hits:
            sec4_pos = sec4_hits[-1].start()
            before_sec4 = text[:sec4_pos]
            sec4_text = text[sec4_pos:]
            cut_at = 2000
            if len(sec4_text) > cut_at:
                sec4_text = (
                    sec4_text[:cut_at]
                    + "\n\n(... older shareholder history omitted, "
                    f"{len(text) - sec4_pos - cut_at} chars truncated ...)"
                )
            text = before_sec4 + sec4_text

        return header + text

    except Exception as e:
        return f"Error retrieving insider/shareholder data for {code}: {str(e)}"
