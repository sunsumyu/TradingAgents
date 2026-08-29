# 通达信风格交易平台设计文档

> **文档驱动开发 (DDD)** — 本文档是功能开发的唯一真相来源。所有代码实现必须先在此文档中定义接口，再编写实现。

## 目录

1. [架构总览](#1-架构总览)
2. [深度模块设计](#2-深度模块设计)
3. [模块接口规范](#3-模块接口规范)
4. [实现路线图](#4-实现路线图)
5. [测试策略](#5-测试策略)
6. [开源参考](#6-开源参考)

---

## 1. 架构总览

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| **深度模块** | 小接口 + 大实现，调用者学习成本最小化 |
| **接缝优先** | 每个模块通过接缝(Seam)与外界交互，可独立替换 |
| **适配器模式** | 数据源、指标计算、绘图工具均为适配器，可插拔 |
| **事件驱动** | 行情推送、用户操作、策略信号均为事件 |
| **离线优先** | 所有数据本地缓存，支持断网使用 |

### 1.2 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      GUI Layer (React)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Chart   │ │ Drawing  │ │ Screener │ │ Portfolio│       │
│  │  Engine  │ │  Engine  │ │  Engine  │ │  Engine  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────┤
│                    API Layer (FastAPI)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  Market  │ │ Indicator│ │  Signal  │ │  Cache   │       │
│  │  Data    │ │  Compute │ │  Engine  │ │  Manager │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────┤
│                    Data Layer (Vendor Routing)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │  TDX     │ │ Eastmoney│ │  Sina    │ │ yfinance │       │
│  │ Protocol │ │   API    │ │  Finance │ │  API     │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────┤
│                    Storage Layer (SQLite + CSV)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ OHLCV    │ │Indicator │ │ Drawing  │ │Strategy  │       │
│  │ Cache    │ │ Cache    │ │ Store    │ │ Store    │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 技术栈

| 层级 | 技术 | 理由 |
|------|------|------|
| GUI | React 18 + ECharts 6 + TypeScript | 现有基础，ECharts 金融图表成熟 |
| API | FastAPI + Pydantic v2 | 现有基础，高性能异步 |
| 数据 | Python 3.10+ + pandas + stockstats | 科学计算生态 |
| 缓存 | SQLite + 文件系统 | 轻量级，无需额外服务 |
| 桌面 | Tauri 2.x (Rust) | 跨平台，原生性能 |

---

## 2. 深度模块设计

### 2.1 模块总览

```
TradingAgents
├── chart_engine/           # 图表引擎 (深度模块)
│   ├── ChartRenderer       # 渲染器接口
│   ├── IndicatorComputer   # 指标计算器
│   ├── DrawingManager      # 绘图管理器
│   └── TimeframeManager    # 周期管理器
├── data_center/            # 数据中心 (深度模块)
│   ├── QuoteProvider       # 行情提供者
│   ├── FundamentalProvider # 基本面提供者
│   ├── NewsProvider        # 新闻提供者
│   └── CacheManager        # 缓存管理器
├── signal_engine/          # 信号引擎 (深度模块)
│   ├── IndicatorLibrary    # 指标库
│   ├── StrategyRunner      # 策略运行器
│   └── AlertManager        # 预警管理器
├── screener_engine/        # 选股引擎 (深度模块)
│   ├── FilterCompiler      # 筛选条件编译器
│   ├── StockRanker         # 股票排名器
│   └── TemplateManager     # 模板管理器
└── portfolio_engine/       # 组合引擎 (深度模块)
    ├── PositionTracker     # 持仓跟踪器
    ├── OrderManager        # 订单管理器
    └── RiskAnalyzer        # 风险分析器
```

### 2.2 图表引擎 (Chart Engine)

**职责**: 管理所有图表渲染、指标计算、绘图工具交互

**深度**: 接口仅 5 个方法，内部包含 15+ 指标、5+ 绘图工具、11 种周期

```python
class ChartEngine:
    """图表引擎 — 深度模块，小接口大实现"""
    
    def render(
        self,
        ticker: str,
        timeframe: str,           # "1m" | "5m" | "15m" | "30m" | "60m" | "1D" | "1W" | "1M"
        indicators: list[str],    # ["MA", "MACD", "RSI", ...]
        drawings: list[Drawing],  # 绘图工具状态
    ) -> ChartState:
        """渲染图表，返回完整图表状态"""
        ...
    
    def compute_indicator(
        self,
        data: pd.DataFrame,
        indicator: str,
        params: dict[str, Any],
    ) -> IndicatorResult:
        """计算技术指标"""
        ...
    
    def add_drawing(
        self,
        drawing_type: str,
        points: list[tuple[float, float]],
        style: DrawingStyle,
    ) -> Drawing:
        """添加绘图工具"""
        ...
    
    def export_image(
        self,
        format: str = "png",
        width: int = 1920,
        height: int = 1080,
    ) -> bytes:
        """导出图表为图片"""
        ...
    
    def replay(
        self,
        ticker: str,
        timeframe: str,
        speed: float = 1.0,
        start_date: str | None = None,
    ) -> Iterator[ChartSnapshot]:
        """K 线回放"""
        ...
```

### 2.3 数据中心 (Data Center)

**职责**: 统一数据访问层，屏蔽多数据源差异，提供离线缓存

**深度**: 接口仅 4 个方法，内部包含 17+ 数据源适配器、SQLite 缓存、数据清洗

```python
class DataCenter:
    """数据中心 — 深度模块，统一数据访问"""
    
    def get_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",  # qfq=前复权, hfq=后复权, none=不复权
    ) -> pd.DataFrame:
        """获取 OHLCV 数据，自动缓存和数据源路由"""
        ...
    
    def get_realtime(
        self,
        tickers: list[str],
    ) -> dict[str, Quote]:
        """批量获取实时行情"""
        ...
    
    def get_fundamental(
        self,
        ticker: str,
        data_type: str,  # "balance_sheet" | "income" | "cashflow" | "indicator"
    ) -> dict[str, Any]:
        """获取基本面数据"""
        ...
    
    def get_news(
        self,
        ticker: str,
        days: int = 7,
    ) -> list[NewsItem]:
        """获取新闻"""
        ...
```

### 2.4 信号引擎 (Signal Engine)

**职责**: 技术指标计算、策略运行、买卖信号生成、预警管理

**深度**: 接口仅 3 个方法，内部包含 25+ 指标、策略模板、预警规则

```python
class SignalEngine:
    """信号引擎 — 深度模块，技术分析核心"""
    
    def compute_signals(
        self,
        ticker: str,
        timeframe: str,
        indicators: list[str],
        params: dict[str, list[Any]],
    ) -> SignalResult:
        """计算技术指标信号，返回综合评分"""
        ...
    
    def run_strategy(
        self,
        strategy: Strategy,
        ticker: str,
        timeframe: str,
        params: dict[str, Any],
    ) -> StrategyResult:
        """运行策略，返回回测结果"""
        ...
    
    def check_alerts(
        self,
        ticker: str,
        price: float,
        volume: float,
    ) -> list[Alert]:
        """检查预警条件，触发则返回预警列表"""
        ...
```

### 2.5 选股引擎 (Screener Engine)

**职责**: 条件选股、模板管理、排名筛选

**深度**: 接口仅 3 个方法，内部包含 50+ 预定义条件、模板系统、LLM 自然语言解析

```python
class ScreenerEngine:
    """选股引擎 — 深度模块，条件选股核心"""
    
    def screen(
        self,
        criteria: list[Filter],
        sort_by: str | None = None,
        ascending: bool = False,
        limit: int = 50,
    ) -> list[ScreenerResult]:
        """条件选股，返回排名结果"""
        ...
    
    def screen_natural(
        self,
        query: str,  # 自然语言查询，如 "PE<20 消费股 北向连续加仓"
    ) -> list[ScreenerResult]:
        """自然语言选股 (LLM 解析)"""
        ...
    
    def get_templates(self) -> list[Template]:
        """获取预定义选股模板"""
        ...
```

### 2.6 组合引擎 (Portfolio Engine)

**职责**: 持仓管理、订单执行、风险分析、绩效评估

**深度**: 接口仅 4 个方法，内部包含仓位跟踪、P&L 计算、风险指标、基准对比

```python
class PortfolioEngine:
    """组合引擎 — 深度模块，模拟交易核心"""
    
    def execute_trade(
        self,
        ticker: str,
        side: str,  # "buy" | "sell"
        quantity: int,
        price: float,
        reason: str = "",
    ) -> TradeResult:
        """执行交易，更新持仓"""
        ...
    
    def get_positions(self) -> PortfolioSummary:
        """获取持仓汇总，包含 P&L、收益率、风险指标"""
        ...
    
    def get_performance(
        self,
        benchmark: str = "000300",  # 沪深300
    ) -> PerformanceResult:
        """获取绩效分析，包含夏普比率、最大回撤、胜率等"""
        ...
    
    def get_history(self) -> list[TradeRecord]:
        """获取交易历史"""
        ...
```

---

## 3. 模块接口规范

### 3.1 图表引擎接口

#### 3.1.1 周期枚举

```python
from enum import Enum

class Timeframe(Enum):
    """K 线周期"""
    MIN_1 = "1m"
    MIN_2 = "2m"
    MIN_3 = "3m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    MIN_60 = "60m"
    DAILY = "1D"
    WEEKLY = "1W"
    MONTHLY = "1M"
    QUARTERLY = "3M"
    YEARLY = "1Y"
    ALL = "ALL"
    
    @property
    def default_days(self) -> int:
        """默认回溯天数"""
        mapping = {
            "1m": 1, "2m": 2, "3m": 3, "5m": 5,
            "15m": 10, "30m": 20, "60m": 60,
            "1D": 90, "1W": 180, "1M": 365,
            "3M": 730, "1Y": 1825, "ALL": 3650,
        }
        return mapping[self.value]
    
    @property
    def max_bars(self) -> int:
        """最大返回条数"""
        if self.value.endswith("m"):
            return 800
        return 500
```

#### 3.1.2 技术指标定义

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class IndicatorDef:
    """技术指标定义"""
    name: str                    # 指标名称
    category: str                # "overlay" | "oscillator" | "volume"
    params: dict[str, Any]       # 默认参数
    param_ranges: dict[str, tuple[int, int]]  # 参数范围
    description: str             # 中文描述

# 预定义指标库
INDICATOR_LIBRARY: dict[str, IndicatorDef] = {
    # 叠加指标 (主图)
    "MA": IndicatorDef(
        name="移动平均线",
        category="overlay",
        params={"period": 20},
        param_ranges={"period": (1, 250)},
        description="简单移动平均线",
    ),
    "EMA": IndicatorDef(
        name="指数移动平均线",
        category="overlay",
        params={"period": 20},
        param_ranges={"period": (1, 250)},
        description="指数移动平均线",
    ),
    "BOLL": IndicatorDef(
        name="布林带",
        category="overlay",
        params={"period": 20, "std_dev": 2},
        param_ranges={"period": (5, 100), "std_dev": (1, 4)},
        description="布林带通道",
    ),
    "SAR": IndicatorDef(
        name="抛物线转向",
        category="overlay",
        params={"af_start": 0.02, "af_step": 0.02, "af_max": 0.2},
        param_ranges={"af_start": (0.01, 0.1), "af_step": (0.01, 0.1), "af_max": (0.1, 0.5)},
        description="抛物线转向指标",
    ),
    
    # 振荡指标 (副图)
    "MACD": IndicatorDef(
        name="MACD",
        category="oscillator",
        params={"fast": 12, "slow": 26, "signal": 9},
        param_ranges={"fast": (2, 50), "slow": (5, 100), "signal": (2, 50)},
        description="指数平滑异同移动平均线",
    ),
    "RSI": IndicatorDef(
        name="相对强弱指数",
        category="oscillator",
        params={"period": 14},
        param_ranges={"period": (2, 100)},
        description="相对强弱指数",
    ),
    "KDJ": IndicatorDef(
        name="随机指标",
        category="oscillator",
        params={"k_period": 9, "d_period": 3, "j_period": 3},
        param_ranges={"k_period": (2, 50), "d_period": (2, 20), "j_period": (2, 20)},
        description="随机指标 KDJ",
    ),
    "WR": IndicatorDef(
        name="威廉指标",
        category="oscillator",
        params={"period": 14},
        param_ranges={"period": (2, 100)},
        description="威廉指标 %R",
    ),
    "CCI": IndicatorDef(
        name="顺势指标",
        category="oscillator",
        params={"period": 20},
        param_ranges={"period": (5, 100)},
        description="商品通道指数",
    ),
    "DMI": IndicatorDef(
        name="趋向指标",
        category="oscillator",
        params={"period": 14},
        param_ranges={"period": (5, 100)},
        description="趋向指标 DMI",
    ),
    "TRIX": IndicatorDef(
        name="三重指数平滑移动平均",
        category="oscillator",
        params={"period": 12},
        param_ranges={"period": (5, 50)},
        description="三重指数平滑移动平均",
    ),
    "DMA": IndicatorDef(
        name="平行线差指标",
        category="oscillator",
        params={"short_period": 10, "long_period": 50},
        param_ranges={"short_period": (2, 50), "long_period": (10, 200)},
        description="平行线差指标",
    ),
    "ROC": IndicatorDef(
        name="变动率指标",
        category="oscillator",
        params={"period": 12},
        param_ranges={"period": (2, 100)},
        description="价格变动率",
    ),
    "MTM": IndicatorDef(
        name="动量指标",
        category="oscillator",
        params={"period": 12},
        param_ranges={"period": (2, 100)},
        description="动量指标",
    ),
    "BIAS": IndicatorDef(
        name="乖离率",
        category="oscillator",
        params={"period": 20},
        param_ranges={"period": (2, 100)},
        description="乖离率",
    ),
    "ASI": IndicatorDef(
        name="振动升降指标",
        category="oscillator",
        params={"period": 26},
        param_ranges={"period": (5, 50)},
        description="振动升降指标",
    ),
    "EMV": IndicatorDef(
        name="简易波动指标",
        category="oscillator",
        params={"period": 14},
        param_ranges={"period": (5, 50)},
        description="简易波动指标",
    ),
    "ARBR": IndicatorDef(
        name="人气意愿指标",
        category="oscillator",
        params={"period": 26},
        param_ranges={"period": (5, 50)},
        description="人气意愿指标",
    ),
    "CR": IndicatorDef(
        name="能量指标",
        category="oscillator",
        params={"period": 26},
        param_ranges={"period": (5, 50)},
        description="能量指标",
    ),
    "VR": IndicatorDef(
        name="成交量变异率",
        category="volume",
        params={"period": 26},
        param_ranges={"period": (5, 50)},
        description="成交量变异率",
    ),
    "OBV": IndicatorDef(
        name="能量潮",
        category="volume",
        params={},
        param_ranges={},
        description="能量潮指标",
    ),
    "VWAP": IndicatorDef(
        name="成交量加权平均价",
        category="volume",
        params={},
        param_ranges={},
        description="成交量加权平均价",
    },
}
```

#### 3.1.3 绘图工具定义

```python
from dataclasses import dataclass
from enum import Enum

class DrawingType(Enum):
    """绘图工具类型"""
    CROSSHAIR = "crosshair"
    TRENDLINE = "trendline"
    HORIZONTAL_LINE = "horizontal_line"
    VERTICAL_LINE = "vertical_line"
    RECTANGLE = "rectangle"
    FIBONACCI = "fibonacci"
    PARALLEL_CHANNEL = "parallel_channel"
    PITCHFORK = "pitchfork"
    GANN_FAN = "gann_fan"
    ARC = "arc"
    ELLIPSE = "ellipse"
    TEXT = "text"
    ARROW = "arrow"
    SPEED_LINE = "speed_line"
    TIME_ZONE = "time_zone"

class LineStyle(Enum):
    """线型"""
    SOLID = "solid"
    DOTTED = "dotted"
    DASHED = "dashed"
    LONG_DASHED = "long_dashed"

@dataclass
class DrawingStyle:
    """绘图样式"""
    color: str = "#FFFFFF"
    line_width: int = 1
    line_style: LineStyle = LineStyle.SOLID
    fill_color: str | None = None  # 填充颜色 (矩形等)
    opacity: float = 1.0

@dataclass
class Drawing:
    """绘图对象"""
    id: str
    type: DrawingType
    points: list[tuple[float, float]]  # (time, price) 坐标
    style: DrawingStyle
    text: str | None = None  # 文本标注
    created_at: float = 0.0
    updated_at: float = 0.0
```

#### 3.1.4 图表状态

```python
from dataclasses import dataclass, field

@dataclass
class ChartState:
    """图表完整状态"""
    ticker: str
    timeframe: str
    data: pd.DataFrame          # OHLCV 数据
    indicators: dict[str, Any]  # 计算后的指标数据
    drawings: list[Drawing]     # 绘图工具列表
    metadata: dict[str, Any]    # 元数据 (名称、行业等)

@dataclass
class IndicatorResult:
    """指标计算结果"""
    name: str
    params: dict[str, Any]
    data: dict[str, list[float]]  # 指标数据 (如 {"macd": [...], "signal": [...]})
    signals: list[Signal] = field(default_factory=list)  # 买卖信号

@dataclass
class Signal:
    """交易信号"""
    type: str        # "buy" | "sell" | "hold"
    strength: float  # 0-100 信号强度
    reason: str      # 信号原因
    timestamp: float # 时间戳
```

### 3.2 数据中心接口

#### 3.2.1 行情数据

```python
from dataclasses import dataclass

@dataclass
class Quote:
    """实时行情"""
    ticker: str
    name: str
    price: float
    change: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: int
    amount: float           # 成交额
    bid_prices: list[float]  # 买一到买五
    ask_prices: list[float]  # 卖一到卖五
    bid_volumes: list[int]
    ask_volumes: list[int]
    timestamp: float

@dataclass
class OHLCVBar:
    """单根 K 线"""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    turnover: float = 0.0   # 换手率
    adjust_factor: float = 1.0  # 复权因子
```

#### 3.2.2 数据源适配器接口

```python
from abc import ABC, abstractmethod

class DataAdapter(ABC):
    """数据源适配器基类"""
    
    @abstractmethod
    def fetch_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_date: str,
        end_date: str,
    ) -> list[OHLCVBar]:
        """获取 OHLCV 数据"""
        ...
    
    @abstractmethod
    def fetch_realtime(
        self,
        tickers: list[str],
    ) -> list[Quote]:
        """获取实时行情"""
        ...
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查数据源是否可用"""
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """数据源名称"""
        ...

# 适配器注册表
ADAPTER_REGISTRY: dict[str, type[DataAdapter]] = {}

def register_adapter(name: str):
    """注册数据源适配器"""
    def decorator(cls):
        ADAPTER_REGISTRY[name] = cls
        return cls
    return decorator

@register_adapter("mootdx")
class MootdxAdapter(DataAdapter):
    """通达信协议适配器"""
    ...

@register_adapter("eastmoney")
class EastmoneyAdapter(DataAdapter):
    """东方财富适配器"""
    ...

@register_adapter("yfinance")
class YfinanceAdapter(DataAdapter):
    """Yahoo Finance 适配器"""
    ...
```

#### 3.2.3 缓存管理器

```python
from pathlib import Path

class CacheManager:
    """数据缓存管理器 — SQLite + 文件系统"""
    
    def __init__(self, cache_dir: Path, max_size_mb: int = 500):
        self.cache_dir = cache_dir
        self.max_size_mb = max_size_mb
        self._ensure_dir()
    
    def get_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame | None:
        """获取缓存的 OHLCV 数据"""
        ...
    
    def set_ohlcv(
        self,
        ticker: str,
        timeframe: str,
        data: pd.DataFrame,
    ) -> None:
        """存储 OHLCV 数据到缓存"""
        ...
    
    def get_indicator_cache(
        self,
        ticker: str,
        indicator: str,
        params: dict[str, Any],
    ) -> pd.DataFrame | None:
        """获取缓存的指标数据"""
        ...
    
    def set_indicator_cache(
        self,
        ticker: str,
        indicator: str,
        params: dict[str, Any],
        data: pd.DataFrame,
    ) -> None:
        """存储指标数据到缓存"""
        ...
    
    def clear(
        self,
        ticker: str | None = None,
        older_than_days: int | None = None,
    ) -> int:
        """清理缓存，返回清理的条目数"""
        ...
    
    def stats(self) -> dict[str, Any]:
        """返回缓存统计信息"""
        ...
```

### 3.3 信号引擎接口

#### 3.3.1 指标计算

```python
class IndicatorComputer:
    """指标计算器 — 支持 25+ 技术指标"""
    
    def compute(
        self,
        data: pd.DataFrame,
        indicator: str,
        params: dict[str, Any] | None = None,
    ) -> IndicatorResult:
        """计算单个指标"""
        ...
    
    def compute_batch(
        self,
        data: pd.DataFrame,
        indicators: list[str],
        params: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, IndicatorResult]:
        """批量计算多个指标"""
        ...
    
    def detect_signals(
        self,
        data: pd.DataFrame,
        indicator: str,
        params: dict[str, Any] | None = None,
    ) -> list[Signal]:
        """检测指标产生的交易信号"""
        ...
```

#### 3.3.2 策略运行器

```python
from abc import ABC, abstractmethod

class Strategy(ABC):
    """策略基类"""
    
    @abstractmethod
    def on_bar(self, bar: OHLCVBar, position: int) -> str:
        """收到新 K 线时的处理逻辑，返回交易信号"""
        ...
    
    @abstractmethod
    def params(self) -> dict[str, Any]:
        """策略参数"""
        ...

@dataclass
class StrategyResult:
    """策略回测结果"""
    ticker: str
    timeframe: str
    start_date: str
    end_date: str
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    trades: list[TradeRecord]

class StrategyRunner:
    """策略运行器"""
    
    def run(
        self,
        strategy: Strategy,
        ticker: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 1_000_000,
    ) -> StrategyResult:
        """运行策略回测"""
        ...
```

### 3.4 选股引擎接口

#### 3.4.1 筛选条件

```python
from dataclasses import dataclass
from enum import Enum

class FilterOperator(Enum):
    """筛选运算符"""
    GT = ">"           # 大于
    LT = "<"           # 小于
    GTE = ">="         # 大于等于
    LTE = "<="         # 小于等于
    EQ = "="           # 等于
    NEQ = "!="         # 不等于
    IN = "in"          # 包含在列表中
    CONTAINS = "contains"  # 字符串包含
    BETWEEN = "between"    # 区间

@dataclass
class Filter:
    """筛选条件"""
    field: str           # 筛选字段
    operator: FilterOperator
    value: Any           # 筛选值
    value2: Any = None   # 第二个值 (BETWEEN 使用)

# 预定义筛选字段
SCREEN_FIELDS = {
    # 技术面
    "pe_ratio": "市盈率",
    "pb_ratio": "市净率",
    "ps_ratio": "市销率",
    "market_cap": "总市值",
    "circulating_cap": "流通市值",
    "change_pct": "涨跌幅",
    "volume_ratio": "量比",
    "turnover_rate": "换手率",
    "amplitude": "振幅",
    
    # 基本面
    "roe": "净资产收益率",
    "roa": "总资产收益率",
    "gross_margin": "毛利率",
    "net_margin": "净利率",
    "revenue_growth": "营收增长率",
    "profit_growth": "净利润增长率",
    "debt_ratio": "资产负债率",
    "current_ratio": "流动比率",
    "dividend_yield": "股息率",
    
    # 资金面
    "northbound_flow": "北向资金净流入",
    "main_force_flow": "主力资金净流入",
    "retail_flow": "散户资金净流入",
    
    # 其他
    "industry": "行业",
    "concept": "概念",
    "list_date": "上市日期",
    "ipo_date": "上市日期",
}
```

#### 3.4.2 选股模板

```python
@dataclass
class ScreenerTemplate:
    """选股模板"""
    id: str
    name: str                    # 模板名称
    description: str             # 模板描述
    category: str                # "technical" | "fundamental" | "capital" | "combined"
    filters: list[Filter]        # 筛选条件列表
    sort_by: str | None = None   # 排序字段
    ascending: bool = False
    tags: list[str] = field(default_factory=list)

# 预定义模板
PRESET_TEMPLATES: list[ScreenerTemplate] = [
    ScreenerTemplate(
        id="value",
        name="价值股筛选",
        description="低 PE/PB、高股息率的价值型股票",
        category="fundamental",
        filters=[
            Filter("pe_ratio", FilterOperator.LT, 15),
            Filter("pb_ratio", FilterOperator.LT, 2),
            Filter("dividend_yield", FilterOperator.GT, 3),
            Filter("roe", FilterOperator.GT, 10),
        ],
        sort_by="dividend_yield",
        tags=["价值投资", "防御型"],
    ),
    ScreenerTemplate(
        id="growth",
        name="成长股筛选",
        description="高增长、高 ROE 的成长型股票",
        category="fundamental",
        filters=[
            Filter("revenue_growth", FilterOperator.GT, 20),
            Filter("profit_growth", FilterOperator.GT, 25),
            Filter("roe", FilterOperator.GT, 15),
            Filter("market_cap", FilterOperator.GT, 50_000_000_000),  # 500亿以上
        ],
        sort_by="profit_growth",
        tags=["成长投资", "进攻型"],
    ),
    ScreenerTemplate(
        id="momentum",
        name="动量突破",
        description="放量突破、资金流入的强势股",
        category="technical",
        filters=[
            Filter("change_pct", FilterOperator.GT, 3),
            Filter("volume_ratio", FilterOperator.GT, 2),
            Filter("northbound_flow", FilterOperator.GT, 0),
            Filter("turnover_rate", FilterOperator.GT, 5),
        ],
        sort_by="volume_ratio",
        tags=["短线", "动量"],
    ),
    ScreenerTemplate(
        id="oversold",
        name="超跌反弹",
        description="RSI 超卖、跌幅较大的反弹机会",
        category="technical",
        filters=[
            Filter("rsi_14", FilterOperator.LT, 30),
            Filter("change_pct", FilterOperator.LT, -5),
            Filter("volume_ratio", FilterOperator.GT, 1.5),
        ],
        sort_by="rsi_14",
        tags=["短线", "反弹"],
    ),
]
```

### 3.5 组合引擎接口

#### 3.5.1 持仓与交易

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Position:
    """持仓"""
    ticker: str
    name: str
    quantity: int
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight: float               # 持仓权重

@dataclass
class TradeRecord:
    """交易记录"""
    id: str
    ticker: str
    name: str
    side: str                   # "buy" | "sell"
    quantity: int
    price: float
    amount: float
    commission: float
    timestamp: datetime
    reason: str = ""

@dataclass
class PortfolioSummary:
    """组合汇总"""
    total_value: float          # 总资产
    cash: float                 # 现金
    market_value: float         # 持仓市值
    total_pnl: float           # 总盈亏
    total_pnl_pct: float       # 总收益率
    today_pnl: float           # 今日盈亏
    today_pnl_pct: float       # 今日收益率
    positions: list[Position]
    max_drawdown: float = 0.0  # 最大回撤
    sharpe_ratio: float = 0.0  # 夏普比率
```

---

## 4. 实现路线图

### Phase 1: 图表引擎核心 (2 周)

**目标**: 实现完整的 K 线图表和基础指标

| 任务 | 优先级 | 预估工时 |
|------|--------|----------|
| 实现 ChartEngine 接口 | P0 | 2 天 |
| 实现 MA/EMA/BOLL 叠加指标 | P0 | 1 天 |
| 实现 MACD/RSI/KDJ 副图指标 | P0 | 1 天 |
| 实现 WR/CCI/DMI 指标 | P1 | 1 天 |
| 实现 TRX/DMA/ROC 指标 | P1 | 1 天 |
| 实现绘图工具 (趋势线、水平线、矩形、斐波那契) | P0 | 2 天 |
| 实现周期切换 (1m-60m, 1D-1Y) | P0 | 1 天 |
| 实现 K 线回放功能 | P1 | 1 天 |

**交付物**:
- `tradingagents/chart_engine/__init__.py`
- `tradingagents/chart_engine/indicators.py`
- `tradingagents/chart_engine/drawings.py`
- `tradingagents/chart_engine/timeframes.py`
- `tests/test_chart_engine.py`

### Phase 2: 数据中心 (2 周)

**目标**: 统一数据访问层，支持多数据源和离线缓存

| 任务 | 优先级 | 预估工时 |
|------|--------|----------|
| 实现 DataAdapter 基类和注册表 | P0 | 1 天 |
| 实现 MootdxAdapter (TDX 协议) | P0 | 2 天 |
| 实现 EastmoneyAdapter (东方财富) | P0 | 2 天 |
| 实现 YfinanceAdapter (Yahoo Finance) | P0 | 1 天 |
| 实现 CacheManager (SQLite) | P0 | 2 天 |
| 实现 DataCenter 统一接口 | P0 | 1 天 |
| 实现实时行情批量获取 | P1 | 1 天 |

**交付物**:
- `tradingagents/data_center/__init__.py`
- `tradingagents/data_center/adapters/` (各数据源适配器)
- `tradingagents/data_center/cache.py`
- `tests/test_data_center.py`

### Phase 3: 信号引擎 (2 周)

**目标**: 技术指标计算、策略运行、买卖信号生成

| 任务 | 优先级 | 预估工时 |
|------|--------|----------|
| 实现 IndicatorComputer (25+ 指标) | P0 | 3 天 |
| 实现信号检测逻辑 | P0 | 2 天 |
| 实现 Strategy 基类和 StrategyRunner | P0 | 2 天 |
| 实现 AlertManager (价格/指标预警) | P1 | 2 天 |
| 实现策略模板库 | P1 | 1 天 |

**交付物**:
- `tradingagents/signal_engine/__init__.py`
- `tradingagents/signal_engine/indicators.py`
- `tradingagents/signal_engine/strategies.py`
- `tradingagents/signal_engine/alerts.py`
- `tests/test_signal_engine.py`

### Phase 4: 选股引擎 (1 周)

**目标**: 条件选股、模板系统、自然语言选股

| 任务 | 优先级 | 预估工时 |
|------|--------|----------|
| 实现 FilterCompiler (条件编译) | P0 | 2 天 |
| 实现 StockRanker (排名筛选) | P0 | 1 天 |
| 实现模板系统 (10+ 预定义模板) | P1 | 1 天 |
| 实现 LLM 自然语言选股 | P1 | 1 天 |

**交付物**:
- `tradingagents/screener_engine/__init__.py`
- `tradingagents/screener_engine/filters.py`
- `tradingagents/screener_engine/templates.py`
- `tests/test_screener_engine.py`

### Phase 5: 组合引擎 (1 周)

**目标**: 模拟交易、持仓管理、绩效分析

| 任务 | 优先级 | 预估工时 |
|------|--------|----------|
| 实现 PositionTracker (持仓跟踪) | P0 | 1 天 |
| 实现 OrderManager (订单管理) | P0 | 1 天 |
| 实现 PerformanceAnalyzer (绩效分析) | P0 | 1 天 |
| 实现 RiskAnalyzer (风险分析) | P1 | 1 天 |
| 实现基准对比 (沪深300等) | P1 | 1 天 |

**交付物**:
- `tradingagents/portfolio_engine/__init__.py`
- `tradingagents/portfolio_engine/positions.py`
- `tradingagents/portfolio_engine/orders.py`
- `tradingagents/portfolio_engine/performance.py`
- `tests/test_portfolio_engine.py`

### Phase 6: GUI 集成 (2 周)

**目标**: 将所有引擎集成到 GUI

| 任务 | 优先级 | 预估工时 |
|------|--------|----------|
| 更新 TradingViewChart 使用新 ChartEngine | P0 | 2 天 |
| 更新 IndicatorBar 支持 25+ 指标 | P0 | 1 天 |
| 更新 DrawingToolbar 支持 15+ 绘图工具 | P0 | 2 天 |
| 实现 ScreenerPanel 使用新 ScreenerEngine | P0 | 2 天 |
| 实现 PortfolioPanel 使用新 PortfolioEngine | P0 | 2 天 |
| 实现 AlertPanel 使用新 AlertManager | P1 | 1 天 |

**交付物**:
- 更新 `tradingagents_gui/src/components/tradingview/` 下所有组件
- `tests/test_gui_integration.py`

---

## 5. 测试策略

### 5.1 单元测试

每个深度模块必须有完整的单元测试：

```python
# tests/test_chart_engine.py
import pytest
from tradingagents.chart_engine import ChartEngine

@pytest.fixture
def engine():
    return ChartEngine()

class TestIndicatorComputation:
    def test_ma_basic(self, engine):
        """测试 MA 基本计算"""
        ...
    
    def test_ma_with_nan(self, engine):
        """测试 MA 处理 NaN 值"""
        ...
    
    def test_macd_crossover(self, engine):
        """测试 MACD 金叉死叉"""
        ...

class TestDrawingTools:
    def test_trendline_creation(self, engine):
        """测试趋势线创建"""
        ...
    
    def test_fibonacci_levels(self, engine):
        """测试斐波那契回撤水平"""
        ...

class TestTimeframes:
    @pytest.mark.parametrize("timeframe", ["1m", "5m", "15m", "30m", "60m", "1D", "1W", "1M"])
    def test_timeframe_loading(self, engine, timeframe):
        """测试各周期数据加载"""
        ...
```

### 5.2 集成测试

```python
# tests/test_integration.py
import pytest

class TestDataFlow:
    def test_data_center_to_chart(self):
        """测试数据中心 → 图表引擎数据流"""
        ...
    
    def test_indicator_to_signal(self):
        """测试指标计算 → 信号生成数据流"""
        ...
    
    def test_screen_to_portfolio(self):
        """测试选股 → 组合执行数据流"""
        ...
```

### 5.3 性能测试

```python
# tests/test_performance.py
import pytest

class TestPerformance:
    @pytest.mark.benchmark
    def test_ohlcv_render_time(self):
        """OHLCV 渲染时间 < 100ms"""
        ...
    
    @pytest.mark.benchmark
    def test_indicator_compute_time(self):
        """单个指标计算时间 < 10ms"""
        ...
    
    @pytest.mark.benchmark
    def test_screen_time(self):
        """选股执行时间 < 1s"""
        ...
```

---

## 6. 开源参考

### 6.1 架构参考

| 项目 | 参考价值 | 关键特性 |
|------|----------|----------|
| **vnpy** | 高 | 事件驱动引擎、Gateway 模式、插件化策略 |
| **mootdx** | 高 | TDX 协议实现、Reader/Quotes 模式 |
| **akshare** | 中 | 数据源适配器、模块化设计 |
| **TradingAgents** | 中 | 多 Agent 架构、LLM 集成 |
| **qmt** | 中 | 量化交易框架、MCP 协议 |

### 6.2 技术参考

| 技术 | 用途 | 参考项目 |
|------|------|----------|
| ECharts | 图表渲染 | 现有 TradingViewChart |
| stockstats | 技术指标计算 | 现有 stockstats_utils |
| mootdx | TDX 数据源 | mootdx/mootdx |
| SQLite | 本地缓存 | 现有 llm_cache |
| Zustand | 前端状态管理 | 现有 useChartStore |

### 6.3 数据源对比

| 数据源 | 实时数据 | 历史数据 | 基本面 | 新闻 | 免费 |
|--------|----------|----------|--------|------|------|
| TDX (mootdx) | ✓ | ✓ | ✓ | ✗ | ✓ |
| 东方财富 | ✓ | ✓ | ✓ | ✓ | ✓ |
| 新浪财经 | ✓ | ✓ | ✗ | ✓ | ✓ |
| Yahoo Finance | ✓ | ✓ | ✓ | ✓ | ✓ |
| akshare | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## 附录 A: 文件结构

```
tradingagents/
├── chart_engine/
│   ├── __init__.py
│   ├── indicators.py      # 25+ 技术指标实现
│   ├── drawings.py        # 15+ 绘图工具
│   ├── timeframes.py      # 周期管理
│   └── renderer.py        # 图表状态渲染
├── data_center/
│   ├── __init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py        # DataAdapter 基类
│   │   ├── mootdx.py      # TDX 协议适配器
│   │   ├── eastmoney.py   # 东方财富适配器
│   │   ├── sina.py        # 新浪财经适配器
│   │   └── yfinance.py    # Yahoo Finance 适配器
│   ├── cache.py           # SQLite 缓存管理
│   └── router.py          # 数据源路由
├── signal_engine/
│   ├── __init__.py
│   ├── indicators.py      # 指标计算器
│   ├── signals.py         # 信号检测
│   ├── strategies.py      # 策略运行器
│   └── alerts.py          # 预警管理
├── screener_engine/
│   ├── __init__.py
│   ├── filters.py         # 筛选条件编译
│   ├── ranker.py          # 排名筛选
│   └── templates.py       # 预定义模板
└── portfolio_engine/
    ├── __init__.py
    ├── positions.py        # 持仓跟踪
    ├── orders.py           # 订单管理
    ├── performance.py      # 绩效分析
    └── risk.py             # 风险分析
```

---

## 附录 B: 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| K 线 | Candlestick | 金融图表中最基本的图表类型 |
| 指标 | Indicator | 技术分析的数学公式计算结果 |
| 周期 | Timeframe | K 线的时间粒度 (1m, 5m, 1D 等) |
| 选股 | Screener | 根据条件筛选股票 |
| 持仓 | Position | 投资组合中的股票持有 |
| 回撤 | Drawdown | 从峰值到谷值的跌幅 |
| 夏普比率 | Sharpe Ratio | 风险调整后收益指标 |
| 北向资金 | Northbound Flow | 通过沪港通/深港通流入 A 股的资金 |
| 主力资金 | Main Force | 大单资金流向 |
| 筹码分布 | Chip Distribution | 不同价位的持仓分布 |
| 龙虎榜 | Dragon Tiger List | 异常波动个股的交易席位数据 |
| 解禁 | Lockup Expiry | 限售股解禁 |
| 复权 | Adjust | 前复权(qfq)/后复权(hfq)/不复权(none) |
