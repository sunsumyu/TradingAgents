"""Log graph state to disk as JSON.

Extracted from TradingAgentsGraph._log_state to follow SRP:
the God Class should not manage JSON serialization paths.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from tradingagents.dataflows.utils import safe_ticker_component

logger = logging.getLogger(__name__)


def log_state(trade_date, final_state, ticker: str, config: dict, log_states_dict: dict) -> None:
    """Log the final state to a JSON file.

    Args:
        trade_date: The trade date string (YYYY-MM-DD).
        final_state: The final graph state dict.
        ticker: The ticker symbol.
        config: The full TradingAgents config dict.
        log_states_dict: Mutable dict keyed by date — updated in place.
    """
    log_states_dict[str(trade_date)] = {
        "company_of_interest": final_state["company_of_interest"],
        "trade_date": final_state["trade_date"],
        "market_report": final_state["market_report"],
        "sentiment_report": final_state["sentiment_report"],
        "news_report": final_state["news_report"],
        "fundamentals_report": final_state["fundamentals_report"],
        # A-share analyst reports; empty strings for non-A-share runs.
        "policy_report": final_state.get("policy_report", ""),
        "hot_money_report": final_state.get("hot_money_report", ""),
        "lockup_report": final_state.get("lockup_report", ""),
        "investment_debate_state": {
            "bull_history": final_state["investment_debate_state"]["bull_history"],
            "bear_history": final_state["investment_debate_state"]["bear_history"],
            "history": final_state["investment_debate_state"]["history"],
            "current_response": final_state["investment_debate_state"][
                "current_response"
            ],
            "judge_decision": final_state["investment_debate_state"][
                "judge_decision"
            ],
        },
        "trader_investment_decision": final_state["trader_investment_plan"],
        "risk_debate_state": {
            "aggressive_history": final_state["risk_debate_state"]["aggressive_history"],
            "conservative_history": final_state["risk_debate_state"]["conservative_history"],
            "neutral_history": final_state["risk_debate_state"]["neutral_history"],
            "history": final_state["risk_debate_state"]["history"],
            "judge_decision": final_state["risk_debate_state"]["judge_decision"],
        },
        "investment_plan": final_state["investment_plan"],
        "final_trade_decision": final_state["final_trade_decision"],
    }

    # Save to file.  Reject ticker values that would escape the
    # results directory when joined as a path component.
    safe = safe_ticker_component(ticker)
    directory = Path(config["results_dir"]) / safe / "TradingAgentsStrategy_logs"
    directory.mkdir(parents=True, exist_ok=True)

    log_path = directory / f"full_states_log_{trade_date}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_states_dict[str(trade_date)], f, indent=4)
