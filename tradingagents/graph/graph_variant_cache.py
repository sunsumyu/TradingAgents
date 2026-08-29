"""Lazy pre-compilation cache for graph workflow variants.

Instead of save/restore gymnastics when switching between cached and
uncached LLMs, or between US and A-share analyst sets, the GraphVariantCache
pre-compiles each (analyst_set, llm_variant) combination on first use and
keeps the compiled graphs around for the lifetime of the TradingAgentsGraph
instance.

This eliminates the ``_base_workflow`` / ``_base_quick_thinking_llm`` /
``_base_deep_thinking_llm`` save-restore pattern in propagate().
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class GraphVariantCache:
    """Cache of compiled graphs keyed by (frozen_analyst_set, llm_signature).

    Usage::

        cache = GraphVariantCache(graph_setup_factory, base_workflow_factory)
        graph = cache.get_or_compile(
            analysts=("market", "news"),
            llm_sig="openai-quick:abc123",
            build_fn=lambda: graph_setup.setup_graph(("market", "news")).compile(),
        )
    """

    def __init__(self):
        # Key: (frozenset(analysts), llm_signature) → compiled graph
        self._cache: dict[tuple, Any] = {}

    @staticmethod
    def _key(analysts: tuple[str, ...], llm_sig: str) -> tuple:
        return (frozenset(analysts), llm_sig)

    def get_or_compile(
        self,
        analysts: tuple[str, ...],
        llm_sig: str,
        build_fn,
    ):
        """Return a compiled graph for the given variant, compiling on first use.

        Args:
            analysts: The analyst tuple (e.g. ``("market", "news")``).
            llm_sig: A string signature that changes when the LLM set changes
                (e.g. hash of model names + provider).  When LLM cache is
                enabled/disabled the signature changes, triggering recompilation.
            build_fn: A zero-argument callable that builds and compiles the
                graph.  Only called on cache miss.

        Returns:
            The compiled LangGraph graph.
        """
        key = self._key(analysts, llm_sig)
        if key not in self._cache:
            logger.debug(
                "GraphVariantCache miss for analysts=%s, llm_sig=%s — compiling",
                analysts, llm_sig,
            )
            self._cache[key] = build_fn()
        return self._cache[key]

    def invalidate(self, analysts: tuple[str, ...] | None = None, llm_sig: str | None = None):
        """Invalidate cached graphs.

        If both arguments are ``None``, clears the entire cache.
        If only *analysts* is given, clears all entries for that analyst set.
        If only *llm_sig* is given, clears all entries for that LLM variant.
        """
        if analysts is None and llm_sig is None:
            self._cache.clear()
            return
        keys_to_remove = []
        for key in self._cache:
            cached_analysts, cached_sig = key
            if analysts is not None and cached_analysts != frozenset(analysts):
                continue
            if llm_sig is not None and cached_sig != llm_sig:
                continue
            keys_to_remove.append(key)
        for k in keys_to_remove:
            del self._cache[k]

    @property
    def size(self) -> int:
        return len(self._cache)
