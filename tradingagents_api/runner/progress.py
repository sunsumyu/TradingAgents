"""Progress detection and heartbeat logic for analysis tasks.

Inspects streaming chunks emitted by the LangGraph pipeline and converts
them into ``ProgressEvent``s that the SSE endpoint streams to the GUI.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from .task_state import TaskState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ANALYST_REPORT_KEYS = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
    # A-share analysts
    "policy": "policy_report",
    "hot_money": "hot_money_report",
    "lockup": "lockup_report",
}

ANTHROPOLOGIST_NAMES = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
    # A-share analysts
    "policy": "Policy Analyst",
    "hot_money": "Hot Money Analyst",
    "lockup": "Lockup Analyst",
}

# Ordered pipeline phases for progress tracking
PIPELINE_PHASES = [
    ("analysts", "Analyst Team"),
    ("research", "Research Team"),
    ("trading", "Trading Team"),
    ("risk", "Risk Management"),
    ("portfolio", "Portfolio Management"),
]


# ---------------------------------------------------------------------------
# Analyst completion helpers
# ---------------------------------------------------------------------------

def is_analyst_completed(task: TaskState, agent_name: str) -> bool:
    """Check if an analyst already has a 'completed' event."""
    return any(
        e.agent == agent_name and e.status == "completed"
        for e in task.events
    )


def emit_next_agent(task: TaskState, selected_analysts: list[str],
                     completed_agent_key: str | None = None):
    """Emit an ``in_progress`` event for the next analyst that hasn't started.

    *completed_agent_key* is the short key (``"market"`` etc.) of the analyst
    that just finished.  When *None*, this is the initial call before any
    analyst has completed (used to mark the very first analyst as in_progress).
    """
    skip_agent = (
        ANTHROPOLOGIST_NAMES.get(completed_agent_key, completed_agent_key)
        if completed_agent_key
        else None
    )
    for analyst_key in selected_analysts:
        agent_name = ANTHROPOLOGIST_NAMES.get(analyst_key, analyst_key)
        if agent_name == skip_agent:
            continue  # don't re-emit for the agent that just completed
        if is_analyst_completed(task, agent_name):
            continue  # already completed — skip
        task.add_event("analysts", agent_name, "in_progress",
                       f"⏳ {agent_name} 正在分析…")
        break  # only emit for the next pending analyst


# ---------------------------------------------------------------------------
# Chunk-based progress detection
# ---------------------------------------------------------------------------

def detect_progress(task: TaskState, chunk: dict, selected_analysts: list[str]):
    """Inspect a streaming chunk and emit ProgressEvents for newly appeared content.

    Only emits "completed" events based on chunk content.  "in_progress" events
    are emitted exclusively by the callback handler (on_chat_model_start).
    """

    # -- Analyst reports --
    for analyst_key in selected_analysts:
        report_key = ANALYST_REPORT_KEYS.get(analyst_key)
        if report_key and chunk.get(report_key):
            agent_name = ANTHROPOLOGIST_NAMES.get(analyst_key, analyst_key)
            task.add_event(
                "analysts",
                agent_name,
                "completed",
                f"{agent_name} report completed",
            )

    # -- Investment debate / Research team --
    debate = chunk.get("investment_debate_state")
    if debate:
        bull = debate.get("bull_history", "").strip()
        bear = debate.get("bear_history", "").strip()
        judge = debate.get("judge_decision", "").strip()
        if bull:
            task.add_event("research", "Bull Researcher", "completed", "Bull analysis complete")
        if bear:
            task.add_event("research", "Bear Researcher", "completed", "Bear analysis complete")
        if judge:
            task.add_event("research", "Research Manager", "completed", "Research manager decision complete")

    # -- Trader --
    if chunk.get("trader_investment_plan"):
        task.add_event("trading", "Trader", "completed", "Trader investment plan complete")

    # -- Risk debate --
    risk = chunk.get("risk_debate_state")
    if risk:
        if risk.get("aggressive_history", "").strip():
            task.add_event("risk", "Aggressive Analyst", "completed", "Aggressive analysis complete")
        if risk.get("conservative_history", "").strip():
            task.add_event("risk", "Conservative Analyst", "completed", "Conservative analysis complete")
        if risk.get("neutral_history", "").strip():
            task.add_event("risk", "Neutral Analyst", "completed", "Neutral analysis complete")
        if risk.get("judge_decision", "").strip():
            task.add_event("portfolio", "Portfolio Manager", "completed", "Portfolio manager decision complete")

    # -- Final trade decision --
    if chunk.get("final_trade_decision"):
        task.add_event("portfolio", "Final Decision", "completed", "Final trade decision reached")


# ---------------------------------------------------------------------------
# Heartbeat thread
# ---------------------------------------------------------------------------

def start_heartbeat(task: TaskState, analysis_start: datetime,
                    last_event_ts: list[datetime]) -> threading.Thread:
    """Launch a daemon heartbeat thread that emits a "still waiting" event every 15s."""
    def _heartbeat_loop():
        while task.status == "running":
            time.sleep(15)
            try:
                if (datetime.now() - last_event_ts[0]).total_seconds() >= 15:
                    # Find the most recent in_progress agent for a useful message
                    current_agent = "System"
                    for ev in reversed(task.events):
                        if ev.status == "in_progress" and ev.agent != "System":
                            current_agent = ev.agent
                            break
                    elapsed = (datetime.now() - analysis_start).total_seconds()
                    task.add_event(
                        "heartbeat", "System", "in_progress",
                        f"⏳ {current_agent} 正在处理中… ({int(elapsed)}s)",
                    )
            except Exception:
                logger.debug("Heartbeat loop error", exc_info=True)

    hb_thread = threading.Thread(target=_heartbeat_loop, daemon=True, name="heartbeat")
    hb_thread.start()
    return hb_thread
