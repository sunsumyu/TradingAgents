# TradingAgents/graph/trading_graph.py

import logging
import os
from typing import Any

import yfinance as yf  # re-export for backward compat (tests patch tg.yf.Ticker)
from langgraph.prebuilt import ToolNode

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    resolve_instrument_identity,
)
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients import create_llm_client
from tradingagents.llm_clients.factory import create_quick_llm, create_deep_llm

from .checkpointer import checkpoint_step, clear_checkpoint, get_checkpointer, thread_id
from .conditional_logic import ConditionalLogic
from .graph_variant_cache import GraphVariantCache
from .llm_client_manager import coerce_max_retries as _coerce_max_retries  # re-export for backward compat
from .llm_client_manager import get_provider_kwargs
from .memory_orchestrator import resolve_pending_entries
from .propagation import Propagator
from .reflection import Reflector
from .report_writer import save_reports as _save_reports
from .returns_resolver import fetch_returns, resolve_benchmark
from .setup import GraphSetup
from .signal_processing import SignalProcessor
from .state_logger import log_state as _log_state

logger = logging.getLogger(__name__)


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework.

    Responsibilities have been extracted into peer modules under ``graph/``:

    - ``llm_client_manager`` — provider-kwargs resolution
    - ``returns_resolver`` — benchmark selection + yfinance return fetching
    - ``memory_orchestrator`` — deferred outcome tracking
    - ``report_writer`` — markdown report tree assembly
    - ``state_logger`` — JSON state serialization
    - ``graph_variant_cache`` — lazy pre-compilation of graph variants

    This class is now a thin orchestrator that delegates to these modules.
    The public API is **unchanged** — all existing callers (CLI, API runner,
    programmatic use) work without modification.
    """

    def __init__(
        self,
        selected_analysts=("market", "social", "news", "fundamentals"),
        debug=False,
        config: dict[str, Any] = None,
        callbacks: list | None = None,
    ):
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []

        set_config(self.config)
        os.makedirs(self.config["data_cache_dir"], exist_ok=True)
        os.makedirs(self.config["results_dir"], exist_ok=True)

        # Create LLMs with provider-specific thinking configuration
        quick_kwargs = get_provider_kwargs(self.config, "quick")
        deep_kwargs = get_provider_kwargs(self.config, "deep")

        if self.callbacks:
            quick_kwargs["callbacks"] = self.callbacks
            deep_kwargs["callbacks"] = self.callbacks

        self.quick_thinking_llm = create_quick_llm(self.config, **quick_kwargs)
        self.deep_thinking_llm = create_deep_llm(self.config, **deep_kwargs)

        # Keep unwrapped originals so propagate() can re-wrap per-run with cache.
        self._base_quick_thinking_llm = self.quick_thinking_llm
        self._base_deep_thinking_llm = self.deep_thinking_llm

        self.memory_log = TradingMemoryLog(self.config)

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic(
            max_debate_rounds=self.config["max_debate_rounds"],
            max_risk_discuss_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.conditional_logic,
        )

        from tradingagents.graph.propagation import compute_recursion_limit

        computed_limit = compute_recursion_limit(
            n_analysts=len(selected_analysts),
            debate_rounds=self.config["max_debate_rounds"],
            risk_rounds=self.config["max_risk_discuss_rounds"],
        )
        self.propagator = Propagator(
            max_recur_limit=max(
                self.config.get("max_recur_limit", 100), computed_limit
            ),
        )
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Graph-shape-affecting run choices, kept for the checkpoint signature.
        self.selected_analysts = tuple(selected_analysts)
        self.astock_analysts = tuple(
            config.get("astock_analysts", ("policy", "hot_money", "lockup"))
        ) if config else ("policy", "hot_money", "lockup")

        # Set up the graph: keep the workflow for recompilation with a checkpointer.
        self._base_workflow = self.graph_setup.setup_graph(selected_analysts)
        self.workflow = self._base_workflow
        self.graph = self.workflow.compile()
        self._checkpointer_ctx = None

        # Graph variant cache: eliminates save/restore pattern for LLM cache
        # and A-share analyst switching.
        self._variant_cache = GraphVariantCache()

    # ── public helpers (unchanged API) ────────────────────────────────────

    def _get_provider_kwargs(self, model_type: str = "quick") -> dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation.

        Delegates to ``llm_client_manager.get_provider_kwargs``.
        Kept as a method for backward compatibility (tests, subclasses).
        """
        return get_provider_kwargs(self.config, model_type)

    def _create_tool_nodes(self) -> dict[str, ToolNode]:
        """Create tool nodes from the static registry in tool_wiring.py."""
        from .tool_wiring import ANALYST_TOOLS
        return {
            name: ToolNode(tools) for name, tools in ANALYST_TOOLS.items() if tools
        }

    def resolve_instrument_context(self, ticker: str, asset_type: str = "stock") -> str:
        """Resolve ticker identity once and return the full instrument context."""
        identity = resolve_instrument_identity(ticker)
        return build_instrument_context(ticker, asset_type, identity)

    def _run_signature(self, asset_type: str) -> str:
        """Graph-shape inputs that must invalidate a checkpoint if changed."""
        return "|".join([
            "analysts=" + ",".join(self.selected_analysts),
            f"debate={self.config['max_debate_rounds']}",
            f"risk={self.config['max_risk_discuss_rounds']}",
            f"asset={asset_type}",
        ])

    def resolve_benchmark(self, ticker: str) -> str:
        """Pick the benchmark ticker for alpha calculation (delegated)."""
        return resolve_benchmark(self.config, ticker)

    def save_reports(self, final_state, ticker, save_path=None):
        """Write the markdown report tree for a completed run (delegated).

        Handles unbound calls (``TradingAgentsGraph.save_reports(None, state, "X",
        save_path=…)``) used in tests — when *self* is None and *save_path* is
        explicit the method does not need a config.
        """
        config = self.config if self is not None else {"results_dir": "."}
        return _save_reports(final_state, ticker, config, save_path)

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)

    def _resolve_pending_entries(self, ticker: str) -> None:
        """Resolve pending log entries for ticker at the start of a new run.

        Fetches returns for each same-ticker pending entry, generates reflections,
        then writes all updates in a single atomic batch write.
        """
        pending = [e for e in self.memory_log.get_pending_entries() if e["ticker"] == ticker]
        if not pending:
            return

        benchmark = self._resolve_benchmark(ticker)
        updates = []
        for entry in pending:
            raw, alpha, days = self._fetch_returns(
                ticker, entry["date"], benchmark=benchmark,
            )
            if raw is None:
                continue
            reflection = self.reflector.reflect_on_final_decision(
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
            self.memory_log.batch_update_with_outcomes(updates)

    def _log_state(self, trade_date, final_state):
        """Log the final state to disk (delegated). Kept for backward compat."""
        _log_state(trade_date, final_state, self.ticker, self.config, self.log_states_dict)

    def _fetch_returns(self, ticker, trade_date, holding_days=5, benchmark="SPY"):
        """Fetch raw/alpha returns (delegated). Kept for backward compat."""
        return fetch_returns(ticker, trade_date, holding_days, benchmark)

    def _resolve_benchmark(self, ticker):
        """Resolve benchmark (delegated). Kept for backward compat."""
        return resolve_benchmark(self.config, ticker)

    # ── LLM cache signature (replaces save/restore pattern) ───────────────

    def _llm_signature(self) -> str:
        """Fingerprint of the current LLM configuration.

        Changes when model names, providers, or cache state change, triggering
        recompilation via GraphVariantCache instead of save/restore.
        """
        parts = [
            getattr(self.quick_thinking_llm, "model_name", "?"),
            getattr(self.deep_thinking_llm, "model_name", "?"),
            str(id(self.quick_thinking_llm)),
            str(id(self.deep_thinking_llm)),
        ]
        return "|".join(parts)

    # ── propagate: the main entry point ───────────────────────────────────

    def propagate(self, company_name, trade_date, asset_type: str = "stock"):
        """Run the trading agents graph for a company on a specific date.

        ``asset_type`` selects between the stock pipeline (default) and the
        crypto pipeline (``"crypto"``) shipped in #567 — the CLI auto-detects
        from the ticker; programmatic callers pass it explicitly.  When
        ``checkpoint_enabled`` is set in config, the graph is recompiled with
        a per-ticker SqliteSaver so a crashed run can resume from the last
        successful node on a subsequent invocation with the same ticker+date.
        """
        self.ticker = company_name

        # Resolve any pending memory-log entries for this ticker before the pipeline runs.
        self._resolve_pending_entries(company_name)

        # ── Market detection integration ──────────────────────────────────
        _UNSET = object()  # sentinel: distinguishes "missing key" from None
        _orig_selected_analysts = self.selected_analysts
        _orig_data_vendors = self.config.get("data_vendors", _UNSET)
        _orig_output_language = self.config.get("output_language", _UNSET)
        _astock_applied = False

        market_type = self.propagator.resolve_market_type(
            company_name, self.config.get("market_type", "auto"),
        )
        if market_type == "astock":
            _astock_applied = True
            self.propagator.apply_astock_config_overrides(self.config)
            self.selected_analysts = tuple(
                list(self.selected_analysts) + list(self.astock_analysts)
            )
            self.workflow = self.graph_setup.setup_graph(self.selected_analysts)
            self.graph = self.workflow.compile()

        # Recompile with a checkpointer if the user opted in.
        if self.config.get("checkpoint_enabled"):
            self._checkpointer_ctx = get_checkpointer(
                self.config["data_cache_dir"], company_name
            )
            saver = self._checkpointer_ctx.__enter__()
            self.graph = self.workflow.compile(checkpointer=saver)

            step = checkpoint_step(
                self.config["data_cache_dir"], company_name, str(trade_date),
                self._run_signature(asset_type),
            )
            if step is not None:
                logger.info(
                    "Resuming from step %d for %s on %s", step, company_name, trade_date
                )
            else:
                logger.info("Starting fresh for %s on %s", company_name, trade_date)

        # Wrap LLMs with per-call result cache when enabled.
        # Uses GraphVariantCache to avoid rebuilding GraphSetup+workflow
        # when the same (analysts, llm_sig) combination is seen again.
        _llm_cache = None
        if self.config.get("llm_cache_enabled"):
            from tradingagents.agents.utils.cached_llm import CachedLLM
            from tradingagents.llm_cache import LLMCache

            _llm_cache = LLMCache(
                self.config["data_cache_dir"],
                ticker=company_name,
                ttl_hours=self.config.get("llm_cache_ttl_hours", 24),
            )
            self.quick_thinking_llm = CachedLLM(
                self._base_quick_thinking_llm, _llm_cache
            )
            self.deep_thinking_llm = CachedLLM(
                self._base_deep_thinking_llm, _llm_cache
            )
            # Rebuild graph setup with cached LLMs so agent factories pick them up.
            self.graph_setup = GraphSetup(
                self.quick_thinking_llm,
                self.deep_thinking_llm,
                self.tool_nodes,
                self.conditional_logic,
            )
            # Use variant cache: avoids recompilation for same analyst+LLM combo.
            _llm_sig = "cached|" + self._llm_signature()
            self.workflow = self._variant_cache.get_or_compile(
                self.selected_analysts, _llm_sig,
                lambda: self.graph_setup.setup_graph(self.selected_analysts),
            )
            if self.config.get("checkpoint_enabled") and self._checkpointer_ctx is not None:
                self.graph = self.workflow.compile(checkpointer=saver)
            else:
                self.graph = self.workflow.compile()

        try:
            return self._run_graph(company_name, trade_date, asset_type=asset_type)
        finally:
            # Restore unwrapped LLMs so the next run starts clean.
            if _llm_cache is not None:
                stats = _llm_cache.stats()
                logger.info(
                    "LLM cache stats for %s: %s", company_name, stats
                )
                _llm_cache.prune_expired()
                _llm_cache.close()
                self.quick_thinking_llm = self._base_quick_thinking_llm
                self.deep_thinking_llm = self._base_deep_thinking_llm
                # Rebuild graph setup with unwrapped LLMs (use cached variant).
                self.graph_setup = GraphSetup(
                    self.quick_thinking_llm,
                    self.deep_thinking_llm,
                    self.tool_nodes,
                    self.conditional_logic,
                )
                self.workflow = self._variant_cache.get_or_compile(
                    self.selected_analysts,
                    "base|" + self._llm_signature(),
                    lambda: self.graph_setup.setup_graph(self.selected_analysts),
                )
                self.graph = self.workflow.compile()

            # C1 FIX: Restore original state so the next run isn't polluted
            # by A-share overrides from a previous run.
            if _astock_applied:
                self.selected_analysts = _orig_selected_analysts
                if _orig_data_vendors is _UNSET:
                    self.config.pop("data_vendors", None)
                else:
                    self.config["data_vendors"] = _orig_data_vendors
                if _orig_output_language is _UNSET:
                    self.config.pop("output_language", None)
                else:
                    self.config["output_language"] = _orig_output_language
                self.workflow = self._base_workflow
                self.graph = self.workflow.compile()
            if self._checkpointer_ctx is not None:
                self._checkpointer_ctx.__exit__(None, None, None)
                self._checkpointer_ctx = None
                self.workflow = self._base_workflow
                self.graph = self.workflow.compile()

    # ── internal: execute the graph ────────────────────────────────────────

    def _run_graph(self, company_name, trade_date, asset_type: str = "stock"):
        """Execute the graph and write the resulting state to disk and memory log."""
        past_context = self.memory_log.get_past_context(company_name)
        instrument_context = self.resolve_instrument_context(company_name, asset_type)
        market_type = self.propagator.resolve_market_type(
            company_name, self.config.get("market_type", "auto"),
        )
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            asset_type=asset_type,
            past_context=past_context,
            instrument_context=instrument_context,
        )
        init_agent_state["market_type"] = market_type

        args = self.propagator.get_graph_args()

        if self.config.get("checkpoint_enabled"):
            tid = thread_id(company_name, str(trade_date), self._run_signature(asset_type))
            args.setdefault("config", {}).setdefault("configurable", {})["thread_id"] = tid

        if self.debug:
            trace = []
            last_printed = None
            for chunk in self.graph.stream(init_agent_state, **args):
                if chunk["messages"]:
                    msg = chunk["messages"][-1]
                    signature = (type(msg).__name__, getattr(msg, "content", None))
                    if signature != last_printed:
                        msg.pretty_print()
                        last_printed = signature
                    trace.append(chunk)
            final_state = {}
            for chunk in trace:
                final_state.update(chunk)
        else:
            final_state = self.graph.invoke(init_agent_state, **args)

        self.curr_state = final_state

        # Log state to disk (delegated).
        _log_state(trade_date, final_state, self.ticker, self.config, self.log_states_dict)

        # Store decision for deferred reflection on the next same-ticker run.
        self.memory_log.store_decision(
            ticker=company_name,
            trade_date=trade_date,
            final_trade_decision=final_state["final_trade_decision"],
        )

        # Clear checkpoint on successful completion.
        if self.config.get("checkpoint_enabled"):
            clear_checkpoint(
                self.config["data_cache_dir"], company_name, str(trade_date),
                self._run_signature(asset_type),
            )

        return final_state, self.process_signal(final_state["final_trade_decision"])
