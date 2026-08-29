# Multi-Platform LLM Support Design

## Overview

Enable TradingAgents to use different LLM providers for quick-thinking and deep-thinking models, allowing users to combine capabilities from multiple platforms (e.g., Anthropic for deep analysis, OpenAI for fast responses).

## Problem Statement

Currently, TradingAgents supports only one LLM provider at a time. Both quick_think_llm and deep_think_llm must come from the same provider, limiting flexibility.

## Design Approach

**Quick/Deep + Provider Combination**: Each model type (quick/deep) can independently select its LLM provider.

## Backend Architecture

### 1. Config Layer (`tradingagents/default_config.py`)

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
}
```

### 2. LLM Factory (`tradingagents/llm_clients/factory.py`)

Add convenience functions:

```python
def create_quick_llm(config: dict, **kwargs) -> BaseChatModel:
    provider = config.get("quick_llm_provider") or config["llm_provider"]
    model = config["quick_think_llm"]
    base_url = config.get("backend_url_quick") or config.get("backend_url")
    return create_llm_client(provider, model, base_url, **kwargs).get_llm()

def create_deep_llm(config: dict, **kwargs) -> BaseChatModel:
    provider = config.get("deep_llm_provider") or config["llm_provider"]
    model = config["deep_think_llm"]
    base_url = config.get("backend_url_deep") or config.get("backend_url")
    return create_llm_client(provider, model, base_url, **kwargs).get_llm()
```

### 3. Graph (`tradingagents/graph/trading_graph.py`)

```python
class TradingAgentsGraph:
    def __init__(self, config: dict):
        self.config = config

        # Create LLMs with independent providers
        self.quick_thinking_llm = create_quick_llm(config, ...)
        self.deep_thinking_llm = create_deep_llm(config, ...)
```

## GUI Design

### LLM Configuration Section

```
┌─────────────────────────────────────────────────────┐
│ LLM 配置                                           │
├─────────────────────────────────────────────────────┤
│ 快速模型 (分析师团队)                               │
│  提供商:  [Dropdown: openai|anthropic|google|...]   │
│  模型:    [Input: gpt-4o-mini]  [Select: ...]      │
│  API Key: [Input: sk-...***]                        │
│  代理URL: [Input: https://.../openai]              │
├─────────────────────────────────────────────────────┤
│ 深度模型 (研究/交易团队)                            │
│  提供商:  [Dropdown: openai|anthropic|google|...]   │
│  模型:    [Input: gpt-4o]  [Select: ...]           │
│  API Key: [Input: sk-...***]                        │
│  代理URL: [Input: https://.../anthropic]           │
├─────────────────────────────────────────────────────┤
│  [测试连接]                                         │
└─────────────────────────────────────────────────────┘
```

### Key UI Behaviors

1. **Provider Change**: Update model dropdown to show available models for that provider
2. **API Key Auto-fill**: Show env var hint (e.g., `OPENAI_API_KEY`) based on provider
3. **URL Default**: Show default base_url for provider, allow override
4. **Test Connection**: Validate quick and deep configs independently

## API Contract

### Request Format

```json
{
  "symbol": "NIO",
  "date": "2026-08-08",
  "language": "Chinese",
  "analyst_team": ["Market", "Sentiment", "News", "Fundamentals"],
  "research_depth": "deep",
  "quick_model": {
    "provider": "anthropic",
    "model": "Kimi",
    "api_key": "sk-ant-...",
    "backend_url": "http://..."
  },
  "deep_model": {
    "provider": "openai",
    "model": "glm-5.2",
    "api_key": "sk-...",
    "backend_url": "http://..."
  }
}
```

### Response Format

```json
{
  "status": "success",
  "quick_model_status": "connected",
  "deep_model_status": "connected",
  "result": {...}
}
```

## Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| Only `llm_provider` set | Both quick/deep use same provider |
| `quick_llm_provider` set, `deep_llm_provider` not | Quick uses specified, deep uses fallback |
| Both set | Each uses its own provider |
| Legacy config (no quick/deep keys) | Works exactly as before |

## Files to Modify

| File | Change Description |
|------|-------------------|
| `tradingagents/default_config.py` | Add quick/deep provider config keys |
| `tradingagents/llm_clients/factory.py` | Add `create_quick_llm`, `create_deep_llm` |
| `tradingagents/graph/trading_graph.py` | Use new factory functions |
| `tradingagents/graph/setup.py` | No change needed (already receives LLM objects) |
| `tradingagents_api/routes.py` | Parse split config from request |
| `tradingagents_gui/src/components/` | Dual LLM config UI |
| `tradingagents_gui/src/api/client.ts` | Update API payload structure |

## Testing

1. **Unit Tests**: Factory routing for each provider
2. **Integration Tests**: Graph with different quick/deep providers
3. **GUI Tests**: Config UI interactions

## Success Criteria

1. Quick and deep models can use different providers
2. Single-provider configs still work (backward compatible)
3. GUI clearly shows separate configs for quick/deep
4. Test connection validates both configs independently
5. No regression in existing functionality
