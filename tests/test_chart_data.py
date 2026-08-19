"""Tests for chart data parsing utilities, schema models, and build_chart_data."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tradingagents_api.chart_data import (
    _is_astock_ticker,
    _parse_fund_flow_text,
    _parse_northbound_text,
    build_chart_data,
    parse_indicator_bundle,
    parse_indicator_text,
    parse_ohlcv_csv,
)
from tradingagents_api.schemas import (
    BollingerData,
    ChartData,
    DashboardData,
    DimensionScore,
    FundFlowData,
    KlineData,
    MacdData,
    ReportResponse,
    RsiData,
)


# ---------------------------------------------------------------------------
# parse_ohlcv_csv
# ---------------------------------------------------------------------------

class TestParseOhlcvCsv:
    VALID_CSV = (
        "# Stock data for AAPL from 2026-07-01 to 2026-07-05\n"
        "# Total records: 3\n"
        "# Data retrieved on: 2026-07-05 10:00:00\n"
        "\n"
        "Date,Open,High,Low,Close,Adj Close,Volume\n"
        "2026-07-01,150.50,152.00,149.80,151.25,151.25,1234567\n"
        "2026-07-02,151.25,153.00,150.50,152.80,152.80,1345678\n"
        "2026-07-03,152.80,154.00,151.00,153.50,153.50,1456789\n"
    )

    def test_parses_valid_csv(self):
        records = parse_ohlcv_csv(self.VALID_CSV)
        assert len(records) == 3
        assert records[0]["date"] == "2026-07-01"
        assert records[0]["open"] == 150.50
        assert records[0]["high"] == 152.00
        assert records[0]["low"] == 149.80
        assert records[0]["close"] == 151.25
        assert records[0]["volume"] == 1234567.0

    def test_extracts_all_dates(self):
        records = parse_ohlcv_csv(self.VALID_CSV)
        dates = [r["date"] for r in records]
        assert dates == ["2026-07-01", "2026-07-02", "2026-07-03"]

    def test_empty_input(self):
        assert parse_ohlcv_csv("") == []

    def test_only_comments(self):
        assert parse_ohlcv_csv("# just a comment\n# another comment\n") == []

    def test_skips_malformed_rows(self):
        csv = (
            "Date,Open,High,Low,Close,Adj Close,Volume\n"
            "2026-07-01,150.50,152.00,149.80,151.25,151.25,1234567\n"
            "bad-row\n"
            "2026-07-02,151.25,153.00,150.50,152.80,152.80,1345678\n"
        )
        records = parse_ohlcv_csv(csv)
        assert len(records) == 2

    def test_numeric_values_are_floats(self):
        records = parse_ohlcv_csv(self.VALID_CSV)
        for key in ("open", "high", "low", "close", "adj_close", "volume"):
            assert isinstance(records[0][key], float)


# ---------------------------------------------------------------------------
# parse_indicator_text
# ---------------------------------------------------------------------------

class TestParseIndicatorText:
    VALID_TEXT = (
        "## rsi values from 2026-07-20 to 2026-07-25:\n"
        "\n"
        "2026-07-25: 55.32\n"
        "2026-07-24: 52.10\n"
        "2026-07-23: N/A: Not a trading day (weekend or holiday)\n"
        "2026-07-22: 48.75\n"
        "2026-07-21: 50.00\n"
        "2026-07-20: 51.23\n"
        "\n"
        "RSI: Measures momentum to flag overbought/oversold conditions. "
        "Usage: Apply 70/30 thresholds.\n"
    )

    def test_parses_valid_text(self):
        result = parse_indicator_text(self.VALID_TEXT)
        assert result["dates"] == [
            "2026-07-25",
            "2026-07-24",
            "2026-07-22",
            "2026-07-21",
            "2026-07-20",
        ]
        assert result["values"] == [55.32, 52.10, 48.75, 50.00, 51.23]

    def test_excludes_na_entries(self):
        result = parse_indicator_text(self.VALID_TEXT)
        assert len(result["dates"]) == 5  # 6 lines minus 1 N/A
        assert all(isinstance(v, float) for v in result["values"])

    def test_empty_input(self):
        result = parse_indicator_text("")
        assert result["dates"] == []
        assert result["values"] == []

    def test_all_na(self):
        text = (
            "2026-07-25: N/A: Not a trading day (weekend or holiday)\n"
            "2026-07-24: N/A: Not a trading day (weekend or holiday)\n"
        )
        result = parse_indicator_text(text)
        assert result["dates"] == []
        assert result["values"] == []

    def test_description_lines_ignored(self):
        text = (
            "2026-07-25: 55.32\n"
            "RSI: Measures momentum to flag overbought/oversold conditions.\n"
            "2026-07-24: 52.10\n"
        )
        result = parse_indicator_text(text)
        assert len(result["dates"]) == 2

    def test_dates_are_strings_values_are_floats(self):
        result = parse_indicator_text(self.VALID_TEXT)
        for d in result["dates"]:
            assert isinstance(d, str)
        for v in result["values"]:
            assert isinstance(v, float)


# ---------------------------------------------------------------------------
# parse_indicator_bundle
# ---------------------------------------------------------------------------

class TestParseIndicatorBundle:
    def test_parses_multiple_indicators(self):
        bundle = {
            "rsi": "2026-07-25: 55.32\n2026-07-24: 52.10\n",
            "macd": "2026-07-25: 0.15\n2026-07-24: -0.05\n",
        }
        result = parse_indicator_bundle(bundle)
        assert "rsi" in result
        assert "macd" in result
        assert result["rsi"]["values"] == [55.32, 52.10]
        assert result["macd"]["values"] == [0.15, -0.05]

    def test_empty_bundle(self):
        assert parse_indicator_bundle({}) == {}


# ---------------------------------------------------------------------------
# Schema models
# ---------------------------------------------------------------------------

class TestChartDataModels:
    def test_kline_data(self):
        kline = KlineData(
            dates=["2026-07-01"],
            ohlc=[(150.0, 151.0, 149.0, 152.0)],
            volumes=[1000000.0],
        )
        assert kline.dates == ["2026-07-01"]
        assert kline.ma5 == []  # default empty

    def test_bollinger_invariant(self):
        """Upper band must be > middle > lower for all dates."""
        boll = BollingerData(
            dates=["2026-07-01"],
            upper=[160.0],
            middle=[150.0],
            lower=[140.0],
            close=[151.0],
        )
        for i in range(len(boll.dates)):
            assert boll.upper[i] > boll.middle[i] > boll.lower[i]

    def test_dashboard_confidence_bounds(self):
        dashboard = DashboardData(signal="Buy", confidence=75.0)
        assert 0 <= dashboard.confidence <= 100

    def test_chart_data_all_optional(self):
        chart = ChartData()
        assert chart.kline is None
        assert chart.macd is None
        assert chart.rsi is None
        assert chart.bollinger is None
        assert chart.dashboard is None
        assert chart.fundFlow is None

    def test_chart_data_partial(self):
        chart = ChartData(
            dashboard=DashboardData(signal="Hold", confidence=60.0),
        )
        assert chart.kline is None
        assert chart.dashboard is not None
        assert chart.dashboard.signal == "Hold"


# ---------------------------------------------------------------------------
# ReportResponse serialization
# ---------------------------------------------------------------------------

class TestReportResponseChartData:
    def test_chart_data_none_by_default(self):
        resp = ReportResponse(
            ticker="AAPL",
            signal="Buy",
            report_md="# Report",
        )
        assert resp.chart_data is None

    def test_chart_data_serialization_roundtrip(self):
        chart = ChartData(
            kline=KlineData(
                dates=["2026-07-01"],
                ohlc=[(150.0, 151.0, 149.0, 152.0)],
                volumes=[1000000.0],
            ),
            dashboard=DashboardData(signal="Sell", confidence=80.0),
        )
        resp = ReportResponse(
            ticker="AAPL",
            signal="Sell",
            report_md="# Report",
            chart_data=chart,
        )
        # Serialize to dict and back
        data = resp.model_dump()
        resp2 = ReportResponse.model_validate(data)
        assert resp2.chart_data is not None
        assert resp2.chart_data.kline is not None
        assert resp2.chart_data.kline.dates == ["2026-07-01"]
        assert resp2.chart_data.dashboard.signal == "Sell"

    def test_json_omits_none_chart_data(self):
        resp = ReportResponse(
            ticker="AAPL",
            signal="Hold",
            report_md="# Report",
        )
        data = resp.model_dump()
        # chart_data should be None, which serializes as null in JSON
        assert data["chart_data"] is None


# ---------------------------------------------------------------------------
# build_chart_data (with mocked vendor APIs)
# ---------------------------------------------------------------------------

_SAMPLE_OHLCV_CSV = (
    "# Stock data for AAPL from 2026-06-01 to 2026-08-19\n"
    "# Total records: 5\n"
    "# Data retrieved on: 2026-08-19 10:00:00\n"
    "\n"
    "Date,Open,High,Low,Close,Adj Close,Volume\n"
    "2026-08-13,150.00,152.00,149.00,151.00,151.00,1000000\n"
    "2026-08-14,151.00,153.00,150.00,152.00,152.00,1100000\n"
    "2026-08-15,152.00,154.00,151.00,153.00,153.00,1200000\n"
    "2026-08-16,153.00,155.00,152.00,154.00,154.00,1300000\n"
    "2026-08-19,154.00,156.00,153.00,155.00,155.00,1400000\n"
)

_SAMPLE_RSI = (
    "## rsi values from 2026-08-01 to 2026-08-19:\n"
    "\n"
    "2026-08-19: 55.32\n"
    "2026-08-18: N/A: Not a trading day (weekend or holiday)\n"
    "2026-08-17: N/A: Not a trading day (weekend or holiday)\n"
    "2026-08-16: 52.10\n"
    "2026-08-15: 48.75\n"
    "\n"
    "RSI: Measures momentum to flag overbought/oversold conditions.\n"
)

_SAMPLE_MACD = (
    "## macd values from 2026-08-01 to 2026-08-19:\n\n"
    "2026-08-19: 0.15\n2026-08-16: 0.10\n2026-08-15: -0.05\n\n"
    "MACD: Computes momentum.\n"
)
_SAMPLE_MACDS = (
    "## macds values from 2026-08-01 to 2026-08-19:\n\n"
    "2026-08-19: 0.12\n2026-08-16: 0.08\n2026-08-15: -0.02\n\n"
    "MACD Signal.\n"
)
_SAMPLE_MACDH = (
    "## macdh values from 2026-08-01 to 2026-08-19:\n\n"
    "2026-08-19: 0.03\n2026-08-16: 0.02\n2026-08-15: -0.03\n\n"
    "MACD Histogram.\n"
)
_SAMPLE_BOLL = (
    "## boll values from 2026-08-01 to 2026-08-19:\n\n"
    "2026-08-19: 153.00\n2026-08-16: 152.50\n2026-08-15: 152.00\n\n"
    "Bollinger Middle.\n"
)
_SAMPLE_BOLL_UB = (
    "## boll_ub values from 2026-08-01 to 2026-08-19:\n\n"
    "2026-08-19: 160.00\n2026-08-16: 159.00\n2026-08-15: 158.00\n\n"
    "Bollinger Upper.\n"
)
_SAMPLE_BOLL_LB = (
    "## boll_lb values from 2026-08-01 to 2026-08-19:\n\n"
    "2026-08-19: 146.00\n2026-08-16: 146.00\n2026-08-15: 146.00\n\n"
    "Bollinger Lower.\n"
)


def _mock_route_to_vendor(tool_name: str, *args: str) -> str:
    """Mock route_to_vendor that returns sample data."""
    if tool_name == "get_stock_data":
        return _SAMPLE_OHLCV_CSV
    indicator = args[1] if len(args) > 1 else ""
    mapping = {
        "rsi": _SAMPLE_RSI,
        "macd": _SAMPLE_MACD,
        "macds": _SAMPLE_MACDS,
        "macdh": _SAMPLE_MACDH,
        "boll": _SAMPLE_BOLL,
        "boll_ub": _SAMPLE_BOLL_UB,
        "boll_lb": _SAMPLE_BOLL_LB,
    }
    return mapping.get(indicator, "")


class TestBuildChartData:
    """Tests for build_chart_data with mocked vendor APIs."""

    @patch("tradingagents_api.chart_data._fetch_ohlcv")
    @patch("tradingagents_api.chart_data._fetch_indicator")
    def test_full_chart_data(self, mock_indicator, mock_ohlcv):
        mock_ohlcv.return_value = _SAMPLE_OHLCV_CSV
        mock_indicator.side_effect = lambda sym, ind, date, days=30: {
            "rsi": _SAMPLE_RSI,
            "macd": _SAMPLE_MACD,
            "macds": _SAMPLE_MACDS,
            "macdh": _SAMPLE_MACDH,
            "boll": _SAMPLE_BOLL,
            "boll_ub": _SAMPLE_BOLL_UB,
            "boll_lb": _SAMPLE_BOLL_LB,
        }.get(ind, "")

        state = {
            "final_trade_decision": "**Rating**: Buy\n**Executive Summary**: Bullish.",
            "market_report": "RSI trend MACD analysis",
            "sentiment_report": "**Overall Sentiment:** **Bullish** (Score: 7/10)\n**Confidence:** high",
        }
        chart = build_chart_data(state, "AAPL", "2026-08-19")
        assert chart is not None
        assert chart.kline is not None
        assert len(chart.kline.dates) == 5
        assert chart.macd is not None
        assert chart.rsi is not None
        assert chart.bollinger is not None
        assert chart.dashboard is not None
        assert chart.dashboard.signal == "Buy"
        assert chart.dashboard.confidence == 85.0

    @patch("tradingagents_api.chart_data._fetch_ohlcv")
    @patch("tradingagents_api.chart_data._fetch_indicator")
    def test_graceful_degradation_no_ohlcv(self, mock_indicator, mock_ohlcv):
        mock_ohlcv.return_value = None
        mock_indicator.return_value = None

        state = {"final_trade_decision": "**Rating**: Hold"}
        chart = build_chart_data(state, "AAPL", "2026-08-19")
        # Should return None if nothing useful
        assert chart is None

    @patch("tradingagents_api.chart_data._fetch_ohlcv")
    @patch("tradingagents_api.chart_data._fetch_indicator")
    def test_partial_data_kline_only(self, mock_indicator, mock_ohlcv):
        mock_ohlcv.return_value = _SAMPLE_OHLCV_CSV
        mock_indicator.return_value = None

        state = {"final_trade_decision": "**Rating**: Sell"}
        chart = build_chart_data(state, "AAPL", "2026-08-19")
        assert chart is not None
        assert chart.kline is not None
        assert chart.macd is None
        assert chart.rsi is None
        assert chart.dashboard.signal == "Sell"

    @patch("tradingagents_api.chart_data._fetch_ohlcv")
    @patch("tradingagents_api.chart_data._fetch_indicator")
    def test_dashboard_default_signal(self, mock_indicator, mock_ohlcv):
        mock_ohlcv.return_value = _SAMPLE_OHLCV_CSV
        mock_indicator.return_value = None

        state = {"final_trade_decision": "No rating found"}
        chart = build_chart_data(state, "AAPL", "2026-08-19")
        assert chart is not None
        assert chart.dashboard.signal == "Hold"  # default

    @patch("tradingagents_api.chart_data._fetch_ohlcv")
    @patch("tradingagents_api.chart_data._fetch_indicator")
    def test_kline_has_moving_averages(self, mock_indicator, mock_ohlcv):
        mock_ohlcv.return_value = _SAMPLE_OHLCV_CSV
        mock_indicator.return_value = None

        state = {"final_trade_decision": "**Rating**: Hold"}
        chart = build_chart_data(state, "AAPL", "2026-08-19")
        assert chart is not None
        assert chart.kline is not None
        # MA5 should have values for all but first 4 entries
        assert len(chart.kline.ma5) == 5
        assert chart.kline.ma5[0] is None  # not enough data
        assert chart.kline.ma5[1] is None
        assert chart.kline.ma5[2] is None
        assert chart.kline.ma5[3] is None
        assert chart.kline.ma5[4] is not None  # 5 entries available

    @patch("tradingagents_api.chart_data._fetch_ohlcv")
    @patch("tradingagents_api.chart_data._fetch_indicator")
    def test_bollinger_alignment(self, mock_indicator, mock_ohlcv):
        mock_ohlcv.return_value = _SAMPLE_OHLCV_CSV
        mock_indicator.side_effect = lambda sym, ind, date, days=30: {
            "boll": _SAMPLE_BOLL,
            "boll_ub": _SAMPLE_BOLL_UB,
            "boll_lb": _SAMPLE_BOLL_LB,
        }.get(ind, "")

        state = {"final_trade_decision": "**Rating**: Hold"}
        chart = build_chart_data(state, "AAPL", "2026-08-19")
        assert chart is not None
        assert chart.bollinger is not None
        # Upper > middle > lower for all dates
        for i in range(len(chart.bollinger.dates)):
            assert chart.bollinger.upper[i] > chart.bollinger.middle[i] > chart.bollinger.lower[i]

    def test_invalid_date_returns_none(self):
        chart = build_chart_data({}, "AAPL", "not-a-date")
        assert chart is None

    @patch("tradingagents_api.chart_data._fetch_ohlcv")
    @patch("tradingagents_api.chart_data._fetch_indicator")
    def test_sentiment_confidence_mapping(self, mock_indicator, mock_ohlcv):
        mock_ohlcv.return_value = _SAMPLE_OHLCV_CSV
        mock_indicator.return_value = None

        for conf, expected in [("low", 30.0), ("medium", 60.0), ("high", 85.0)]:
            state = {
                "final_trade_decision": "**Rating**: Hold",
                "sentiment_report": f"**Confidence:** {conf}",
            }
            chart = build_chart_data(state, "AAPL", "2026-08-19")
            assert chart.dashboard.confidence == expected

    @patch("tradingagents_api.chart_data._fetch_ohlcv")
    @patch("tradingagents_api.chart_data._fetch_indicator")
    def test_dimension_scores(self, mock_indicator, mock_ohlcv):
        mock_ohlcv.return_value = _SAMPLE_OHLCV_CSV
        mock_indicator.return_value = None

        state = {
            "final_trade_decision": "**Rating**: Hold",
            "market_report": "RSI MACD SMA EMA Bollinger trend momentum",  # 7 keyword matches
            "sentiment_report": "bullish sentiment social reddit",  # 4 keyword matches
            "news_report": "news headline announcement regulatory",  # 4 keyword matches
            "fundamentals_report": "revenue earnings P/E ROE",  # 4 keyword matches
        }
        chart = build_chart_data(state, "AAPL", "2026-08-19")
        assert chart is not None
        assert len(chart.dashboard.scores) == 4
        # Technical should have high score (7 mentions, capped at 10 → 7.0)
        tech_score = next(s for s in chart.dashboard.scores if s.name == "Technical")
        assert tech_score.value == 7.0


# ---------------------------------------------------------------------------
# _is_astock_ticker
# ---------------------------------------------------------------------------


class TestIsAstockTicker:
    def test_six_digit_code(self):
        assert _is_astock_ticker("600519") is True

    def test_six_digit_with_exchange(self):
        assert _is_astock_ticker("SH600519") is False  # has letters

    def test_us_ticker(self):
        assert _is_astock_ticker("AAPL") is False

    def test_four_digit_hk(self):
        assert _is_astock_ticker("00700") is False

    def test_with_dot_suffix(self):
        assert _is_astock_ticker("600519.SH") is True  # splits on "."


# ---------------------------------------------------------------------------
# _parse_fund_flow_text
# ---------------------------------------------------------------------------

_SAMPLE_FUND_FLOW = (
    "# Fund Flow for 600519 (A-stock)\n"
    "# Source: 东财 push2 (Eastmoney)\n"
    "\n"
    "## Historical Daily Fund Flow (last 5 trading days)\n"
    "Date | 主力净流入(万) | 大单(万) | 中单(万) | 小单(万) | 超大单(万)\n"
    "  2026-08-13 | main=1500 | large=800 | mid=-200 | small=-300 | super=700\n"
    "  2026-08-14 | main=-500 | large=-300 | mid=100 | small=200 | super=-200\n"
    "  2026-08-15 | main=2000 | large=1200 | mid=-400 | small=-600 | super=800\n"
    "  2026-08-18 | main=-1000 | large=-600 | mid=300 | small=400 | super=-400\n"
    "  2026-08-19 | main=800 | large=500 | mid=-100 | small=-200 | super=300\n"
)


class TestParseFundFlowText:
    def test_valid_text(self):
        result = _parse_fund_flow_text(_SAMPLE_FUND_FLOW)
        assert len(result["dates"]) == 5
        assert result["dates"][0] == "2026-08-13"
        assert result["dates"][-1] == "2026-08-19"
        # mainForce = main column
        assert result["mainForce"][0] == 1500.0
        assert result["mainForce"][1] == -500.0
        # retail = mid + small
        assert result["retail"][0] == -500.0  # -200 + -300
        assert result["retail"][1] == 300.0  # 100 + 200

    def test_empty_text(self):
        result = _parse_fund_flow_text("")
        assert result["dates"] == []
        assert result["mainForce"] == []
        assert result["retail"] == []


# ---------------------------------------------------------------------------
# _parse_northbound_text
# ---------------------------------------------------------------------------

_SAMPLE_NORTHBOUND = (
    "# Northbound Capital Flow (2026-08-19)\n"
    "# Source: 同花顺 hsgtApi (沪深股通) + local cache\n"
    "\n"
    "## Historical Daily Close (local cache, 亿元)\n"
    "Date       | HGT(沪股通) | SGT(深股通) | Total\n"
    "  2026-08-13: HGT=12.50 SGT=8.30 Total=20.80\n"
    "  2026-08-14: HGT=-5.20 SGT=-3.10 Total=-8.30\n"
    "  2026-08-15: HGT=20.00 SGT=15.00 Total=35.00\n"
)


class TestParseNorthboundText:
    def test_valid_text(self):
        result = _parse_northbound_text(_SAMPLE_NORTHBOUND)
        assert len(result["dates"]) == 3
        assert result["dates"][0] == "2026-08-13"
        # HGT + SGT
        assert result["values"][0] == 20.80  # 12.50 + 8.30
        assert result["values"][1] == -8.30  # -5.20 + -3.10
        assert result["values"][2] == 35.00  # 20.00 + 15.00

    def test_empty_text(self):
        result = _parse_northbound_text("")
        assert result["dates"] == []
        assert result["values"] == []
