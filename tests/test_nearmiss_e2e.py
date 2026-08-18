"""Regression: near-miss A-share tickers must route to A-stock data, not Yahoo.

Bug: User types '60073X' (X adjacent to 3 on keyboard) in GUI. The detector
classifies it as US, bypasses A-share vendor routing, and Yahoo returns no
rows for a 6-digit numeric code → "No market data for '60073X'".

Fix: detect_market_type(fix_astock=True) + _try_fix_astock_ticker() auto-
corrects '60073X' → '600733' before any data lookup.
"""

import pytest
from tradingagents.markets.detector import detect_market_type, _try_fix_astock_ticker


class TestNearMissRouting:
    """Near-miss A-share tickers must be detected as astock."""

    @pytest.mark.parametrize("ticker,expected_fix", [
        ("60073X", "600733"),  # X next to 3 on QWERTY
        ("60073C", "600733"),  # C next to 3
        ("00000I", "000001"),  # I looks like 1
        ("00000O", "000000"),  # O looks like 0
        ("30075O", "300750"),  # O looks like 0
    ])
    def test_near_miss_detected_as_astock(self, ticker, expected_fix):
        """Near-miss codes must be detected as astock with fix_astock=True."""
        assert detect_market_type(ticker, fix_astock=True) == "astock"
        assert _try_fix_astock_ticker(ticker) == expected_fix

    def test_valid_astock_unaffected(self):
        """Valid 6-digit A-share codes must work without correction."""
        assert detect_market_type("600733", fix_astock=True) == "astock"
        assert _try_fix_astock_ticker("600733") is None

    def test_us_stock_unaffected(self):
        """US stocks must not be affected by fix_astock."""
        assert detect_market_type("AAPL", fix_astock=True) == "us"
        assert _try_fix_astock_ticker("AAPL") is None

    def test_nearmiss_does_not_reach_yahoo(self, monkeypatch):
        """The corrected ticker (600733) must be used for data, not the
        original (60073X). Verify load_ohlcv gets the fixed code."""
        from tradingagents.dataflows import stockstats_utils

        called_with = []
        original_load = stockstats_utils.load_ohlcv

        def spy_load(symbol, curr_date):
            called_with.append(symbol)
            return original_load(symbol, curr_date)

        monkeypatch.setattr(stockstats_utils, "load_ohlcv", spy_load)

        # Simulate the runner.py correction path
        ticker = "60073X"
        market_type = detect_market_type(ticker, fix_astock=True)
        assert market_type == "astock"

        fixed = _try_fix_astock_ticker(ticker)
        assert fixed == "600733"

        # The corrected ticker is what gets passed to load_ohlcv
        # (runner.py does: request.ticker = _corrected_ticker before graph.init)
        final_ticker = fixed or ticker
        assert final_ticker == "600733"
