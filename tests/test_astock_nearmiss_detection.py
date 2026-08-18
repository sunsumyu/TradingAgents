"""Regression tests for near-miss A-share ticker detection.

The GUI sends user input as-is; common typos like "60073X" (X next to 3 on
QWERTY) should be detected as an A-share near-miss and auto-corrected to
the valid 6-digit code "600733".
"""

import pytest

from tradingagents.markets.detector import (
    detect_market_type,
    normalize_astock_ticker,
    _try_fix_astock_ticker,
)


class TestTryFixAstockTicker:
    """_try_fix_astock_ticker should correct common near-miss A-share codes."""

    @pytest.mark.parametrize(
        "input_ticker,expected",
        [
            ("60073X", "600733"),  # X next to 3
            ("60073C", "600733"),  # C next to 3
            ("00000I", "000001"),  # I looks like 1
            ("00000O", "000000"),  # O looks like 0
            ("30075O", "300750"),  # O looks like 0
            ("00085Z", "000852"),  # Z looks like 2
        ],
    )
    def test_near_miss_corrections(self, input_ticker: str, expected: str):
        result = _try_fix_astock_ticker(input_ticker)
        assert result == expected, f"{input_ticker!r} should fix to {expected!r}, got {result!r}"

    @pytest.mark.parametrize(
        "input_ticker",
        [
            "600733",   # Already valid — no fix needed
            "000001",   # Already valid
            "AAPL",     # 4 letters, not 6 chars
            "MSFT",     # 4 letters
            "60073",    # 5 chars
            "6007333",  # 7 chars
            "",         # Empty
            "abcdef",   # 6 letters — too many to be a typo
        ],
    )
    def test_no_fix_needed(self, input_ticker: str):
        result = _try_fix_astock_ticker(input_ticker)
        assert result is None, f"{input_ticker!r} should not be fixed, got {result!r}"


class TestDetectMarketTypeNearMiss:
    """detect_market_type with fix_astock=True should catch near-miss codes."""

    def test_valid_astock_unchanged(self):
        assert detect_market_type("600733") == "astock"
        assert detect_market_type("600733", fix_astock=True) == "astock"

    def test_near_miss_detected_with_fix(self):
        assert detect_market_type("60073X") == "us"
        assert detect_market_type("60073X", fix_astock=True) == "astock"

    def test_us_stock_unaffected(self):
        assert detect_market_type("AAPL", fix_astock=True) == "us"
        assert detect_market_type("MSFT", fix_astock=True) == "us"

    def test_hk_stock_unaffected(self):
        assert detect_market_type("0700.HK", fix_astock=True) == "hk"

    def test_crypto_unaffected(self):
        assert detect_market_type("BTC-USD", fix_astock=True) == "crypto"

    def test_suffix_astock_unchanged(self):
        assert detect_market_type("600733.SS", fix_astock=True) == "astock"
