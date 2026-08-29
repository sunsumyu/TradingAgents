"""Resolve pending memory-log entries at the start of a run.

Extracted from TradingAgentsGraph._resolve_pending_entries to follow SRP:
the God Class should not orchestrate deferred outcome tracking.
"""

from __future__ import annotations

import logging

from .returns_resolver import fetch_returns, resolve_benchmark

logger = logging.getLogger(__name__)


def resolve_pending_entries(
    memory_log,
    ticker: str,
    reflector=None,
) -> None:
    """Resolve pending log entries for *ticker* at the start of a new run.

    Fetches returns for each same-ticker pending entry, generates reflections,
    then writes all updates in a single atomic batch write to avoid redundant I/O.
    Skips entries whose price data is not yet available (too recent or delisted).

    Args:
        memory_log: A ``TradingMemoryLog`` instance.
        reflector: A ``Reflector`` instance (needs ``reflect_on_final_decision``).
        ticker: The ticker whose pending entries to resolve.
    """
    pending = [e for e in memory_log.get_pending_entries() if e["ticker"] == ticker]
    if not pending:
        return
    if reflector is None:
        logger.warning("No reflector available; skipping pending resolution for %s", ticker)
        return

    # We need config to resolve benchmark; grab it from memory_log which holds it.
    config = getattr(memory_log, "config", {})
    benchmark = resolve_benchmark(config, ticker)
    updates = []
    for entry in pending:
        raw, alpha, days = fetch_returns(
            ticker, entry["date"], benchmark=benchmark,
        )
        if raw is None:
            continue  # price not available yet — try again next run
        reflection = reflector.reflect_on_final_decision(
            final_decision=entry.get("decision", ""),
            raw_return=raw,
            alpha_return=alpha,
            benchmark_name=benchmark,
        )
        updates.append({
            "ticker": ticker,
            "trade_date": entry["date"],
            "raw_return": raw,
            "alpha_return": alpha,
            "holding_days": days,
            "reflection": reflection,
        })

    if updates:
        memory_log.batch_update_with_outcomes(updates)
