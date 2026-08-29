# Multi-Platform LLM Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable TradingAgents to use different LLM providers for quick-thinking and deep-thinking models.

**Architecture:** Split the single `llm_provider` config into `quick_llm_provider` and `deep_llm_provider`, with backward-compatible fallback to the legacy single-provider config. Add factory helper functions and update the GUI for dual-model configuration.

**Tech Stack:** Python (LangChain), React (GUI), FastAPI (API)

## Global Constraints

- Python >= 3.10
- React 18+
- Maintain backward compatibility with existing single-provider configs
- All provider-specific kwargs (thinking_level, reasoning_effort, effort) must work independently per model

---

## File Structure

| File | Responsibility |
|------|----------------|
| `tradingagents/default_config.py` | Config keys for quick/deep providers |
| `tradingagents/llm_clients/factory.py` | `create_quick_llm()`, `create_deep_llm()` |
| `tradingagents/graph/trading_graph.py` | Create separate quick/deep LLMs |
| `tradingagents_api/routes.py` | Parse split config from API request |
| `tradingagents_gui/src/components/LLMConfig.tsx` | Dual-model config UI |

---

### Task 1: Add Config Keys

**Files:**
- Modify: `tradingagents/default_config.py`

**Interfaces:**
- Produces: `quick_llm_provider`, `deep_llm_provider`, `backend_url_quick`, `backend_url_deep` config keys

- [ ] **Step 1: Add new config keys**

Add to `DEFAULT_CONFIG` dict after existing `llm_provider`:

```python
DEFAULT_CONFIG = {
    # Quick model configuration
    "quick_llm_provider": None,  # Falls back to llm_provider if None
    "quick_think_llm": "gpt-4o-mini",
    "backend_url_quick": None,   # Falls back to backend_url if None

    # Deep model configuration
    "deep_llm_provider": None,   # Falls back to llm_provider if None
    "deep_think_llm": "gpt-4o",
    "backend_url_deep": None,    # Falls back to backend_url if None

    # Legacy single-provider config (backward compatible)
    "llm_provider": "openai",
    "backend_url": None,
    # ... rest of existing config
}
```

- [ ] **Step 2: Add environment variable overrides**

Add to `_ENV_OVERRIDES` mapping:

```python
_ENV_OVERRIDES = {
    # ... existing overrides
    "quick_llm_provider": "TRADINGAGENTS_QUICK_LLM_PROVIDER",
    "deep_llm_provider": "TRADINGAGENTS_DEEP_LLM_PROVIDER",
    "backend_url_quick": "TRADINGAGENTS_BACKEND_URL_QUICK",
    "backend_url_deep": "TRADINGAGENTS_BACKEND_URL_DEEP",
}
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v -k config`
Expected: All config tests pass

- [ ] **Step 4: Commit**

```bash
git add tradingagents/default_config.py
git commit -m "feat(config): add quick/deep provider config keys"
```

---

### Task 2: Add Factory Helper Functions

**Files:**
- Modify: `tradingagents/llm_clients/factory.py`

**Interfaces:**
- Consumes: `quick_llm_provider`, `deep_llm_provider` config keys
- Produces: `create_quick_llm(config, **kwargs)`, `create_deep_llm(config, **kwargs)` functions

- [ ] **Step 1: Add create_quick_llm function**

```python
def create_quick_llm(config: dict, **kwargs) -> BaseChatModel:
    """Create the quick-thinking LLM with its configured provider."""
    provider = config.get("quick_llm_provider") or config.get("llm_provider", "openai")
    model = config.get("quick_think_llm", "gpt-4o-mini")
    base_url = config.get("backend_url_quick") or config.get("backend_url")

    client = create_llm_client(provider, model, base_url, **kwargs)
    return client.get_llm()
```

- [ ] **Step 2: Add create_deep_llm function**

```python
def create_deep_llm(config: dict, **kwargs) -> BaseChatModel:
    """Create the deep-thinking LLM with its configured provider."""
    provider = config.get("deep_llm_provider") or config.get("llm_provider", "openai")
    model = config.get("deep_think_llm", "gpt-4o")
    base_url = config.get("backend_url_deep") or config.get("backend_url")

    client = create_llm_client(provider, model, base_url, **kwargs)
    return client.get_llm()
```

- [ ] **Step 3: Write test for factory helpers**

Create `tests/test_llm_factory.py`:

```python
import pytest
from tradingagents.llm_clients.factory import create_quick_llm, create_deep_llm

def test_create_quick_llm_fallback_to_single_provider():
    config = {
        "llm_provider": "openai",
        "quick_think_llm": "gpt-4o-mini",
        "backend_url": None,
    }
    llm = create_quick_llm(config)
    assert llm is not None

def test_create_quick_llm_independent_provider():
    config = {
        "quick_llm_provider": "anthropic",
        "quick_think_llm": "Kimi",
        "llm_provider": "openai",  # Should be ignored
    }
    llm = create_quick_llm(config)
    assert llm is not None

def test_create_deep_llm_independent_provider():
    config = {
        "deep_llm_provider": "google",
        "deep_think_llm": "gemini-2.0-flash",
    }
    llm = create_deep_llm(config)
    assert llm is not None
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_llm_factory.py -v`
Expected: All tests pass (with valid API keys)

- [ ] **Step 5: Commit**

```bash
git add tradingagents/llm_clients/factory.py tests/test_llm_factory.py
git commit -m "feat(factory): add create_quick_llm and create_deep_llm helpers"
```

---

### Task 3: Update Graph to Use New Factory

**Files:**
- Modify: `tradingagents/graph/trading_graph.py:65-150`

**Interfaces:**
- Consumes: `create_quick_llm`, `create_deep_llm` from factory
- Produces: `self.quick_thinking_llm`, `self.deep_thinking_llm` with independent providers

- [ ] **Step 1: Import new factory functions**

```python
from tradingagents.llm_clients.factory import create_quick_llm, create_deep_llm
```

- [ ] **Step 2: Replace LLM creation in __init__**

Replace the existing LLM creation block with:

```python
class TradingAgentsGraph:
    def __init__(self, config: dict):
        self.config = config

        # Build provider-specific kwargs
        quick_kwargs = self._get_provider_kwargs("quick")
        deep_kwargs = self._get_provider_kwargs("deep")

        # Create LLMs with independent providers
        self.quick_thinking_llm = create_quick_llm(config, **quick_kwargs)
        self.deep_thinking_llm = create_deep_llm(config, **deep_kwargs)
```

- [ ] **Step 3: Update _get_provider_kwargs to handle model type**

```python
def _get_provider_kwargs(self, model_type: str = "quick") -> dict:
    """Get provider-specific kwargs for a model type."""
    provider_key = f"{model_type}_llm_provider" if model_type in ("quick", "deep") else "llm_provider"
    provider = self.config.get(provider_key) or self.config.get("llm_provider")

    kwargs = {
        "temperature": self.config.get("temperature", 0.7),
        "max_retries": self.config.get("llm_max_retries", 2),
    }

    # Add API key
    from tradingagents.llm_clients.api_key_env import get_api_key
    api_key = get_api_key(provider)
    if api_key:
        kwargs["api_key"] = api_key

    # Add provider-specific reasoning knobs
    if provider == "google":
        kwargs["thinking_level"] = self.config.get("google_thinking_level")
    elif provider == "openai":
        kwargs["reasoning_effort"] = self.config.get("openai_reasoning_effort")
    elif provider == "anthropic":
        kwargs["effort"] = self.config.get("anthropic_effort")

    return kwargs
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v -k graph`
Expected: Graph tests pass

- [ ] **Step 5: Commit**

```bash
git add tradingagents/graph/trading_graph.py
git commit -m "feat(graph): use create_quick_llm/create_deep_llm for independent providers"
```

---

### Task 4: Update API Routes

**Files:**
- Modify: `tradingagents_api/routes.py`

**Interfaces:**
- Consumes: Request payload with `quick_model` and `deep_model` objects
- Produces: Config dict with `quick_llm_provider`, `deep_llm_provider`, etc.

- [ ] **Step 1: Update request schema**

```python
from pydantic import BaseModel, Field
from typing import Optional

class ModelConfig(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = None
    backend_url: Optional[str] = None

class AnalysisRequest(BaseModel):
    symbol: str
    date: str
    language: str = "English"
    analyst_team: list[str] = ["Market", "Sentiment", "News", "Fundamentals"]
    research_depth: str = "medium"
    # New: split model config
    quick_model: ModelConfig
    deep_model: ModelConfig
    # Legacy: single model config (backward compatible)
    llm_provider: Optional[str] = None
    model: Optional[str] = None
```

- [ ] **Step 2: Add config builder function**

```python
def build_config(request: AnalysisRequest) -> dict:
    """Build TradingAgents config from API request."""
    config = {
        "symbol": request.symbol,
        "date": request.date,
        "language": request.language,
        "analyst_team": request.analyst_team,
        "research_depth": request.research_depth,
    }

    # New split config
    if request.quick_model:
        config["quick_llm_provider"] = request.quick_model.provider
        config["quick_think_llm"] = request.quick_model.model
        if request.quick_model.api_key:
            config["quick_api_key"] = request.quick_model.api_key
        if request.quick_model.backend_url:
            config["backend_url_quick"] = request.quick_model.backend_url

    if request.deep_model:
        config["deep_llm_provider"] = request.deep_model.provider
        config["deep_think_llm"] = request.deep_model.model
        if request.deep_model.api_key:
            config["deep_api_key"] = request.deep_model.api_key
        if request.deep_model.backend_url:
            config["backend_url_deep"] = request.deep_model.backend_url

    # Legacy single config fallback
    if request.llm_provider and not request.quick_model:
        config["llm_provider"] = request.llm_provider
        config["deep_think_llm"] = request.model or "gpt-4o"

    return config
```

- [ ] **Step 3: Update analysis endpoint**

```python
@app.post("/api/analyze")
async def analyze(request: AnalysisRequest):
    config = build_config(request)
    # ... rest of analysis logic
```

- [ ] **Step 4: Add test connection endpoint**

```python
@app.post("/api/test-connection")
async def test_connection(model_config: ModelConfig):
    """Test connection to a specific LLM provider."""
    try:
        from tradingagents.llm_clients.factory import create_llm_client
        client = create_llm_client(
            model_config.provider,
            model_config.model,
            model_config.backend_url
        )
        # Simple test call
        llm = client.get_llm()
        result = llm.invoke("Say 'connected'")
        return {"status": "success", "message": str(result)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/api/ -v`
Expected: API tests pass

- [ ] **Step 6: Commit**

```bash
git add tradingagents_api/routes.py
git commit -m "feat(api): add split model config support"
```

---

### Task 5: Update GUI LLM Config Component

**Files:**
- Create/Modify: `tradingagents_gui/src/components/LLMConfig.tsx`
- Modify: `tradingagents_gui/src/api/client.ts`

**Interfaces:**
- Consumes: Provider list from model_catalog
- Produces: `quick_model` and `deep_model` config objects for API

- [ ] **Step 1: Create dual-model config component**

```tsx
// tradingagents_gui/src/components/LLMConfig.tsx
import React, { useState } from 'react';

interface ModelConfig {
  provider: string;
  model: string;
  api_key: string;
  backend_url: string;
}

interface LLMConfigProps {
  quickModel: ModelConfig;
  deepModel: ModelConfig;
  onQuickModelChange: (config: ModelConfig) => void;
  onDeepModelChange: (config: ModelConfig) => void;
}

export const LLMConfig: React.FC<LLMConfigProps> = ({
  quickModel,
  deepModel,
  onQuickModelChange,
  onDeepModelChange,
}) => {
  // ... render dual config UI
};
```

- [ ] **Step 2: Add model dropdown per provider**

```tsx
const ModelDropdown = ({ provider, value, onChange }) => {
  const models = getModelOptions(provider); // From model_catalog
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {models.map(m => <option key={m} value={m}>{m}</option>)}
    </select>
  );
};
```

- [ ] **Step 3: Update API client**

```typescript
// tradingagents_gui/src/api/client.ts
interface AnalysisRequest {
  symbol: string;
  date: string;
  language: string;
  quick_model: {
    provider: string;
    model: string;
    api_key: string;
    backend_url: string;
  };
  deep_model: {
    provider: string;
    model: string;
    api_key: string;
    backend_url: string;
  };
}
```

- [ ] **Step 4: Add test connection button**

```tsx
const testConnection = async (modelConfig: ModelConfig) => {
  const response = await fetch('/api/test-connection', {
    method: 'POST',
    body: JSON.stringify(modelConfig),
  });
  const result = await response.json();
  return result.status === 'success';
};
```

- [ ] **Step 5: Run GUI tests**

Run: `cd tradingagents_gui && npm test`
Expected: All component tests pass

- [ ] **Step 6: Commit**

```bash
git add tradingagents_gui/src/components/LLMConfig.tsx tradingagents_gui/src/api/client.ts
git commit -m "feat(gui): add dual-model LLM configuration UI"
```

---

### Task 6: Integration Test

**Files:**
- Create: `tests/test_multi_platform_integration.py`

- [ ] **Step 1: Write integration test**

```python
import pytest
from tradingagents.graph.trading_graph import TradingAgentsGraph

def test_multi_platform_config():
    config = {
        "symbol": "NIO",
        "date": "2026-08-08",
        "quick_llm_provider": "anthropic",
        "quick_think_llm": "Kimi",
        "deep_llm_provider": "openai",
        "deep_think_llm": "gpt-4o",
        "llm_provider": "openai",  # Should be ignored
    }
    graph = TradingAgentsGraph(config)
    assert graph.quick_thinking_llm is not None
    assert graph.deep_thinking_llm is not None
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_multi_platform_integration.py -v`
Expected: Test passes (with valid API keys)

- [ ] **Step 3: Commit**

```bash
git add tests/test_multi_platform_integration.py
git commit -m "test: add multi-platform LLM integration test"
```

---

### Task 7: Update Documentation

**Files:**
- Modify: `README.md` or `docs/configuration.md`

- [ ] **Step 1: Add multi-platform config docs**

```markdown
## Multi-Platform LLM Configuration

TradingAgents supports using different LLM providers for quick and deep thinking models.

### Configuration Options

| Key | Description | Default |
|-----|-------------|---------|
| `quick_llm_provider` | Provider for quick-thinking model | Falls back to `llm_provider` |
| `quick_think_llm` | Model for quick analysis | `gpt-4o-mini` |
| `backend_url_quick` | Base URL for quick model | Falls back to `backend_url` |
| `deep_llm_provider` | Provider for deep-thinking model | Falls back to `llm_provider` |
| `deep_think_llm` | Model for deep analysis | `gpt-4o` |
| `backend_url_deep` | Base URL for deep model | Falls back to `backend_url` |

### Example

```python
config = {
    "quick_llm_provider": "anthropic",
    "quick_think_llm": "Kimi",
    "deep_llm_provider": "openai",
    "deep_think_llm": "gpt-4o",
}
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md docs/configuration.md
git commit -m "docs: add multi-platform LLM configuration guide"
```

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-10-multi-platform-llm-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
