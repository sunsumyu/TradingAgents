"""Tool wiring registry — maps analyst names to their tool sets.

Pure data: no state, no I/O, no side effects.  Extracted from
``TradingAgentsGraph._create_tool_nodes`` to separate the static
tool declarations from the orchestration that consumes them.

Design: **Registry pattern** — a dict of analyst-name -> list-of-tool-functions.
The ``ToolNode`` construction (LangGraph-specific) stays in the graph layer;
this module only declares which tools each analyst may call.
"""

from __future__ import annotations

from tradingagents.agents.utils.agent_utils import (
    get_balance_sheet,
    get_cashflow,
    get_chip_distribution,
    get_concept_blocks,
    get_dragon_tiger_board,
    get_fund_flow,
    get_fundamentals,
    get_global_news,
    get_hot_stocks,
    get_income_statement,
    get_indicators,
    get_industry_comparison,
    get_insider_transactions,
    get_lockup_expiry,
    get_macro_indicators,
    get_news,
    get_northbound_flow,
    get_prediction_markets,
    get_profit_forecast,
    get_stock_data,
    get_verified_market_snapshot,
)


# ── Analyst tool registry ─────────────────────────────────────────────────────
#
# Each key is an analyst identifier; the value is the list of tool functions
# that analyst is allowed to invoke.  Adding a new analyst means adding one
# entry here — no changes to the graph orchestration code.

ANALYST_TOOLS: dict[str, list] = {
    # ── US / global analysts ─────────────────────────────────────────────
    "market": [
        get_stock_data,
        get_indicators,
        get_verified_market_snapshot,
    ],
    "social": [
        get_news,
    ],
    "news": [
        get_news,
        get_global_news,
        get_insider_transactions,
        get_macro_indicators,
        get_prediction_markets,
    ],
    "fundamentals": [
        get_fundamentals,
        get_balance_sheet,
        get_cashflow,
        get_income_statement,
    ],
    # ── A-share analysts ─────────────────────────────────────────────────
    "policy": [
        get_news,
        get_global_news,
    ],
    "hot_money": [
        get_stock_data,
        get_news,
        get_insider_transactions,
        get_hot_stocks,
        get_northbound_flow,
        get_concept_blocks,
        get_fund_flow,
        get_dragon_tiger_board,
        get_industry_comparison,
    ],
    "lockup": [
        get_insider_transactions,
        get_news,
        get_fundamentals,
        get_lockup_expiry,
        get_chip_distribution,
    ],
    # ── Research / debate analysts ────────────────────────────────────────
    "research": [],  # uses LLM only, no data tools
    "research_manager": [],
    "trader": [],
    "risk": [],
    "portfolio": [],
}


def get_analyst_tool_names(analyst: str) -> list[str]:
    """Return the function names for an analyst's tools (for diagnostics)."""
    return [fn.__name__ for fn in ANALYST_TOOLS.get(analyst, [])]
