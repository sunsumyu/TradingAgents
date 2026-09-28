"""A-stock feature center (Phase 5, ticket 5.01).

Thin adapter over the "sleeping" deep modules in
``tradingagents.dataflows.a_stock``: those functions are battle-tested
against Eastmoney/THS/Sina rate limits but return **markdown text** built
for LLM agents. This module exposes them to the GUI through a single
dispatch table so the API surface stays one URL wide.

Envelope contract (see spec docs/specs/2026-08-26-phase5-astock-data-center.md):

    AstockFeatureResponse {
        feature, ticker, date,
        data: dict   # feature-specific structured payload (parser output)
        raw_md: str  # verbatim markdown from the backend function
    }

Ticket 5.01 ships the skeleton + dispatch table with every feature wired
through the generic passthrough parser; per-feature structured parsers and
Pydantic payloads land in tickets 5.02+.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic import BaseModel, Field

from tradingagents.cache import get_cache, register_feature_ttl

logger = logging.getLogger(__name__)


def _box_table_to_markdown(text: str) -> str:
    """Convert box-drawing tables to standard markdown tables.

    Handles: │ U+2502 (box-drawing vertical), ｜ U+FF5C (fullwidth vertical),
    ┌┬┐├┼┤└┴┘─ (box-drawing borders).
    """
    import re

    lines = text.split("\n")
    result: list[str] = []
    in_table = False

    for line in lines:
        # Check for any box-drawing or fullwidth vertical line chars
        has_vline = bool(re.search(r"[│｜|]", line))
        has_border = bool(re.search(r"[┌┬┐├┼┤└┴┘─]", line))

        # Pure border line (only box-drawing chars) → skip
        if has_border and not has_vline:
            stripped = re.sub(r"[─┌┬┐├┼┤└┴┘│｜\s]", "", line)
            if not stripped.strip():
                continue

        # Data line with vertical separators → convert
        if has_vline:
            cells = re.split(r"[│｜]", line)
            cleaned = [c.strip() for c in cells if c.strip()]
            if cleaned:
                row_str = " | ".join(cleaned)
                if not in_table or (result and result[-1] != row_str):
                    result.append(row_str)
                    in_table = True
                continue

        in_table = False
        result.append(line)

    return "\n".join(result)


class AstockFeatureRequest(BaseModel):
    """Request for one named feature of the A-stock data center."""

    feature: str = Field(description="Feature name, see FEATURE_TABLE")
    ticker: str = Field(
        description=(
            "6-digit A-share code. Market-wide features (northbound_flow, "
            "hot_stocks) still require it for the envelope but ignore it."
        )
    )
    date: str = Field(description="Anchor date YYYY-MM-DD")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Feature-specific passthrough params (days, top_n, freq, ...)",
    )


class AstockFeatureResponse(BaseModel):
    """Unified envelope for all features."""

    feature: str
    ticker: str
    date: str
    data: dict[str, Any] = Field(default_factory=dict)
    raw_md: str = Field(default="")


# ── Structured payload models (tickets 5.02+) ──────────────────────────────


class PriceLevelChip(BaseModel):
    """One price bin of the chip distribution."""

    price: float = Field(description="Bin midpoint price")
    ratio: float = Field(description="Share of chips at this level, percent")
    is_peak: bool = Field(default=False, description="True for the densest bin")


class ChipDistributionData(BaseModel):
    """Structured output of ``chip_distribution`` (ticket 5.02)."""

    price_levels: list[PriceLevelChip] = Field(default_factory=list)
    current_price: float | None = None
    profit_ratio: float | None = Field(
        default=None, description="Percent of chips below current price (获利盘)"
    )
    avg_cost: float | None = None
    peak_price: float | None = None


class DragonTigerSeat(BaseModel):
    """One seat (broker branch or institution) on the dragon tiger board."""

    name: str = Field(description="Seat name (营业部 or 机构专用)")
    side: str = Field(description="'buy' or 'sell'")
    buy_wan: float = Field(default=0, description="买入金额(万)")
    sell_wan: float = Field(default=0, description="卖出金额(万)")
    net_wan: float = Field(default=0, description="净额(万)")
    is_institution: bool = Field(default=False, description="True if '机构专用'")


class DragonTigerAppearance(BaseModel):
    """One LHB appearance record."""

    date: str = Field(description="Trade date YYYY-MM-DD")
    reason: str = Field(description="上榜原因")
    net_buy_wan: float = Field(default=0, description="当日净买入(万)")
    turnover_rate: float | None = Field(default=None, description="换手率 %")


class DragonTigerData(BaseModel):
    """Structured output of ``dragon_tiger`` (ticket 5.03)."""

    appearances: list[DragonTigerAppearance] = Field(default_factory=list)
    buy_seats: list[DragonTigerSeat] = Field(default_factory=list)
    sell_seats: list[DragonTigerSeat] = Field(default_factory=list)
    inst_buy_wan: float | None = None
    inst_sell_wan: float | None = None


class NorthboundDay(BaseModel):
    """One day of northbound flow (close snapshot)."""

    date: str
    hgt: float = Field(description="沪股通净流入(亿)")
    sgt: float = Field(description="深股通净流入(亿)")


class NorthboundData(BaseModel):
    """Structured output of ``northbound_flow`` (ticket 5.04)."""

    hgt_net_inflow: float | None = Field(default=None, description="沪股通当日净流入(亿)")
    sgt_net_inflow: float | None = Field(default=None, description="深股通当日净流入(亿)")
    history: list[NorthboundDay] = Field(default_factory=list)


class ConceptBlockItem(BaseModel):
    """One concept/industry/region block a stock belongs to."""

    name: str
    category: str = Field(description="'行业' | '概念' | '地域' ...")
    change_pct: float | None = Field(default=None, description="板块当日涨跌幅 %")
    note: str | None = Field(default=None, description="e.g. 申万一级 / 申万二级")


class ConceptBlocksData(BaseModel):
    """Structured output of ``concept_blocks`` (ticket 5.05)."""

    blocks: list[ConceptBlockItem] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list, description="'概念' 分类下的标签名")


class ProfitForecastYear(BaseModel):
    """One fiscal year of consensus EPS forecast."""

    year: str
    mean_eps: float | None = None
    min_eps: float | None = None
    max_eps: float | None = None
    analysts: int | None = None


class ProfitForecastData(BaseModel):
    """Structured output of ``profit_forecast`` (ticket 5.05)."""

    years: list[ProfitForecastYear] = Field(default_factory=list)
    current_price: float | None = None
    pe_ttm: float | None = None
    forward_pe: float | None = None
    peg: float | None = None


class LockupBatch(BaseModel):
    """One lockup expiry record."""

    date: str = Field(description="解禁日期 YYYY-MM-DD")
    shares_type: str = Field(default="", description="解禁类型")
    quantity: float | None = Field(default=None, description="解禁数量(股)")
    ratio: float | None = Field(default=None, description="占总股本比例")


class LockupExpiryData(BaseModel):
    """Structured output of ``lockup_expiry`` (ticket 5.06)."""

    batches: list[LockupBatch] = Field(default_factory=list)
    future_batches: list[LockupBatch] = Field(default_factory=list)
    has_future: bool = Field(default=False, description="未来90天是否有待解禁")


class HotStockItem(BaseModel):
    """One hot stock entry."""

    ticker: str
    name: str
    change_pct: float | None = None
    turnover_rate: float | None = None
    volume_wan: float | None = Field(default=None, description="成交额(万)")
    net_flow_wan: float | None = Field(default=None, description="大单净量(万)")
    topics: str = Field(default="", description="题材标签(+/)")


class HotStocksData(BaseModel):
    """Structured output of ``hot_stocks`` (ticket 5.06)."""

    items: list[HotStockItem] = Field(default_factory=list)
    total: int = 0


def _passthrough_parser(md: str, ticker: str, date: str, params: dict[str, Any]) -> dict[str, Any]:
    """Default parser: no structured fields yet, markdown only.

    Tickets 5.03+ replace entries in FEATURE_TABLE with real parsers;
    until then the GUI renders ``raw_md`` directly.
    """
    return {}


def _parse_financial_csv(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse CSV-formatted financial report from raw_md.

    The raw_md from ``sina_finance`` looks like::

        # Balance Sheet for 600519 (A-stock, quarterly)
        # Data source: sina direct HTTP
        # Data retrieved on: 2026-08-26 14:30:00
        报告日,资产合计,负债合计,股东权益合计,...
        2026-06-30,312456789.00,123456789.00,...
        2026-03-31,305000000.00,120000000.00,...

    Returns::

        {
            "periods": ["2026-06-30", "2026-03-31", ...],
            "columns": ["资产合计", "负债合计", ...],
            "items": {"资产合计": [312456789.0, ...], ...}
        }
    """
    if not md or not md.strip():
        return {"periods": [], "columns": [], "items": {}}

    lines = md.strip().splitlines()
    header_idx = -1
    for i, line in enumerate(lines):
        if "报告日" in line and not line.startswith("#"):
            header_idx = i
            break

    if header_idx < 0:
        return {"periods": [], "columns": [], "items": {}}

    cols = [c.strip().strip('"') for c in lines[header_idx].split(",")]
    if not cols or cols[0] != "报告日":
        return {"periods": [], "columns": [], "items": {}}

    data_cols = cols[1:]
    periods: list[str] = []
    items: dict[str, list[float | None]] = {c: [] for c in data_cols}

    for line in lines[header_idx + 1 :]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip().strip('"') for p in line.split(",")]
        if len(parts) < 2:
            continue
        periods.append(parts[0])
        for j, col in enumerate(data_cols):
            val_str = parts[j + 1] if j + 1 < len(parts) else ""
            try:
                items[col].append(float(val_str) if val_str else None)
            except (ValueError, TypeError):
                items[col].append(None)

    return {"periods": periods, "columns": data_cols, "items": items}


def _parse_industry_comparison(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse industry comparison markdown into structured rankings.

    Expected format (from eastmoney.py)::

        # 行业横向对比 | 600519 | 2026-08-26
        ## 全行业表现 (东财 30 个行业)
        排名 | 行业 | 涨跌幅 | 上涨 | 下跌 | 领涨股
          1. 白酒 | +1.23% | 12 | 3 | 贵州茅台
          2. 食品饮料 | +0.85% | 18 | 5 | 伊利股份

    Returns::

        {"rankings": [{rank, name, change_pct, up_count, down_count, leader}, ...]}
    """
    import re

    if not md or not md.strip():
        return {"rankings": []}

    rankings: list[dict[str, Any]] = []
    for line in md.splitlines():
        line = line.strip()
        # Match lines like "  1. 白酒 | +1.23% | 12 | 3 | 贵州茅台"
        m = re.match(
            r"^\s*(\d+)\.\s*(.+?)\s*\|\s*([+-]?[\d.]+)%\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.+)$",
            line,
        )
        if not m:
            continue
        try:
            change_pct = float(m.group(3))
        except (ValueError, TypeError):
            change_pct = None
        try:
            up_count = int(m.group(4))
        except (ValueError, TypeError):
            up_count = None
        try:
            down_count = int(m.group(5))
        except (ValueError, TypeError):
            down_count = None
        rankings.append({
            "rank": int(m.group(1)),
            "name": m.group(2).strip(),
            "change_pct": change_pct,
            "up_count": up_count,
            "down_count": down_count,
            "leader": m.group(6).strip(),
        })

    return {"rankings": rankings}


def _parse_insider_transactions(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse insider transactions (mootdx F10 shareholder research) markdown.

    Mootdx returns free-form text. We extract sections delimited by
    ``【N.标题】`` patterns and preserve the raw text as fallback.

    Returns::

        {"sections": [{title, content}, ...], "raw_text": str}
    """
    import re

    if not md or not md.strip():
        return {"sections": [], "raw_text": ""}

    raw_text = _box_table_to_markdown(md)
    sections: list[dict[str, str]] = []

    # Split on 【N.标题】 or 【标题】 patterns
    parts = re.split(r"(?=【[^】]+】)", md)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        title_match = re.match(r"【([^】]+)】\s*", part)
        if title_match:
            title = title_match.group(1).strip()
            content = part[title_match.end():].strip()
            if content:
                sections.append({"title": title, "content": _box_table_to_markdown(content)})

    return {"sections": sections, "raw_text": raw_text}


def _parse_chip_distribution(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse ``get_chip_distribution`` markdown into ChipDistributionData.

    Line formats handled (see a_stock.get_chip_distribution):
      当前价: 71.90 / 筹码峰值价: 74.66 / 平均成本: 75.17 / 获利盘比例: 9.2%
      "     70.90 |   2.7% | █████[ ◄ 峰值]"   (bin rows)

    Failure text ("筹码分布查询失败: ...") parses to an empty payload and
    lets raw_md carry the error to the panel.
    """
    import re

    out: dict[str, Any] = {"price_levels": []}
    levels: list[PriceLevelChip] = []

    def _f(text: str) -> float:
        return float(text.replace(",", ""))

    try:
        for line in md.splitlines():
            line = line.strip()
            m = re.match(r"^当前价:\s*([\d,.]+)", line)
            if m:
                out["current_price"] = _f(m.group(1))
                continue
            m = re.match(r"^筹码峰值价:\s*([\d,.]+)", line)
            if m:
                out["peak_price"] = _f(m.group(1))
                continue
            m = re.match(r"^平均成本:\s*([\d,.]+)", line)
            if m:
                out["avg_cost"] = _f(m.group(1))
                continue
            m = re.match(r"^获利盘比例:\s*([\d,.]+)%", line)
            if m:
                out["profit_ratio"] = _f(m.group(1))
                continue
            # Bin row: "<price> | <pct>% | <bars>[ ◄ 峰值]"
            m = re.match(r"^([\d,.]+)\s*\|\s*([\d,.]+)%\s*\|", line)
            if m:
                levels.append(
                    PriceLevelChip(
                        price=_f(m.group(1)),
                        ratio=_f(m.group(2)),
                        is_peak="◄ 峰值" in line,
                    )
                )
    except Exception as exc:  # never break the endpoint on parser drift
        logger.warning("chip parser failed for %s: %s", ticker, exc)
        return {"price_levels": []}

    out["price_levels"] = [lvl.model_dump() for lvl in levels]
    return out


def _parse_dragon_tiger(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse ``get_dragon_tiger_board`` markdown into DragonTigerData.

    Handles three sections:
      1. 上榜记录 table: date | reason | net_buy(万) | turnover%
      2. 买入/卖出席位 TOP5: name | buy(万) | sell(万) | net(万)
      3. 机构动向 line: 机构买入 X 万 | 卖出 Y 万 | 净额 Z 万

    Empty-response text ("近{days}日未上龙虎榜") returns empty lists.
    """
    import re

    appearances: list[DragonTigerAppearance] = []
    buy_seats: list[DragonTigerSeat] = []
    sell_seats: list[DragonTigerSeat] = []
    inst_buy: float | None = None
    inst_sell: float | None = None

    def _f(text: str) -> float:
        try:
            return float(text.replace(",", "").replace("%", ""))
        except (ValueError, TypeError):
            return 0.0

    try:
        section = None  # 'appearances' | 'buy_seats' | 'sell_seats'
        for line in md.splitlines():
            stripped = line.strip()

            # Section headers
            if stripped.startswith("## 上榜记录"):
                section = "appearances"
                continue
            if stripped.startswith("## 最近上榜席位明细"):
                section = None  # will be set by ### headers below
                continue
            if stripped.startswith("### 买入席位"):
                section = "buy_seats"
                continue
            if stripped.startswith("### 卖出席位"):
                section = "sell_seats"
                continue
            if stripped.startswith("## 机构动向"):
                section = "inst"
                continue
            if stripped.startswith("## ") or stripped.startswith("# "):
                section = None
                continue

            # Skip header/separator rows
            if stripped.startswith("日期 |") or stripped.startswith("营业部 |"):
                continue
            if stripped.startswith("---") or not stripped:
                continue

            # 机构动向 line: "机构买入 3385 万 | 卖出 8805 万 | 净额 -5420 万"
            if section == "inst":
                m = re.match(r"机构买入\s*([\d,.]+)\s*万\s*\|\s*卖出\s*([\d,.]+)\s*万", stripped)
                if m:
                    inst_buy = _f(m.group(1))
                    inst_sell = _f(m.group(2))
                continue

            # Appearance rows: "  2026-08-26 | 日换手率达到20%的前5只证券 | -2566 | 35.33%"
            if section == "appearances":
                parts = [p.strip() for p in stripped.split("|")]
                if len(parts) >= 4:
                    appearances.append(
                        DragonTigerAppearance(
                            date=parts[0],
                            reason=parts[1],
                            net_buy_wan=_f(parts[2]),
                            turnover_rate=_f(parts[3]) if parts[3] else None,
                        )
                    )
                continue

            # Seat rows: "  国新证券... | 4015 | 0 | 4015"
            if section in ("buy_seats", "sell_seats"):
                parts = [p.strip() for p in stripped.split("|")]
                if len(parts) >= 4:
                    name = parts[0]
                    is_inst = "机构专用" in name
                    seats = buy_seats if section == "buy_seats" else sell_seats
                    seats.append(
                        DragonTigerSeat(
                            name=name,
                            side="buy" if section == "buy_seats" else "sell",
                            buy_wan=_f(parts[1]),
                            sell_wan=_f(parts[2]),
                            net_wan=_f(parts[3]),
                            is_institution=is_inst,
                        )
                    )
                continue

    except Exception as exc:
        logger.warning("dragon tiger parser failed for %s: %s", ticker, exc)

    return {
        "appearances": [a.model_dump() for a in appearances],
        "buy_seats": [s.model_dump() for s in buy_seats],
        "sell_seats": [s.model_dump() for s in sell_seats],
        "inst_buy_wan": inst_buy,
        "inst_sell_wan": inst_sell,
    }


def _parse_northbound(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse ``get_northbound_flow`` markdown into NorthboundData.

    Handles:
      "Close: HGT(沪股通)=-9.28亿 SGT(深股通)=379.75亿 Total=370.47亿"
      History rows: "  2026-08-19: HGT=-9.28 SGT=379.75 Total=370.47"

    SGT may be "N/A" during trading hours; treated as None upstream but the
    close line always carries both values when present.
    """
    import re

    hgt_close: float | None = None
    sgt_close: float | None = None
    history: list[NorthboundDay] = []

    def _f(text: str) -> float | None:
        try:
            return float(text.replace(",", ""))
        except (ValueError, TypeError):
            return None

    try:
        for line in md.splitlines():
            stripped = line.strip()

            m = re.match(
                r"^Close:\s*HGT(?:\(沪股通\))?\s*=\s*(-?[\d,.]+)亿\s*"
                r"SGT(?:\(深股通\))?\s*=\s*(-?[\d,.NA]+)亿",
                stripped,
            )
            if m:
                hgt_close = _f(m.group(1))
                sgt_close = _f(m.group(2).replace("N/A", ""))
                continue

            # History row: "2026-08-19: HGT=-9.28 SGT=379.75 Total=370.47"
            m = re.match(
                r"^(\d{4}-\d{2}-\d{2}):\s*HGT\s*=\s*(-?[\d,.]+)\s+SGT\s*=\s*(-?[\d,.]+)",
                stripped,
            )
            if m:
                h, s = _f(m.group(2)), _f(m.group(3))
                if h is not None and s is not None:
                    history.append(NorthboundDay(date=m.group(1), hgt=h, sgt=s))
                continue

    except Exception as exc:
        logger.warning("northbound parser failed: %s", exc)

    return {
        "hgt_net_inflow": hgt_close,
        "sgt_net_inflow": sgt_close,
        "history": [d.model_dump() for d in history],
    }


def _parse_concept_blocks(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse ``get_concept_blocks`` markdown into ConceptBlocksData.

    Formats:
      "## 行业" / "## 概念" / "## 地域"  → category headers
      "  食品饮料 (申万一级): -0.03%"   → item with note + change
      "Concept tags: a / b / c"        → concept tag summary
    """
    import re

    blocks: list[ConceptBlockItem] = []
    concepts: list[str] = []
    category = ""

    try:
        for line in md.splitlines():
            stripped = line.strip()

            m = re.match(r"^##\s+(.+)$", stripped)
            if m and not stripped.startswith("###"):
                category = m.group(1).strip()
                continue

            m = re.match(r"^Concept tags:\s*(.+)$", stripped)
            if m:
                concepts = [t.strip() for t in m.group(1).split("/") if t.strip()]
                continue

            if not category or stripped.startswith("#") or ":" not in stripped and "|" not in stripped:
                if not category or not re.match(r"^.+\s*[(:].*[:：]", stripped):
                    # fallthrough attempt below handles "name (note): x%"
                    pass

            # Item line: "<name>[ (<note>)]: <change>%"
            m = re.match(r"^(.+?)(?:\s*\(([^)]+)\))?\s*[:：]\s*([+-]?[\d,.]+)%$", stripped)
            if m and category:
                blocks.append(
                    ConceptBlockItem(
                        name=m.group(1).strip(),
                        category=category,
                        change_pct=float(m.group(3).replace(",", "")),
                        note=m.group(2),
                    )
                )

    except Exception as exc:
        logger.warning("concept blocks parser failed for %s: %s", ticker, exc)

    if not concepts:
        concepts = [b.name for b in blocks if b.category == "概念"]

    return {
        "blocks": [b.model_dump() for b in blocks],
        "concepts": concepts,
    }


def _parse_profit_forecast(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse ``get_profit_forecast`` markdown into ProfitForecastData.

    Formats:
      "FY2026.0: EPS=67.88 (range 64.78~77.85), analysts=49"
      "Current: price=1302.8, PE(TTM)=20.0"
      "Forward PE (FY2026.0): 19.2x"
      "PEG: 3.30 (CAGR=6%)"
    """
    import re

    years: list[ProfitForecastYear] = []
    price = pe_ttm = fwd_pe = peg = None

    def _f(text: str) -> float | None:
        try:
            return float(text.replace(",", ""))
        except (ValueError, TypeError):
            return None

    try:
        for line in md.splitlines():
            stripped = line.strip()

            m = re.match(
                r"^FY(\d{4}(?:\.0)?):\s*EPS\s*=\s*(-?[\d,.]+)"
                r"(?:\s*\(range\s*(-?[\d,.]+)~(-?[\d,.]+)\))?"
                r"(?:,\s*analysts\s*=\s*(\d+))?",
                stripped,
            )
            if m:
                years.append(
                    ProfitForecastYear(
                        year=m.group(1).removesuffix(".0"),
                        mean_eps=_f(m.group(2)),
                        min_eps=_f(m.group(3)) if m.group(3) else None,
                        max_eps=_f(m.group(4)) if m.group(4) else None,
                        analysts=int(m.group(5)) if m.group(5) else None,
                    )
                )
                continue

            m = re.match(r"^Current:\s*price\s*=\s*(-?[\d,.]+),?\s*PE\(TTM\)\s*=\s*(-?[\d,.]+)", stripped)
            if m:
                price = _f(m.group(1))
                pe_ttm = _f(m.group(2))
                continue

            m = re.match(r"^Forward PE\s*\(FY[\w.]+\):\s*([\d,.]+)x", stripped)
            if m:
                fwd_pe = _f(m.group(1))
                continue

            m = re.match(r"^PEG:\s*([\d,.]+)", stripped)
            if m:
                peg = _f(m.group(1))
                continue

    except Exception as exc:
        logger.warning("profit forecast parser failed for %s: %s", ticker, exc)

    return {
        "years": [y.model_dump() for y in years],
        "current_price": price,
        "pe_ttm": pe_ttm,
        "forward_pe": fwd_pe,
        "peg": peg,
    }


def _parse_lockup_expiry(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse lockup expiry markdown into LockupExpiryData.

    Line formats:
      2019-06-19 |  |  | 0.090636670532
    """
    import re

    def _f(text: str) -> float | None:
        try:
            return float(text.replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    batches: list[dict[str, Any]] = []
    future_batches: list[dict[str, Any]] = []
    has_future = False
    section = "history"

    for line in md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "未来" in stripped and "待解禁" in stripped:
            has_future = "无" not in stripped
            section = "future"
            continue
        # table row: date | type | quantity | ratio
        m = re.match(r"^\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*([\d.]+)", stripped)
        if m:
            entry = {
                "date": m.group(1),
                "shares_type": m.group(2).strip(),
                "quantity": _f(m.group(3)) if m.group(3).strip() else None,
                "ratio": _f(m.group(4)),
            }
            if section == "future":
                future_batches.append(entry)
            else:
                batches.append(entry)

    return {
        "batches": batches,
        "future_batches": future_batches,
        "has_future": has_future,
    }


def _parse_hot_stocks(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Parse hot_stocks markdown into HotStocksData.

    Supports two formats:
    1. Single-line (legacy):
       002084 海鸥住工: +10.115% 换手0.52% 成交额1593 大单净量0.35 | 控制权拟变更+装配式厨卫+越南制造
    2. Multi-line (同花顺 format):
       ## 深圳华强 (000062)
         Reason: 半年报增长+华为昇腾+存储芯片
         涨幅: 10.004%
         换手: 5.83%
         成交额: 147246
         DDE净量: 1.56
    """
    import re

    def _f(text: str) -> float | None:
        try:
            return float(text.replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    items: list[dict[str, Any]] = []
    total = 0

    # Try multi-line format first (同花顺 style)
    # Split by ## headers to identify stock blocks
    blocks = re.split(r"(?=^## )", md, flags=re.MULTILINE)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Check if this is a stock block (starts with ## and contains stock code)
        header_match = re.match(r"^##\s+(.+?)\s*\((\d{6})\)", block)
        if not header_match:
            # Try extracting total from header
            m = re.match(r"#\s*Total:\s*(\d+)", block)
            if m:
                total = int(m.group(1))
            continue

        name = header_match.group(1)
        code = header_match.group(2)

        # Extract fields from the block
        change_pct = None
        turnover_rate = None
        volume_wan = None
        net_flow_wan = None
        topics = ""

        # Extract Reason (topics)
        reason_match = re.search(r"Reason:\s*(.+)", block)
        if reason_match:
            topics = reason_match.group(1).strip()

        # Extract 涨幅
        zhangfu_match = re.search(r"涨幅:\s*([\d.]+)%?", block)
        if zhangfu_match:
            change_pct = _f(zhangfu_match.group(1))

        # Extract 换手
        huanshou_match = re.search(r"换手:\s*([\d.]+)%?", block)
        if huanshou_match:
            turnover_rate = _f(huanshou_match.group(1))

        # Extract 成交额
        chengjiao_match = re.search(r"成交额:\s*([\d,.]+)", block)
        if chengjiao_match:
            volume_wan = _f(chengjiao_match.group(1))

        # Extract DDE净量
        dde_match = re.search(r"DDE净量:\s*([\d.]+)", block)
        if dde_match:
            net_flow_wan = _f(dde_match.group(1))

        items.append({
            "ticker": code,
            "name": name,
            "change_pct": change_pct,
            "turnover_rate": turnover_rate,
            "volume_wan": volume_wan,
            "net_flow_wan": net_flow_wan,
            "topics": topics,
        })

    # If multi-line format didn't match, try single-line format (legacy)
    if not items:
        for line in md.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                # extract total from header
                m = re.match(r"#\s*Total:\s*(\d+)", stripped)
                if m:
                    total = int(m.group(1))
                continue

            m = re.match(
                r"(\d{6})\s+(.+?):\s+"
                r"([+-]?[\d.]+)%\s+"
                r"换手([\d.]+)%\s+"
                r"成交额([\d.]+)\s+"
                r"大单净量([\d.]+)"
                r"(?:\s*\|\s*(.+))?",
                stripped,
            )
            if m:
                topics = (m.group(7) or "").strip()
                items.append({
                    "ticker": m.group(1),
                    "name": m.group(2),
                    "change_pct": _f(m.group(3)),
                    "turnover_rate": _f(m.group(4)),
                    "volume_wan": _f(m.group(5)),
                    "net_flow_wan": _f(m.group(6)),
                    "topics": topics,
                })

    return {"items": items, "total": total or len(items)}


def _md_table_rows(md: str) -> tuple[list[str], list[list[str]]]:
    """Extract the first pipe-delimited table from markdown text.

    The Phase 9 backend functions emit a header line then one data row per
    record, each "a | b | c" (optionally indented; the unindented rows likewise
    start with an integer index). Returns ``(headers, rows)``; either may be
    empty when the markdown carries no table (e.g. the "无数据" branch).

    A line is treated as a table row when it contains ``|`` and has the same
    field count as the first such line.
    """
    if not md or not md.strip():
        return [], []

    headers: list[str] = []
    rows: list[list[str]] = []
    width = 0

    for raw in md.splitlines():
        if raw.lstrip().startswith("#"):
            continue
        line = raw.strip()
        if "|" not in line:
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if not headers:
            headers, width = parts, len(parts)
            continue
        if len(parts) != width:
            continue
        # Skip a markdown separator row (--- | ---).
        if all(set(p) <= {"-", ":", " "} and p for p in parts):
            continue
        rows.append(parts)

    return headers, rows


def _cell(values: list[str], idx: int) -> str:
    return values[idx] if 0 <= idx < len(values) else ""


def _num(text: str) -> float | None:
    """Parse a numeric cell, tolerating %, commas and 万/亿 suffixes."""
    if text is None:
        return None
    t = str(text).strip().replace(",", "").replace("%", "")
    if not t or t in {"-", "--", "—", "N/A", "nan", "None"}:
        return None
    try:
        return float(t)
    except (ValueError, TypeError):
        return None


def _parse_block_trade_detail(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """个股大宗交易明细 → structured rows.

    Backend emits: 序号 | 证券代码 | 证券简称 | 成交价 | 收盘价 | 溢折价率(%) |
    成交额(万) | 成交量(万) | 买方营业部 | 卖方营业部
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "index": _num(_cell(r, 0)),
            "code": _cell(r, 1),
            "name": _cell(r, 2),
            "price": _num(_cell(r, 3)),
            "close": _num(_cell(r, 4)),
            "premium_pct": _num(_cell(r, 5)),
            "amount_wan": _num(_cell(r, 6)),
            "volume_wan": _num(_cell(r, 7)),
            "buyer": _cell(r, 8),
            "seller": _cell(r, 9),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_block_trade_industry(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """大宗交易行业分布 → 行业 | 溢折价率(%) | 成交金额(万) | 成交次数."""
    _, rows = _md_table_rows(md)
    items = [
        {
            "industry": _cell(r, 0),
            "premium_pct": _num(_cell(r, 1)),
            "amount_wan": _num(_cell(r, 2)),
            "count": _num(_cell(r, 3)),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_block_trade_market_stat(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """大盘大宗交易统计 → 日期 | 溢折价率(%) | 成交金额(万) | 成交次数."""
    _, rows = _md_table_rows(md)
    items = [
        {
            "date": _cell(r, 0),
            "premium_pct": _num(_cell(r, 1)),
            "amount_wan": _num(_cell(r, 2)),
            "count": _num(_cell(r, 3)),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_dividend_bonus(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """分红送转方案明细.

    序号 | 证券代码 | 证券简称 | 送股 | 转股 | 送转总数 | 派息(元) | 收益 |
    净资产 | 公积金 | 未分配利润 | 预案公告日 | 股权登记日 | 除权除息日 | 方案进度
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "index": _num(_cell(r, 0)),
            "code": _cell(r, 1),
            "name": _cell(r, 2),
            "bonus_share": _num(_cell(r, 3)),
            "transfer_share": _num(_cell(r, 4)),
            "total_share": _num(_cell(r, 5)),
            "dividend_yuan": _num(_cell(r, 6)),
            "eps": _num(_cell(r, 7)),
            "net_asset": _num(_cell(r, 8)),
            "reserve": _num(_cell(r, 9)),
            "retained": _num(_cell(r, 10)),
            "plan_date": _cell(r, 11),
            "record_date": _cell(r, 12),
            "ex_date": _cell(r, 13),
            "status": _cell(r, 14),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_earnings_forecast(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """业绩预告 → 序号 | 证券代码 | 证券简称 | 报告期 | 预告类型 | 预告内容 | 预告日期."""
    _, rows = _md_table_rows(md)
    items = [
        {
            "index": _num(_cell(r, 0)),
            "code": _cell(r, 1),
            "name": _cell(r, 2),
            "report_period": _cell(r, 3),
            "forecast_type": _cell(r, 4),
            "content": _cell(r, 5),
            "forecast_date": _cell(r, 6),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_earnings_express(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """业绩快报 — same shape as 业绩预告 (see earnings_forecast.py)."""
    return _parse_earnings_forecast(md, ticker, date, params)


def _parse_analyst_rating(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """分析师评级.

    序号 | 报告日期 | 证券代码 | 证券简称 | 评级 | 评级变化 | 目标价 |
    EPS实际值 | T年度 | T+1年 | T+2年 | 标题 | 研究机构
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "index": _num(_cell(r, 0)),
            "report_date": _cell(r, 1),
            "code": _cell(r, 2),
            "name": _cell(r, 3),
            "rating": _cell(r, 4),
            "rating_change": _cell(r, 5),
            "target_price": _num(_cell(r, 6)),
            "eps_actual": _num(_cell(r, 7)),
            "eps_t": _num(_cell(r, 8)),
            "eps_t1": _num(_cell(r, 9)),
            "eps_t2": _num(_cell(r, 10)),
            "title": _cell(r, 11),
            "institution": _cell(r, 12),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_board_fund_flow(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """行业/概念板块资金流（Phase 12.01，东财 datacenter 报表）.

    表头: 板块 | 涨跌幅% | 主力净流入(亿) | 主力净占比% | 超大单(亿) |
    大单(亿) | 中单(亿) | 小单(亿) | 领涨股
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "board_name": _cell(r, 0),
            "change_pct": _num(_cell(r, 1)),
            "net_inflow_yi": _num(_cell(r, 2)),
            "net_inflow_pct": _num(_cell(r, 3)),
            "super_deal_yi": _num(_cell(r, 4)),
            "big_deal_yi": _num(_cell(r, 5)),
            "mid_deal_yi": _num(_cell(r, 6)),
            "small_deal_yi": _num(_cell(r, 7)),
            "lead_stock": _cell(r, 8),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_holder_num(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """股东户数历史披露（Phase 12.02 / 2026-09-28 换源 RPT_HOLDERNUM_DET，历史各期）.

    表头: 报告期 | 股东户数 | 较上期增减 | 环比增幅% | 公告日期
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "end_date": _cell(r, 0),
            "holder_num": _num(_cell(r, 1)),
            "holder_num_change": _num(_cell(r, 2)),
            "holder_num_ratio": _num(_cell(r, 3)),
            "hold_notice_date": _cell(r, 4),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_free_holders(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """十大流通股东（Phase 12.02，RPT_F10_EH_FREEHOLDERS）.

    表头: 报告期 | 排名 | 股东名称 | 持股数量(万股) | 占流通股比%
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "end_date": _cell(r, 0),
            "holder_rank": _num(_cell(r, 1)),
            "holder_name": _cell(r, 2),
            "hold_num_wan": _num(_cell(r, 3)),
            "free_ratio": _num(_cell(r, 4)),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_holder_increase(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """股东增减持（Phase 12.02，RPT_SHARE_HOLDER_INCREASE）.

    表头: 公告日 | 股东名称 | 方向 | 变动股数(万股) | 变动后持股比例%
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "notice_date": _cell(r, 0),
            "holder_name": _cell(r, 1),
            "direction": _cell(r, 2),
            "change_num_wan": _num(_cell(r, 3)),
            "hold_ratio": _num(_cell(r, 4)),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_pledge_market(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """市场质押统计（Phase 12.03，RPT_CSDC_STATISTICS）.

    表头: 日期 | 质押公司数 | 质押股数(亿股) | 质押市值(亿元) | 沪深300指数 | 沪深300涨跌幅%
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "trade_date": _cell(r, 0),
            "pledge_co_num": _num(_cell(r, 1)),
            "pledged_shares_yi": _num(_cell(r, 2)),
            "pledge_mv_yi": _num(_cell(r, 3)),
            "csi300_index": _num(_cell(r, 4)),
            "csi300_chg": _num(_cell(r, 5)),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_pledge_industry(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """行业质押统计（Phase 12.03，RPT_CSDC_INDUSTRY_STATISTICS）.

    表头: 行业 | 平均质押比例% | 质押市值(亿元) | 质押股数(亿股)
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "industry": _cell(r, 0),
            "avg_pledge_ratio": _num(_cell(r, 1)),
            "pledge_mv_yi": _num(_cell(r, 2)),
            "pledged_shares_yi": _num(_cell(r, 3)),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_pledge_stock(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """个股质押（Phase 12.03，RPT_CSDC_LIST_NEWEST，个股/榜单双模式）.

    表头: 日期 | 代码 | 简称 | 行业 | 质押比例% | 质押笔数 | 质押市值(亿元)
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "trade_date": _cell(r, 0),
            "code": _cell(r, 1),
            "name": _cell(r, 2),
            "industry": _cell(r, 3),
            "pledge_ratio": _num(_cell(r, 4)),
            "pledge_deal_num": _num(_cell(r, 5)),
            "pledge_mv_yi": _num(_cell(r, 6)),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_buyback(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """股票回购（Phase 12.03，RPTA_WEB_GPHG）.

    表头: 公告日 | 代码 | 简称 | 回购金额(万元) | 回购数量(万股) |
    回购最低价 | 回购最高价 | 市价 | 涨跌幅%
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "notice_date": _cell(r, 0),
            "code": _cell(r, 1),
            "name": _cell(r, 2),
            "amount_wan": _num(_cell(r, 3)),
            "shares_wan": _num(_cell(r, 4)),
            "price_low": _num(_cell(r, 5)),
            "price_high": _num(_cell(r, 6)),
            "price": _num(_cell(r, 7)),
            "change_pct": _num(_cell(r, 8)),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_convert_bond_list(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """可转债列表（Phase 12.06，RPT_BOND_CB_LIST）.

    表头: 转债代码 | 转债简称 | 市场 | 正股代码 | 正股简称 | 评级 |
    规模(亿元) | 转股价 | 最新价 | 申购日 | 上市日 | 到期日
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "bond_code": _cell(r, 0),
            "bond_name": _cell(r, 1),
            "market": _cell(r, 2),
            "stock_code": _cell(r, 3),
            "stock_name": _cell(r, 4),
            "rating": _cell(r, 5),
            "issue_scale_yi": _num(_cell(r, 6)),
            "convert_price": _num(_cell(r, 7)),
            "bond_price": _num(_cell(r, 8)),
            "public_start_date": _cell(r, 9),
            "listing_date": _cell(r, 10),
            "expire_date": _cell(r, 11),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_stock_notices(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """公司公告（Phase 12.04，np-anotice 个股公告流）.

    表头: 公告日 | 分类 | 标题
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "notice_date": _cell(r, 0),
            "column_name": _cell(r, 1),
            "title": _cell(r, 2),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _parse_research_reports(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """研报流（Phase 12.05，reportapi 研究报告）.

    个股模式表头: 研报日期 | 券商 | 评级 | 分析师 | 标题
    全市场模式表头: 研报日期 | 券商 | 评级 | 分析师 | 正股代码 | 正股简称 | 标题
    """
    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        if len(r) >= 7:
            item = {
                "publish_date": _cell(r, 0),
                "org_name": _cell(r, 1),
                "rating": _cell(r, 2),
                "researcher": _cell(r, 3),
                "stock_code": _cell(r, 4),
                "stock_name": _cell(r, 5),
                "title": _cell(r, 6),
            }
        else:
            item = {
                "publish_date": _cell(r, 0),
                "org_name": _cell(r, 1),
                "rating": _cell(r, 2),
                "researcher": _cell(r, 3),
                "title": _cell(r, 4),
            }
        items.append(item)
    return {"items": items, "total": len(items)}


def _walk_md_tables(md: str) -> list[list[list[str]]]:
    """提取 markdown 中**全部**管道表（_md_table_rows 只取第一张）。

    返回按出现顺序的表列表，每张表为行列表（分隔行已剔除）。
    """
    import re

    tables: list[list[list[str]]] = []
    cur: list[list[str]] = []
    for line in md.split("\n"):
        t = line.strip()
        if t.startswith("|") and t.endswith("|"):
            if re.match(r"^\|[\s\-:|]+\|$", t):
                continue
            cur.append([c.strip() for c in t.strip("|").split("|")])
        elif cur:
            tables.append(cur)
            cur = []
    if cur:
        tables.append(cur)
    return tables


def _parse_macro_gdp(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """GDP 宏观数据（Phase 13 批次，三表 → MacroAnalysisPanel 转置格式）.

    趋势表 5 列: 季度 | GDP(亿元) | 第一产业 | 第二产业 | 第三产业
    增速表 2 列: 季度 | 同比增长%
    结构表 4 列: 季度 | 第一产业% | 第二产业% | 第三产业%

    返回 ``{"gdp": {"trend": [...], "growth": [...], "structure": [...]}}``
    —— 既有 MacroAnalysisPanel 的消费形状（季度为列、指标为行的通达信式视图）。
    无趋势数据时返回 ``{}``（前端回落 rawMd）。
    """
    trend: list[dict[str, Any]] = []
    growth: list[dict[str, Any]] = []
    structure: list[dict[str, Any]] = []
    for table in _walk_md_tables(md):
        if not table:
            continue
        width = len(table[0])
        for r in table[1:]:
            quarter = _cell(r, 0)
            if not quarter:
                continue
            if width == 5:
                trend.append({
                    "quarter": quarter,
                    "gdp": _num(_cell(r, 1)),
                    "primary": _num(_cell(r, 2)),
                    "secondary": _num(_cell(r, 3)),
                    "tertiary": _num(_cell(r, 4)),
                })
            elif width == 2:
                growth.append({"quarter": quarter, "gdp_growth": _num(_cell(r, 1))})
            elif width == 4:
                structure.append({
                    "quarter": quarter,
                    "primary_pct": _num(_cell(r, 1)),
                    "secondary_pct": _num(_cell(r, 2)),
                    "tertiary_pct": _num(_cell(r, 3)),
                })
    if not trend:
        return {}
    return {"gdp": {"trend": trend, "growth": growth, "structure": structure}}


def _parse_macro_dict_lines(md: str) -> list[dict[str, Any]]:
    """解析 "- {'k': v, ...}" 形式的 dict 行列表（CPI/PMI 格式）。"""
    import ast

    items: list[dict[str, Any]] = []
    for line in md.split("\n"):
        t = line.strip()
        if not (t.startswith("- {") and t.endswith("}")):
            continue
        try:
            data = ast.literal_eval(t[2:])
        except (ValueError, SyntaxError):
            continue
        if isinstance(data, dict):
            items.append(data)
    return items


def _parse_macro_cpi(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """CPI 宏观数据（Phase 13 批次，月度 dict 行）.

    行格式: - {'商品': ..., '日期': 'YYYY-MM-DD', '今值': x, '前值': y}
    """
    items = [
        {
            "date": str(d.get("日期", "-") or "-"),
            "value": _num(str(d.get("今值", "")) if d.get("今值") is not None else ""),
            "prev": _num(str(d.get("前值", "")) if d.get("前值") is not None else ""),
        }
        for d in _parse_macro_dict_lines(md)
    ]
    return {"items": items, "total": len(items)}


def _parse_fund_purchase(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """基金发行列表 → 保留上游字段的结构化行，并满足 FundDataPanel 契约。"""
    import re

    headers, rows = _md_table_rows(md)
    items = []
    for row in rows:
        if len(row) < 7:
            continue
        offset = 1 if row and row[0] == "" else 0
        code = _clean_cell(_cell(row, offset))
        if code == "-" or not code.isdigit():
            continue
        name = _clean_cell(_cell(row, offset + 1))
        fund_type = _clean_cell(_cell(row, offset + 2))
        nav = _clean_cell(_cell(row, offset + 3))
        subscribe = _clean_cell(_cell(row, offset + 5))
        redeem = _clean_cell(_cell(row, offset + 6))
        fee = _clean_cell(_cell(row, offset + 10 if len(headers) - offset > 10 else offset + 6))
        items.append({
            "code": code,
            "name": name,
            "type": fund_type,
            "nav": nav if nav == "-" else (_num(nav) if _num(nav) is not None else nav),
            "subscribe_status": subscribe,
            "redeem_status": redeem,
            "next_open": _clean_cell(_cell(row, offset + 7 if len(headers) - offset > 7 else offset + 6)),
            "fee_rate": fee if fee == "-" else (_num(fee) if _num(fee) is not None else fee),
        })
    total_match = re.search(r"共\s*([\d,]+)\s*只", md)
    total = int(total_match.group(1).replace(",", "")) if total_match else len(items)
    issuing = [item for item in items if "暂停" in item["subscribe_status"] or "暂停" in item["redeem_status"]]
    upcoming = [item for item in items if item["next_open"] != "-"]
    return {"items": items, "all": items, "issuing": issuing, "upcoming": upcoming, "total": total}


def _parse_fund_sections(md: str) -> dict[str, Any]:
    """Parse sectioned fund markdown, retaining each table's source columns."""
    import re

    sections: dict[str, list[dict[str, str]]] = {}
    current = "items"
    lines = md.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            index += 1
            continue
        if "|" not in line or line.startswith("#"):
            index += 1
            continue
        headers = [part.strip() for part in line.strip("|").split("|")]
        index += 1
        if index < len(lines) and "|" in lines[index] and all(
            set(part.strip()) <= {"-", ":", " "} for part in lines[index].strip().strip("|").split("|")
        ):
            index += 1
        while index < len(lines) and "|" in lines[index]:
            values = [part.strip() for part in lines[index].strip().strip("|").split("|")]
            if len(values) == len(headers):
                sections.setdefault(current, []).append(dict(zip(headers, values)))
            index += 1
    return sections


def _parse_fund_announcement(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    sections = _parse_fund_sections(md)
    return {"sections": sections, **sections, "total": sum(map(len, sections.values()))}


def _parse_fund_scale(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    sections = _parse_fund_sections(md)
    items = sections.get("items", [])
    return {"items": items, "by_type": items, "total": len(items)}


def _parse_fund_open_info(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    sections = _parse_fund_sections(md)
    items = sections.get("items", [])
    total_match = __import__("re").search(r"共\s*([\d,]+)\s*只", md)
    total = int(total_match.group(1).replace(",", "")) if total_match else len(items)
    return {"items": items, "total": total}


def _parse_investment_calendar(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """投资日历（Phase 13 批次，InvestmentCalendarPanel 契约）.

    后端按事件类型分组，组头形如 ``首发新股上市（共 N 条记录）``；数据行以两空格
    缩进，表头行不缩进——以此区分表头与行。返回五组事件。
    """
    import re

    group_map = {
        "首发新股上市": "ipo_listing",
        "首发新股发行": "ipo_declaration",
        "沪深停复牌": "suspension_resumption",
        "特别处理": "special_treatment",
        "限售解禁": "lockup_expiry",
    }
    result: dict[str, Any] = {
        "date": date,
        "ipo_listing": [],
        "ipo_declaration": [],
        "suspension_resumption": [],
        "special_treatment": [],
        "lockup_expiry": [],
    }
    date_match = re.search(r"投资日历\s*\|\s*([\d-]+)", md)
    if date_match:
        result["date"] = date_match.group(1)

    current: str | None = None
    for raw in md.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for keyword, key in group_map.items():
            if keyword in line and "共" in line:
                current = key
                break
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if current is None:
            continue
        code = _clean_cell(_cell(cells, 0))
        # Header / separator rows carry label text or dashes, not a real code;
        # note the cached markdown is box-converted and loses its indentation,
        # so we key off content rather than leading whitespace.
        if code == "-" or "代码" in code or set(code) <= {"-", ":"}:
            continue
        name = _clean_cell(_cell(cells, 1))
        event: dict[str, Any] = {"code": code, "name": name}
        if current in ("ipo_listing", "ipo_declaration", "special_treatment"):
            event["description"] = _clean_cell(_cell(cells, 2))
        elif current == "suspension_resumption":
            event["suspend_date"] = _clean_cell(_cell(cells, 2))
            event["resume_date"] = _clean_cell(_cell(cells, 3))
            event["description"] = _clean_cell(_cell(cells, 4))
            event["reason"] = _clean_cell(_cell(cells, 5))
        elif current == "lockup_expiry":
            event["date"] = _clean_cell(_cell(cells, 2))
            event["quantity_wan"] = _num(_cell(cells, 3))
            event["ratio_pct"] = _num(_cell(cells, 4))
            event["reason"] = _clean_cell(_cell(cells, 5))
        result[current].append(event)
    return result


def _parse_seat_activity(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """席位活跃度（Phase 13 批次）.

    表头 7 列: 序号 | 营业部名称 | 龙虎榜成交额(万) | 上榜次数 | 买入额(万) |
    卖出额(万) | 净买入额(万)
    """
    import re

    period_match = re.search(r"周期[:：]\s*(\S+)", md)
    period = period_match.group(1) if period_match else str(params.get("period", "1个月"))
    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        name = _clean_cell(_cell(r, 1))
        if not name or name == "-":
            continue
        items.append({
            "name": name,
            "turnover_wan": _num(_cell(r, 2)),
            "appear_count": _num(_cell(r, 3)),
            "buy_amount_wan": _num(_cell(r, 4)),
            "sell_amount_wan": _num(_cell(r, 5)),
            "net_buy_wan": _num(_cell(r, 6)),
        })
    return {"period": period, "items": items, "total": len(items)}


def _parse_stock_activity(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """股票活跃度（Phase 13 批次）.

    表头 6 列: 序号 | 证券代码 | 证券简称 | 最近上榜日 | 龙虎榜成交额(万) | 上榜次数
    """
    import re

    period_match = re.search(r"周期[:：]\s*(\S+)", md)
    period = period_match.group(1) if period_match else str(params.get("period", "1个月"))
    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        code = _clean_cell(_cell(r, 1))
        if not code or code == "-":
            continue
        items.append({
            "code": code,
            "name": _clean_cell(_cell(r, 2)),
            "last_appear_date": _clean_cell(_cell(r, 3)),
            "turnover_wan": _num(_cell(r, 4)),
            "appear_count": _num(_cell(r, 5)),
        })
    return {"period": period, "items": items, "total": len(items)}


def _parse_industry_chain_categories(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """产业链分类树 → ``{categories: {大类: [子类]}, count}``（IndustryChainPanel 契约）."""
    categories: dict[str, list[str]] = {}
    current: str | None = None
    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("## ") or line.startswith("### "):
            name = line.split(" ", 1)[1].strip()
            # Overview nests the tree under "## 分类"; the card sections are
            # not categories — stop collecting there.
            import re as _re
            if _re.match(r"^分类(\s|\()", name) or name in ("hot", "new", "all", "分类"):
                current = None
                continue
            current = name
            categories.setdefault(current, [])
            continue
        if line.startswith("- ") and current is not None:
            categories[current].append(line[2:].strip())
    return {
        "categories": categories,
        "count": len(categories),
        "total": sum(len(v) for v in categories.values()),
    }


def _parse_industry_chain_chains(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """产业链卡片（hot/new/all）→ IndustryChainPanel 契约 ``{hot,new,all}``."""
    import re

    result: dict[str, Any] = {"hot": [], "new": [], "all": []}
    current: str | None = None
    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            current = line[3:].strip()
            continue
        m = re.match(r"-\s+(.+?)\s*\(\s*([+-]?[\d.]+)%\s*\)", line)
        if m and current in result:
            result[current].append({
                "name": m.group(1).strip(),
                "change_pct": float(m.group(2)),
                "has_data": True,
            })
    result["total"] = sum(len(result[k]) for k in ("hot", "new", "all"))
    return result


def _parse_industry_chain_overview(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """产业链聚合 → ``{categories: {...}, chains: {...}}``（IndustryChainPanel 契约）."""
    return {
        "categories": _parse_industry_chain_categories(md, ticker, date, params),
        "chains": _parse_industry_chain_chains(md, ticker, date, params),
    }


def _parse_industry_list(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """行业板块列表 → IndustryDataPanel 契约（total_market_cap 存元）."""
    import re

    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        name = _clean_cell(_cell(r, 0))
        if not name or name == "-":
            continue
        up_count, down_count = 0, 0
        ratio = _clean_cell(_cell(r, 4))
        if "/" in ratio:
            a, b = ratio.split("/", 1)
            up_count = int(_num(a) or 0)
            down_count = int(_num(b) or 0)
        items.append({
            "name": name,
            "change_pct": _num(_cell(r, 1)),
            "total_market_cap": _parse_cn_quantity(_cell(r, 2)),
            "turnover_rate": _num(_cell(r, 3)),
            "up_count": up_count,
            "down_count": down_count,
        })
    total_match = re.search(r"共\s*([\d,]+)\s*个", md)
    total = int(total_match.group(1).replace(",", "")) if total_match else len(items)
    return {"industries": items, "items": items, "total": total}


def _parse_industry_commodity(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """商品价格 → IndustryDataPanel 契约 ``{commodities:[{name,unit,price,change,change_pct,history}]}``."""
    import re

    commodities: list[dict[str, Any]] = []
    lines = md.splitlines()
    current: dict[str, Any] | None = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = re.match(r"#{2,3}\s+(.+?)\s*\(([^)]*)\)\s*$", line)
        if m:
            name = m.group(1).strip()
            if name in ("行业分类", "商品价格"):
                i += 1
                continue
            current = {
                "name": name,
                "unit": m.group(2).strip(),
                "price": None,
                "change": None,
                "change_pct": None,
                "history": [],
            }
            commodities.append(current)
            i += 1
            continue
        pm = re.match(
            r"价格[:：]\s*(\S+)\s+涨跌[:：]\s*([+-]?[\d.]+)\s*\(\s*([+-]?[\d.]+)%\s*\)",
            line,
        )
        if pm and current is not None:
            current["price"] = _num(pm.group(1))
            current["change"] = float(pm.group(2))
            current["change_pct"] = float(pm.group(3))
            i += 1
            continue
        if current is not None and line.startswith("| 日期"):
            i += 2  # header + separator
            while i < len(lines) and "|" in lines[i]:
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                if len(cells) >= 4 and _clean_cell(cells[0]) != "-":
                    current["history"].append({
                        "date": _clean_cell(cells[0]),
                        "price": _num(cells[1]),
                        "change": _num(cells[2]),
                        "change_pct": _num(cells[3]),
                    })
                i += 1
            continue
        i += 1
    return {"commodities": commodities, "items": commodities, "total": len(commodities)}


def _parse_industry_data_overview(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """行业数据聚合 → ``{list:{categories}, commodity:{commodities}}``（IndustryDataPanel 契约）."""
    categories: list[str] = []
    in_cats = False
    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("## 行业分类"):
            in_cats = True
            continue
        if line.startswith("## "):
            in_cats = False
            continue
        if in_cats and line.startswith("- "):
            categories.append(line[2:].strip())
    commodities = _parse_industry_commodity(md, ticker, date, params)["commodities"]
    return {
        "list": {"categories": categories},
        "categories": categories,
        "commodity": {"commodities": commodities},
        "total": len(categories),
    }


def _parse_industry_detail(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """行业详情 → ``{name, stocks:[...], history:[...]}``（保留原始条目文本）."""
    import re

    name_match = re.search(r"#\s*(.+?)\s*行业详情", md)
    name = name_match.group(1).strip() if name_match else str(params.get("name", ""))
    stocks: list[str] = []
    history: list[str] = []
    current: list[str] | None = None
    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("## 成分股"):
            current = stocks
            continue
        if line.startswith("## 近期走势"):
            current = history
            continue
        if current is not None and line.startswith("- "):
            current.append(line[2:].strip())
    return {
        "name": name,
        "stocks": stocks,
        "history": history,
        "total": len(stocks),
    }


def _parse_company_name_changes(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """公司更名记录（Phase 13 批次，深交所真源）.

    表头 6 列: 序号 | 变更日期 | 证券代码 | 证券简称 | 变更前 | 变更后
    """
    import re

    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        code = _clean_cell(_cell(r, 2))
        if not code or code == "-":
            continue
        items.append({
            "change_date": _clean_cell(_cell(r, 1)),
            "code": code,
            "name": _clean_cell(_cell(r, 3)),
            "before": _clean_cell(_cell(r, 4)),
            "after": _clean_cell(_cell(r, 5)),
        })
    source_match = re.search(r"（([^，]+)，仅覆盖深市证券）", md)
    total_match = re.search(r"共\s*([\d,]+)\s*条更名记录", md)
    return {
        "source_symbol": source_match.group(1) if source_match else "简称变更",
        "items": items,
        "total": int(total_match.group(1).replace(",", "")) if total_match else len(items),
    }


def _parse_st_changes(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """ST 变更记录（Phase 13 批次，深交所简称变更派生）.

    表头 7 列: 序号 | 变更日期 | 证券代码 | 证券简称 | 变更前简称 | 变更后简称 | 方向
    """
    import re

    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        code = _clean_cell(_cell(r, 2))
        if not code or code == "-":
            continue
        items.append({
            "change_date": _clean_cell(_cell(r, 1)),
            "code": code,
            "name": _clean_cell(_cell(r, 3)),
            "before": _clean_cell(_cell(r, 4)),
            "after": _clean_cell(_cell(r, 5)),
            "direction": _clean_cell(_cell(r, 6)),
        })
    total_match = re.search(r"共\s*([\d,]+)\s*条ST变更记录", md)
    return {
        "items": items,
        "total": int(total_match.group(1).replace(",", "")) if total_match else len(items),
    }


def _parse_survey_interaction(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """机构调研（Phase 13 批次）.

    表头 13 列: 序号 | 证券代码 | 证券简称 | 所属行业 | 最新调研日 |
    近一月调研 | 近三月调研 | 近半年调研 | 近一月机构 | 近三月机构 |
    近半年机构 | 最新价 | 涨跌幅%
    """
    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        code = _clean_cell(_cell(r, 1))
        if not code or code == "-":
            continue
        items.append({
            "code": code,
            "name": _clean_cell(_cell(r, 2)),
            "industry": _clean_cell(_cell(r, 3)),
            "last_survey_date": _clean_cell(_cell(r, 4)),
            "survey_1m": _num(_cell(r, 5)),
            "survey_3m": _num(_cell(r, 6)),
            "survey_6m": _num(_cell(r, 7)),
            "inst_1m": _num(_cell(r, 8)),
            "inst_3m": _num(_cell(r, 9)),
            "inst_6m": _num(_cell(r, 10)),
            "price": _num(_cell(r, 11)),
            "change_pct": _num(_cell(r, 12)),
        })
    return {"items": items, "total": len(items)}


def _parse_market_statistics(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """市场统计三节 → ``{scale, turnover, investors}``（各含 items）."""
    sections: dict[str, list[dict[str, Any]]] = {
        "scale": [], "turnover": [], "investors": [],
    }
    key_map = {
        "市场规模统计": "scale",
        "成交概况": "turnover",
        "投资者情况": "investors",
    }
    current: str | None = None
    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            head = line[3:].strip()
            current = None
            for prefix, key in key_map.items():
                if head.startswith(prefix):
                    current = key
                    break
            continue
        if current is None or "|" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        first = _clean_cell(_cell(cells, 0))
        if first == "-" or "交易所" in first or first.startswith("市场") or first.startswith("月份"):
            continue  # header / separator rows
        if current == "scale":
            sections["scale"].append({
                "exchange": first,
                "listed_stocks": _num(_cell(cells, 1)),
                "listed_companies": _num(_cell(cells, 2)),
                "market_cap_yi": _num(_cell(cells, 3)),
                "float_cap_yi": _num(_cell(cells, 4)),
                "float_shares_yi": _num(_cell(cells, 5)),
                "pe_avg": _num(_cell(cells, 6)),
                "pe_star": _num(_cell(cells, 7)),
            })
        elif current == "turnover":
            sections["turnover"].append({
                "market": first,
                "variety": _clean_cell(_cell(cells, 1)),
                "count": _num(_cell(cells, 2)),
                "amount_yi": _num(_cell(cells, 3)),
            })
        else:
            sections["investors"].append({
                "month": first,
                "new_investors_wan": _num(_cell(cells, 1)),
                "total_investors_wan": _num(_cell(cells, 2)),
                "a_account_wan": _num(_cell(cells, 3)),
                "total_cap_yi": _num(_cell(cells, 4)),
                "avg_cap_wan": _num(_cell(cells, 5)),
            })
    return {
        "scale": {"items": sections["scale"], "total": len(sections["scale"])},
        "turnover": {"items": sections["turnover"], "total": len(sections["turnover"])},
        "investors": {"items": sections["investors"], "total": len(sections["investors"])},
    }


def _parse_futures_position(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """股指期货持仓龙虎榜 → ``{variety, date, contracts:[{symbol, volume/long/short}]}``."""
    import re

    variety = str(params.get("contract", "IF"))
    variety_match = re.search(r"品种[:：]\s*(\S+)", md)
    if variety_match:
        variety = variety_match.group(1)
    date_match = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*$", md.splitlines()[0] if md else "")
    anchor = date_match.group(1) if date_match else date

    kind_map = {
        "成交量龙虎榜": "volume",
        "多头持仓龙虎榜": "long",
        "空头持仓龙虎榜": "short",
    }
    contracts: list[dict[str, Any]] = []
    contract: dict[str, Any] | None = None
    kind: str | None = None
    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("## 合约"):
            contract = {"symbol": line.replace("## 合约", "").strip()}
            contracts.append(contract)
            kind = None
            continue
        if line.startswith("### "):
            head = line[4:].strip()
            kind = kind_map.get(head)
            if contract is not None and kind is not None and kind not in contract:
                contract[kind] = {"items": [], "total": None}
            continue
        if contract is None or kind is None or "|" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        first = _clean_cell(cells[0])
        if first.startswith("名次"):
            continue
        entry = {
            "rank": None if first == "本日合计" else (_num(first)),
            "member": _clean_cell(cells[1]),
            "value": _num(cells[2]),
            "change": _num(cells[3]),
        }
        if first == "本日合计":
            contract[kind]["total"] = {
                "rank": None,
                "member": "本日合计",
                "value": entry["value"],
                "change": entry["change"],
            }
        else:
            contract[kind]["items"].append(entry)
    return {"variety": variety, "date": anchor, "contracts": contracts, "total": len(contracts)}


def _parse_consensus_estimate(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """机构一致预期（工单 17 余项，RPT_WEB_RESPREDICT）.

    表头 14 列: 证券代码 | 证券简称 | 评级机构数 | 买入 | 增持 | 中性 | 减持 |
    卖出 | 目标价低(元) | 目标价高(元) | 年度1 | EPS1(元) | 年度2 | EPS2(元)
    年度单元格形如 ``2026E``（A=实际 / E=预测）。
    """
    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        code = _clean_cell(_cell(r, 0))
        if not code or code == "-":
            continue
        items.append({
            "code": code,
            "name": _clean_cell(_cell(r, 1)),
            "rating_org_num": _num(_cell(r, 2)),
            "rating_buy": _num(_cell(r, 3)),
            "rating_add": _num(_cell(r, 4)),
            "rating_neutral": _num(_cell(r, 5)),
            "rating_reduce": _num(_cell(r, 6)),
            "rating_sale": _num(_cell(r, 7)),
            "aim_price_min": _num(_cell(r, 8)),
            "aim_price_max": _num(_cell(r, 9)),
            "year1": _clean_cell(_cell(r, 10)),
            "eps1": _num(_cell(r, 11)),
            "year2": _clean_cell(_cell(r, 12)),
            "eps2": _num(_cell(r, 13)),
        })
    return {"items": items, "total": len(items)}


def _parse_hk_ipo(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """港股新股（工单 08 真源 aastocks，双分区）.

    招股中 8 列: 代码 | 名称 | 行业 | 招股价 | 每手股数 | 入场费(港元) |
    招股截止日 | 上市日期（代码为 5 位港股码，如 01256）
    已上市 5 列: 上市日期 | 代码 | 名称 | 上市价 | 超额倍数
    衍生权证行已在数据端过滤。
    """
    section: str | None = None
    subscribing: list[dict[str, Any]] = []
    listed: list[dict[str, Any]] = []
    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("## 招股中"):
            section = "sub"
            continue
        if line.startswith("## 已上市"):
            section = "listed"
            continue
        if section is None or "|" not in line or line.startswith("#"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        first = _clean_cell(_cell(cells, 0))
        if first == "-" or not first[:1].isdigit():
            continue  # 表头行
        code_match = first
        if section == "sub":
            subscribing.append({
                "code": code_match,
                "name": _clean_cell(_cell(cells, 1)),
                "industry": _clean_cell(_cell(cells, 2)),
                "price_range": _clean_cell(_cell(cells, 3)),
                "lot_size": _num(_cell(cells, 4)),
                "entry_fee": _num(_cell(cells, 5)),
                "deadline": _clean_cell(_cell(cells, 6)),
                "listing_date": _clean_cell(_cell(cells, 7)),
            })
        else:
            listed.append({
                "listing_date": first,
                "code": _clean_cell(_cell(cells, 1)),
                "name": _clean_cell(_cell(cells, 2)),
                "offer_price": _num(_cell(cells, 3)),
                "oversubscription": _num(_cell(cells, 4)),
            })
    return {
        "subscribing": subscribing,
        "listed": listed,
        "items": subscribing + listed,
        "total": len(subscribing) + len(listed),
    }


def _parse_macro_pmi(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """PMI 宏观数据（Phase 13 批次，季度 dict 行）.

    行格式: - {'季度': ..., '企业景气指数-指数': x, '企业景气指数-同比': y,
    '企业景气指数-环比': z}
    """
    items = [
        {
            "quarter": str(d.get("季度", "-") or "-"),
            "index": _num(str(d.get("企业景气指数-指数")) if d.get("企业景气指数-指数") is not None else ""),
            "yoy": _num(str(d.get("企业景气指数-同比")) if d.get("企业景气指数-同比") is not None else ""),
            "mom": _num(str(d.get("企业景气指数-环比")) if d.get("企业景气指数-环比") is not None else ""),
        }
        for d in _parse_macro_dict_lines(md)
    ]
    return {"items": items, "total": len(items)}



def _clean_cell(raw: str) -> str:
    """空占位（-/--/—/N/A/NA/nan/空）统一归一为 "-"。"""
    t = (raw or "").strip()
    return "-" if t in ("", "-", "--", "—", "N/A", "NA", "nan") else t


def _parse_ipo_declaration(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """新股发行预告（Phase 13 批次，IpoCenterPanel 契约）.

    表头 11 列: 序号 | 证券代码 | 证券简称 | 申购日期 | 申购代码 | 申购价(元) |
    发行量(万) | 网上发行量(万) | 申购上限(万) | 市盈率(摊薄) | 中签号公布日
    """
    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        code = _clean_cell(_cell(r, 1))
        if not code or code == "-":
            continue
        items.append({
            "code": code,
            "name": _clean_cell(_cell(r, 2)),
            "subscribe_date": _clean_cell(_cell(r, 3)),
            "subscribe_code": _clean_cell(_cell(r, 4)),
            "price": _num(_clean_cell(_cell(r, 5))),
            "volume_wan": _num(_clean_cell(_cell(r, 6))),
            "online_volume_wan": _num(_clean_cell(_cell(r, 7))),
            "subscribe_limit_wan": _num(_clean_cell(_cell(r, 8))),
            "pe_ratio": _num(_clean_cell(_cell(r, 9))),
            "lottery_date": _clean_cell(_cell(r, 10)),
        })
    return {"items": items, "total": len(items)}


def _parse_ipo_listing(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """新股上市预告（Phase 13 批次，IpoCenterPanel 契约）.

    表头 10 列: 序号 | 证券代码 | 证券简称 | 上市日期 | 发行价(元) | 发行量(万) |
    网上发行量(万) | 市盈率(摊薄) | 申购日期 | 中签率%
    注意: ``win_rate`` 后端为百分数（1.3361），存小数（0.013361）供面板 ×100 显示。
    """
    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        code = _clean_cell(_cell(r, 1))
        if not code or code == "-":
            continue
        win_raw = _num(_clean_cell(_cell(r, 9)))
        items.append({
            "code": code,
            "name": _clean_cell(_cell(r, 2)),
            "listing_date": _clean_cell(_cell(r, 3)),
            "price": _num(_clean_cell(_cell(r, 4))),
            "volume_wan": _num(_clean_cell(_cell(r, 5))),
            "online_volume_wan": _num(_clean_cell(_cell(r, 6))),
            "pe_ratio": _num(_clean_cell(_cell(r, 7))),
            "subscribe_date": _clean_cell(_cell(r, 8)),
            "win_rate": None if win_raw is None else win_raw / 100.0,
        })
    return {"items": items, "total": len(items)}



def _parse_cn_quantity(raw: str) -> "float | None":
    """解析带中文数量级的数值: "358.36亿"→元(×1e8), "594.48万"→×1e4, 逗号数字→原值。"""
    t = _clean_cell(raw)
    if t == "-":
        return None
    t = t.replace(",", "")
    try:
        if t.endswith("亿"):
            return float(t[:-1]) * 1e8
        if t.endswith("万"):
            return float(t[:-1]) * 1e4
        return float(t)
    except ValueError:
        return None


def _parse_margin_detail(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """融资融券明细（Phase 13 批次，MarginTradingPanel 契约）.

    表头 11 列: 序号 | 证券代码 | 证券简称 | 融资余额(亿) | 融资买入(亿) |
    融资偿还(亿) | 净买入(亿) | 融券余量 | 融券卖出 | 融券偿还 | 净卖出
    亿字段 ×1e8 存元，融券字段 ×1e4 存股——面板 fmtYi/fmtWan 反向除回。
    """
    import re as _re

    market = "-"
    m = _re.search(r"市场[:：]\s*(\S+)", md)
    if m:
        market = m.group(1)
    total = None
    m2 = _re.search(r"共\s*([\d,]+)\s*只", md)
    if m2:
        total = int(m2.group(1).replace(",", ""))

    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        code = _clean_cell(_cell(r, 1))
        if not code or code == "-":
            continue
        items.append({
            "code": code,
            "name": _clean_cell(_cell(r, 2)),
            "margin_balance": _parse_cn_quantity(_cell(r, 3)),
            "margin_buy": _parse_cn_quantity(_cell(r, 4)),
            "margin_repay": _parse_cn_quantity(_cell(r, 5)),
            "net_buy": _parse_cn_quantity(_cell(r, 6)),
            "short_qty": _parse_cn_quantity(_cell(r, 7)),
            "short_sell": _parse_cn_quantity(_cell(r, 8)),
            "short_repay": _parse_cn_quantity(_cell(r, 9)),
            "net_short": _parse_cn_quantity(_cell(r, 10)),
        })
    return {"items": items, "total": total if total is not None else len(items), "market": market}


def _parse_margin_market_stat(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """融资融券市场统计（Phase 13 批次，MarginTradingPanel 时序图契约）.

    表头 6 列: 日期 | 融资余额(亿) | 融资买入(亿) | 融券余量 | 融券余量金额(亿) |
    融资融券余额(亿)。亿字段 ×1e8 存元，融券余量为股数（逗号分隔）。
    """
    _, rows = _md_table_rows(md)
    items = []
    for r in rows:
        d = _clean_cell(_cell(r, 0))
        if not d or d == "-":
            continue
        items.append({
            "date": d,
            "margin_balance": _parse_cn_quantity(_cell(r, 1)),
            "margin_buy": _parse_cn_quantity(_cell(r, 2)),
            "short_qty": _parse_cn_quantity(_cell(r, 3)),
            "short_balance": _parse_cn_quantity(_cell(r, 4)),
            "total_balance": _parse_cn_quantity(_cell(r, 5)),
        })
    return {"items": items, "total": len(items)}



def _parse_institutional_hold(
    md: str, ticker: str, date: str, params: dict[str, Any]
) -> dict[str, Any]:
    """机构持股明细.

    序号 | 证券代码 | 证券简称 | 所属行业 | 持股机构数 | 持仓数量(万股) |
    持仓市值(万元) | 占总股本比例(%) | 占已流通A股比例(%) | 较上期增减(万股) | 仓位类型
    """
    _, rows = _md_table_rows(md)
    items = [
        {
            "index": _num(_cell(r, 0)),
            "code": _cell(r, 1),
            "name": _cell(r, 2),
            "industry": _cell(r, 3),
            "inst_count": _num(_cell(r, 4)),
            "shares_wan": _num(_cell(r, 5)),
            "market_value_wan": _num(_cell(r, 6)),
            "total_pct": _num(_cell(r, 7)),
            "float_pct": _num(_cell(r, 8)),
            "change_wan": _num(_cell(r, 9)),
            "position_type": _cell(r, 10),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}


def _build_feature_table() -> dict[str, dict[str, Any]]:
    """feature name -> backend caller (+ optional future parser).

    Kept as a table (not if/elif chains) so adding a feature is one row:
    a caller lambda plus, from 5.02 on, a structured parser entry.
    """
    from tradingagents.dataflows.a_stock import (
        get_balance_sheet,
        get_cashflow,
        get_chip_distribution,
        get_concept_blocks,
        get_dragon_tiger_board,
        get_hot_stocks,
        get_income_statement,
        get_industry_comparison,
        get_insider_transactions,
        get_lockup_expiry,
        get_northbound_flow,
        get_profit_forecast,
    )
    # Phase 7 imports
    from tradingagents.dataflows.a_stock.ipo_center import (
        get_ipo_declaration,
        get_ipo_listing,
    )
    from tradingagents.dataflows.a_stock.margin_trading import (
        get_margin_detail,
        get_margin_market_stat,
        get_margin_industry,
    )
    from tradingagents.dataflows.a_stock.investment_calendar import (
        get_investment_calendar,
    )
    from tradingagents.dataflows.a_stock.eastmoney import (
        get_seat_activity_analysis,
        get_stock_activity_analysis,
    )
    # Phase 9 imports
    from tradingagents.dataflows.a_stock.block_trade import (
        get_block_trade_detail,
        get_block_trade_industry,
        get_block_trade_market_stat,
    )
    from tradingagents.dataflows.a_stock.dividend_bonus import (
        get_dividend_bonus,
    )
    from tradingagents.dataflows.a_stock.earnings_forecast import (
        get_earnings_forecast,
        get_earnings_express,
    )
    from tradingagents.dataflows.a_stock.consensus_estimate import (
        get_consensus_estimate,
    )
    from tradingagents.dataflows.a_stock.analyst_rating import (
        get_analyst_rating,
    )
    from tradingagents.dataflows.a_stock.institutional_hold import (
        get_institutional_hold,
    )
    from tradingagents.dataflows.a_stock.mootdx_client import (
        get_insider_change_chart,
    )
    # TongDaXin reference data
    from tradingagents.dataflows.a_stock.survey_reference import (
        get_survey_interaction,
        get_company_name_changes,
        get_st_changes,
    )
    from tradingagents.dataflows.a_stock.tdx_reference import (
        get_neeq_abnormal_trade,
        get_hk_ipo,
        get_us_ipo,
    )
    from tradingagents.dataflows.a_stock.fund_flow_ranking import get_board_fund_flow
    from tradingagents.dataflows.a_stock.holder_structure import (
        get_free_holders,
        get_holder_increase,
        get_holder_num,
    )
    from tradingagents.dataflows.a_stock.corporate_actions import (
        get_buyback,
        get_pledge_industry,
        get_pledge_market,
        get_pledge_stock,
    )
    from tradingagents.dataflows.a_stock.convert_bond import get_convert_bond_list
    from tradingagents.dataflows.a_stock.stock_notices import get_stock_notices
    from tradingagents.dataflows.a_stock.research_reports import get_research_reports
    from tradingagents.dataflows.a_stock.futures_position import (
        get_futures_position,
    )
    from tradingagents.dataflows.a_stock.market_stats import (
        get_market_statistics,
    )
    # Phase 10: TongDaXin 数据菜单新模块
    from tradingagents.dataflows.a_stock.fund_data import (
        get_fund_purchase,
        get_fund_announcement,
        get_fund_scale,
        get_fund_open_info,
    )
    from tradingagents.dataflows.a_stock.industry_chain import (
        get_industry_chain_categories,
        get_industry_chain_chains,
        get_industry_chain_overview,
    )
    from tradingagents.dataflows.a_stock.industry_data import (
        get_industry_list,
        get_industry_detail,
        get_industry_commodity,
        get_industry_data_overview,
    )
    from tradingagents.dataflows.a_stock.macro_analysis import (
        get_macro_gdp,
        get_macro_cpi,
        get_macro_pmi,
        get_macro_overview,
    )
    from tradingagents.dataflows.a_stock.stock_info_panel import (
        get_stock_info_panel,
    )

    def _call_chip(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_chip_distribution(ticker, date, days=int(p.get("days", 90)))

    def _call_dragon(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_dragon_tiger_board(
            ticker, date, look_back_days=int(p.get("look_back_days", 30))
        )

    def _call_northbound(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_northbound_flow(date, include_history=bool(p.get("include_history", True)))

    def _call_concept(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_concept_blocks(ticker)

    def _call_profit(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_profit_forecast(ticker, date)

    def _call_lockup(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_lockup_expiry(ticker, date, forward_days=int(p.get("forward_days", 90)))

    def _call_industry(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_industry_comparison(ticker, date, top_n=int(p.get("top_n", 20)))

    def _call_hot(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_hot_stocks(date)

    def _call_insider(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_insider_transactions(ticker)

    # Phase 7 call functions
    def _call_ipo_decl(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_ipo_declaration(date)

    def _call_ipo_list(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_ipo_listing(date)

    def _call_margin_detail(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_margin_detail(market=str(p.get("market", "sh")), curr_date=date)

    def _call_margin_stat(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_margin_market_stat(market=str(p.get("market", "total")), curr_date=date)

    def _call_margin_industry(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_margin_industry(curr_date=date)

    def _call_investment_calendar(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_investment_calendar(date)

    def _call_seat_activity(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_seat_activity_analysis(curr_date=date, period=str(p.get("period", "1个月")))

    def _call_stock_activity(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_stock_activity_analysis(curr_date=date, period=str(p.get("period", "1个月")))

    # Phase 9 call functions with PG cache
    def _call_block_detail(ticker: str, date: str, p: dict[str, Any]) -> str:
        from tradingagents.cache.manager import get_cache
        mgr = get_cache("BLOCK")
        with mgr.fetch("block_trade_detail", date, source_fn=lambda: get_block_trade_detail(curr_date=date, market=str(p.get("market", "all")))) as (data, hit):
            return data if isinstance(data, str) else str(data)

    def _call_block_industry(ticker: str, date: str, p: dict[str, Any]) -> str:
        from tradingagents.cache.manager import get_cache
        mgr = get_cache("BLOCK")
        month = str(p.get("month", date[:7]))
        with mgr.fetch("block_trade_industry", month, source_fn=lambda: get_block_trade_industry(month=month)) as (data, hit):
            return data if isinstance(data, str) else str(data)

    def _call_block_market_stat(ticker: str, date: str, p: dict[str, Any]) -> str:
        from tradingagents.cache.manager import get_cache
        mgr = get_cache("BLOCK")
        month = str(p.get("month", date[:7]))
        with mgr.fetch("block_trade_market_stat", month, source_fn=lambda: get_block_trade_market_stat(month=month)) as (data, hit):
            return data if isinstance(data, str) else str(data)

    def _call_dividend(ticker: str, date: str, p: dict[str, Any]) -> str:
        from tradingagents.cache.manager import get_cache
        mgr = get_cache("DIV")
        with mgr.fetch("dividend_bonus", date, source_fn=lambda: get_dividend_bonus(curr_date=date, market=str(p.get("market", "all")), status=str(p.get("status", "all")))) as (data, hit):
            return data if isinstance(data, str) else str(data)

    def _call_earnings_fc(ticker: str, date: str, p: dict[str, Any]) -> str:
        from tradingagents.cache.manager import get_cache
        mgr = get_cache("EARN")
        with mgr.fetch("earnings_forecast", date, source_fn=lambda: get_earnings_forecast(curr_date=date, forecast_type=str(p.get("forecast_type", "all")))) as (data, hit):
            return data if isinstance(data, str) else str(data)

    def _call_earnings_ex(ticker: str, date: str, p: dict[str, Any]) -> str:
        from tradingagents.cache.manager import get_cache
        mgr = get_cache("EARN")
        with mgr.fetch("earnings_express", date, source_fn=lambda: get_earnings_express(curr_date=date)) as (data, hit):
            return data if isinstance(data, str) else str(data)

    # 工单 17 余项 — 机构一致预期（东财 RPT_WEB_RESPREDICT，实测核实）
    def _call_consensus_estimate(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_consensus_estimate(
            ticker if is_astock_code(ticker) else None,
            page_size=int(p.get("page_size", 50)),
        )

    def _call_analyst(ticker: str, date: str, p: dict[str, Any]) -> str:
        from tradingagents.cache.manager import get_cache
        mgr = get_cache("ANALYST")
        with mgr.fetch("analyst_rating", date, source_fn=lambda: get_analyst_rating(curr_date=date, period=str(p.get("period", "一月内")))) as (data, hit):
            return data if isinstance(data, str) else str(data)

    def _call_inst_hold(ticker: str, date: str, p: dict[str, Any]) -> str:
        from tradingagents.cache.manager import get_cache
        mgr = get_cache("INST")
        with mgr.fetch("institutional_hold", date, source_fn=lambda: get_institutional_hold(report_date=date, inst_type=str(p.get("inst_type", "all")), position_type=str(p.get("position_type", "all")))) as (data, hit):
            return data if isinstance(data, str) else str(data)

    def _call_insider_chart(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_insider_change_chart(ticker=ticker, market=str(p.get("market", "all")), curr_date=date)

    # TongDaXin reference data call functions
    def _call_survey_interaction(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_survey_interaction(
            curr_date=date,
            page_size=int(p.get("page_size", 50)),
            page_number=int(p.get("page_number", 1)),
        )

    def _call_company_name_changes(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_company_name_changes(
            start_date=str(p.get("start_date", "")) or None,
            end_date=str(p.get("end_date", "")) or None,
            page_size=int(p.get("page_size", 50)),
            page_number=int(p.get("page_number", 1)),
        )

    def _call_st_changes(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_st_changes(
            start_date=str(p.get("start_date", "")) or None,
            end_date=str(p.get("end_date", "")) or None,
            page_size=int(p.get("page_size", 50)),
            page_number=int(p.get("page_number", 1)),
        )

    def _call_neeq_abnormal_trade(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_neeq_abnormal_trade(
            curr_date=date,
            page_size=int(p.get("page_size", 50)),
            page_number=int(p.get("page_number", 1)),
        )

    def _call_hk_ipo(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_hk_ipo(
            curr_date=date,
            page_size=int(p.get("page_size", 50)),
            page_number=int(p.get("page_number", 1)),
        )

    def _call_us_ipo(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_us_ipo(
            curr_date=date,
            page_size=int(p.get("page_size", 50)),
            page_number=int(p.get("page_number", 1)),
        )

    def _call_futures_position(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_futures_position(
            contract=str(p.get("contract", "IF")),
            curr_date=date,
            page_size=int(p.get("page_size", 50)),
            page_number=int(p.get("page_number", 1)),
        )

    def _call_market_statistics(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_market_statistics(curr_date=date)

    # Phase 12.01 call functions — 板块资金流（东财 datacenter，实测核实）
    def _call_industry_fund_flow(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_board_fund_flow(
            "industry",
            curr_date=date,
            page_size=int(p.get("page_size", 50)),
        )

    def _call_concept_fund_flow(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_board_fund_flow(
            "concept",
            curr_date=date,
            page_size=int(p.get("page_size", 50)),
        )

    # Phase 12.02 call functions — 持仓股东（东财 datacenter/F10，实测核实）
    def _call_holder_num(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_holder_num(ticker, page_size=int(p.get("page_size", 50)))

    def _call_free_holders(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_free_holders(ticker)

    def _call_holder_increase(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_holder_increase(ticker, page_size=int(p.get("page_size", 30)))

    # Phase 12.03 call functions — 公司行动（东财 datacenter，实测核实）
    def _call_pledge_market(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_pledge_market()

    def _call_pledge_industry(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_pledge_industry(page_size=int(p.get("page_size", 50)))

    def _call_pledge_stock(ticker: str, date: str, p: dict[str, Any]) -> str:
        use_ticker = ticker if is_astock_code(ticker) else None
        return get_pledge_stock(
            use_ticker,
            page_size=int(p.get("page_size", 50)),
        )

    def _call_buyback(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_buyback(page_size=int(p.get("page_size", 50)))

    # Phase 12.06 call function — 可转债列表（东财 datacenter，实测核实）
    def _call_convert_bond_list(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_convert_bond_list(page_size=int(p.get("page_size", 50)))

    # Phase 12.04 call function — 公司公告（东财 np-anotice，实测核实）
    # f_node/s_node 公告分类过滤：官方分类树见 stock_notices.py docstring
    def _call_stock_notices(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_stock_notices(
            ticker,
            page_size=int(p.get("page_size", 30)),
            f_node=int(p.get("f_node", 0)),
            s_node=int(p.get("s_node", 0)),
        )

    # Phase 12.05 call function — 研报流（东财 reportapi，实测核实）
    def _call_research_reports(ticker: str, date: str, p: dict[str, Any]) -> str:
        return get_research_reports(
            ticker if is_astock_code(ticker) else None,
            date=date,
            page_size=int(p.get("page_size", 30)),
        )

    # Phase 10 call functions — return markdown strings
    def _call_fund_purchase(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_fund_purchase()
        if not data or not data.get("all"):
            return "暂无基金发行数据"
        lines = ["# 基金发行列表\n"]
        lines.append(f"共 {data.get('total', 0)} 只基金\n")
        lines.append("| 基金代码 | 基金简称 | 基金类型 | 最新净值 | 净值日期 | 申购状态 | 赎回状态 | 下一开放日 | 最低购买 | 日累计限额 | 手续费 |")
        lines.append("|---------|---------|---------|---------|---------|---------|---------|---------|---------|---------|--------|")
        for item in data.get("all", [])[:50]:
            values = [item.get(key, "-") for key in ("code", "name", "type", "nav", "nav_date", "subscribe_status", "redeem_status", "next_open", "min_buy", "daily_limit", "fee_rate")]
            lines.append("| " + " | ".join(str(value) for value in values) + " |")
        return "\n".join(lines)

    def _call_fund_announcement(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_fund_announcement()
        if not data:
            return "暂无基金公告数据"
        lines = ["# 基金公告\n"]
        for key in ["reports", "dividends", "personnel"]:
            items = data.get(key, [])
            if not items:
                continue
            lines.extend([f"## {key}", ""])
            headers = list(dict.fromkeys(column for item in items for column in item))
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for item in items[:50]:
                lines.append("| " + " | ".join(str(item.get(column, "-")) for column in headers) + " |")
        return "\n".join(lines)

    def _call_fund_scale(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_fund_scale()
        items = data.get("by_type", []) if data else []
        if not items:
            return "暂无基金规模数据"
        lines = ["# 基金规模统计\n"]
        headers = list(dict.fromkeys(column for item in items for column in item))
        lines.extend(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"])
        for item in items:
            lines.append("| " + " | ".join(str(item.get(column, "-")) for column in headers) + " |")
        return "\n".join(lines)

    def _call_fund_open_info(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_fund_open_info()
        items = data.get("items", []) if data else []
        if not items:
            return "暂无开放式基金数据"
        lines = ["# 开放式基金信息\n", f"共 {data.get('total', 0)} 只\n"]
        headers = list(dict.fromkeys(column for item in items for column in item))
        lines.extend(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"])
        for item in items:
            lines.append("| " + " | ".join(str(item.get(column, "-")) for column in headers) + " |")
        return "\n".join(lines)

    def _call_industry_chain_overview(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_industry_chain_overview()
        if not data:
            return "暂无产业链数据"
        lines = ["# 产业链平台\n"]
        cats = data.get("categories", {}).get("categories", {})
        lines.append(f"## 分类 ({len(cats)} 个大类)\n")
        for cat, subs in list(cats.items())[:10]:
            lines.append(f"### {cat}")
            if subs:
                for s in subs[:5]:
                    lines.append(f"- {s}")
        chains = data.get("chains", {})
        for section in ["hot", "new", "all"]:
            items = chains.get(section, [])
            if items:
                lines.append(f"\n## {section}\n")
                for item in items[:10]:
                    lines.append(f"- {item.get('name', '')} ({item.get('change_pct', 0):.2f}%)")
        return "\n".join(lines)

    def _call_industry_chain_categories(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_industry_chain_categories()
        if not data:
            return "暂无产业链分类数据"
        lines = ["# 产业链分类\n"]
        for cat, subs in data.get("categories", {}).items():
            lines.append(f"## {cat}")
            if subs:
                for s in subs:
                    lines.append(f"- {s}")
        return "\n".join(lines)

    def _call_industry_chain_chains(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_industry_chain_chains()
        if not data:
            return "暂无产业链卡片数据"
        lines = ["# 产业链卡片\n"]
        for section in ["hot", "new", "all"]:
            items = data.get(section, [])
            if items:
                lines.append(f"## {section}\n")
                for item in items:
                    pct = item.get("change_pct", 0)
                    lines.append(f"- {item.get('name', '')} ({pct:+.2f}%)")
        return "\n".join(lines)

    def _call_industry_data_overview(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_industry_data_overview()
        if not data:
            return "暂无行业数据"
        lines = ["# 行业数据\n"]
        # Categories
        cats = data.get("list", {}).get("categories", [])
        lines.append(f"## 行业分类 ({len(cats)})\n")
        for c in cats:
            lines.append(f"- {c}")
        # Commodities
        commodities = data.get("commodity", {}).get("commodities", [])
        if commodities:
            lines.append("\n## 商品价格\n")
            for c in commodities:
                lines.append(f"### {c.get('name', '')} ({c.get('unit', '')})")
                lines.append(f"价格: {c.get('price', '--')}  涨跌: {c.get('change', 0):+.2f} ({c.get('change_pct', 0):+.2f}%)")
                hist = c.get("history", [])
                if hist:
                    lines.append("\n| 日期 | 价格 | 涨跌 | 涨跌幅 |")
                    lines.append("|-----|-----|-----|-------|")
                    for h in hist[:10]:
                        lines.append(f"| {h.get('date','')} | {h.get('price','')} | {h.get('change',0):+.2f} | {h.get('change_pct',0):+.2f}% |")
        return "\n".join(lines)

    def _call_industry_list(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_industry_list()
        if not data or not data.get("industries"):
            return "暂无行业板块数据"
        lines = ["# 行业板块列表\n"]
        lines.append(f"共 {data.get('total', 0)} 个行业\n")
        lines.append("| 板块名称 | 涨跌幅 | 总市值 | 换手率 | 涨/跌 |")
        lines.append("|---------|-------|-------|-------|-------|")
        for item in data.get("industries", [])[:30]:
            cap = item.get("total_market_cap", 0)
            cap_str = f"{cap/1e8:.0f}亿" if cap else "--"
            lines.append(f"| {item.get('name','')} | {item.get('change_pct',0):+.2f}% | {cap_str} | {item.get('turnover_rate',0):.2f}% | {item.get('up_count',0)}/{item.get('down_count',0)} |")
        return "\n".join(lines)

    def _call_industry_detail(ticker: str, date: str, p: dict[str, Any]) -> str:
        name = str(p.get("name", ""))
        data = get_industry_detail(name=name)
        if not data:
            return "暂无行业详情数据"
        lines = [f"# {name} 行业详情\n"]
        stocks = data.get("stocks", [])
        if stocks:
            lines.append(f"## 成分股 ({len(stocks)})\n")
            for s in stocks[:20]:
                lines.append(f"- {s}")
        history = data.get("history", [])
        if history:
            lines.append(f"\n## 近期走势\n")
            for h in history[:10]:
                lines.append(f"- {h}")
        return "\n".join(lines)

    def _call_industry_commodity(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_industry_commodity()
        if not data or not data.get("commodities"):
            return "暂无商品数据"
        lines = ["# 商品价格\n"]
        for c in data.get("commodities", []):
            lines.append(f"## {c.get('name', '')} ({c.get('unit', '')})")
            lines.append(f"价格: {c.get('price', '--')}  涨跌: {c.get('change', 0):+.2f} ({c.get('change_pct', 0):+.2f}%)")
            hist = c.get("history", [])
            if hist:
                lines.append("\n| 日期 | 价格 | 涨跌 | 涨跌幅 |")
                lines.append("|-----|-----|-----|-------|")
                for h in hist:
                    lines.append(f"| {h.get('date','')} | {h.get('price','')} | {h.get('change',0):+.2f} | {h.get('change_pct',0):+.2f}% |")
        return "\n".join(lines)

    def _call_macro_overview(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_macro_overview()
        if not data:
            return "暂无宏观数据"
        lines = ["# 宏观分析\n"]
        gdp = data.get("gdp", {})
        if gdp.get("trend"):
            lines.append("## GDP 趋势\n")
            lines.append("| 季度 | GDP(亿元) | 第一产业 | 第二产业 | 第三产业 |")
            lines.append("|-----|---------|---------|---------|--------|")
            for q in gdp["trend"][:10]:
                lines.append(f"| {q.get('quarter','')} | {q.get('gdp',0):.0f} | {q.get('primary',0):.0f} | {q.get('secondary',0):.0f} | {q.get('tertiary',0):.0f} |")
        return "\n".join(lines)

    def _call_macro_gdp(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_macro_gdp()
        if not data or not data.get("trend"):
            return "暂无GDP数据"
        lines = ["# 国内生产总值(GDP)\n"]
        lines.append("## 趋势\n")
        lines.append("| 季度 | GDP(亿元) | 第一产业 | 第二产业 | 第三产业 |")
        lines.append("|-----|---------|---------|---------|--------|")
        for q in data.get("trend", [])[:12]:
            lines.append(f"| {q.get('quarter','')} | {q.get('gdp',0):.0f} | {q.get('primary',0):.0f} | {q.get('secondary',0):.0f} | {q.get('tertiary',0):.0f} |")
        struct = data.get("structure", [])
        if struct:
            lines.append("\n## 产业结构占比\n")
            lines.append("| 季度 | 第一产业% | 第二产业% | 第三产业% |")
            lines.append("|-----|---------|---------|---------|")
            for q in struct[:12]:
                lines.append(f"| {q.get('quarter','')} | {q.get('primary_pct',0):.2f} | {q.get('secondary_pct',0):.2f} | {q.get('tertiary_pct',0):.2f} |")
        return "\n".join(lines)

    def _call_macro_cpi(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_macro_cpi()
        if not data:
            return "暂无CPI数据"
        lines = ["# 消费者物价指数(CPI)\n"]
        monthly = data.get("monthly", [])
        if monthly:
            lines.append("## 月度CPI\n")
            for item in monthly[:15]:
                lines.append(f"- {item}")
        yearly = data.get("yearly", [])
        if yearly:
            lines.append("\n## 年度CPI\n")
            for item in yearly[:10]:
                lines.append(f"- {item}")
        return "\n".join(lines)

    def _call_macro_pmi(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_macro_pmi()
        if not data or not data.get("data"):
            return "暂无PMI数据"
        lines = ["# 采购经理人指数(PMI)\n"]
        for item in data.get("data", [])[:15]:
            lines.append(f"- {item}")
        return "\n".join(lines)

    def _call_stock_info_panel(ticker: str, date: str, p: dict[str, Any]) -> str:
        data = get_stock_info_panel(code=ticker)
        if not data:
            return "暂无个股信息数据"
        lines = ["# 个股信息面板", ""]
        fin = data.get("financial", {})
        if fin:
            lines.append("## 财务摘要")
            lines.append("")
            rev = fin.get("revenue", {})
            if rev:
                yoy = f" 同比{rev['yoy']:+.1f}%" if rev.get("yoy") else ""
                lines.append(f"- 营业总收入：{rev['value']:.2f}亿{yoy}")
            np_ = fin.get("net_profit", {})
            if np_:
                yoy = f" 同比{np_['yoy']:+.1f}%" if np_.get("yoy") else ""
                lines.append(f"- 归母净利润：{np_['value']:.2f}亿{yoy}")
            nr = fin.get("non_recurring", {})
            if nr:
                lines.append(f"- 扣非净利润：{nr['value']:.2f}亿")
            cash = fin.get("cash", {})
            if cash:
                lines.append(f"- 货币资金：{cash['value']:.2f}亿")
        sh = data.get("shareholder", {})
        if sh.get("shareholders"):
            lines.append("")
            lines.append("## 股东变动")
            lines.append("")
            for s in sh["shareholders"][:5]:
                lines.append(f"- {s['name']} {s['change']} ({s['method']})")
        fund = data.get("fund", {})
        if fund.get("funds"):
            lines.append("")
            lines.append(f"## 基金持仓 ({fund['total_funds']}家)")
            lines.append("")
            for f_item in fund["funds"][:5]:
                lines.append(f"- {f_item['name']} 持股{f_item['pct']:.2f}% 市值{f_item['value']/1e8:.2f}亿")
        div = data.get("dividend", {})
        if div.get("dividends"):
            lines.append("")
            lines.append("## 分红")
            lines.append("")
            for d in div["dividends"][:3]:
                lines.append(f"- {d['date']} 派息{d['dividend']}元 {d['status']}")
        return "\n".join(lines)

    def _make_financial(fn: Callable[..., str]) -> Callable[[str, str, dict[str, Any]], str]:
        def _call(ticker: str, date: str, p: dict[str, Any]) -> str:
            return fn(ticker, freq=str(p.get("freq", "quarterly")), curr_date=date)

        return _call

    return {
        "chip_distribution": {"call": _call_chip, "parse": _parse_chip_distribution},
        "dragon_tiger": {"call": _call_dragon, "parse": _parse_dragon_tiger},
        "northbound_flow": {"call": _call_northbound, "parse": _parse_northbound},
        "concept_blocks": {"call": _call_concept, "parse": _parse_concept_blocks},
        "profit_forecast": {"call": _call_profit, "parse": _parse_profit_forecast},
        "lockup_expiry": {"call": _call_lockup, "parse": _parse_lockup_expiry},
        "industry_comparison": {"call": _call_industry, "parse": _parse_industry_comparison},
        "hot_stocks": {"call": _call_hot, "parse": _parse_hot_stocks},
        "insider_transactions": {"call": _call_insider, "parse": _parse_insider_transactions},
        "balance_sheet": {
            "call": _make_financial(get_balance_sheet),
            "parse": _parse_financial_csv,
        },
        "cashflow": {
            "call": _make_financial(get_cashflow),
            "parse": _parse_financial_csv,
        },
        "income_statement": {
            "call": _make_financial(get_income_statement),
            "parse": _parse_financial_csv,
        },
        # Phase 7: new features
        "ipo_declaration": {"call": _call_ipo_decl, "parse": _parse_ipo_declaration},
        "ipo_listing": {"call": _call_ipo_list, "parse": _parse_ipo_listing},
        "margin_detail": {"call": _call_margin_detail, "parse": _parse_margin_detail},
        "margin_market_stat": {"call": _call_margin_stat, "parse": _parse_margin_market_stat},
        "margin_industry": {"call": _call_margin_industry, "parse": _passthrough_parser},
        "investment_calendar": {"call": _call_investment_calendar, "parse": _parse_investment_calendar},
        "seat_activity": {"call": _call_seat_activity, "parse": _parse_seat_activity},
        "stock_activity": {"call": _call_stock_activity, "parse": _parse_stock_activity},
        # Phase 9: new features — cache_ttl per Phase 9 spec §6 (ticket 11):
        # 当日行情类短 TTL，季报类长 TTL；未声明者沿用默认（交易日 4h / 盘后 24h）
        "block_trade_detail": {"call": _call_block_detail, "parse": _parse_block_trade_detail, "cache_ttl": 3600},
        "block_trade_industry": {"call": _call_block_industry, "parse": _parse_block_trade_industry, "cache_ttl": 86400},
        "block_trade_market_stat": {"call": _call_block_market_stat, "parse": _parse_block_trade_market_stat, "cache_ttl": 3600},
        "dividend_bonus": {"call": _call_dividend, "parse": _parse_dividend_bonus, "cache_ttl": 86400},
        "earnings_forecast": {"call": _call_earnings_fc, "parse": _parse_earnings_forecast, "cache_ttl": 86400},
        "earnings_express": {"call": _call_earnings_ex, "parse": _parse_earnings_express, "cache_ttl": 86400},
        "analyst_rating": {"call": _call_analyst, "parse": _parse_analyst_rating, "cache_ttl": 21600},
        # 工单 17 余项: 一致预期（评级汇总+EPS 共识+目标价区间，随研报更新 → 24h）
        "consensus_estimate": {"call": _call_consensus_estimate, "parse": _parse_consensus_estimate, "cache_ttl": 86400},
        "institutional_hold": {"call": _call_inst_hold, "parse": _parse_institutional_hold, "cache_ttl": 259200},
        # Phase 12.01: 板块资金流（东财 datacenter，日频+盘中刷新，当日 1h）
        "industry_fund_flow": {"call": _call_industry_fund_flow, "parse": _parse_board_fund_flow, "cache_ttl": 3600},
        "concept_fund_flow": {"call": _call_concept_fund_flow, "parse": _parse_board_fund_flow, "cache_ttl": 3600},
        # Phase 12.02: 持仓股东（东财 datacenter/F10，实测核实；个股级）
        "holder_num": {"call": _call_holder_num, "parse": _parse_holder_num, "cache_ttl": 86400},
        "free_holders": {"call": _call_free_holders, "parse": _parse_free_holders, "cache_ttl": 259200},
        "holder_increase": {"call": _call_holder_increase, "parse": _parse_holder_increase},
        # Phase 12.03: 公司行动（东财 datacenter，实测核实；回购/质押）
        "pledge_market": {"call": _call_pledge_market, "parse": _parse_pledge_market, "cache_ttl": 86400},
        "pledge_industry": {"call": _call_pledge_industry, "parse": _parse_pledge_industry, "cache_ttl": 86400},
        "pledge_stock": {"call": _call_pledge_stock, "parse": _parse_pledge_stock, "cache_ttl": 86400},
        "buyback": {"call": _call_buyback, "parse": _parse_buyback},
        # Phase 12.06: 可转债列表（东财 datacenter，实测核实）
        "convert_bond_list": {"call": _call_convert_bond_list, "parse": _parse_convert_bond_list, "cache_ttl": 3600},
        # Phase 12.04: 公司公告（东财 np-anotice，实测核实；及时性 → 默认 TTL）
        "stock_notices": {"call": _call_stock_notices, "parse": _parse_stock_notices},
        # Phase 12.05: 研报流（东财 reportapi，实测核实；券商观点 → 默认 TTL）
        "research_reports": {"call": _call_research_reports, "parse": _parse_research_reports},
        "insider_change_chart": {"call": _call_insider_chart, "parse": _passthrough_parser},
        # TongDaXin reference data (market-wide)
        "survey_interaction": {"call": _call_survey_interaction, "parse": _parse_survey_interaction},
        "company_name_changes": {"call": _call_company_name_changes, "parse": _parse_company_name_changes},
        "st_changes": {"call": _call_st_changes, "parse": _parse_st_changes},
        "neeq_abnormal_trade": {"call": _call_neeq_abnormal_trade, "parse": _passthrough_parser},
        "hk_ipo": {"call": _call_hk_ipo, "parse": _parse_hk_ipo},
        "us_ipo": {"call": _call_us_ipo, "parse": _passthrough_parser},
        "futures_position": {"call": _call_futures_position, "parse": _parse_futures_position},
        "market_statistics": {"call": _call_market_statistics, "parse": _parse_market_statistics},
        # Phase 10: TongDaXin 数据菜单新模块
        "fund_purchase": {"call": _call_fund_purchase, "parse": _parse_fund_purchase},
        "fund_announcement": {"call": _call_fund_announcement, "parse": _parse_fund_announcement},
        "fund_scale": {"call": _call_fund_scale, "parse": _parse_fund_scale},
        "fund_open_info": {"call": _call_fund_open_info, "parse": _parse_fund_open_info},
        "industry_chain_categories": {"call": _call_industry_chain_categories, "parse": _parse_industry_chain_categories},
        "industry_chain_chains": {"call": _call_industry_chain_chains, "parse": _parse_industry_chain_chains},
        "industry_chain_overview": {"call": _call_industry_chain_overview, "parse": _parse_industry_chain_overview},
        "industry_list": {"call": _call_industry_list, "parse": _parse_industry_list},
        "industry_detail": {"call": _call_industry_detail, "parse": _parse_industry_detail},
        "industry_commodity": {"call": _call_industry_commodity, "parse": _parse_industry_commodity},
        "industry_data_overview": {"call": _call_industry_data_overview, "parse": _parse_industry_data_overview},
        "macro_gdp": {"call": _call_macro_gdp, "parse": _parse_macro_gdp},
        "macro_cpi": {"call": _call_macro_cpi, "parse": _parse_macro_cpi},
        "macro_pmi": {"call": _call_macro_pmi, "parse": _parse_macro_pmi},
        "macro_overview": {"call": _call_macro_overview, "parse": _passthrough_parser},
        "stock_info_panel": {"call": _call_stock_info_panel, "parse": _passthrough_parser},
    }


# Materialized once at import; the underlying vendor adapters carry their own
# caches/limits so rebuilding per request would only add overhead.
FEATURE_TABLE = _build_feature_table()

# Ticket 11: hand every declared cache_ttl to the cache layer so expiry is
# explicit per feature (Phase 9 spec §6). No declaration → default TTL,
# unchanged. The ohlcv special case is preserved inside the cache layer.
for _feature_name, _feature_entry in FEATURE_TABLE.items():
    _declared_ttl = _feature_entry.get("cache_ttl")
    if _declared_ttl:
        register_feature_ttl(_feature_name, _declared_ttl)


def is_astock_code(ticker: str) -> bool:
    """Mirror of a_stock's A-share rule: exactly 6 digits after normalization."""
    t = ticker.strip().upper()
    for suffix in (".SH", ".SZ", ".BJ", ".SS"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
            break
    for prefix in ("SH", "SZ", "BJ"):
        if t.startswith(prefix):
            t = t[len(prefix):]
            break
    return t.isdigit() and len(t) == 6


class UnknownFeatureError(ValueError):
    """Raised when ``feature`` is not in the dispatch table."""


def run_astock_feature(request: AstockFeatureRequest) -> AstockFeatureResponse:
    """Dispatch one feature call and wrap the result in the envelope.

    Uses unified CacheManager for all caching — no more dual-path.
    """
    entry = FEATURE_TABLE.get(request.feature)
    if entry is None:
        raise UnknownFeatureError(
            f"Unknown feature '{request.feature}'. Available: {sorted(FEATURE_TABLE)}"
        )

    ticker = request.ticker.strip()
    mgr = get_cache(ticker)

    with mgr.fetch(
        feature=request.feature,
        date=request.date,
        source_fn=lambda: entry["call"](ticker, request.date, dict(request.params)),
        convert_box=True,
        params=dict(request.params),
    ) as (raw_md, hit):
        if hit:
            # Cache hit: raw_md is already a dict with {data, raw_md}
            if isinstance(raw_md, dict):
                return AstockFeatureResponse(
                    feature=request.feature,
                    ticker=ticker,
                    date=request.date,
                    data=raw_md.get("data", {}),
                    raw_md=raw_md.get("raw_md", ""),
                )
            # Backward compat: old cache format stored raw_md directly
            return AstockFeatureResponse(
                feature=request.feature,
                ticker=ticker,
                date=request.date,
                data={},
                raw_md=str(raw_md),
            )

        # Cache miss: parse the raw markdown
        data = entry["parse"](raw_md, ticker, request.date, dict(request.params))

        # Store both parsed data and raw markdown in cache
        mgr.set(
            request.feature,
            request.date,
            {"data": data, "raw_md": raw_md},
            params=dict(request.params),
        )

    return AstockFeatureResponse(
        feature=request.feature,
        ticker=ticker,
        date=request.date,
        data=data,
        raw_md=raw_md,
    )
