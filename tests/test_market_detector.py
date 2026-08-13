import pytest
from tradingagents.markets.detector import detect_market_type, normalize_astock_ticker


class TestDetectMarketType:
    def test_pure_6digit_is_astock(self):
        assert detect_market_type("600519") == "astock"

    def test_600_is_astock(self):
        assert detect_market_type("000001") == "astock"

    def test_ss_suffix_is_astock(self):
        assert detect_market_type("600519.SS") == "astock"

    def test_sz_suffix_is_astock(self):
        assert detect_market_type("000001.SZ") == "astock"

    def test_hk_suffix(self):
        assert detect_market_type("0700.HK") == "hk"

    def test_usd_suffix_is_crypto(self):
        assert detect_market_type("BTC-USD") == "crypto"

    def test_pure_letters_is_us(self):
        assert detect_market_type("NVDA") == "us"

    def test_us_with_dot_suffix(self):
        assert detect_market_type("BRK.B") == "us"

    def test_short_code_defaults_us(self):
        # 3-digit codes are ambiguous, default to us
        assert detect_market_type("123") == "us"


class TestNormalizeAstockTicker:
    def test_strip_ss_suffix(self):
        assert normalize_astock_ticker("600519.SS") == "600519"

    def test_strip_sz_suffix(self):
        assert normalize_astock_ticker("000001.SZ") == "000001"

    def test_pure_digits_unchanged(self):
        assert normalize_astock_ticker("600519") == "600519"

    def test_lowercase_sh_prefix(self):
        assert normalize_astock_ticker("sh600519") == "600519"

    def test_lowercase_sz_prefix(self):
        assert normalize_astock_ticker("sz000001") == "000001"
