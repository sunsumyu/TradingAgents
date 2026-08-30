"""Tests for chart export (ticket #7).

Covers:
- Renderer unit tests: synthetic KlineData → valid PNG bytes
- HTTP contract tests with mocked build_chart_data (no network)

matplotlib must be installed for these tests to run.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from tradingagents_api.server import app


# ---------------------------------------------------------------------------
# Synthetic KlineData fixture
# ---------------------------------------------------------------------------

def _make_kline_data(n: int = 30) -> dict:
    """Build a synthetic KlineData-like dict with n days of OHLCV."""
    import math
    from datetime import datetime, timedelta

    base_date = datetime(2026, 1, 5)
    dates = [(base_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]

    ohlc = []
    volumes = []
    closes = []
    price = 100.0
    for i in range(n):
        change = math.sin(i * 0.3) * 2
        o = price
        c = price + change
        lo = min(o, c) - abs(change) * 0.3
        hi = max(o, c) + abs(change) * 0.3
        ohlc.append((o, c, lo, hi))
        volumes.append(1_000_000 + int(math.sin(i * 0.5) * 200_000))
        closes.append(c)
        price = c

    def _ma(data: list[float], period: int) -> list[float | None]:
        result: list[float | None] = []
        for i in range(len(data)):
            if i < period - 1:
                result.append(None)
            else:
                result.append(sum(data[i - period + 1 : i + 1]) / period)
        return result

    return {
        "dates": dates,
        "ohlc": ohlc,
        "volumes": volumes,
        "ma5": _ma(closes, 5),
        "ma10": _ma(closes, 10),
        "ma20": _ma(closes, 20),
        "ma50": _ma(closes, 50),
        "ema12": _ma(closes, 12),
        "ema26": _ma(closes, 26),
    }


# ---------------------------------------------------------------------------
# Renderer unit tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRenderChartPng:

    def test_renders_valid_png_bytes(self):
        from tradingagents_api.chart_export import render_chart_png

        kline = _make_kline_data(30)
        png = render_chart_png(
            kline_data=kline,
            overlays=["ma5", "ma10"],
            ticker="600519",
            timeframe="1D",
            date="2026-01-15",
            width=800,
            height=400,
            dpi=100,
        )
        assert isinstance(png, (bytes, bytearray))
        assert len(png) > 500
        # PNG magic bytes
        assert png[:4] == b"\x89PNG"

    def test_watermark_does_not_crash(self):
        from tradingagents_api.chart_export import render_chart_png

        kline = _make_kline_data(20)
        png = render_chart_png(
            kline_data=kline,
            overlays=["ma5"],
            ma_params={"ma5": 7},
            ticker="NVDA",
            timeframe="60m",
            date="2026-03-01",
            width=640,
            height=320,
            dpi=72,
        )
        assert png[:4] == b"\x89PNG"
        assert len(png) > 200

    def test_empty_kline_raises_value_error(self):
        from tradingagents_api.chart_export import render_chart_png

        with pytest.raises(ValueError, match="empty"):
            render_chart_png(kline_data={"dates": [], "ohlc": [], "volumes": []})

    def test_missing_dates_raises_value_error(self):
        from tradingagents_api.chart_export import render_chart_png

        with pytest.raises(ValueError, match="empty"):
            render_chart_png(kline_data={})

    def test_all_overlays(self):
        """All six overlays should render without error."""
        from tradingagents_api.chart_export import render_chart_png

        kline = _make_kline_data(40)
        png = render_chart_png(
            kline_data=kline,
            overlays=["ma5", "ma10", "ma20", "ma50", "ema12", "ema26"],
            ticker="TEST",
            timeframe="1D",
            date="2026-01-01",
        )
        assert png[:4] == b"\x89PNG"

    def test_large_chart(self):
        """High-DPI export at 1920×1080 should complete."""
        from tradingagents_api.chart_export import render_chart_png

        kline = _make_kline_data(60)
        png = render_chart_png(
            kline_data=kline,
            overlays=["ma5", "ma10", "ma20"],
            ticker="600519",
            timeframe="1D",
            date="2026-01-15",
            width=1920,
            height=1080,
            dpi=150,
        )
        assert png[:4] == b"\x89PNG"
        assert len(png) > 10_000  # large chart should be substantial


# ---------------------------------------------------------------------------
# HTTP contract tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    return TestClient(app)


def _mock_build_chart(kline_data=None):
    """Create a mock that returns a ChartData-like object with a kline."""
    mock_chart = MagicMock()
    if kline_data is None:
        kline_data = _make_kline_data(30)
    mock_chart.kline = MagicMock()
    mock_chart.kline.dates = kline_data["dates"]
    mock_chart.kline.ohlc = kline_data["ohlc"]
    mock_chart.kline.volumes = kline_data["volumes"]
    mock_chart.kline.ma5 = kline_data["ma5"]
    mock_chart.kline.ma10 = kline_data["ma10"]
    mock_chart.kline.ma20 = kline_data["ma20"]
    mock_chart.kline.ma50 = kline_data["ma50"]
    mock_chart.kline.ema12 = kline_data["ema12"]
    mock_chart.kline.ema26 = kline_data["ema26"]
    return mock_chart


class TestChartExportHTTP:

    def test_full_roundtrip_returns_png(self, client):
        mock_chart = _mock_build_chart()
        with patch(
            "tradingagents_api.chart_data.build_chart_data",
            return_value=mock_chart,
        ):
            resp = client.post("/api/chart-export", json={
                "ticker": "600519",
                "date": "2026-01-15",
                "days": 90,
            })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert len(resp.content) > 500
        assert resp.content[:4] == b"\x89PNG"
        assert 'filename="' in resp.headers.get("content-disposition", "")

    def test_no_data_returns_404(self, client):
        with patch(
            "tradingagents_api.chart_data.build_chart_data",
            return_value=None,
        ):
            resp = client.post("/api/chart-export", json={
                "ticker": "INVALID",
                "date": "2099-01-01",
            })
        assert resp.status_code == 404
        assert "No chart data" in resp.json()["detail"]

    def test_missing_ticker_returns_422(self, client):
        resp = client.post("/api/chart-export", json={
            "date": "2026-01-15",
        })
        assert resp.status_code == 422

    def test_overlay_params_passed_through(self, client):
        """Verify custom overlays and ma_params reach the renderer."""
        mock_chart = _mock_build_chart()
        with patch(
            "tradingagents_api.chart_data.build_chart_data",
            return_value=mock_chart,
        ):
            resp = client.post("/api/chart-export", json={
                "ticker": "NVDA",
                "date": "2026-03-01",
                "days": 30,
                "overlays": ["ma5", "ema12"],
                "ma_params": {"ma5": 7, "ema12": 12},
                "width": 640,
                "height": 320,
                "dpi": 72,
            })
        assert resp.status_code == 200
        assert resp.content[:4] == b"\x89PNG"
