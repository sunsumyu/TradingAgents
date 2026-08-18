# TradingAgents/graph/propagation.py

from typing import Any

from tradingagents.agents.utils.agent_states import (
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.markets.detector import detect_market_type


class Propagator:
    """Handles state initialization and propagation through the graph."""

    def __init__(self, max_recur_limit=100):
        """Initialize with configuration parameters."""
        self.max_recur_limit = max_recur_limit

    def create_initial_state(
        self,
        company_name: str,
        trade_date: str,
        asset_type: str = "stock",
        past_context: str = "",
        instrument_context: str = "",
    ) -> dict[str, Any]:
        """Create the initial state for the agent graph.

        ``instrument_context`` is the deterministic ticker-identity string
        resolved once at run start (see
        ``TradingAgentsGraph.resolve_instrument_context``). When empty, agents
        fall back to ticker-only context via
        ``get_instrument_context_from_state``.
        """
        return {
            "messages": [("human", company_name)],
            "company_of_interest": company_name,
            "asset_type": asset_type,
            "instrument_context": instrument_context,
            "trade_date": str(trade_date),
            "past_context": past_context,
            "investment_debate_state": InvestDebateState(
                {
                    "bull_history": "",
                    "bear_history": "",
                    "history": "",
                    "current_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "risk_debate_state": RiskDebateState(
                {
                    "aggressive_history": "",
                    "conservative_history": "",
                    "neutral_history": "",
                    "history": "",
                    "latest_speaker": "",
                    "current_aggressive_response": "",
                    "current_conservative_response": "",
                    "current_neutral_response": "",
                    "judge_decision": "",
                    "count": 0,
                }
            ),
            "market_report": "",
            "fundamentals_report": "",
            "sentiment_report": "",
            "news_report": "",
        }

    def get_graph_args(self, callbacks: list | None = None) -> dict[str, Any]:
        """Get arguments for the graph invocation.

        Args:
            callbacks: Optional list of callback handlers for tool execution tracking.
                       Note: LLM callbacks are handled separately via LLM constructor.
        """
        config = {"recursion_limit": self.max_recur_limit}
        if callbacks:
            config["callbacks"] = callbacks
        return {
            "stream_mode": "values",
            "config": config,
        }

    def resolve_market_type(self, ticker: str, market_type: str = "auto") -> str:
        """Resolve market type from ticker when config says 'auto'.

        When ``market_type`` is ``"auto"`` (the default), delegates to
        :func:`~tradingagents.markets.detector.detect_market_type`.  Any
        other value is returned unchanged so explicit overrides always win.
        """
        if market_type == "auto":
            return detect_market_type(ticker, fix_astock=True)
        return market_type

    def apply_astock_config_overrides(self, config: dict) -> None:
        """Apply A-share specific config overrides in-place.

        Switches ``data_vendors`` to ``"a_stock"`` for all data categories
        and sets ``output_language`` to ``"Chinese"`` when it was English.
        Only meaningful when ``market_type`` is ``"astock"`` — callers
        should gate on that before calling.
        """
        config["data_vendors"] = {
            "core_stock_apis": "a_stock",
            "technical_indicators": "a_stock",
            "fundamental_data": "a_stock",
            "news_data": "a_stock",
            "signal_data": "a_stock",
        }
        if config.get("output_language") == "English":
            config["output_language"] = "Chinese"

    def create_initial_state_with_market_detection(
        self,
        company_name: str,
        trade_date: str,
        market_type: str = "auto",
        asset_type: str = "stock",
        past_context: str = "",
        instrument_context: str = "",
    ) -> dict[str, Any]:
        """Create initial state with ``market_type`` injected.

        Delegates to :meth:`create_initial_state` for the standard fields,
        then resolves the market type (auto-detecting when ``"auto"``) and
        injects ``market_type`` into the returned dict.
        """
        resolved = self.resolve_market_type(company_name, market_type)
        state = self.create_initial_state(
            company_name,
            trade_date,
            asset_type=asset_type,
            past_context=past_context,
            instrument_context=instrument_context,
        )
        state["market_type"] = resolved
        return state
