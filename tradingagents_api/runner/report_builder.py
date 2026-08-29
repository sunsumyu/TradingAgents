"""Assemble the final ReportResponse from graph output chunks.

Pure data assembly — no I/O, no side effects.
"""

from __future__ import annotations

import logging

from ..chart_data import build_chart_data
from ..schemas import ReportResponse

logger = logging.getLogger(__name__)


def build_report(
    final_state: dict,
    ticker: str,
    date: str,
    signal: str,
    report_md: str,
    chart=None,
) -> ReportResponse:
    """Build a ReportResponse from the merged graph state.

    Parameters
    ----------
    final_state:
        Merged chunks from ``graph.stream()``.
    ticker / date:
        Used for chart data re-fetch.
    signal:
        Trade signal string ("BUY" / "SELL" / "HOLD").
    report_md:
        Consolidated markdown report from disk.
    chart:
        Pre-built ChartData, or None (will attempt to build).
    """
    sections: dict[str, str] = {}

    # Analyst reports — combined into a single "analyst" section for the
    # GUI's 分析师 tab.
    analyst_sections: list[str] = []
    for report_key, display_name in (
        ("market_report", "Market Analyst"),
        ("sentiment_report", "Sentiment Analyst"),
        ("news_report", "News Analyst"),
        ("fundamentals_report", "Fundamentals Analyst"),
    ):
        content = final_state.get(report_key)
        if content:
            sections[report_key] = content
            analyst_sections.append(f"## {display_name}\n\n{content}")
    if analyst_sections:
        sections["analyst"] = "\n\n".join(analyst_sections)

    # Research debate
    debate = final_state.get("investment_debate_state", {})
    if debate.get("judge_decision"):
        sections["research_decision"] = debate["judge_decision"]

    # Trader plan
    if final_state.get("trader_investment_plan"):
        sections["trader_plan"] = final_state["trader_investment_plan"]

    # Risk debate
    risk = final_state.get("risk_debate_state", {})
    if risk.get("judge_decision"):
        sections["risk_decision"] = risk["judge_decision"]

    # Final decision
    if final_state.get("final_trade_decision"):
        sections["final_decision"] = final_state["final_trade_decision"]

    # Build chart visualization data if not provided
    if chart is None:
        try:
            chart = build_chart_data(final_state, ticker, date)
        except Exception as exc:
            logger.warning("Chart data assembly failed for %s: %s", ticker, exc)

    return ReportResponse(
        ticker=ticker,
        signal=signal,
        report_md=report_md,
        sections=sections,
        chart_data=chart,
    )
