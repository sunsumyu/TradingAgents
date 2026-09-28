"""数据源连通性测试 — 逐一验证各免费数据源当前是否可用。

用法: python -m tradingagents.dataflows.a_stock.source_test
"""

from __future__ import annotations

import json
import re
import time

import requests

_session = requests.Session()
_session.trust_env = False
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

results: list[tuple[str, str, str]] = []  # (name, status, detail)


def record(name: str, ok: bool, detail: str):
    results.append((name, "OK " if ok else "FAIL", detail))
    print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")


def test_baostock():
    """BaoStock: 登录 + 查询最近 1 根 5min K线 (30s 硬超时)."""
    name = "BaoStock 分钟线"
    try:
        import baostock as bs

        lg = bs.login()
        if lg.error_code != "0":
            record(name, False, f"login error: {lg.error_msg}")
            return
        rs = bs.query_history_k_data_plus(
            "sh.600519", "date,open,high,low,close,volume",
            start_date="2026-09-10", end_date="2026-09-14",
            frequency="5", adjustflag="3",
        )
        rows = []
        while (rs.error_code == "0") and rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        if rows:
            record(name, True, f"{len(rows)} bars, latest {rows[-1][0]}")
        else:
            record(name, False, "query returned 0 rows")
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {str(exc)[:80]}")


def test_eastmoney_daily():
    """东财: 日线 K线 (1 根)."""
    name = "东财 日线"
    try:
        r = _session.get(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params={
                "secid": "1.600519",
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "klt": "101", "fqt": "1", "lmt": "3", "end": "20500101",
            },
            headers=_UA, timeout=10,
        )
        kl = (r.json().get("data") or {}).get("klines") or []
        record(name, len(kl) > 0, f"{len(kl)} bars, latest {kl[-1].split(',')[0] if kl else '-'}")
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {str(exc)[:80]}")


def test_eastmoney_5min():
    """东财: 5min K线 (1 根)."""
    name = "东财 5min"
    try:
        r = _session.get(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params={
                "secid": "1.600519",
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "klt": "5", "fqt": "1", "lmt": "3", "end": "20500101",
            },
            headers=_UA, timeout=10,
        )
        kl = (r.json().get("data") or {}).get("klines") or []
        record(name, len(kl) > 0, f"{len(kl)} bars, latest {kl[-1].split(',')[0] if kl else '-'}")
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {str(exc)[:80]}")


def test_sina_5min():
    """新浪: 5min K线 (1 根)."""
    name = "新浪 5min"
    try:
        r = _session.get(
            "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_sh600519=/CN_MarketDataService.getKLineData",
            params={"symbol": "sh600519", "scale": "5", "ma": "no", "datalen": "3"},
            headers=_UA, timeout=10,
        )
        m = re.search(r"=\((\[.*\])\)", r.text, re.DOTALL)
        bars = json.loads(m.group(1)) if m else []
        record(name, len(bars) > 0, f"{len(bars)} bars, latest {bars[-1]['day'] if bars else '-'}")
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {str(exc)[:80]}")


def test_tencent_quote():
    """腾讯: 实时报价 (snapshot_recorder 使用的接口)."""
    name = "腾讯 实时报价"
    try:
        r = _session.get(
            "http://qt.gtimg.cn/q=sh600519,sz000001",
            headers=_UA, timeout=10,
        )
        # 腾讯返回 GBK 编码
        text = r.content.decode("gbk", errors="replace")
        prices = re.findall(r'~([\d.]+)~', text)
        record(name, len(prices) >= 2, f"600519={prices[0]} 000001={prices[6] if len(prices)>6 else prices[1]}")
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {str(exc)[:80]}")


def test_postgres():
    """PostgreSQL: 连接 + 行数."""
    name = "PostgreSQL"
    try:
        import psycopg2

        from tradingagents.config import (
            PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER,
        )

        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, user=PG_USER,
            password=PG_PASSWORD, dbname=PG_DB,
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM data_history")
        n = cur.fetchone()[0]
        conn.close()
        record(name, True, f"data_history {n:,} rows")
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {str(exc)[:80]}")


def test_tdengine():
    """TDengine: WebSocket 连接 + 超级表."""
    name = "TDengine"
    try:
        import taosws

        from tradingagents.config import TD_DSN

        conn = taosws.connect(TD_DSN)
        cur = conn.cursor()
        cur.execute("SHOW STABLES")
        stables = [r[0] for r in cur.fetchall()]
        conn.close()
        record(name, len(stables) > 0, f"{len(stables)} super tables")
    except Exception as exc:
        record(name, False, f"{type(exc).__name__}: {str(exc)[:80]}")


def main():
    print(f"=== 数据源连通性测试 {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    t0 = time.time()
    test_baostock()
    test_eastmoney_daily()
    test_eastmoney_5min()
    test_sina_5min()
    test_tencent_quote()
    test_postgres()
    test_tdengine()
    elapsed = time.time() - t0
    ok = sum(1 for _, s, _ in results if s == "OK ")
    print(f"\n=== 结果: {ok}/{len(results)} 可用, 耗时 {elapsed:.0f}s ===")


if __name__ == "__main__":
    main()
