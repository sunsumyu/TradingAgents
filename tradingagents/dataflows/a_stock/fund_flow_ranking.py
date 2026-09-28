"""板块资金流报表（Phase 12.01）— 行业/概念主力净流入。

数据源：东财 datacenter-web（已实测核实，2026-09-27）：

* ``RPT_INDUSTRY_FUNDFLOW``  行业板块资金流（约 86 行/交易日，全量 10.8 万行）
* ``RPT_CONCEPT_FUNDFLOW``   概念板块资金流（约 400 行/交易日）

字段（两侧报表同构，均已核验）：
``TRADE_DATE`` / ``BOARD_CODE`` / ``BOARD_NAME`` / ``CHANGE_RATE`` /
``NET_INFLOW``(元) / ``NET_INFLOW_RATIO``(%) / ``SUPERDEAL_NET`` / ``BIGDEAL_NET`` /
``MIDDEAL_NET`` / ``SMALLDEAL_NET``（各级单型净流入，元）/ ``MAX_NETINFLOW_SEC``（领涨股名）。

已验证语法：``filter=(TRADE_DATE<='YYYY-MM-DD')`` + ``sortColumns=TRADE_DATE`` 取
某日（含）前最近交易日的整日数据；等值过滤对非交易日返回 9201 空。

注意：个股资金流排名（push2 clist fid=f62）属盘中实时接口，本模块不含——
该路径生产可用（行情页涨幅榜同通道），但本环境无法核实字段语义，留待工单
13 后续接入。本模块输出为日频报表，走 PG 缓存（Phase 12 新规）。
"""

from __future__ import annotations

from datetime import datetime

from .eastmoney import _eastmoney_datacenter

_REPORTS = {
    "industry": "RPT_INDUSTRY_FUNDFLOW",
    "concept": "RPT_CONCEPT_FUNDFLOW",
}

# 一页必须装下至少一个完整交易日：行业 ~86 行、概念 ~400 行。
_FETCH_PAGE_SIZE = 500


def _fmt_yi(value) -> str:
    """元 → 亿元字符串（保留 2 位；空值返回 -）。"""
    try:
        return f"{float(value) / 1e8:.2f}"
    except (TypeError, ValueError):
        return "-"


def _fmt_pct(value) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def get_board_fund_flow(
    board_type: str,
    curr_date: str | None = None,
    page_size: int = 50,
) -> str:
    """获取行业/概念板块资金流（某交易日的主力净流入排名）。

    Args:
        board_type: "industry"（行业板块）或 "concept"（概念板块）
        curr_date: 参考日期 YYYY-MM-DD；取该日（含）前最近交易日。默认最新交易日。
        page_size: 返回前 N 个板块（按主力净流入降序）

    Returns:
        Markdown 管道表（供 ``_parse_board_fund_flow`` 解析）。
    """
    report = _REPORTS.get(board_type)
    if report is None:
        return f"⚠️ 未知板块类型: {board_type}（支持 industry / concept）"

    filter_str = ""
    if curr_date:
        filter_str = f"(TRADE_DATE<='{curr_date}')"

    rows = _eastmoney_datacenter(
        report,
        filter_str=filter_str,
        page_size=_FETCH_PAGE_SIZE,
        sort_columns="TRADE_DATE",
        sort_types="-1",
    )

    if not rows:
        when = f"≤ {curr_date}" if curr_date else "最新"
        return (
            f"# {'行业' if board_type == 'industry' else '概念'}资金流 | 暂无数据\n\n"
            f"⚠️ 东财 {report} 在 {when} 交易日无数据（可能为非交易日或接口 9701 繁忙，可稍后重试）。"
        )

    # 排序键 TRADE_DATE desc → 取第一页里最新交易日的整日数据
    latest = max(str(r.get("TRADE_DATE", ""))[:10] for r in rows)
    day_rows = [r for r in rows if str(r.get("TRADE_DATE", ""))[:10] == latest]

    def net_inflow(r: dict) -> float:
        try:
            return float(r.get("NET_INFLOW") or 0)
        except (TypeError, ValueError):
            return 0.0

    day_rows.sort(key=net_inflow, reverse=True)
    day_rows = day_rows[: max(1, page_size)]

    label = "行业" if board_type == "industry" else "概念"
    lines = [
        f"# {label}资金流 (主力净流入) | {latest}",
        f"# Source: 东财 datacenter {report}",
        f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "板块 | 涨跌幅% | 主力净流入(亿) | 主力净占比% | 超大单(亿) | 大单(亿) | 中单(亿) | 小单(亿) | 领涨股",
    ]
    for r in day_rows:
        lines.append(
            " | ".join([
                str(r.get("BOARD_NAME", "-")),
                _fmt_pct(r.get("CHANGE_RATE")),
                _fmt_yi(r.get("NET_INFLOW")),
                _fmt_pct(r.get("NET_INFLOW_RATIO")),
                _fmt_yi(r.get("SUPERDEAL_NET")),
                _fmt_yi(r.get("BIGDEAL_NET")),
                _fmt_yi(r.get("MIDDEAL_NET")),
                _fmt_yi(r.get("SMALLDEAL_NET")),
                str(r.get("MAX_NETINFLOW_SEC", "-") or "-"),
            ])
        )
    return "\n".join(lines)
