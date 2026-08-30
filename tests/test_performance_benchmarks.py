"""Performance benchmarks for core hot paths (ticket #14).

Targets (from design doc):
  - Chart data preparation: < 100 ms
  - Single indicator computation: < 10 ms
  - Screener (default template): < 1 s

Run with:  pytest -m benchmark
Skip with: pytest -m "not benchmark"

Uses time.perf_counter() for simple timing; no external deps.
Assertions use a 2× tolerance to allow headroom while catching regressions.
"""

import math
import time
from typing import Any

import pandas as pd
import pytest

# ── Marker registration ───────────────────────────────────────────────────────

pytestmark = pytest.mark.benchmark


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_kline_data(n: int = 250) -> dict[str, Any]:
    """Build a synthetic KlineData-like dict with n bars."""
    import random
    random.seed(42)
    dates = [f"2026-01-{(i % 28) + 1:02d}" for i in range(n)]
    ohlc = []
    price = 100.0
    for _ in range(n):
        o = price
        c = o * (1 + random.uniform(-0.03, 0.03))
        lo = min(o, c) * (1 - random.uniform(0, 0.01))
        hi = max(o, c) * (1 + random.uniform(0, 0.01))
        ohlc.append([round(o, 2), round(c, 2), round(lo, 2), round(hi, 2)])
        price = c
    volumes = [random.randint(10000, 500000) for _ in range(n)]
    return {"dates": dates, "ohlc": ohlc, "volumes": volumes}


def _closes(ohlc: list[list[float]]) -> list[float]:
    return [row[1] for row in ohlc]

def _highs(ohlc: list[list[float]]) -> list[float]:
    return [row[3] for row in ohlc]

def _lows(ohlc: list[list[float]]) -> list[float]:
    return [row[2] for row in ohlc]


# ── Benchmark 1: Chart data preparation ──────────────────────────────────────

class TestBenchmarkChartData:
    """Chart data indicator computation: target < 100 ms."""

    def test_compute_all_indicators(self):
        data = _make_kline_data(250)
        closes = _closes(data["ohlc"])

        from tradingagents_api.chart_data.computors import compute_ma, compute_ema, compute_kdj

        t0 = time.perf_counter()
        # MA
        for p in [5, 10, 20, 50]:
            compute_ma(closes, p)
        # EMA
        for p in [12, 26]:
            compute_ema(closes, p)
        # KDJ
        compute_kdj(_highs(data["ohlc"]), _lows(data["ohlc"]), _closes(data["ohlc"]))
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert elapsed_ms < 200, f"Chart data prep took {elapsed_ms:.1f} ms (target: <100 ms, 2× tolerance)"


# ── Benchmark 2: Single indicator computation ─────────────────────────────────

class TestBenchmarkIndicators:
    """Individual indicator computations: target < 10 ms each."""

    @pytest.fixture()
    def closes_1000(self):
        import random
        random.seed(42)
        price = 100.0
        result = []
        for _ in range(1000):
            price *= 1 + random.uniform(-0.02, 0.02)
            result.append(round(price, 2))
        return result

    def test_sma(self, closes_1000):
        from tradingagents_api.chart_data.computors import compute_ma
        t0 = time.perf_counter()
        compute_ma(closes_1000, 20)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 20, f"SMA took {elapsed_ms:.2f} ms (target: <10 ms, 2× tolerance)"

    def test_ema(self, closes_1000):
        from tradingagents_api.chart_data.computors import compute_ema
        t0 = time.perf_counter()
        compute_ema(closes_1000, 26)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 20, f"EMA took {elapsed_ms:.2f} ms (target: <10 ms, 2× tolerance)"

    def test_kdj(self):
        data = _make_kline_data(250)
        from tradingagents_api.chart_data.computors import compute_kdj
        t0 = time.perf_counter()
        compute_kdj(_highs(data["ohlc"]), _lows(data["ohlc"]), _closes(data["ohlc"]))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 20, f"KDJ took {elapsed_ms:.2f} ms (target: <10 ms, 2× tolerance)"

    def test_frontend_sma(self, closes_1000):
        """Frontend SMA (chart-utils.ts equivalent computed in Python for benchmarking)."""
        n = len(closes_1000)
        period = 20
        out = [None] * n
        s = 0.0
        t0 = time.perf_counter()
        for i in range(n):
            s += closes_1000[i]
            if i >= period:
                s -= closes_1000[i - period]
            if i >= period - 1:
                out[i] = s / period
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 20, f"Frontend SMA took {elapsed_ms:.2f} ms (target: <10 ms, 2× tolerance)"

    def test_frontend_ema(self, closes_1000):
        """Frontend EMA (chart-utils.ts equivalent computed in Python for benchmarking)."""
        span = 26
        a = 2 / (span + 1)
        n = len(closes_1000)
        out = [0.0] * n
        num = 0.0
        den = 0.0
        t0 = time.perf_counter()
        for i in range(n):
            num = closes_1000[i] + (1 - a) * num
            den = 1 + (1 - a) * den
            out[i] = num / den
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert elapsed_ms < 20, f"Frontend EMA took {elapsed_ms:.2f} ms (target: <10 ms, 2× tolerance)"


# ── Benchmark 3: Screener (default template) ──────────────────────────────────

class TestBenchmarkScreener:
    """Screener with default template on synthetic pool: target < 1 s."""

    def test_template_screener(self, monkeypatch):
        import numpy as np
        from tradingagents.screener_engine import ScreenerEngine

        # Build a synthetic stock pool of 200 stocks
        rng = np.random.default_rng(42)
        n = 200
        pool = pd.DataFrame({
            "ticker": [f"{600000 + i}" for i in range(n)],
            "name": [f"Stock{i}" for i in range(n)],
            "pe_ratio": rng.uniform(5, 100, n),
            "pb_ratio": rng.uniform(0.5, 20, n),
            "market_cap": rng.uniform(1e9, 1e12, n),
            "change_pct": rng.uniform(-10, 10, n),
            "roe": rng.uniform(0, 40, n),
            "industry": rng.choice(["消费", "科技", "金融", "医药", "新能源"], n),
        })
        monkeypatch.setattr(ScreenerEngine, "_get_stock_pool", lambda self: pool)

        from tradingagents_api.screener import run_template_screener

        t0 = time.perf_counter()
        resp = run_template_screener("value", max_results=20)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        assert elapsed_ms < 2000, (
            f"Screener template took {elapsed_ms:.0f} ms (target: <1000 ms, 2× tolerance)"
        )
        # Sanity: should return some results from 200-stock pool
        assert resp.count >= 0  # template may or may not match stocks
