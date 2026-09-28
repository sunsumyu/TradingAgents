"""市场统计模块 — 沪深交易所市场总貌。

Data source: 上交所/深交所官网统计 (via akshare) + 中国结算投资者统计

通达信「市场统计」菜单对应功能：市场规模统计 / 成交概况 / 投资者情况。

Functions:
    get_market_statistics()  — 沪深交易所市场总貌聚合
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _safe_akshare_call(fn_name: str, **kwargs) -> Any:
    try:
        import akshare as ak
        fn = getattr(ak, fn_name)
        return fn(**kwargs)
    except ImportError:
        logger.warning("akshare not installed; %s unavailable", fn_name)
        return None
    except Exception as e:
        logger.warning("akshare.%s failed: %s", fn_name, e)
        return None


def _yi(val: Any) -> str:
    """数值转亿元字符串（输入为元时使用）。"""
    try:
        return f"{float(val) / 1e8:,.2f}"
    except (ValueError, TypeError):
        return "--"


def _num(val: Any) -> str:
    try:
        f = float(val)
        return f"{f:,.0f}" if f == int(f) else f"{f:,.2f}"
    except (ValueError, TypeError):
        return "--"


def _sse_section(lines: list[str]) -> None:
    """上交所市场规模统计。"""
    df = _safe_akshare_call("stock_sse_summary")
    if df is None or getattr(df, "empty", True):
        lines.append("上交所 | 数据暂不可用")
        return

    try:
        # 行=项目, 列=[股票, 主板, 科创板]
        df = df.set_index("项目")
        stocks = df["股票"] if "股票" in df.columns else df.iloc[:, 0]
        kcb = df.get("科创板")

        def _get(row: str, col) -> str:
            try:
                return _num(stocks[row])
            except (KeyError, TypeError):
                return "--"

        kcb_pe = "--"
        if kcb is not None:
            try:
                kcb_pe = _num(kcb.loc["平均市盈率"])
            except (KeyError, TypeError):
                pass

        lines.append(
            f"  上交所 | {_get('上市股票', '股票')} | {_get('上市公司', '股票')} | "
            f"{_get('总市值', '股票')} | {_get('流通市值', '股票')} | "
            f"{_get('流通股本', '股票')} | {_get('平均市盈率', '股票')} | {kcb_pe}"
        )
    except Exception as exc:
        logger.warning("SSE summary parse failed: %s", exc)
        lines.append("  上交所 | 数据解析失败")


def _szse_section(lines: list[str], date_compact: str) -> None:
    """深交所市场总貌（日期回溯到最近发布日）。"""
    from datetime import timedelta

    df = None
    ref = datetime.strptime(date_compact, "%Y%m%d")
    for offset in range(0, 7):
        probe = (ref - timedelta(days=offset)).strftime("%Y%m%d")
        df = _safe_akshare_call("stock_szse_summary", date=probe)
        if df is not None and not getattr(df, "empty", True):
            break
    if df is None or getattr(df, "empty", True):
        lines.append("  深交所 | 数据暂不可用")
        return

    try:
        stock_row = df[df["证券类别"] == "股票"].iloc[0]
        lines.append(
            f"  深交所 | {_num(stock_row['数量'])} | -- | "
            f"{_yi(stock_row['总市值'])} | {_yi(stock_row['流通市值'])} | "
            f"-- | -- | --"
        )
    except Exception as exc:
        logger.warning("SZSE summary parse failed: %s", exc)
        lines.append("  深交所 | 数据解析失败")


def _deal_section(lines: list[str], date_compact: str) -> None:
    """成交概况 — 品种分类成交金额。"""
    from datetime import timedelta

    lines.append("")
    lines.append("## 成交概况（品种分类）")
    lines.append("")
    lines.append("市场 | 品种 | 数量 | 成交金额(亿)")

    ref = datetime.strptime(date_compact, "%Y%m%d")

    def _probe(fn_name: str):
        for offset in range(0, 7):
            probe = (ref - timedelta(days=offset)).strftime("%Y%m%d")
            df = _safe_akshare_call(fn_name, date=probe)
            if df is not None and not getattr(df, "empty", True):
                return df
        return None

    # 上交所（股票口径）
    sse = _probe("stock_sse_deal_daily")
    if sse is not None and not getattr(sse, "empty", True):
        try:
            row = sse[sse["单日情况"] == "成交金额"].iloc[0]
            lines.append(f"  上交所 | 股票 | -- | {_num(row['股票'])}")
        except Exception as exc:
            logger.warning("SSE deal parse failed: %s", exc)

    # 深交所（股票/基金/债券/期权全品种）
    szse = _probe("stock_szse_summary")
    if szse is not None and not getattr(szse, "empty", True):
        for cat in ("股票", "基金", "债券", "期权"):
            rows = szse[szse["证券类别"] == cat]
            if rows.empty:
                continue
            row = rows.iloc[0]
            lines.append(
                f"  深交所 | {cat} | {_num(row['数量'])} | {_yi(row['成交金额'])}"
            )


def _account_section(lines: list[str]) -> None:
    """投资者情况 — 中国结算月度统计。"""
    df = _safe_akshare_call("stock_account_statistics_em")
    lines.append("")
    lines.append("## 投资者情况（中国结算月度）")
    lines.append("")
    lines.append("月份 | 新增投资者(万) | 期末投资者总量(万) | A股账户(万) | 沪深总市值(亿) | 户均市值(万)")

    if df is None or getattr(df, "empty", True):
        lines.append("  数据暂不可用")
        return

    try:
        latest = df.iloc[-1]
        # 沪深总市值 数据源单位已是亿元
        lines.append(
            f"  {latest['数据日期']} | {_num(latest['新增投资者-数量'])} | "
            f"{_num(latest['期末投资者-总量'])} | {_num(latest['期末投资者-A股账户'])} | "
            f"{_num(latest['沪深总市值'])} | {_num(latest['沪深户均市值'])}"
        )
    except Exception as exc:
        logger.warning("account stats parse failed: %s", exc)
        lines.append("  数据解析失败")


def get_market_statistics(
    curr_date: str | None = None,
    page_size: int = 50,
    page_number: int = 1,
) -> str:
    """获取市场统计 — 沪深交易所市场总貌。

    Args:
        curr_date: 参考日期（用于标题与交易所接口日期），默认今天
        page_size/page_number: 保持接口一致性（本功能为聚合快照，不支持分页）

    Returns:
        Markdown 字符串
    """
    if curr_date is None:
        curr_date = datetime.now().strftime("%Y-%m-%d")

    date_compact = curr_date.replace("-", "")

    lines: list[str] = [
        f"# 市场统计 | {curr_date}",
        "",
        "数据来源: 上交所/深交所官网统计、中国结算",
        "",
        "## 市场规模统计",
        "",
        "交易所 | 上市股票数(只) | 上市公司数(个) | 市价总值(亿) | 流通市值(亿) | 流通股本(亿股) | 平均市盈率 | 科创板平均市盈率",
    ]

    _sse_section(lines)
    _szse_section(lines, date_compact)
    _deal_section(lines, date_compact)
    _account_section(lines)

    return "\n".join(lines)
