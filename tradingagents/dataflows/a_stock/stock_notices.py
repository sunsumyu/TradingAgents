"""公司公告（Phase 12.04）— 东财 np-anotice 个股公告。

数据源（2026-09-27 实测核实）：np-anotice-stock.eastmoney.com/api/security/ann
带 ``stock_list=<code>`` 参数做个股过滤（600519 三条全部命中同一股票，
市场参数 ``codes`` 不过滤——实测返回的是全市场最新公告）。

返回字段：``notice_date`` / ``title`` / ``codes[].stock_code,short_name`` /
``columns[].column_name``（公告分类，如 业绩说明会/首发上市公告书）。

公告分类树（2026-09-28 实测，源：data.eastmoney.com/notices/ 页面
``#filter_f_node`` / ``#filter_s_node`` 过滤器定义）：

* 一级 ``f_node``：0 全部 / 1 财务报告 / 2 融资公告 / 3 风险提示 /
  4 信息变更 / 5 重大事项 / 6 资产重组 / 7 持股变动
* 二级 ``s_node``：0 全部 / 1 定期报告 / 2 新股发行 / 3 增发 / 4 配股 /
  5 业绩预告 / 6 业绩快报 / 7 重大合同 / 8 投资相关 / 9 股权激励 /
  10 要约收购 / 11 吸收合并 / 12 回购 / 13 利润分配
* 注意：**股东大会/关联交易不在东财公告树的过滤节点中**（仅作为
  column_name 标签出现）；组合过滤 e2e 验证通过
  （600519: f1s1 定期报告 5 条、f1s5 业绩预告 1 条、f7s0 持股变动 5 条、
  f5s7 重大合同 0 条——茅台无此类公告）。

公告及时性强 → 走默认缓存 TTL（交易日 4h/盘后 24h）。
"""

from __future__ import annotations

from datetime import datetime

from .eastmoney_client import _np_notice_get
from .utils import normalize_ticker


def get_stock_notices(
    ticker: str,
    page_size: int = 30,
    f_node: int = 0,
    s_node: int = 0,
) -> str:
    """个股公告列表（最新在前），可按公告分类过滤。

    Args:
        ticker: 6 位 A 股代码
        page_size: 返回条数（默认 30）
        f_node: 一级分类节点（0=全部，见模块 docstring 分类树）
        s_node: 二级分类节点（0=全部；需与 f_node 组合使用）
    """
    code = normalize_ticker(ticker)
    d = _np_notice_get(params={
        "sr": "-1",
        "page_size": str(max(1, page_size)),
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "f_node": str(f_node),
        "s_node": str(s_node),
        "stock_list": code,
    })
    items = ((d or {}).get("data") or {}).get("list") or []
    if not items:
        filtered = "（按分类 f_node={} s_node={} 过滤）".format(f_node, s_node) if f_node or s_node else ""
        return f"# 公司公告 | {code}\n\n⚠️ 暂无公告数据{filtered}（可稍后重试）。"

    lines = []
    for it in items:
        title = str(it.get("title", "-") or "-").replace("|", "／").strip()
        date = str(it.get("notice_date", "-") or "-")[:10]
        cols = it.get("columns") or []
        cat = str(cols[0].get("column_name", "-") if cols else "-") or "-"
        cat = cat.replace("|", "／")
        lines.append(f"{date} | {cat} | {title}")

    return "\n".join([
        f"# 公司公告 | {code}",
        "# Source: 东财 np-anotice（个股公告）",
        f"# Retrieved: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "公告日 | 分类 | 标题",
        *lines,
    ])
