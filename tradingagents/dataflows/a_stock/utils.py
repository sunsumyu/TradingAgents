"""Shared utilities for A-stock data vendors.

Ticker normalization, market detection, date helpers, and common constants.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import re

import pandas as pd

from ..errors import NoMarketDataError
from ..utils import safe_ticker_component

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_HEADERS = {"User-Agent": _UA}

# A 股市场时区
_MARKET_TZ = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# Ticker format & market detection
# ---------------------------------------------------------------------------

def get_prefix(code: str) -> str:
    """6-digit A-stock code -> market prefix for Tencent API.

    The 92 prefix must be checked before the leading-9 rule: the Beijing Stock
    Exchange started issuing 920xxx codes for new listings in October 2024, and
    a bare ``startswith("9")`` routes them to Shanghai, where the Tencent quote
    endpoint returns an empty payload (issue #85).  Only 900xxx (Shanghai B
    shares) legitimately belongs to ``sh``.
    """
    if code.startswith("92"):
        return "bj"
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith("8"):
        return "bj"
    return "sz"


def reject_non_a_share(original: str, code: str) -> None:
    """港股/美股代码走到 A 股数据层时当场报错，而不是拿去查 A 股（#43）。"""
    if code.isdigit() and len(code) == 6:
        return
    upper = original.strip().upper()
    if upper.endswith(".HK") or (code.isdigit() and len(code) in (4, 5)):
        raise ValueError(
            f"'{original}' 是港股代码。本数据层只支持 A 股（6 位数字代码，"
            f"如 600519 / 000001）。港股数据请用姊妹项目 global-stock-data，"
            f"多 Agent 港股分析仍在 roadmap（issue #43）。"
        )
    if code and not code.isdigit():
        raise ValueError(
            f"'{original}' 不是 A 股代码。本数据层只支持 A 股 6 位数字代码"
            f"（如 600519）；美股/港股请用姊妹项目 global-stock-data。"
        )
    raise ValueError(
        f"'{original}' 不是有效的 A 股代码：A 股代码恒为 6 位数字（如 600519），"
        f"这里解析出的是 '{code}'。"
    )


def normalize_ticker(symbol: str) -> str:
    """Strip exchange prefix/suffix, return pure 6-digit code.

    Handles: '688017', 'SH688017', '688017.SH', 'sh688017', '600519.SS'

    非 A 股代码（港股 `00700` / `0700.HK`、美股 `AAPL`）会直接报错，不再原样
    放行去查 A 股数据源（#43）。
    """
    s = symbol.strip().upper()
    for suffix in (".SH", ".SZ", ".BJ", ".SS"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    for prefix in ("SH", "SZ", "BJ"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    code = safe_ticker_component(s)
    reject_non_a_share(symbol, code)
    return code


# ---------------------------------------------------------------------------
# Stock name <-> code mapping (cached)
# ---------------------------------------------------------------------------

_name_to_code: dict[str, str] | None = None
_code_to_name: dict[str, str] | None = None


def _build_name_code_map() -> tuple[dict[str, str], dict[str, str]]:
    """Build name→code and code→name maps via mootdx (both SH & SZ markets)."""
    global _name_to_code, _code_to_name
    if _name_to_code is not None:
        return _name_to_code, _code_to_name

    from .mootdx_client import mootdx_call

    n2c: dict[str, str] = {}
    c2n: dict[str, str] = {}

    try:
        for market in (0, 1):  # 0=SZ, 1=SH
            stocks = mootdx_call("stocks", market=market)
            if stocks is None or stocks.empty:
                continue
            for _, row in stocks.iterrows():
                code = str(row["code"]).strip()
                name = str(row["name"]).strip()
                if not re.match(r"^[036]\d{5}$", code):
                    continue
                clean_name = name.replace(" ", "").replace("\u3000", "")
                n2c[clean_name] = code
                c2n[code] = clean_name
    except Exception as e:
        raise ValueError(
            "无法通过 mootdx 解析股票名称（通达信服务暂时不可达）：%s。"
            "请稍后重试，或直接输入 6 位股票代码。" % e
        ) from e

    _name_to_code = n2c
    _code_to_name = c2n
    logger.info("Built stock name-code map: %d entries", len(n2c))
    return _name_to_code, _code_to_name


def resolve_ticker(user_input: str) -> str:
    """Resolve user input (code or Chinese name) to a 6-digit A-stock code.

    Accepts: '600379', 'SH600379', '600379.SH', '宝光股份'
    Returns: '600379'
    Raises: ValueError if not resolvable.
    """
    s = user_input.strip()
    if not s:
        raise ValueError("输入不能为空")

    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in s)

    if not has_chinese:
        return normalize_ticker(s)

    clean = s.replace(" ", "").replace("\u3000", "")
    n2c, _ = _build_name_code_map()

    if clean in n2c:
        return n2c[clean]

    matches = {name: code for name, code in n2c.items() if clean in name}
    if len(matches) == 1:
        return next(iter(matches.values()))
    if len(matches) > 1:
        examples = ", ".join(f"{n}({c})" for n, c in list(matches.items())[:5])
        raise ValueError(f"'{s}' 匹配到多只股票: {examples}，请输入完整名称或代码")

    raise ValueError(
        f"找不到股票 '{s}'。ticker 参数只接受 6 位股票代码（如 '600519'）"
        f"或完整股票名称（如 '贵州茅台'）；行业/概念/板块名（如 '游戏'）不是"
        f"有效的股票标识。请改用目标个股的 6 位股票代码重试。"
    )


# ---------------------------------------------------------------------------
# Point-in-time helpers
# ---------------------------------------------------------------------------

def market_today() -> date:
    """A 股市场当前日期（Asia/Shanghai），与主机时区无关。"""
    return datetime.now(_MARKET_TZ).date()


def is_historical(curr_date) -> bool:
    """分析日期是否早于市场当天。"""
    if not curr_date:
        return False
    try:
        return (
            datetime.strptime(str(curr_date)[:10], "%Y-%m-%d").date()
            < market_today()
        )
    except ValueError:
        return False


def snapshot_notice(curr_date: str, what: str) -> str:
    """实时快照被用在历史日期上时，在正文顶部明说。"""
    return (
        f"⚠️ 未来函数警告：以下{what}是**此刻的实时快照**，不是 {curr_date} 当天的值。"
        f"本数据源不提供历史时点数据。在复盘历史日期时，**不得**把这些数字当作"
        f"{curr_date} 当天已知的事实，也不要据此推断当时的判断。\n"
    )


# ---------------------------------------------------------------------------
# OHLCV date normalization helpers
# ---------------------------------------------------------------------------

def _normalize_ohlcv_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OHLCV Date values to daily granularity."""
    if df is None or df.empty or "Date" not in df.columns:
        return df
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()
    return df.dropna(subset=["Date"])


def _needs_sina_supplement(df: pd.DataFrame, target_date: str | None) -> bool:
    """True when mootdx/cache data is older than the requested cutoff date."""
    if not target_date:
        return False
    last_date = _last_ohlcv_date(df)
    if last_date is None:
        return True
    target = pd.to_datetime(target_date).normalize()
    return last_date < target


def _last_ohlcv_date(df: pd.DataFrame) -> pd.Timestamp | None:
    """Return the latest OHLCV Date in a normalized dataframe."""
    if df is None or df.empty or "Date" not in df.columns:
        return None
    dates = pd.to_datetime(df["Date"], errors="coerce")
    if dates.dropna().empty:
        return None
    return dates.max().normalize()


def _merge_ohlcv(primary: pd.DataFrame, supplement: pd.DataFrame) -> pd.DataFrame:
    """Merge OHLCV frames, preferring supplement rows on duplicate dates."""
    frames = [frame for frame in (primary, supplement) if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    combined = pd.concat(frames, ignore_index=True)
    combined = _normalize_ohlcv_dates(combined)
    combined = combined.drop_duplicates(subset=["Date"], keep="last")
    combined = combined.sort_values("Date").reset_index(drop=True)
    return combined
