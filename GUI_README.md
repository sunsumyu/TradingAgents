# TradingAgents 桌面 GUI

基于 **Tauri 2 + React 18 + Tailwind CSS** 的桌面客户端，通过 HTTP/SSE 与 Python FastAPI 后端通信，提供图形化股票分析界面。

## 架构

```
┌───────────────────────────┐        HTTP/SSE         ┌──────────────────────────┐
│   Tauri Desktop GUI       │ ◄─────────────────────► │   Python FastAPI Server   │
│   (Rust 壳 + React 前端)  │                          │   (tradingagents_api/)   │
│                           │   POST /api/analyze      │                          │
│  - 参数输入面板           │   SSE /api/analyze/stream│  - TradingAgentsGraph    │
│  - 实时进度展示           │   GET /api/report/{id}   │  - LangGraph streaming   │
│  - Markdown 报告渲染      │   GET /api/providers     │  - 进度事件推送           │
└───────────────────────────┘                          └──────────────────────────┘
```

## 快速开始

### 前置条件

- Python 3.10+ 且已安装 TradingAgents 依赖
- Node.js 18+ 和 npm
- Rust toolchain (rustup)
- 已安装的 Python 包：`pip install fastapi uvicorn sse-starlette`

### 一键启动

```bash
# 1. 安装后端依赖
pip install fastapi uvicorn sse-starlette

# 2. 编译 GUI（首次编译约 8 分钟，之后增量秒级）
cd tradingagents_gui
npm install
npm run tauri build -- --no-bundle
cd ..

# 3. 一键启动（自动拉起后端 + GUI）
python start_gui.py
```

### 手动启动

```bash
# 终端 1: 启动 Python 后端
uvicorn tradingagents_api.server:app --host 127.0.0.1 --port 8420

# 终端 2: 开发模式（热更新）
cd tradingagents_gui
npm run tauri dev
```

### 前端开发（浏览器预览，无需 Tauri）

```bash
cd tradingagents_gui
npm run dev   # 打开 http://localhost:5173
```

## GUI 功能

### 1. 配置面板
- 输入股票代码（如 AAPL、NVDA、0700.HK、600519.SS）
- 选择分析日期
- 选择输出语言（中文、英文等 12 种语言）
- 勾选分析师团队（市场、情绪、新闻、基本面）
- 选择研究深度（浅度 1 轮 / 中度 3 轮 / 深度 5 轮辩论）
- 选择 LLM 提供商和模型
- 输入 API Key

### 2. 进度面板
- 实时显示 5 个阶段的 agent 状态
- 每个 agent 显示状态图标：✅ 完成 / 🔄 进行中 / ⬜ 等待 / ❌ 错误
- 滚动日志显示最新消息
- 显示已用时间

### 3. 报告面板
- 信号颜色标识：🟢 Buy/Overweight、🟡 Hold、🔴 Underweight/Sell
- 5 个 Tab 切换查看不同阶段的报告
- Markdown 内容渲染
- 保存报告按钮

## 支持的 LLM 提供商

OpenAI、Anthropic、Google Gemini、xAI Grok、DeepSeek、通义千问、智谱 GLM、MiniMax、Ollama、OpenRouter、Mistral、Moonshot、Groq、NVIDIA NIM、Azure OpenAI、Bedrock

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/providers` | 提供商列表 |
| GET | `/api/models/{provider}` | 模型列表 |
| POST | `/api/analyze` | 启动分析 |
| GET | `/api/analyze/{task_id}/stream` | SSE 实时进度 |
| GET | `/api/report/{task_id}` | 获取报告 |
