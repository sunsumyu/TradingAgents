# A股市场集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate A-share market analysis capabilities from the TradingAgents-astock fork into the current TradingAgents framework, enabling automatic market detection, A-share data sources, 3 new analysts, and Chinese trading rules.

**Architecture:** Add A-share as a market module that plugs into the existing vendor routing and analyst execution systems. A `market_type` field auto-detected from the ticker drives all conditional behavior (data sources, analysts, prompts, trading rules). The existing US/HK/crypto pipelines remain untouched.

**Tech Stack:** Python 3.10+, LangGraph, LangChain Core, mootdx (TCP 7709), requests (HTTP to Tencent/Eastmoney/Sina/Tonghuashun/CLS/Baidu APIs)

## Global Constraints

- Python >= 3.10 (from pyproject.toml)
- langchain-core >= 0.3.81, langgraph >= 0.4.8
- mootdx >= 0.11.7 (new dependency)
- No new API keys required for A-share data sources
- All A-share data sources are free public HTTP/TCP APIs
- Existing US/HK analysis must continue working unchanged
- Keep existing LLM client layer (18+ providers) unchanged

---

## Task 1: Market Detection Module

**Files:**
- Create: `tradingagents/markets/__init__.py`
- Create: `tradingagents/markets/detector.py`
- Create: `tests/test_market_detector.py`

**Interfaces:**
- Consumes: ticker string from user input
- Produces: `detect_market_type(ticker: str) -> str` returning `"us"` | `"astock"` | `"hk"` | `"crypto"`, and `normalize_astock_ticker(ticker: str) -> str` returning 6-digit code

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_market_detector.py
import pytest
from tradingagents.markets.detector import detect_market_type, normalize_astock_ticker


class TestDetectMarketType:
    def test_pure_6digit_is_astock(self):
        assert detect_market_type("600519") == "astock"

    def test_600_is_astock(self):
        assert detect_market_type("000001") == "astock"

    def test_ss_suffix_is_astock(self):
        assert detect_market_type("600519.SS") == "astock"

    def test_sz_suffix_is_astock(self):
        assert detect_market_type("000001.SZ") == "astock"

    def test_hk_suffix(self):
        assert detect_market_type("0700.HK") == "hk"

    def test_usd_suffix_is_crypto(self):
        assert detect_market_type("BTC-USD") == "crypto"

    def test_pure_letters_is_us(self):
        assert detect_market_type("NVDA") == "us"

    def test_us_with_dot_suffix(self):
        assert detect_market_type("BRK.B") == "us"

    def test_short_code_defaults_us(self):
        # 3-digit codes are ambiguous, default to us
        assert detect_market_type("123") == "us"


class TestNormalizeAstockTicker:
    def test_strip_ss_suffix(self):
        assert normalize_astock_ticker("600519.SS") == "600519"

    def test_strip_sz_suffix(self):
        assert normalize_astock_ticker("000001.SZ") == "000001"

    def test_pure_digits_unchanged(self):
        assert normalize_astock_ticker("600519") == "600519"

    def test_lowercase_sh_prefix(self):
        assert normalize_astock_ticker("sh600519") == "600519"

    def test_lowercase_sz_prefix(self):
        assert normalize_astock_ticker("sz000001") == "000001"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_market_detector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tradingagents.markets'`

- [ ] **Step 3: Create the markets package and detector**

```python
# tradingagents/markets/__init__.py
```

```python
# tradingagents/markets/detector.py
"""Centralized market type detection from ticker symbols."""

import re

_ASTOCK_6DIGIT = re.compile(r"^\d{6}$")
_ASTOCK_SUFFIX = re.compile(r"^\d{6}\.(SS|SZ)$", re.IGNORECASE)
_ASTOCK_PREFIX = re.compile(r"^(sh|sz)\d{6}$", re.IGNORECASE)
_HK_SUFFIX = re.compile(r"\.HK$", re.IGNORECASE)
_CRYPTO_SUFFIX = re.compile(r"-USD$", re.IGNORECASE)
_LETTERS_ONLY = re.compile(r"^[A-Za-z]+$")
_US_DOT = re.compile(r"^[A-Za-z]+\.[A-Za-z]+$")


def detect_market_type(ticker: str) -> str:
    """Detect market type from a ticker symbol.

    Returns one of: "astock", "us", "hk", "crypto".
    Falls back to "us" for ambiguous inputs.
    """
    t = ticker.strip()

    if _ASTOCK_6DIGIT.match(t):
        return "astock"
    if _ASTOCK_SUFFIX.match(t):
        return "astock"
    if _ASTOCK_PREFIX.match(t):
        return "astock"
    if _HK_SUFFIX.search(t):
        return "hk"
    if _CRYPTO_SUFFIX.search(t):
        return "crypto"
    if _LETTERS_ONLY.match(t):
        return "us"
    if _US_DOT.match(t):
        return "us"

    return "us"


def normalize_astock_ticker(ticker: str) -> str:
    """Normalize an A-share ticker to a pure 6-digit code.

    Strips .SS/.SZ suffixes and sh/sz prefixes.
    Returns the input unchanged if it is not an A-share ticker.
    """
    t = ticker.strip()

    m = _ASTOCK_SUFFIX.match(t)
    if m:
        return t[:6]

    m = _ASTOCK_PREFIX.match(t)
    if m:
        return t[2:]

    return t
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_market_detector.py -v`
Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tradingagents/markets/__init__.py tradingagents/markets/detector.py tests/test_market_detector.py
git commit -m "feat(markets): add centralized market type detection module"
```

---

## Task 2: A-Share Data Module — Core Functions

**Files:**
- Create: `tradingagents/dataflows/a_stock.py`
- Create: `tests/test_a_stock_data.py`

**Interfaces:**
- Consumes: ticker strings, date strings
- Produces: 17 functions returning formatted strings (CSV/text), each with the signature pattern `def get_XXX(ticker, ...) -> str`

**Note:** This is the largest single file (~2400 lines in the fork). Port it from the fork with minimal adaptation. The fork's implementation is battle-tested and uses zero third-party data libraries.

- [ ] **Step 1: Write the failing import test**

```python
# tests/test_a_stock_data.py
import pytest


def test_a_stock_module_importable():
    """Verify the a_stock module can be imported."""
    from tradingagents.dataflows import a_stock
    assert hasattr(a_stock, "get_stock_data")
    assert hasattr(a_stock, "get_indicators")
    assert hasattr(a_stock, "get_fundamentals")
    assert hasattr(a_stock, "get_balance_sheet")
    assert hasattr(a_stock, "get_cashflow")
    assert hasattr(a_stock, "get_income_statement")
    assert hasattr(a_stock, "get_news")
    assert hasattr(a_stock, "get_global_news")
    assert hasattr(a_stock, "get_insider_transactions")
    assert hasattr(a_stock, "get_profit_forecast")
    assert hasattr(a_stock, "get_hot_stocks")
    assert hasattr(a_stock, "get_northbound_flow")
    assert hasattr(a_stock, "get_concept_blocks")
    assert hasattr(a_stock, "get_fund_flow")
    assert hasattr(a_stock, "get_dragon_tiger_board")
    assert hasattr(a_stock, "get_lockup_expiry")
    assert hasattr(a_stock, "get_industry_comparison")


def test_normalize_ticker():
    from tradingagents.dataflows.a_stock import _normalize_ticker
    assert _normalize_ticker("600519.SS") == "600519"
    assert _normalize_ticker("000001.SZ") == "000001"
    assert _normalize_ticker("sh600519") == "600519"
    assert _normalize_ticker("600519") == "600519"


def test_reject_non_a_share():
    from tradingagents.dataflows.a_stock import _reject_non_a_share
    # Should raise ValueError for non-A-share codes
    with pytest.raises(ValueError):
        _reject_non_a_share("get_stock_data", "NVDA")
    with pytest.raises(ValueError):
        _reject_non_a_share("get_stock_data", "0700.HK")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_a_stock_data.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Port a_stock.py from the fork**

Copy the complete `tradingagents/dataflows/a_stock.py` from the TradingAgents-astock fork (commit latest). The file contains:

1. **Ticker utilities:** `_get_prefix()`, `_reject_non_a_share()`, `_normalize_ticker()`, `resolve_ticker()`
2. **Point-in-time protection:** `_market_today()`, `_is_historical()`, `_snapshot_notice()`
3. **mootdx client:** Singleton with `_get_mootdx_client()`, `_TDX_SERVERS`, retry logic, `_mootdx_call()`
4. **Eastmoney anti-ban:** `_EM_SESSION`, `_EM_MIN_INTERVAL`, `_em_get()`, `_eastmoney_datacenter()`
5. **17 data functions:** `get_stock_data`, `get_indicators`, `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement`, `get_news`, `get_global_news`, `get_insider_transactions`, `get_profit_forecast`, `get_hot_stocks`, `get_northbound_flow`, `get_concept_blocks`, `get_fund_flow`, `get_dragon_tiger_board`, `get_lockup_expiry`, `get_industry_comparison`

Adaptations needed:
- Ensure all imports resolve (check `from tradingagents.dataflows.config import get_config`)
- Verify the `EM_MIN_INTERVAL` env var default matches our config pattern

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_a_stock_data.py -v`
Expected: All 3 tests PASS (import test, normalize test, reject test)

- [ ] **Step 5: Commit**

```bash
git add tradingagents/dataflows/a_stock.py tests/test_a_stock_data.py
git commit -m "feat(dataflows): add A-share data module with 17 vendor functions"
```

---

## Task 3: Register A-Share Vendor in Interface

**Files:**
- Modify: `tradingagents/dataflows/interface.py`
- Modify: `tradingagents/agents/utils/agent_utils.py` (add tool exports)
- Create: `tests/test_astock_vendor_routing.py`

**Interfaces:**
- Consumes: 17 functions from `a_stock.py`
- Produces: Updated `VENDOR_LIST`, `VENDOR_METHODS`, `TOOLS_CATEGORIES` with a_stock entries

- [ ] **Step 1: Write the failing routing test**

```python
# tests/test_astock_vendor_routing.py
import pytest
from unittest.mock import patch
from tradingagents.dataflows.interface import (
    VENDOR_LIST,
    VENDOR_METHODS,
    TOOLS_CATEGORIES,
    get_category_for_method,
)


def test_a_stock_in_vendor_list():
    assert "a_stock" in VENDOR_LIST


def test_a_stock_has_all_core_methods():
    """All existing tool methods must have an a_stock implementation."""
    core_methods = [
        "get_stock_data",
        "get_indicators",
        "get_fundamentals",
        "get_balance_sheet",
        "get_cashflow",
        "get_income_statement",
        "get_news",
        "get_global_news",
        "get_insider_transactions",
    ]
    for method in core_methods:
        assert method in VENDOR_METHODS, f"Missing VENDOR_METHODS entry for {method}"
        assert "a_stock" in VENDOR_METHODS[method], f"Missing a_stock vendor for {method}"


def test_astock_signal_methods_exist():
    """A-stock signal methods (only available via a_stock)."""
    signal_methods = [
        "get_profit_forecast",
        "get_hot_stocks",
        "get_northbound_flow",
        "get_concept_blocks",
        "get_fund_flow",
        "get_dragon_tiger_board",
        "get_lockup_expiry",
        "get_industry_comparison",
    ]
    for method in signal_methods:
        assert method in VENDOR_METHODS, f"Missing VENDOR_METHODS for {method}"
        assert "a_stock" in VENDOR_METHODS[method], f"Missing a_stock for {method}"
        # These should be a_stock-only
        assert len(VENDOR_METHODS[method]) == 1


def test_signal_data_category_exists():
    assert "signal_data" in TOOLS_CATEGORIES
    signal_tools = TOOLS_CATEGORIES["signal_data"]["tools"]
    assert "get_profit_forecast" in signal_tools
    assert "get_hot_stocks" in signal_tools
    assert "get_lockup_expiry" in signal_tools
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_astock_vendor_routing.py -v`
Expected: FAIL — `a_stock` not in `VENDOR_LIST`

- [ ] **Step 3: Update interface.py**

In `tradingagents/dataflows/interface.py`:

1. Add import at top:
```python
from tradingagents.dataflows import a_stock as _a_stock
```

2. Add to `VENDOR_LIST`:
```python
VENDOR_LIST = [
    "yfinance",
    "fred",
    "polymarket",
    "alpha_vantage",
    "a_stock",
]
```

3. Add `signal_data` to `TOOLS_CATEGORIES`:
```python
"signal_data": {
    "description": "A-share signal data tools (profit forecast, hot stocks, fund flow, etc.)",
    "tools": [
        "get_profit_forecast",
        "get_hot_stocks",
        "get_northbound_flow",
        "get_concept_blocks",
        "get_fund_flow",
        "get_dragon_tiger_board",
        "get_lockup_expiry",
        "get_industry_comparison",
    ],
},
```

4. Add a_stock entries to each existing method in `VENDOR_METHODS`:
```python
"get_stock_data": {
    "alpha_vantage": ...,  # existing
    "yfinance": ...,      # existing
    "a_stock": _a_stock.get_stock_data,
},
# ... repeat for all 9 core methods
```

5. Add signal_data methods (a_stock only):
```python
"get_profit_forecast": {"a_stock": _a_stock.get_profit_forecast},
"get_hot_stocks": {"a_stock": _a_stock.get_hot_stocks},
# ... etc for all 8 signal methods
```

- [ ] **Step 4: Add tool exports to agent_utils.py**

In `tradingagents/agents/utils/agent_utils.py`, add imports and exports for the 8 new tools:

```python
from tradingagents.agents.utils.signal_data_tools import (
    get_profit_forecast,
    get_hot_stocks,
    get_northbound_flow,
    get_concept_blocks,
    get_fund_flow,
    get_dragon_tiger_board,
    get_lockup_expiry,
    get_industry_comparison,
)
```

Create `tradingagents/agents/utils/signal_data_tools.py` with thin wrappers that call `route_to_vendor`:

```python
# tradingagents/agents/utils/signal_data_tools.py
"""A-share signal data tool functions — thin wrappers over route_to_vendor."""
from tradingagents.dataflows.interface import route_to_vendor


def get_profit_forecast(ticker: str, curr_date: str = "") -> str:
    return route_to_vendor("get_profit_forecast", ticker, curr_date)


def get_hot_stocks(curr_date: str = "") -> str:
    return route_to_vendor("get_hot_stocks", curr_date)


def get_northbound_flow(curr_date: str = "", include_history: bool = False) -> str:
    return route_to_vendor("get_northbound_flow", curr_date, include_history)


def get_concept_blocks(ticker: str) -> str:
    return route_to_vendor("get_concept_blocks", ticker)


def get_fund_flow(ticker: str, curr_date: str = "", include_history: bool = True) -> str:
    return route_to_vendor("get_fund_flow", ticker, curr_date, include_history)


def get_dragon_tiger_board(ticker: str, trade_date: str = "", look_back_days: int = 30) -> str:
    return route_to_vendor("get_dragon_tiger_board", ticker, trade_date, look_back_days)


def get_lockup_expiry(ticker: str, curr_date: str = "", forward_days: int = 90) -> str:
    return route_to_vendor("get_lockup_expiry", ticker, curr_date, forward_days)


def get_industry_comparison(ticker: str, trade_date: str = "", top_n: int = 20) -> str:
    return route_to_vendor("get_industry_comparison", ticker, trade_date, top_n)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_astock_vendor_routing.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tradingagents/dataflows/interface.py tradingagents/agents/utils/signal_data_tools.py tradingagents/agents/utils/agent_utils.py tests/test_astock_vendor_routing.py
git commit -m "feat(dataflows): register A-share vendor in routing system with 8 signal tools"
```

---

## Task 4: Config and AgentState Updates

**Files:**
- Modify: `tradingagents/default_config.py`
- Modify: `tradingagents/agents/utils/agent_states.py`
- Modify: `pyproject.toml`
- Create: `tests/test_astock_config.py`

**Interfaces:**
- Consumes: none
- Produces: `market_type` config key, `astock_*` config keys, `AgentState` with `market_type` field, `mootdx` dependency

- [ ] **Step 1: Write the failing config test**

```python
# tests/test_astock_config.py
import pytest
from tradingagents.default_config import DEFAULT_CONFIG


def test_market_type_in_config():
    assert "market_type" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["market_type"] == "auto"


def test_astock_config_keys():
    assert "astock_lookback_days" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["astock_lookback_days"] == 60
    assert "astock_trading_sessions" in DEFAULT_CONFIG
    assert DEFAULT_CONFIG["astock_trading_sessions"] is True


def test_market_type_env_override():
    import os
    os.environ["TRADINGAGENTS_MARKET_TYPE"] = "astock"
    try:
        from importlib import reload
        import tradingagents.default_config as cfg
        reload(cfg)
        assert cfg.DEFAULT_CONFIG["market_type"] == "astock"
    finally:
        del os.environ["TRADINGAGENTS_MARKET_TYPE"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_astock_config.py -v`
Expected: FAIL — `market_type` not in config

- [ ] **Step 3: Update default_config.py**

Add to `_ENV_OVERRIDES`:
```python
"TRADINGAGENTS_MARKET_TYPE": "market_type",
```

Add to `DEFAULT_CONFIG`:
```python
"market_type": "auto",
"astock_lookback_days": 60,
"astock_trading_sessions": True,
```

- [ ] **Step 4: Update AgentState**

In `tradingagents/agents/utils/agent_states.py`, add `market_type` as a new field to the state TypedDict. While `asset_type` exists, it represents the financial instrument class (stock/crypto), not the market. `market_type` is a separate concept representing the exchange/market regime (us/astock/hk). Add it as an optional string field with default `None`:

```python
# In AgentState TypedDict:
market_type: str  # "us" | "astock" | "hk" | "crypto" — set at propagation time
```

- [ ] **Step 5: Add mootdx to pyproject.toml**

In `pyproject.toml`, add to `dependencies`:
```toml
"mootdx>=0.11.7",
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_astock_config.py -v`
Expected: All 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add tradingagents/default_config.py tradingagents/agents/utils/agent_states.py pyproject.toml tests/test_astock_config.py
git commit -m "feat(config): add A-share config keys and mootdx dependency"
```

---

## Task 5: Graph Propagation — Market Detection Integration

**Files:**
- Modify: `tradingagents/graph/propagation.py`
- Modify: `tradingagents/graph/trading_graph.py`
- Create: `tests/test_astock_propagation.py`

**Interfaces:**
- Consumes: `detect_market_type()` from Task 1, config `market_type`
- Produces: `market_type` injected into `AgentState`, vendor config auto-switched for A-share

- [ ] **Step 1: Write the failing propagation test**

```python
# tests/test_astock_propagation.py
import pytest
from unittest.mock import patch, MagicMock
from tradingagents.markets.detector import detect_market_type


def test_astock_ticker_detected():
    assert detect_market_type("600519") == "astock"
    assert detect_market_type("NVDA") == "us"


def test_config_vendor_override_for_astock():
    """When market_type is astock, data_vendors should be overridden."""
    from tradingagents.default_config import DEFAULT_CONFIG
    config = DEFAULT_CONFIG.copy()
    # Simulate the override logic that propagation will apply
    if config["market_type"] == "auto":
        # auto mode: detect from ticker (tested separately)
        pass
    # For explicit astock, override vendors
    config["market_type"] = "astock"
    config["data_vendors"] = {
        "core_stock_apis": "a_stock",
        "technical_indicators": "a_stock",
        "fundamental_data": "a_stock",
        "news_data": "a_stock",
        "signal_data": "a_stock",
    }
    assert config["data_vendors"]["core_stock_apis"] == "a_stock"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_astock_propagation.py -v`
Expected: PASS for detection test (from Task 1), but the vendor override logic doesn't exist yet

- [ ] **Step 3: Update propagation.py**

In `tradingagents/graph/propagation.py`, in the `propagate()` method (or wherever initial state is built):

```python
from tradingagents.markets.detector import detect_market_type

# After ticker is received, before building initial state:
market_type = config.get("market_type", "auto")
if market_type == "auto":
    market_type = detect_market_type(ticker)

# Inject market_type into state
initial_state["market_type"] = market_type

# Auto-switch data vendors for A-share
if market_type == "astock":
    config["data_vendors"] = {
        "core_stock_apis": "a_stock",
        "technical_indicators": "a_stock",
        "fundamental_data": "a_stock",
        "news_data": "a_stock",
        "signal_data": "a_stock",
    }

# Set output language for A-share
if market_type == "astock" and config.get("output_language") == "English":
    config["output_language"] = "Chinese"
```

- [ ] **Step 4: Update trading_graph.py**

In `tradingagents/graph/trading_graph.py`, ensure `market_type` is accessible to `GraphSetup` and passed through to analyst selection. The `selected_analysts` list should include A-share analysts when market_type is "astock":

```python
# In TradingAgentsGraph.propagate() or the setup path:
selected_analysts = config.get("selected_analysts", ["market", "social", "news", "fundamentals"])
if market_type == "astock":
    astock_analysts = config.get("astock_analysts", ["policy", "hot_money", "lockup"])
    selected_analysts = selected_analysts + astock_analysts
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_astock_propagation.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add tradingagents/graph/propagation.py tradingagents/graph/trading_graph.py tests/test_astock_propagation.py
git commit -m "feat(graph): integrate market detection into propagation and auto-switch vendors"
```

---

## Task 6: Policy Analyst Agent

**Files:**
- Create: `tradingagents/agents/analysts/policy_analyst.py`
- Create: `tests/test_policy_analyst.py`

**Interfaces:**
- Consumes: `llm` (LangChain chat model), `get_news`, `get_global_news`, `get_language_instruction`, `build_instrument_context`
- Produces: `create_policy_analyst(llm) -> callable(state) -> dict` with `"messages"` and `"policy_report"` keys

- [ ] **Step 1: Write the failing import test**

```python
# tests/test_policy_analyst.py
import pytest


def test_policy_analyst_importable():
    from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
    assert callable(create_policy_analyst)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_policy_analyst.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create policy_analyst.py**

Port from the fork. The factory function:

```python
# tradingagents/agents/analysts/policy_analyst.py
"""A-share policy analyst: tracks regulatory and industrial policy signals."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_global_news,
    get_language_instruction,
    get_news,
)


def create_policy_analyst(llm):
    """Create a policy analyst node for A-share market analysis."""

    def policy_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [get_news, get_global_news]

        system_message = (
            "你是一位专注于 A 股市场的政策分析师。你的核心任务是追踪和解读影响目标公司及所在行业的政策动态，"
            "评估政策对股价的潜在影响方向和力度。"
            "\n\nA 股是全球最典型的「政策市」，政策分析是投资决策中权重最高的因子之一。"
            "\n\n## 政策分析框架："
            "\n- **宏观政策层**：货币政策（降准/降息/MLF/LPR 调整）、财政政策（专项债/减税）、汇率政策"
            "\n- **监管政策层**：证监会（IPO 节奏/再融资/减持新规/退市制度）、银保监会、发改委"
            "\n- **产业政策层**：国务院/部委发布的行业扶持或限制政策"
            "\n- **地方政策层**：地方政府出台的区域性扶持政策"
            "\n- **国际政策层**：中美关系、出口管制、关税变动"
            "\n\n分析方法："
            "\n1. 识别近期发布的与目标公司直接或间接相关的政策"
            "\n2. 评估政策的力度级别：指导意见（弱）< 部委通知（中）< 国务院文件（强）< 法律法规（最强）"
            "\n3. 判断政策的影响时间窗口：短期脉冲（1-2 周）vs 中期趋势（1-3 月）vs 长期结构性（半年以上）"
            "\n4. 分析政策的受益/受损逻辑链：政策 → 行业影响 → 公司业务映射 → 财务影响估算"
            "\n\n工具："
            "\n- `get_news(ticker, start_date, end_date)`：搜索与公司/行业相关的政策新闻"
            "\n- `get_global_news(curr_date, look_back_days, limit)`：获取宏观经济和政策面新闻"
            "\n\n请撰写详细的政策分析报告，明确给出政策面对该公司的总体评级"
            "（重大利好/利好/中性/利空/重大利空），并量化影响程度。"
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has a FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**"
                    " or deliverable, prefix your response with"
                    " FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    " For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([t.name for t in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {"messages": [result], "policy_report": report}

    return policy_analyst_node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_policy_analyst.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tradingagents/agents/analysts/policy_analyst.py tests/test_policy_analyst.py
git commit -m "feat(agents): add A-share policy analyst agent"
```

---

## Task 7: Hot Money Tracker Agent

**Files:**
- Create: `tradingagents/agents/analysts/hot_money_tracker.py`
- Create: `tests/test_hot_money_tracker.py`

**Interfaces:**
- Consumes: `llm`, 9 tool functions (`get_stock_data`, `get_news`, `get_insider_transactions`, `get_hot_stocks`, `get_northbound_flow`, `get_concept_blocks`, `get_fund_flow`, `get_dragon_tiger_board`, `get_industry_comparison`)
- Produces: `create_hot_money_tracker(llm) -> callable(state) -> dict` with `"messages"` and `"hot_money_report"` keys

- [ ] **Step 1: Write the failing import test**

```python
# tests/test_hot_money_tracker.py
import pytest


def test_hot_money_tracker_importable():
    from tradingagents.agents.analysts.hot_money_tracker import create_hot_money_tracker
    assert callable(create_hot_money_tracker)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hot_money_tracker.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create hot_money_tracker.py**

```python
# tradingagents/agents/analysts/hot_money_tracker.py
"""A-share hot money tracker: analyzes capital flows, volume anomalies, and major player movements."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_concept_blocks,
    get_dragon_tiger_board,
    get_fund_flow,
    get_hot_stocks,
    get_industry_comparison,
    get_insider_transactions,
    get_language_instruction,
    get_news,
    get_northbound_flow,
    get_stock_data,
)


def create_hot_money_tracker(llm):
    """Create a hot money tracker node for A-share market analysis."""

    def hot_money_tracker_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_stock_data,
            get_news,
            get_insider_transactions,
            get_hot_stocks,
            get_northbound_flow,
            get_concept_blocks,
            get_fund_flow,
            get_dragon_tiger_board,
            get_industry_comparison,
        ]

        system_message = (
            "你是A股热钱追踪器，专门分析资金流向、量价异常和主力动向。请用中文回答所有问题。"
            "\n\n### 任务："
            "\n- 分析北向资金、融资融券、龙虎榜、主力资金流向，识别游资热钱动向"
            "\n- 监控大单异动（超过10%流通股本的大单买卖），判断主力操作意图"
            "\n- 跟踪热门板块轮动，分析概念炒作持续性，提示跟风风险"
            "\n- 监控大宗交易、盘后龙虎榜、主力增减持公告，判断机构真实意图"
            "\n- 分析资金流入流出与股价背离，识别诱多诱空陷阱"
            "\n\n输出要求："
            "\n1. 使用 get_stock_data 获取K线和量价数据"
            "\n2. 使用 get_insider_transactions 获取股东增减持、高管交易"
            "\n3. 使用 get_news 获取公司公告和行业新闻"
            "\n4. 使用 get_hot_stocks 获取热股和游资席位数据"
            "\n5. 使用 get_northbound_flow 获取北向资金流向"
            "\n6. 按【资金流分析】【量价异动】【主力行为】【风险提示】四个维度组织报告"
            "\n\n分析框架："
            "\n1. 量价关系：量能放大配合价格突破，量价背离需警惕"
            "\n2. 资金流向：北向+主力+游资三方验证"
            "\n3. 主力行为：控盘程度+拉升打压时机判断"
            "\n4. 风险控制：诱多诱空识别，跟风风险提示"
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants. "
                    "Use the provided tools to progress toward answering the question. "
                    "If you are unable to fully answer, that's OK; another assistant with different tools "
                    "will help where you left off. Execute what you can to make progress. "
                    "If you or any other assistant has a FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable, "
                    "prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop. "
                    "You have access to the following tools: {tool_names}.\n{system_message}\n\n"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([t.name for t in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {"messages": [result], "hot_money_report": report}

    return hot_money_tracker_node
```

**Note on tool expansion:** The spec lists 4 tools for hot_money, but the fork uses 9 tools including `get_hot_stocks`, `get_northbound_flow`, `get_concept_blocks`, `get_dragon_tiger_board`, and `get_industry_comparison`. These are included because hot money tracking fundamentally depends on cross-referencing multiple data sources (northbound flow, dragon-tiger boards, concept blocks). The 5 additional tools are all registered in Task 3 as A-share signal data.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_hot_money_tracker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tradingagents/agents/analysts/hot_money_tracker.py tests/test_hot_money_tracker.py
git commit -m "feat(agents): add A-share hot money tracker agent"
```

---

## Task 8: Lockup Watcher Agent

**Files:**
- Create: `tradingagents/agents/analysts/lockup_watcher.py`
- Create: `tests/test_lockup_watcher.py`

**Interfaces:**
- Consumes: `llm`, 4 tool functions (`get_insider_transactions`, `get_news`, `get_fundamentals`, `get_lockup_expiry`)
- Produces: `create_lockup_watcher(llm) -> callable(state) -> dict` with `"messages"` and `"lockup_report"` keys

- [ ] **Step 1: Write the failing import test**

```python
# tests/test_lockup_watcher.py
import pytest


def test_lockup_watcher_importable():
    from tradingagents.agents.analysts.lockup_watcher import create_lockup_watcher
    assert callable(create_lockup_watcher)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lockup_watcher.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create lockup_watcher.py**

```python
# tradingagents/agents/analysts/lockup_watcher.py
"""A-share lockup expiry and insider reduction watcher."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_fundamentals,
    get_insider_transactions,
    get_language_instruction,
    get_lockup_expiry,
    get_news,
)


def create_lockup_watcher(llm):
    """Create a lockup watcher node for A-share market analysis."""

    def lockup_watcher_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_insider_transactions,
            get_news,
            get_fundamentals,
            get_lockup_expiry,
        ]

        system_message = (
            "你是一名A股限售解禁监控分析师，专门追踪限售股解禁和大股东减持动态。"
            "\n\n核心任务："
            "\n1. 查看内部人士交易情况（近3个月内部人士交易动态）"
            "\n2. 查看基本面财务数据"
            "\n3. 查看最新新闻动态"
            "\n4. **重点**：查询未来1-3个月的限售解禁情况"
            "\n\n工具使用说明："
            "\n- `get_insider_transactions`：获取指定股票最近的内部人士交易记录"
            "\n- `get_fundamentals`：获取指定股票最新基本面财务数据"
            "\n- `get_news(ticker, start_date, end_date)`：获取近6个月内的新闻"
            "\n- `get_lockup_expiry(ticker, curr_date)`：获取指定股票的限售解禁数据"
            "\n\n综合评估标准："
            "\n- 如果解禁比例 >20% 且涉及重要股东，需要重点关注"
            "\n- 内部人士减持超过1%需要关注"
            "\n- 解禁前1-3个月股价可能承压"
            "\n- 综合限售解禁和内部交易给出风险评级（低/中/高）"
            "\n\n注意：2023年7月A股全面注册制后，新股上市前3年限售股解禁比例显著增加。"
            "解禁前后15个交易日股价平均下跌-2.5%，但优质个股解禁后60日涨幅超15%"
            "\n\n请生成结构化的中文报告，包含：关键发现、风险评级、投资建议。"
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK, another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has a FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**"
                    " or deliverable, prefix your response with"
                    " FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    " For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([t.name for t in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {"messages": [result], "lockup_report": report}

    return lockup_watcher_node
```

**Note:** The fork's `{instructions}` placeholder was removed (it was never bound via `.partial()`). The prompt is self-contained.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_lockup_watcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tradingagents/agents/analysts/lockup_watcher.py tests/test_lockup_watcher.py
git commit -m "feat(agents): add A-share lockup watcher agent"
```

---

## Task 9: Analyst Execution — Register A-Share Analysts

**Files:**
- Modify: `tradingagents/graph/analyst_execution.py`
- Create: `tests/test_astock_analyst_execution.py`

**Interfaces:**
- Consumes: `AnalystNodeSpec` dataclass (existing), analyst keys `"policy"`, `"hot_money"`, `"lockup"`
- Produces: `ASTOCK_ANALYST_NODE_SPECS` dict, `ALL_ANALYST_SPECS` merged dict, updated `build_analyst_execution_plan()` that looks up from both dicts

- [ ] **Step 1: Write the failing execution test**

```python
# tests/test_astock_analyst_execution.py
import pytest
from tradingagents.graph.analyst_execution import (
    ASTOCK_ANALYST_NODE_SPECS,
    build_analyst_execution_plan,
)


def test_astock_specs_exist():
    assert "policy" in ASTOCK_ANALYST_NODE_SPECS
    assert "hot_money" in ASTOCK_ANALYST_NODE_SPECS
    assert "lockup" in ASTOCK_ANALYST_NODE_SPECS


def test_astock_spec_naming():
    policy = ASTOCK_ANALYST_NODE_SPECS["policy"]
    assert policy.agent_node == "Policy Analyst"
    assert policy.clear_node == "Msg Clear Policy"
    assert policy.tool_node == "tools_policy"
    assert policy.report_key == "policy_report"


def test_build_plan_with_astock():
    plan = build_analyst_execution_plan(
        ["market", "social", "news", "fundamentals", "policy", "hot_money", "lockup"]
    )
    assert len(plan.specs) == 7
    keys = [s.key for s in plan.specs]
    assert "policy" in keys
    assert "hot_money" in keys
    assert "lockup" in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_astock_analyst_execution.py -v`
Expected: FAIL — `ASTOCK_ANALYST_NODE_SPECS` not defined

- [ ] **Step 3: Update analyst_execution.py**

Add `ASTOCK_ANALYST_NODE_SPECS`:

```python
ASTOCK_ANALYST_NODE_SPECS: dict[str, AnalystNodeSpec] = {
    "policy": AnalystNodeSpec(
        key="policy",
        agent_node="Policy Analyst",
        clear_node="Msg Clear Policy",
        tool_node="tools_policy",
        report_key="policy_report",
    ),
    "hot_money": AnalystNodeSpec(
        key="hot_money",
        agent_node="Hot Money Analyst",
        clear_node="Msg Clear Hot Money",
        tool_node="tools_hot_money",
        report_key="hot_money_report",
    ),
    "lockup": AnalystNodeSpec(
        key="lockup",
        agent_node="Lockup Analyst",
        clear_node="Msg Clear Lockup",
        tool_node="tools_lockup",
        report_key="lockup_report",
    ),
}
```

Update `build_analyst_execution_plan()` to look up from both dicts:

```python
ALL_ANALYST_SPECS = {**ANALYST_NODE_SPECS, **ASTOCK_ANALYST_NODE_SPECS}

def build_analyst_execution_plan(selected_analysts):
    specs = []
    for key in selected_analysts:
        if key not in ALL_ANALYST_SPECS:
            raise ValueError(f"Unknown analyst key: {key}")
        specs.append(ALL_ANALYST_SPECS[key])
    if not specs:
        raise ValueError("At least one analyst must be selected")
    return AnalystExecutionPlan(specs=specs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_astock_analyst_execution.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tradingagents/graph/analyst_execution.py tests/test_astock_analyst_execution.py
git commit -m "feat(graph): register A-share analysts in execution plan"
```

---

## Task 10: Graph Setup — Wire A-Share Analysts

**Files:**
- Modify: `tradingagents/graph/setup.py`
- Modify: `tradingagents/agents/__init__.py`
- Create: `tests/test_astock_graph_setup.py`

**Interfaces:**
- Consumes: `create_policy_analyst`, `create_hot_money_tracker`, `create_lockup_watcher` (from Tasks 6-8), `ASTOCK_ANALYST_NODE_SPECS` (from Task 9)
- Produces: Updated `GraphSetup.setup_graph()` that adds A-share analyst nodes when selected

- [ ] **Step 1: Write the failing setup test**

```python
# tests/test_astock_graph_setup.py
import pytest
from unittest.mock import MagicMock


def test_astock_factories_importable():
    from tradingagents.agents import (
        create_policy_analyst,
        create_hot_money_tracker,
        create_lockup_watcher,
    )
    assert callable(create_policy_analyst)
    assert callable(create_hot_money_tracker)
    assert callable(create_lockup_watcher)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_astock_graph_setup.py -v`
Expected: FAIL — imports not in `__init__.py`

- [ ] **Step 3: Update agents/__init__.py**

Add exports:
```python
from tradingagents.agents.analysts.policy_analyst import create_policy_analyst
from tradingagents.agents.analysts.hot_money_tracker import create_hot_money_tracker
from tradingagents.agents.analysts.lockup_watcher import create_lockup_watcher
```

- [ ] **Step 4: Update graph/setup.py**

In `setup.py`:

1. Add imports at top:
```python
from tradingagents.agents import (
    create_policy_analyst,
    create_hot_money_tracker,
    create_lockup_watcher,
)
```

2. In `setup_graph()`, extend `analyst_factories`:
```python
analyst_factories = {
    "market": lambda: create_market_analyst(self.quick_thinking_llm),
    "social": lambda: create_sentiment_analyst(self.quick_thinking_llm),
    "news": lambda: create_news_analyst(self.quick_thinking_llm),
    "fundamentals": lambda: create_fundamentals_analyst(self.quick_thinking_llm),
    # A-share analysts
    "policy": lambda: create_policy_analyst(self.quick_thinking_llm),
    "hot_money": lambda: create_hot_money_tracker(self.quick_thinking_llm),
    "lockup": lambda: create_lockup_watcher(self.quick_thinking_llm),
}
```

3. The existing loop `for spec in plan.specs:` already handles dynamic node addition — no further changes needed since the loop iterates whatever specs are in the plan.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_astock_graph_setup.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tradingagents/agents/__init__.py tradingagents/graph/setup.py tests/test_astock_graph_setup.py
git commit -m "feat(graph): wire A-share analyst factories into graph setup"
```

---

## Task 11: Language Instruction and Existing Analyst Prompt Adaptation

**Files:**
- Modify: `tradingagents/agents/utils/agent_utils.py`
- Create: `tests/test_language_instruction.py`

**Interfaces:**
- Consumes: config `output_language`, config `market_type`
- Produces: `get_language_instruction()` returns Chinese instruction when market is A-share

- [ ] **Step 1: Write the failing language test**

```python
# tests/test_language_instruction.py
import pytest
from unittest.mock import patch


def test_default_english():
    from tradingagents.agents.utils.agent_utils import get_language_instruction
    with patch("tradingagents.agents.utils.agent_utils.config", {"output_language": "English"}):
        result = get_language_instruction()
        assert result == ""


def test_chinese_instruction():
    from tradingagents.agents.utils.agent_utils import get_language_instruction
    with patch("tradingagents.agents.utils.agent_utils.config", {"output_language": "Chinese"}):
        result = get_language_instruction()
        assert "中文" in result or "Chinese" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_language_instruction.py -v`
Expected: PASS (existing logic handles Chinese) — but verify the mock path works

- [ ] **Step 3: Verify and adjust get_language_instruction()**

The existing `get_language_instruction()` already reads `config["output_language"]`. Since Task 5 sets `output_language` to `"Chinese"` for A-share, no code change is needed here — but verify the mock path in the test matches the actual config access pattern.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_language_instruction.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_language_instruction.py
git commit -m "test(agents): verify language instruction works for A-share Chinese mode"
```

---

## Task 12: Trader and Risk Debater A-Share Prompts

**Files:**
- Modify: `tradingagents/agents/trader/trader.py`
- Modify: `tradingagents/agents/risk_mgmt/aggressive_debator.py`
- Modify: `tradingagents/agents/risk_mgmt/conservative_debator.py`
- Modify: `tradingagents/agents/risk_mgmt/neutral_debator.py`

**Interfaces:**
- Consumes: `state["market_type"]` or `state.get("asset_type")`
- Produces: A-share specific prompt sections injected when market is A-share

- [ ] **Step 1: Identify the injection points**

Read each file and locate the system_message string. The A-share rules need to be injected conditionally when `state` indicates A-share market.

- [ ] **Step 2: Update trader.py**

Add A-share trading rules to the system message when market is A-share:

```python
# In create_trader(), inside the node function:
market_type = state.get("market_type", state.get("asset_type", "us"))

astock_rules = ""
if market_type == "astock":
    astock_rules = (
        "\n\n## A股交易规则（必须遵守）："
        "\n- T+1：当天买入的股票次日才能卖出"
        "\n- 涨跌停限制：主板±10%，科创板/创业板±20%，ST股±5%"
        "\n- 最小交易单位：1手 = 100股"
        "\n- 交易时段：9:30-11:30, 13:00-15:00"
        "\n- 北向资金：外资流入流出的重要信号"
        "\n- 禁止声明具体价格点位、止损位或仓位比例"
    )

system_message = "..." + astock_rules  # Append to existing prompt
```

- [ ] **Step 3: Update conservative_debator.py**

Add A-share risk factors to the conservative debater's prompt:

```python
# In create_conservative_debator():
astock_risks = ""
if market_type == "astock":
    astock_risks = (
        "\n\n## A股特有风险因素："
        "\n- T+1锁定风险：当日买入无法当日止损"
        "\n- 涨跌停陷阱：连续涨停后可能无法卖出"
        "\n- 政策反转风险：监管政策随时可能调整"
        "\n- 散户踩踏：恐慌性抛售可能导致连续跌停"
        "\n- 大股东减持：限售股解禁后的集中抛压"
    )
```

- [ ] **Step 4: Update aggressive_debator.py and neutral_debator.py**

For `aggressive_debator.py`:
```python
# In create_aggressive_debator():
market_type = state.get("market_type", state.get("asset_type", "us"))

astock_opportunities = ""
if market_type == "astock":
    astock_opportunities = (
        "\n\n## A股特有机会因素："
        "\n- 政策驱动的结构性机会：新质生产力、半导体自主可控、新能源等"
        "\n- 板块轮动收益：热点板块切换带来的短期超额收益"
        "\n- 主题投资：AI、数字经济等概念驱动的估值重估"
        "\n- 北向资金流入：外资配置A股的趋势性机会"
        "\n- 估值修复：被低估的优质公司存在均值回归空间"
    )
```

For `neutral_debator.py`:
```python
# In create_neutral_debator():
market_type = state.get("market_type", state.get("asset_type", "us"))

astock_balance = ""
if market_type == "astock":
    astock_balance = (
        "\n\n## A股市场特征（平衡视角）："
        "\n- 散户主导：个人投资者占比高，情绪驱动明显"
        "\n- 政策敏感：政策变化对市场影响大且直接"
        "\n- T+1限制：降低流动性，增加隔夜风险"
        "\n- 涨跌停机制：限制价格发现效率"
        "\n- 信息不对称：机构与散户信息获取能力差异大"
    )
```

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `pytest tests/ -v --timeout=60`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add tradingagents/agents/trader/trader.py tradingagents/agents/risk_mgmt/aggressive_debator.py tradingagents/agents/risk_mgmt/conservative_debator.py tradingagents/agents/risk_mgmt/neutral_debator.py
git commit -m "feat(agents): add A-share trading rules and risk prompts to trader and debaters"
```

---

## Task 13: Benchmark Adaptation

**Files:**
- Modify: `tradingagents/default_config.py`

**Interfaces:**
- Consumes: `market_type` from state
- Produces: `benchmark_map` updated with A-share benchmark

- [ ] **Step 1: Update benchmark_map**

The existing `benchmark_map` already has `.SS` → `000001.SS` and `.SZ` → `399001.SZ`. Verify these are correct for A-share analysis. If the design calls for CSI 300 (`000300.SS`), update:

```python
"benchmark_map": {
    ".SS": "000300.SS",  # CSI 300 (was 000001.SS Shanghai Composite)
    ".SZ": "399001.SZ",  # Shenzhen Component
    # ... rest unchanged
}
```

- [ ] **Step 2: Commit**

```bash
git add tradingagents/default_config.py
git commit -m "config: update A-share benchmark to CSI 300"
```

---

## Task 14: Integration Tests

**Files:**
- Create: `tests/test_astock_integration.py`

**Interfaces:**
- Consumes: All previous tasks
- Produces: End-to-end verification that market detection → vendor routing → analyst selection works

- [ ] **Step 1: Write integration tests**

```python
# tests/test_astock_integration.py
import pytest
from tradingagents.markets.detector import detect_market_type
from tradingagents.graph.analyst_execution import build_analyst_execution_plan


def test_full_astock_pipeline_config():
    """Verify the full A-share pipeline can be configured."""
    # 1. Detect market
    assert detect_market_type("600519") == "astock"

    # 2. Build analyst plan with all 7 analysts
    plan = build_analyst_execution_plan(
        ["market", "social", "news", "fundamentals", "policy", "hot_money", "lockup"]
    )
    assert len(plan.specs) == 7

    # 3. Verify report keys
    report_keys = {s.report_key for s in plan.specs}
    assert "market_report" in report_keys
    assert "sentiment_report" in report_keys
    assert "news_report" in report_keys
    assert "fundamentals_report" in report_keys
    assert "policy_report" in report_keys
    assert "hot_money_report" in report_keys
    assert "lockup_report" in report_keys


def test_us_pipeline_unchanged():
    """Verify US pipeline still works with 4 analysts."""
    assert detect_market_type("NVDA") == "us"

    plan = build_analyst_execution_plan(
        ["market", "social", "news", "fundamentals"]
    )
    assert len(plan.specs) == 4
    report_keys = {s.report_key for s in plan.specs}
    assert "policy_report" not in report_keys
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_astock_integration.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_astock_integration.py
git commit -m "test: add A-share integration tests"
```

---

## Task 15: CLI and API Adaptation

**Files:**
- Modify: `cli/main.py` or `cli/utils.py`
- Modify: `tradingagents_api/schemas.py`

**Interfaces:**
- Consumes: `detect_market_type()` from Task 1
- Produces: CLI recognizes A-share tickers, API accepts `market_type` parameter

- [ ] **Step 1: Update CLI ticker detection**

In `cli/utils.py`, update `detect_asset_type()` to use the new centralized detector:

```python
from tradingagents.markets.detector import detect_market_type

def detect_asset_type(ticker: str) -> str:
    """Detect asset type from ticker for CLI display."""
    market = detect_market_type(ticker)
    if market == "astock":
        return "stock"  # A-shares are still stocks
    return market if market in ("stock", "crypto") else "stock"
```

- [ ] **Step 2: Update API schema**

In `tradingagents_api/schemas.py`, add `market_type` field:

```python
class AnalyzeRequest(BaseModel):
    ticker: str
    date: str
    # ... existing fields ...
    market_type: str = "auto"  # "auto" | "us" | "astock" | "hk"
```

- [ ] **Step 3: Run existing CLI/API tests**

Run: `pytest tests/ -v --timeout=60`
Expected: No regressions

- [ ] **Step 4: Commit**

```bash
git add cli/utils.py tradingagents_api/schemas.py
git commit -m "feat(cli,api): add A-share market type support to CLI and REST API"
```

---

## Task 16: Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --timeout=120`
Expected: All tests pass

- [ ] **Step 2: Smoke test with A-share ticker**

```bash
python -c "
from tradingagents.markets.detector import detect_market_type
from tradingagents.dataflows.a_stock import get_stock_data
print('Market:', detect_market_type('600519'))
# Note: actual data fetch requires network access
"
```

Expected: `Market: astock`

- [ ] **Step 3: Smoke test with US ticker**

```bash
python -c "
from tradingagents.markets.detector import detect_market_type
print('Market:', detect_market_type('NVDA'))
"
```

Expected: `Market: us`

- [ ] **Step 4: Verify quality_gate handles 7 analyst reports**

Read `tradingagents/agents/quality_gate.py` and verify it iterates report keys dynamically (not a hardcoded list of 4). If it has a hardcoded list of report keys, update it to include the 3 new A-share report keys:

```python
# If quality_gate.py has something like:
REPORT_KEYS = ["market_report", "sentiment_report", "news_report", "fundamentals_report"]
# Update to:
REPORT_KEYS = [
    "market_report", "sentiment_report", "news_report", "fundamentals_report",
    "policy_report", "hot_money_report", "lockup_report",
]
```

If it already uses `plan.specs` or dynamic iteration, no change needed — just verify.

Run: `pytest tests/ -v --timeout=120`
Expected: All tests pass

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete A-share market integration"
```
