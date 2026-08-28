"""Data quality gate: hard checks + LLM review of analyst reports.

Sits between the last analyst Msg Clear and Bull Researcher.
Layer 1: hard checks (code). Layer 2: LLM review (one call).
Writes data_quality_summary to state for downstream consumers.

Adapted from simonlin1212/TradingAgents-astock quality_gate.py.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Analyst type → state field name mapping
REPORT_FIELDS: dict[str, str] = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
    "policy": "policy_report",
    "hot_money": "hot_money_report",
    "lockup": "lockup_report",
}

ANALYST_NAMES: dict[str, str] = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
    "policy": "Policy Analyst",
    "hot_money": "Hot Money Tracker",
    "lockup": "Lockup Watcher",
}

MIN_REPORT_LENGTH = 200

FAILURE_MARKERS = [
    "无法获取",
    "I cannot retrieve",
    "I don't have access",
    "unable to fetch",
    "工具调用失败",
    "data unavailable",
    "no data found",
]


def _hard_check_report(analyst_type: str, report: str) -> tuple[str, str]:
    """Run hard checks on a single report. Returns (grade, detail)."""
    if not report or not report.strip():
        return ("F", "empty report")

    length = len(report.strip())
    if length < MIN_REPORT_LENGTH:
        return ("D", f"too short ({length} chars < {MIN_REPORT_LENGTH})")

    failure_count = sum(1 for m in FAILURE_MARKERS if m in report)
    stripped = report
    for m in FAILURE_MARKERS:
        stripped = stripped.replace(m, "")
    if failure_count > 0 and len(stripped.strip()) < MIN_REPORT_LENGTH:
        return ("D", f"mostly failure messages ({failure_count} occurrences)")

    has_table = "|" in report and "---" in report
    missing_count = report.count("[数据缺失") + report.count("[data missing")

    issues = []
    if not has_table:
        issues.append("no summary table")
    if missing_count > 0:
        issues.append(f"{missing_count} data gaps")

    if missing_count >= 3:
        return ("C", "；".join(issues))
    if not has_table or missing_count > 0:
        return ("B", "；".join(issues) if issues else "acceptable")

    return ("A", f"complete ({length} chars)")


def _build_review_prompt(
    reports: dict[str, str], trade_date: str, ticker: str
) -> str:
    """Build the LLM review prompt."""
    report_sections = []
    for analyst_type, field in REPORT_FIELDS.items():
        name = ANALYST_NAMES.get(analyst_type, analyst_type)
        content = reports.get(field, "(not run)")
        if not content:
            content = "(empty report)"
        if len(content) > 3000:
            content = content[:3000] + "\n... (truncated for review)"
        report_sections.append(f"### {name} ({analyst_type})\n{content}")

    all_reports = "\n\n".join(report_sections)

    return f"""You are a data quality auditor. Review the following analyst reports for {ticker} on {trade_date}.

{all_reports}

---

Output your review in this format:

## Data Quality Review

**Ticker**: {ticker} | **Date**: {trade_date}

| Analyst | Grade | Timeliness | Missing Items | Notes |
|---------|-------|------------|---------------|-------|
| Market Analyst | A/B/C/D/F | ... | ... | ... |
| Sentiment Analyst | ... | ... | ... | ... |
| News Analyst | ... | ... | ... | ... |
| Fundamentals Analyst | ... | ... | ... | ... |

**Overall Grade**: A/B/C/D/F
**Data Confidence**: High/Medium/Low
**Recommendation**: (if data is missing, warn the debate phase to use that report cautiously)

Grading:
- A: All required data present, timely, with summary table
- B: Missing 1-2 non-critical items, generally usable
- C: Missing 3+ items or timeliness issues, use with caution
- D: Mostly missing or failure messages, low confidence
- F: Empty or completely invalid
"""


def create_quality_gate(llm: Any):
    """Factory for the data quality gate node.

    Sits between the last analyst Msg Clear and Bull Researcher.
    Only checks reports that are present in the state (dynamic).
    """

    def quality_gate_node(state: dict) -> dict:
        trade_date = state.get("trade_date", "")
        ticker = state.get("company_of_interest", "")

        # Collect only reports that are actually present
        reports = {}
        for analyst_type, field in REPORT_FIELDS.items():
            value = state.get(field, "")
            if value:
                reports[field] = value

        if not reports:
            return {"data_quality_summary": "No analyst reports found to audit."}

        # Layer 1: hard checks
        hard_results = {}
        for analyst_type, field in REPORT_FIELDS.items():
            if field in reports:
                grade, detail = _hard_check_report(analyst_type, reports[field])
                hard_results[analyst_type] = (grade, detail)

        hard_summary_lines = []
        for analyst_type, (grade, detail) in hard_results.items():
            name = ANALYST_NAMES.get(analyst_type, analyst_type)
            hard_summary_lines.append(f"- {name}: [{grade}] {detail}")
        hard_summary = "\n".join(hard_summary_lines)

        fail_count = sum(
            1 for _, (g, _) in hard_results.items() if g in ("F", "D")
        )

        # Layer 2: LLM review (skip if most reports failed hard checks)
        llm_review = ""
        if fail_count < len(hard_results) // 2 + 1:
            try:
                review_prompt = _build_review_prompt(reports, trade_date, ticker)
                response = llm.invoke(review_prompt)
                llm_review = response.content
            except Exception as exc:
                llm_review = f"(LLM review failed: {type(exc).__name__}: {exc})"

        summary = (
            f"## Data Quality Gate\n\n"
            f"**Ticker**: {ticker} | **Date**: {trade_date}\n\n"
            f"### Hard Check Results\n{hard_summary}\n\n"
            f"### LLM Review\n"
            f"{llm_review if llm_review else '(skipped —多数报告未通过硬检查)'}\n"
        )

        return {"data_quality_summary": summary}

    return quality_gate_node
