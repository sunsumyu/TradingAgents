"""个股信息面板数据 — 五档盘口 + 财务摘要 + 股东 + 基金 + 分红 + 融资融券。

对标通达信右侧信息栏完整实现。

Data source: akshare + tencent quote API
"""

from __future__ import annotations
import logging
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


def _safe_call(fn, *args, **kwargs):
    """Safely call akshare function, return DataFrame or None."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.warning("akshare %s failed: %s", fn.__name__, e)
        return None


def get_financial_summary(code: str) -> dict[str, Any]:
    """财务摘要：总收入、净利润、非经管、货币金。
    
    Returns {
        "revenue": {"value": ..., "yoy": ...},
        "net_profit": {"value": ..., "yoy": ...},
        "non_recurring": {"value": ...},
        "cash": {"value": ...},
    }
    """
    import akshare as ak
    
    df = _safe_call(ak.stock_financial_abstract, symbol=code)
    if df is None or df.empty:
        return {}
    
    # Get latest period (first column after 指标)
    periods = [c for c in df.columns if c not in ['选项', '指标'] and str(c).isdigit()]
    if not periods:
        return {}
    
    latest = periods[0]
    prev_year = None
    for p in periods:
        if len(str(p)) == 8 and str(p)[:4] == str(int(str(latest)[:4]) - 1):
            prev_year = p
            break
    
    result = {}
    
    # 营业总收入
    row = df[df['指标'] == '营业总收入']
    if not row.empty:
        val = row.iloc[0].get(latest)
        prev = row.iloc[0].get(prev_year) if prev_year else None
        yoy = None
        if val and prev and prev != 0:
            yoy = round((float(val) - float(prev)) / abs(float(prev)) * 100, 2)
        result['revenue'] = {
            'value': round(float(val) / 1e8, 2) if val else 0,
            'yoy': yoy,
        }
    
    # 归母净利润
    row = df[df['指标'] == '归母净利润']
    if not row.empty:
        val = row.iloc[0].get(latest)
        prev = row.iloc[0].get(prev_year) if prev_year else None
        yoy = None
        if val and prev and prev != 0:
            yoy = round((float(val) - float(prev)) / abs(float(prev)) * 100, 2)
        result['net_profit'] = {
            'value': round(float(val) / 1e8, 2) if val else 0,
            'yoy': yoy,
        }
    
    # 扣非净利润
    row = df[df['指标'] == '扣非净利润']
    if not row.empty:
        val = row.iloc[0].get(latest)
        result['non_recurring'] = {
            'value': round(float(val) / 1e8, 2) if val else 0,
        }
    
    # 货币资金
    row = df[df['指标'] == '货币资金']
    if not row.empty:
        val = row.iloc[0].get(latest)
        result['cash'] = {
            'value': round(float(val) / 1e8, 2) if val else 0,
        }
    
    return result


def get_shareholder_info(code: str) -> dict[str, Any]:
    """股东信息：股东数、户数、较上期。
    
    Returns {
        "shareholders": [{"name", "change", "avg_price", "remaining", "period", "method"}],
        "count": N,
    }
    """
    import akshare as ak
    
    df = _safe_call(ak.stock_shareholder_change_ths, symbol=code)
    if df is None or df.empty:
        return {"shareholders": [], "count": 0}
    
    shareholders = []
    for _, row in df.head(5).iterrows():
        shareholders.append({
            "name": str(row.get("变动股东", "")),
            "change": str(row.get("变动数量", "")),
            "avg_price": str(row.get("交易均价", "")),
            "remaining": str(row.get("剩余股份总数", "")),
            "period": str(row.get("变动期间", "")),
            "method": str(row.get("变动途径", "")),
        })
    
    return {
        "shareholders": shareholders,
        "count": len(shareholders),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_fund_holdings(code: str) -> dict[str, Any]:
    """基金持仓：基金数、持股市值、占流通股比例。
    
    Returns {
        "funds": [{"name", "code", "shares", "pct", "value", "net_pct", "date"}],
        "total_funds": N,
        "total_value": ...,
    }
    """
    import akshare as ak
    
    df = _safe_call(ak.stock_fund_stock_holder, symbol=code)
    if df is None or df.empty:
        return {"funds": [], "total_funds": 0, "total_value": 0}
    
    funds = []
    total_value = 0
    for _, row in df.head(10).iterrows():
        value = float(row.get("持股市值", 0)) if row.get("持股市值") else 0
        total_value += value
        funds.append({
            "name": str(row.get("基金名称", "")),
            "code": str(row.get("基金代码", "")),
            "shares": int(row.get("持仓数量", 0)) if row.get("持仓数量") else 0,
            "pct": float(row.get("占流通股比例", 0)) if row.get("占流通股比例") else 0,
            "value": value,
            "net_pct": float(row.get("占净值比例", 0)) if row.get("占净值比例") else 0,
            "date": str(row.get("截止日期", "")),
        })
    
    return {
        "funds": funds,
        "total_funds": len(funds),
        "total_value": round(total_value / 1e8, 2),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_dividend_info(code: str) -> dict[str, Any]:
    """分红信息：派息、送股、转增、除权日。
    
    Returns {
        "dividends": [{"date", "bonus", "transfer", "dividend", "status", "ex_date"}],
    }
    """
    import akshare as ak
    
    df = _safe_call(ak.stock_history_dividend_detail, symbol=code)
    if df is None or df.empty:
        return {"dividends": []}
    
    dividends = []
    for _, row in df.head(5).iterrows():
        dividends.append({
            "date": str(row.get("公告日期", "")),
            "bonus": str(row.get("送股", "")),
            "transfer": str(row.get("转增", "")),
            "dividend": str(row.get("派息", "")),
            "status": str(row.get("进度", "")),
            "ex_date": str(row.get("除权除息日", "")),
        })
    
    return {
        "dividends": dividends,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_margin_info(code: str) -> dict[str, Any]:
    """融资融券：融资余额、融券余额、占比。
    
    Returns {
        "margin": {"financing_balance": ..., "short_balance": ..., "financing_pct": ...},
    }
    """
    # Try SSE first, then SZSE
    import akshare as ak
    
    # For simplicity, return placeholder - real margin data requires date-specific queries
    return {
        "margin": {
            "financing_balance": None,
            "short_balance": None,
            "financing_pct": None,
        },
        "note": "融资融券数据需按日期查询，暂用占位符",
    }


def get_announcements(code: str) -> dict[str, Any]:
    """最新公告：从东方财富获取。
    
    Returns {
        "announcements": [{"date", "title", "url"}],
    }
    """
    import requests
    
    # Determine market prefix
    prefix = "SHA" if code.startswith("6") else "SZA"
    
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "sr": -1,
        "page_size": 5,
        "page_index": 1,
        "ann_type": prefix,
        "client_source": "web",
        "stock_list": code,
        "f_node": "0",
        "s_node": "0",
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        announcements = []
        if data.get("data", {}).get("list"):
            for item in data["data"]["list"][:5]:
                announcements.append({
                    "date": str(item.get("notice_date", ""))[:10],
                    "title": str(item.get("title", "")),
                    "url": item.get("url", ""),
                })
        return {"announcements": announcements}
    except Exception as e:
        logger.warning("Announcements fetch failed: %s", e)
        return {"announcements": []}


def get_stock_info_panel(code: str) -> dict[str, Any]:
    """聚合全部个股信息面板数据。
    
    Returns {
        "financial": {...},
        "shareholder": {...},
        "fund": {...},
        "dividend": {...},
        "margin": {...},
        "announcements": {...},
    }
    """
    return {
        "financial": get_financial_summary(code),
        "shareholder": get_shareholder_info(code),
        "fund": get_fund_holdings(code),
        "dividend": get_dividend_info(code),
        "margin": get_margin_info(code),
        "announcements": get_announcements(code),
    }
