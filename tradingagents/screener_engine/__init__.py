"""Screener Engine — stock screening with filters, templates, and LLM.

Deep module: small interface (3 methods), large implementation
(50+ filter fields, 10+ preset templates, LLM natural language parsing).

Usage::

    from tradingagents.screener_engine import ScreenerEngine

    engine = ScreenerEngine()
    results = engine.screen(criteria, sort_by="pe_ratio", limit=20)
    results = engine.screen_natural("PE<20 消费股 北向连续加仓")
    templates = engine.get_templates()
"""

from .models import (
    Filter,
    FilterOperator,
    ScreenerResult,
    ScreenerTemplate,
    SCREEN_FIELDS,
)
from .engine import ScreenerEngine

__all__ = [
    "Filter",
    "FilterOperator",
    "ScreenerResult",
    "ScreenerTemplate",
    "SCREEN_FIELDS",
    "ScreenerEngine",
]
