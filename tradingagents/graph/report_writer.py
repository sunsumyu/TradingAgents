"""Write the markdown report tree for a completed run.

Extracted from TradingAgentsGraph.save_reports to follow SRP:
the God Class should not handle filesystem report assembly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.reporting import write_report_tree


def save_reports(final_state, ticker: str, config: dict, save_path: str | Path | None = None) -> Path:
    """Write the markdown report tree for a completed run, like the CLI does.

    Programmatic callers get the same on-disk reports the CLI produces.  Pass
    an explicit ``save_path`` or let it default under ``results_dir``.

    Args:
        final_state: The final graph state dict.
        ticker: The ticker symbol.
        config: The full TradingAgents config dict.
        save_path: Optional explicit path.  Defaults to
            ``results_dir/reports/<ticker>_<timestamp>``.

    Returns:
        The ``Path`` where the report tree was written.
    """
    if save_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = (
            Path(config["results_dir"])
            / "reports"
            / f"{safe_ticker_component(ticker)}_{stamp}"
        )
    return write_report_tree(final_state, ticker, save_path)
