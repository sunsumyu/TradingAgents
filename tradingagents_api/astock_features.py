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

from tradingagents.data_cache import cached_fetch_raw

logger = logging.getLogger(__name__)


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

    Line format:
      002084 海鸥住工: +10.115% 换手0.52% 成交额1593 大单净量0.35 | 控制权拟变更+装配式厨卫+越南制造
    """
    import re

    def _f(text: str) -> float | None:
        try:
            return float(text.replace(",", "").strip())
        except (ValueError, TypeError):
            return None

    items: list[dict[str, Any]] = []
    total = 0

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
        "industry_comparison": {"call": _call_industry, "parse": _passthrough_parser},
        "hot_stocks": {"call": _call_hot, "parse": _parse_hot_stocks},
        "insider_transactions": {"call": _call_insider, "parse": _passthrough_parser},
        "balance_sheet": {
            "call": _make_financial(get_balance_sheet),
            "parse": _passthrough_parser,
        },
        "cashflow": {
            "call": _make_financial(get_cashflow),
            "parse": _passthrough_parser,
        },
        "income_statement": {
            "call": _make_financial(get_income_statement),
            "parse": _passthrough_parser,
        },
    }


# Materialized once at import; the underlying vendor adapters carry their own
# caches/limits so rebuilding per request would only add overhead.
FEATURE_TABLE = _build_feature_table()


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

    Backend ValueError (non-A-share code etc.) propagates to the route,
    which maps it to HTTP 400. Vendor/network failures inside the backend
    functions are already caught there and returned *as markdown*, so they
    reach the GUI via raw_md instead of a 500 — deliberate: the panel can
    still render the failure text.
    """
    entry = FEATURE_TABLE.get(request.feature)
    if entry is None:
        raise UnknownFeatureError(
            f"Unknown feature '{request.feature}'. Available: {sorted(FEATURE_TABLE)}"
        )

    # ── Check data cache first ────────────────────────────────────────────
    ticker = request.ticker.strip()
    with cached_fetch_raw(ticker, "astock_feature", feature=request.feature,
                          ticker=ticker, date=request.date,
                          params=dict(request.params)) as ctx:
        if ctx.hit:
            return AstockFeatureResponse(
                feature=request.feature,
                ticker=ticker,
                date=request.date,
                data=ctx.value.get("data", {}),
                raw_md=ctx.value.get("raw_md", ""),
            )

        md = entry["call"](ticker, request.date, dict(request.params))
        data = entry["parse"](md, ticker, request.date, dict(request.params))

        # ── Store in cache ────────────────────────────────────────────────────
        ctx.store({"data": data, "raw_md": md})

    return AstockFeatureResponse(
        feature=request.feature,
        ticker=ticker,
        date=request.date,
        data=data,
        raw_md=md,
    )
