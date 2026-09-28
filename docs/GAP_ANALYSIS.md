# TongDaXin 功能差距分析 (Gap Analysis)

> 日期: 2026-09-07
> 对比: 通达信终端 (TdxW.exe) vs TradingAgents GUI 当前实现
>
> **2026-09-27 状态回标**：本文件已并入并裁决于
> [`specs/2026-09-27-eastmoney-aligned-platform-plan.md`](specs/2026-09-27-eastmoney-aligned-platform-plan.md)。
> 下列正文保留为历史记录，不回改原结论；进展以新方案 §3 + `CONTEXT.md` 为准。
> —— 本节以下「问题 1」现已解决，标注见下。

---

## 🔴 核心问题：数据未显示

### 问题 1: RightInfoPanel 显示 "暂无行情数据"

> **[2026-09-27 已解决]** `RightInfoPanel` 已改为自行每 5s 轮询
> `POST /api/realtime-prices` + 一次性 `GET /api/stock-info/{ticker}`，绕过了
> 原根因（prop `realtimeQuotes.get(ticker)` 为 undefined —— 其实参名已改为 `_quote`
> 且未使用）。原「6 项数据不显示」未再复现；仅余 `TradingViewLayout` 内一处调试
> `console.log`，已列入工单 03 清理。以下为历史分析。

- **现象**: 右侧面板不显示五档盘口、财务摘要等任何数据
- **根因**: `realtimeQuotes.get(ticker)` 返回 `undefined`
- **代码位置**: `TradingViewLayout.tsx:331-332`
- **可能原因**:
  1. WebSocket 连接失败，HTTP polling fallback 未触发
  2. ticker 格式不匹配（前端传 "001232" vs 后端 key "001232"）
  3. `useRealtimePrices` hook 未正确启用

### 验证结果:
- ✅ Backend running on port 8425
- ✅ `POST /api/realtime-prices` returns 五档盘口 data for 001232
- ✅ `GET /api/stock-info/001232` returns 财务/分红/公告
- ❌ Frontend not displaying the data

---

## 📊 通达信功能模块对比

### 一、左侧菜单功能 (Left Menu Features)

| # | 通达信功能 | 当前实现 | 状态 | 备注 |
|---|-----------|---------|------|------|
| 1 | 调研互动 | `astock_features.py` 有 API | ⚠️ | 需要验证数据渲染 |
| 2 | 备查资料 | `astock_features.py` 有 API | ⚠️ | 需要验证数据渲染 |
| 3 | 市场统计 | `market_overview.py` 有基础 | ⚠️ | 缺少交易所规模统计 |
| 4 | 三板 | `astock_features.py` 有 API | ⚠️ | 需要验证 |
| 5 | 股指期货 | `astock_features.py` 有 API | ⚠️ | 需要验证 |
| 6 | 港股数据 | `astock_features.py` 有 API | ⚠️ | 需要验证 |
| 7 | 美股数据 | `astock_features.py` 有 API | ⚠️ | 需要验证 |
| 8 | 基金数据 | `FundDataPanel.tsx` 已实现 | ✅ | 需要验证数据 |
| 9 | 产业链 | `IndustryChainPanel.tsx` 已实现 | ✅ | 需要验证数据 |
| 10 | 行业数据 | `IndustryDataPanel.tsx` 已实现 | ✅ | 需要验证数据 |
| 11 | 宏观分析 | `MacroAnalysisPanel.tsx` 已实现 | ✅ | 需要验证数据 |

### 二、右侧信息面板 (Right Sidebar)

| # | 通达信模块 | 当前实现 | 状态 | 备注 |
|---|-----------|---------|------|------|
| 1 | 五档盘口 | `RightInfoPanel.tsx` | ❌ | **数据不显示** |
| 2 | 财务摘要 | `RightInfoPanel.tsx` | ❌ | **数据不显示** |
| 3 | 股东变动 | `RightInfoPanel.tsx` | ❌ | **数据不显示** |
| 4 | 基金持仓 | `RightInfoPanel.tsx` | ❌ | **数据不显示** |
| 5 | 分红信息 | `RightInfoPanel.tsx` | ❌ | **数据不显示** |
| 6 | 最新公告 | `RightInfoPanel.tsx` | ❌ | **数据不显示** |

### 三、图表区域 (Chart Area)

| # | 通达信功能 | 当前实现 | 状态 |
|---|-----------|---------|------|
| 1 | K线图 | `TradingViewChart` | ✅ |
| 2 | 成交量 | 内置 | ✅ |
| 3 | MACD | `SubPanels` | ✅ |
| 4 | RSI | `SubPanels` | ✅ |
| 5 | 布林带 | `SubPanels` | ✅ |
| 6 | 均线(MA) | overlay | ✅ |
| 7 | 买卖盘曲线 | 缺失 | ❌ |
| 8 | 分时图(Intraday) | `IntradayTimeline` | ✅ |
| 9 | 复权开关 | `ReplayControls` | ✅ |

---

## 🔧 需要修复的具体问题

### P0: RightInfoPanel 数据不显示 (阻塞性)

**问题**: `realtimeQuotes.get(ticker)` 始终返回 undefined

**排查步骤**:
1. 在 `useRealtimePrices.ts` 添加 console.log 追踪
2. 检查 WebSocket 是否连接成功
3. 检查 ticker 格式是否匹配（"001232" vs "sh001232"）
4. 检查 polling fallback 是否触发

**修复方案**:
- 添加 debug logging
- 确认 ticker key 一致
- 如果 WebSocket 失败，确保 HTTP polling 能获取数据

### P1: MarketOverviewPage 数据渲染

所有 tab 使用 `MarkdownRenderer` 回退渲染。需要验证:
- 每个 `_call_*` 函数是否返回正确格式的 markdown
- 东方财富 API 是否可访问（代理/防火墙）
- 缓存是否有效

### P2: 通达信界面布局差异

| 差异 | 通达信 | 当前实现 |
|------|--------|---------|
| 菜单位置 | 左侧垂直菜单 | 顶部 TopBar |
| 市场数据位置 | 独立 Tab | MarketOverviewPage Tab |
| 返回按钮 | 每个子页面 | 仅 market_overview |

---

## 📋 下一步行动

1. **立即修复**: RightInfoPanel 数据不显示 (P0)
   - 添加 console.log 到 `useRealtimePrices`
   - 检查 ticker key
   - 确保 HTTP polling 工作

2. **验证数据流**: 逐个测试所有 API 端点
   - 调研互动
   - 备查资料
   - 三板/期货/港股/美股

3. **UI 对齐**: 调整布局更接近通达信
   - 左侧菜单
   - 更多数据 tab

---

## 测试命令

```bash
# Backend health
curl http://127.0.0.1:8425/

# Realtime prices
curl -X POST http://127.0.0.1:8425/api/realtime-prices \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["001232"]}'

# Stock info
curl http://127.0.0.1:8425/api/stock-info/001232

# Astock features
curl "http://127.0.0.1:8425/api/astock-feature?name=ipo_declaration&ticker=001232"
```
