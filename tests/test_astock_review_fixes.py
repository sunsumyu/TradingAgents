"""Final review fixes for the A-share integration.

C1: propagate() must not permanently mutate selected_analysts / config when
    an A-share ticker runs (a later US run on the same instance would inherit
    the A-share analysts and data vendors).
I1: write_report_tree writes the A-share analyst reports (policy / hot
    money / lockup) to disk and the consolidated report.
I2: _log_state includes the A-share report keys in the JSON state log.
I3: detect_market_type tolerates None / empty tickers (falls back to "us").
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tradingagents.markets.detector import detect_market_type
from tradingagents.reporting import write_report_tree


def _bare_graph():
    """A TradingAgentsGraph without the heavy __init__ (no LLM construction)."""
    from unittest.mock import MagicMock

    from tradingagents.graph.propagation import Propagator
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    g = object.__new__(TradingAgentsGraph)
    g.selected_analysts = ("market", "social", "news", "fundamentals")
    g.astock_analysts = ("policy", "hot_money", "lockup")
    g.config = {
        "market_type": "auto",
        "output_language": "English",
        "data_vendors": {"core_stock_apis": "yfinance"},
    }
    # Lightweight collaborators propagate() touches (no LLM/graph build).
    g.propagator = Propagator()
    g.graph_setup = MagicMock()
    g._base_workflow = MagicMock()
    g._checkpointer_ctx = None
    return g


_mid_run_state = {}


def _fake_run_graph(self, company_name, trade_date, asset_type="stock"):
    # Record the state visible during the run; never touch the real graph.
    _mid_run_state[company_name] = {
        "selected_analysts": self.selected_analysts,
        "data_vendors": dict(self.config.get("data_vendors") or {}),
        "output_language": self.config.get("output_language"),
    }
    return ({
        "company_of_interest": company_name,
        "market_report": "MKT",
        "sentiment_report": "SENT",
        "news_report": "NEWS",
        "fundamentals_report": "FUND",
        "policy_report": "POLICY",
        "hot_money_report": "HOTMONEY",
        "lockup_report": "LOCKUP",
    }, "BUY")


class TestPropagateStateRestore(unittest.TestCase):
    """C1: A-share overrides are reverted after the run (success or failure)."""

    def _run(self, g, ticker):
        with patch.object(type(g), "_run_graph", _fake_run_graph), patch.object(
            type(g), "_resolve_pending_entries", lambda self, t: None
        ):
            g.propagate(ticker, "2026-04-20")

    def test_us_run_does_not_inherit_astock_state(self):
        g = _bare_graph()
        orig_analysts = g.selected_analysts
        orig_vendors = dict(g.config["data_vendors"])
        orig_language = g.config["output_language"]

        self._run(g, "600519")  # A-share run applies the overrides...
        # DURING the run: A-share analysts and vendors were in effect.
        self.assertIn("policy", _mid_run_state["600519"]["selected_analysts"])
        self.assertEqual(
            _mid_run_state["600519"]["data_vendors"].get("core_stock_apis"), "a_stock"
        )
        self.assertEqual(_mid_run_state["600519"]["output_language"], "Chinese")

        # AFTER the run: originals are restored.
        self.assertEqual(g.selected_analysts, orig_analysts)
        self.assertEqual(g.config["data_vendors"], orig_vendors)
        self.assertEqual(g.config["output_language"], "English")

        # The immediate US run must use the US analysts and vendors.
        self._run(g, "NVDA")
        self.assertEqual(g.selected_analysts, orig_analysts)
        self.assertEqual(g.config["data_vendors"], orig_vendors)

    def test_state_restored_when_run_raises(self):
        g = _bare_graph()
        orig_analysts = g.selected_analysts
        orig_vendors = dict(g.config["data_vendors"])

        def boom(self, *args, **kwargs):
            raise RuntimeError("simulated mid-run crash")

        with patch.object(type(g), "_run_graph", boom), patch.object(
            type(g), "_resolve_pending_entries", lambda self, t: None
        ):
            with self.assertRaises(RuntimeError):
                g.propagate("600519", "2026-04-20")

        self.assertEqual(g.selected_analysts, orig_analysts)
        self.assertEqual(g.config["data_vendors"], orig_vendors)
        self.assertEqual(g.config["output_language"], "English")

    def test_missing_config_keys_restored_to_missing(self):
        # A config without data_vendors / output_language must not gain keys.
        g = _bare_graph()
        del g.config["data_vendors"]
        del g.config["output_language"]
        self._run(g, "600519")
        self.assertNotIn("data_vendors", g.config)
        self.assertNotIn("output_language", g.config)


class TestAStockReportWriting(unittest.TestCase):
    """I1: the report tree includes the A-share analyst sections."""

    def _state(self):
        return {
            "market_report": "MKT",
            "policy_report": "POLICY-RPT",
            "hot_money_report": "HOTMONEY-RPT",
            "lockup_report": "LOCKUP-RPT",
        }

    def test_astock_reports_written_to_disk(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            out = write_report_tree(self._state(), "600519", Path(tmp))
            analysts = Path(tmp) / "1_analysts"
            self.assertEqual(
                (analysts / "policy.md").read_text(encoding="utf-8"), "POLICY-RPT"
            )
            self.assertEqual(
                (analysts / "hot_money.md").read_text(encoding="utf-8"), "HOTMONEY-RPT"
            )
            self.assertEqual(
                (analysts / "lockup.md").read_text(encoding="utf-8"), "LOCKUP-RPT"
            )
            complete = out.read_text(encoding="utf-8")
            self.assertIn("### Policy Analyst", complete)
            self.assertIn("### Hot Money Analyst", complete)
            self.assertIn("### Lockup Analyst", complete)

    def test_us_run_report_tree_unchanged(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            out = write_report_tree(
                {"market_report": "MKT"}, "NVDA", Path(tmp)
            )
            complete = out.read_text(encoding="utf-8")
            self.assertIn("### Market Analyst", complete)
            self.assertNotIn("Policy Analyst", complete)
            analysts = Path(tmp) / "1_analysts"
            self.assertFalse((analysts / "policy.md").exists())


class TestLogStateAStockFields(unittest.TestCase):
    """I2: _log_state includes the A-share report keys."""

    def test_astock_keys_logged(self):
        import tempfile
        from pathlib import Path

        from tradingagents.graph.trading_graph import TradingAgentsGraph

        g = object.__new__(TradingAgentsGraph)
        g.log_states_dict = {}
        g.ticker = "600519"
        with tempfile.TemporaryDirectory() as tmp:
            g.config = {"results_dir": tmp}
            g._log_state(
                "2026-04-20",
                {
                    "company_of_interest": "600519",
                    "trade_date": "2026-04-20",
                    "market_report": "MKT",
                    "sentiment_report": "",
                    "news_report": "",
                    "fundamentals_report": "",
                    "policy_report": "POLICY-RPT",
                    "hot_money_report": "HOTMONEY-RPT",
                    "lockup_report": "LOCKUP-RPT",
                    "investment_debate_state": {
                        "bull_history": "",
                        "bear_history": "",
                        "history": "",
                        "current_response": "",
                        "judge_decision": "",
                    },
                    "trader_investment_plan": "",
                    "risk_debate_state": {
                        "aggressive_history": "",
                        "conservative_history": "",
                        "neutral_history": "",
                        "history": "",
                        "judge_decision": "",
                    },
                    "investment_plan": "",
                    "final_trade_decision": "",
                },
            )
            logged = g.log_states_dict["2026-04-20"]
            self.assertEqual(logged["policy_report"], "POLICY-RPT")
            self.assertEqual(logged["hot_money_report"], "HOTMONEY-RPT")
            self.assertEqual(logged["lockup_report"], "LOCKUP-RPT")
            log_file = (
                Path(tmp) / "600519" / "TradingAgentsStrategy_logs"
                / "full_states_log_2026-04-20.json"
            )
            self.assertTrue(log_file.exists())

    def test_us_run_logs_empty_astock_keys(self):
        import tempfile

        from tradingagents.graph.trading_graph import TradingAgentsGraph

        g = object.__new__(TradingAgentsGraph)
        g.log_states_dict = {}
        g.ticker = "NVDA"
        g.config = {"results_dir": tempfile.mkdtemp()}
        g._log_state(
            "2026-04-20",
            {
                "company_of_interest": "NVDA",
                "trade_date": "2026-04-20",
                "market_report": "MKT",
                "sentiment_report": "",
                "news_report": "",
                "fundamentals_report": "",
                "investment_debate_state": {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
                    "judge_decision": "",
                },
                "trader_investment_plan": "",
                "risk_debate_state": {
                    "aggressive_history": "",
                    "conservative_history": "",
                    "neutral_history": "",
                    "history": "",
                    "judge_decision": "",
                },
                "investment_plan": "",
                "final_trade_decision": "",
            },
        )
        logged = g.log_states_dict["2026-04-20"]
        self.assertEqual(logged["policy_report"], "")
        self.assertEqual(logged["hot_money_report"], "")
        self.assertEqual(logged["lockup_report"], "")


class TestDetectMarketTypeGuard(unittest.TestCase):
    """I3: None / empty / whitespace tickers fall back to "us"."""

    def test_none_returns_us(self):
        self.assertEqual(detect_market_type(None), "us")

    def test_empty_returns_us(self):
        self.assertEqual(detect_market_type(""), "us")

    def test_whitespace_returns_us(self):
        self.assertEqual(detect_market_type("   "), "us")

    def test_stripping_still_works(self):
        self.assertEqual(detect_market_type("  600519  "), "astock")


if __name__ == "__main__":
    unittest.main()
