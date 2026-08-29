"""The verified-market-snapshot path must route A-share tickers away from
Yahoo. yfinance 404s on 6-digit codes and returns nothing usable, so
``load_ohlcv`` delegates A-share symbols to the A-share loader instead of
downloading from Yahoo — otherwise the market analyst's first tool call
fails with "Yahoo Finance returned no rows" and blocks every A-share run.
"""

from unittest import mock

import pandas as pd
import pytest

import tradingagents.dataflows.market_data_validator as validator
import tradingagents.dataflows.stockstats_utils as ss_utils


def _astock_frame():
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-08-13", "2026-08-14"]),
            "Open": [5.4, 5.41],
            "High": [5.5, 5.43],
            "Low": [5.3, 5.20],
            "Close": [5.35, 5.30],
            "Volume": [800_000, 875_210],
        }
    )


@pytest.mark.unit
class TestLoadOhlcvAstockRouting:
    def test_astock_routes_to_astock_loader_not_yahoo(self):
        with mock.patch.object(ss_utils, "yf") as mock_yf, \
                mock.patch(
                    "tradingagents.dataflows.a_stock.load_ohlcv_astock",
                    return_value=_astock_frame(),
                ) as mock_astock:
            df = ss_utils.load_ohlcv("600733", "2026-08-16")
        mock_yf.download.assert_not_called()
        mock_astock.assert_called_once_with("600733", "2026-08-16")
        assert not df.empty and {"Date", "Close"} <= set(df.columns)

    def test_astock_with_suffix_routes_to_astock_loader(self):
        with mock.patch.object(ss_utils, "yf") as mock_yf, \
                mock.patch(
                    "tradingagents.dataflows.a_stock.load_ohlcv_astock",
                    return_value=_astock_frame(),
                ):
            ss_utils.load_ohlcv("600733.SS", "2026-08-16")
        mock_yf.download.assert_not_called()

    def test_us_symbol_still_uses_yahoo(self):
        # A US ticker must NOT be routed to the A-share loader — only the
        # A-share branch redirects; the Yahoo path stays for everything else.
        frame = pd.DataFrame({
            "Date": pd.to_datetime(["2026-08-14", "2026-08-13"]),
            "Open": [1.0, 0.9], "High": [1.1, 1.0], "Low": [0.9, 0.8],
            "Close": [1.05, 0.95], "Volume": [1000, 900],
        })
        with mock.patch.object(ss_utils.yf, "download", return_value=frame), \
                mock.patch("tradingagents.dataflows.a_stock.load_ohlcv_astock") as mock_astock:
            ss_utils.load_ohlcv("NVDA", "2026-08-16")
        mock_astock.assert_not_called()


@pytest.mark.unit
class TestSnapshotAstockRouting:
    def test_snapshot_builder_uses_astock_loader(self, monkeypatch):
        from tradingagents.dataflows.a_stock import load_ohlcv_astock

        monkeypatch.setattr(
            validator, "load_ohlcv", lambda s, d: _astock_frame()
        )
        with mock.patch.object(ss_utils, "yf") as mock_yf:
            snap = validator.build_verified_market_snapshot("600733", "2026-08-16")
        mock_yf.download.assert_not_called()
        assert "Verified market data snapshot for 600733" in snap
        assert "Latest trading row used: 2026-08-14" in snap
        assert "5.30" in snap  # the real A-share close made it through
