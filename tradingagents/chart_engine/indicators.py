"""Technical indicator definitions, computation engine, and signal detection.

This module provides:
- IndicatorDef: declarative definition for each indicator (name, params, ranges)
- INDICATOR_LIBRARY: registry of 25+ built-in indicators
- IndicatorComputer: compute indicators from OHLCV data
- Signal detection: generate buy/sell signals from indicator values

All computation operates on pandas DataFrames with columns:
``open``, ``high``, ``low``, ``close``, ``volume``.

The indicator library follows TDX (通达信) naming conventions where possible.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════════════════════════════════


class SignalType(Enum):
    """Trade signal direction."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """A trade signal produced by indicator analysis."""

    type: SignalType
    strength: float  # 0–100
    reason: str
    timestamp: float | None = None


@dataclass
class IndicatorDef:
    """Declarative definition for a single technical indicator."""

    name: str  # Chinese display name
    category: str  # "overlay" | "oscillator" | "volume"
    params: dict[str, Any]  # default parameter values
    param_ranges: dict[str, tuple[int, int]]  # min/max for each param
    description: str  # one-line description


@dataclass
class IndicatorResult:
    """Result of computing one indicator on a dataset."""

    name: str
    params: dict[str, Any]
    data: dict[str, list[float | None]]  # series_name → values
    signals: list[Signal] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Indicator library — 25+ indicators matching TDX conventions
# ═══════════════════════════════════════════════════════════════════════════════

INDICATOR_LIBRARY: dict[str, IndicatorDef] = {
    # ── Overlay (主图叠加) ─────────────────────────────────────────────────
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
        params={"period": 20, "std_dev": 2.0},
        param_ranges={"period": (5, 100), "std_dev": (1, 4)},
        description="布林带通道 (中轨/上轨/下轨)",
    ),
    "SAR": IndicatorDef(
        name="抛物线转向",
        category="overlay",
        params={"af_start": 0.02, "af_step": 0.02, "af_max": 0.2},
        param_ranges={
            "af_start": (1, 10),
            "af_step": (1, 10),
            "af_max": (10, 50),
        },
        description="抛物线转向指标 (SAR)",
    ),
    "ATR": IndicatorDef(
        name="平均真实波幅",
        category="overlay",
        params={"period": 14},
        param_ranges={"period": (2, 100)},
        description="平均真实波幅 (ATR)",
    ),

    # ── Oscillator (副图振荡) ──────────────────────────────────────────────
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
        description="相对强弱指数 (RSI)",
    ),
    "KDJ": IndicatorDef(
        name="随机指标",
        category="oscillator",
        params={"k_period": 9, "d_period": 3, "j_period": 3},
        param_ranges={
            "k_period": (2, 50),
            "d_period": (2, 20),
            "j_period": (2, 20),
        },
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
        description="商品通道指数 (CCI)",
    ),
    "DMI": IndicatorDef(
        name="趋向指标",
        category="oscillator",
        params={"period": 14},
        param_ranges={"period": (5, 100)},
        description="趋向指标 DMI (±DI, ADX, ADXR)",
    ),
    "TRIX": IndicatorDef(
        name="三重指数平滑移动平均",
        category="oscillator",
        params={"period": 12},
        param_ranges={"period": (5, 50)},
        description="三重指数平滑移动平均 (TRIX)",
    ),
    "DMA": IndicatorDef(
        name="平行线差指标",
        category="oscillator",
        params={"short_period": 10, "long_period": 50},
        param_ranges={"short_period": (2, 50), "long_period": (10, 200)},
        description="平行线差指标 (DMA)",
    ),
    "ROC": IndicatorDef(
        name="变动率指标",
        category="oscillator",
        params={"period": 12},
        param_ranges={"period": (2, 100)},
        description="价格变动率 (ROC)",
    ),
    "MTM": IndicatorDef(
        name="动量指标",
        category="oscillator",
        params={"period": 12},
        param_ranges={"period": (2, 100)},
        description="动量指标 (MTM)",
    ),
    "BIAS": IndicatorDef(
        name="乖离率",
        category="oscillator",
        params={"period": 20},
        param_ranges={"period": (2, 100)},
        description="乖离率 (BIAS)",
    ),
    "ASI": IndicatorDef(
        name="振动升降指标",
        category="oscillator",
        params={"period": 26},
        param_ranges={"period": (5, 50)},
        description="振动升降指标 (ASI)",
    ),
    "EMV": IndicatorDef(
        name="简易波动指标",
        category="oscillator",
        params={"period": 14},
        param_ranges={"period": (5, 50)},
        description="简易波动指标 (EMV)",
    ),
    "ARBR": IndicatorDef(
        name="人气意愿指标",
        category="oscillator",
        params={"period": 26},
        param_ranges={"period": (5, 50)},
        description="人气意愿指标 (AR/BR)",
    ),
    "CR": IndicatorDef(
        name="能量指标",
        category="oscillator",
        params={"period": 26},
        param_ranges={"period": (5, 50)},
        description="能量指标 (CR)",
    ),
    "DMIADX": IndicatorDef(
        name="ADX趋势强度",
        category="oscillator",
        params={"period": 14},
        param_ranges={"period": (5, 100)},
        description="平均趋向指数 (ADX)",
    ),

    # ── Volume (成交量) ────────────────────────────────────────────────────
    "VR": IndicatorDef(
        name="成交量变异率",
        category="volume",
        params={"period": 26},
        param_ranges={"period": (5, 50)},
        description="成交量变异率 (VR)",
    ),
    "OBV": IndicatorDef(
        name="能量潮",
        category="volume",
        params={},
        param_ranges={},
        description="能量潮指标 (OBV)",
    ),
    "VWAP": IndicatorDef(
        name="成交量加权平均价",
        category="volume",
        params={},
        param_ranges={},
        description="成交量加权平均价 (VWAP)",
    ),
    "MV": IndicatorDef(
        name="成交量均线",
        category="volume",
        params={"period": 20},
        param_ranges={"period": (2, 100)},
        description="成交量移动平均线",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Indicator computation helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=period, min_periods=1).mean()


def _ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=period, adjust=False).mean()


def _tr(df: pd.DataFrame) -> pd.Series:
    """True Range."""
    h_l = df["high"] - df["low"]
    h_pc = (df["high"] - df["close"].shift(1)).abs()
    l_pc = (df["low"] - df["close"].shift(1)).abs()
    return pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)


# ═══════════════════════════════════════════════════════════════════════════════
# Individual indicator functions
# ═══════════════════════════════════════════════════════════════════════════════


def _compute_ma(df: pd.DataFrame, period: int) -> dict[str, list]:
    ma = _sma(df["close"], period)
    return {"ma": ma.tolist()}


def _compute_ema(df: pd.DataFrame, period: int) -> dict[str, list]:
    ema = _ema(df["close"], period)
    return {"ema": ema.tolist()}


def _compute_boll(
    df: pd.DataFrame, period: int, std_dev: float
) -> dict[str, list]:
    mid = _sma(df["close"], period)
    std = df["close"].rolling(window=period, min_periods=1).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return {
        "upper": upper.tolist(),
        "mid": mid.tolist(),
        "lower": lower.tolist(),
    }


def _compute_sar(
    df: pd.DataFrame, af_start: float, af_step: float, af_max: float
) -> dict[str, list]:
    """Parabolic SAR — TDX style.

    af_start/af_step/af_max are passed as integers (×100) from param_ranges,
    so we divide by 1000 to get the actual AF values (0.02, 0.02, 0.2).
    """
    af_start_real = af_start / 1000
    af_step_real = af_step / 1000
    af_max_real = af_max / 1000

    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(close)

    sar = np.zeros(n)
    trend = 1  # 1 = up, -1 = down
    af = af_start_real
    ep = high[0]
    sar[0] = low[0]

    for i in range(1, n):
        prev_sar = sar[i - 1]
        if trend == 1:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = min(sar[i], low[i - 1])
            if i >= 2:
                sar[i] = min(sar[i], low[i - 2])
            if low[i] < sar[i]:
                trend = -1
                sar[i] = ep
                ep = low[i]
                af = af_start_real
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_step_real, af_max_real)
        else:
            sar[i] = prev_sar + af * (ep - prev_sar)
            sar[i] = max(sar[i], high[i - 1])
            if i >= 2:
                sar[i] = max(sar[i], high[i - 2])
            if high[i] > sar[i]:
                trend = 1
                sar[i] = ep
                ep = high[i]
                af = af_start_real
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_step_real, af_max_real)

    return {"sar": sar.tolist()}


def _compute_atr(df: pd.DataFrame, period: int) -> dict[str, list]:
    """Average True Range (ATR)."""
    tr = _tr(df)
    atr = _ema(tr, period)
    return {"atr": atr.tolist()}


def _compute_macd(
    df: pd.DataFrame, fast: int, slow: int, signal: int
) -> dict[str, list]:
    ema_fast = _ema(df["close"], fast)
    ema_slow = _ema(df["close"], slow)
    dif = ema_fast - ema_slow
    dea = _ema(dif, signal)
    macd_hist = 2 * (dif - dea)
    return {
        "dif": dif.tolist(),
        "dea": dea.tolist(),
        "macd": macd_hist.tolist(),
    }


def _compute_rsi(df: pd.DataFrame, period: int) -> dict[str, list]:
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = _ema(gain, period)
    avg_loss = _ema(loss, period)
    # When avg_loss is 0, RSI = 100 (all gains); when avg_gain is 0, RSI = 0
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - 100 / (1 + rs)
    return {"rsi": rsi.tolist()}


def _compute_kdj(
    df: pd.DataFrame, k_period: int, d_period: int, j_period: int
) -> dict[str, list]:
    low_min = df["low"].rolling(window=k_period, min_periods=1).min()
    high_max = df["high"].rolling(window=k_period, min_periods=1).max()
    rsv = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    rsv = rsv.fillna(50)

    k = pd.Series(np.zeros(len(df)), index=df.index)
    d = pd.Series(np.zeros(len(df)), index=df.index)
    k.iloc[0] = 50
    d.iloc[0] = 50

    for i in range(1, len(df)):
        k.iloc[i] = (2 / 3) * k.iloc[i - 1] + (1 / 3) * rsv.iloc[i]
        d.iloc[i] = (2 / 3) * d.iloc[i - 1] + (1 / 3) * k.iloc[i]

    j = 3 * k - 2 * d
    return {"k": k.tolist(), "d": d.tolist(), "j": j.tolist()}


def _compute_wr(df: pd.DataFrame, period: int) -> dict[str, list]:
    high_max = df["high"].rolling(window=period, min_periods=1).max()
    low_min = df["low"].rolling(window=period, min_periods=1).min()
    wr = -100 * (high_max - df["close"]) / (high_max - low_min).replace(0, np.nan)
    return {"wr": wr.tolist()}


def _compute_cci(df: pd.DataFrame, period: int) -> dict[str, list]:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    ma_tp = _sma(tp, period)
    md = tp.rolling(window=period, min_periods=1).apply(
        lambda x: np.abs(x - x.mean()).mean(), raw=True
    )
    cci = (tp - ma_tp) / (0.015 * md).replace(0, np.nan)
    return {"cci": cci.tolist()}


def _compute_dmi(df: pd.DataFrame, period: int) -> dict[str, list]:
    tr = _tr(df)
    atr = _ema(tr, period)

    up_move = df["high"] - df["high"].shift(1)
    down_move = df["low"].shift(1) - df["low"]

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0), index=df.index)

    plus_di = 100 * _ema(plus_dm, period) / atr.replace(0, np.nan)
    minus_di = 100 * _ema(minus_dm, period) / atr.replace(0, np.nan)

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = _ema(dx, period)
    adxr = (adx + adx.shift(period)) / 2

    return {
        "plus_di": plus_di.tolist(),
        "minus_di": minus_di.tolist(),
        "adx": adx.tolist(),
        "adxr": adxr.tolist(),
    }


def _compute_trix(df: pd.DataFrame, period: int) -> dict[str, list]:
    ema1 = _ema(df["close"], period)
    ema2 = _ema(ema1, period)
    ema3 = _ema(ema2, period)
    trix = ema3.pct_change() * 100
    matrix = _sma(trix, 9)
    return {"trix": trix.tolist(), "matrix": matrix.tolist()}


def _compute_dma(df: pd.DataFrame, short_period: int, long_period: int) -> dict[str, list]:
    pdd = _sma(df["close"], short_period) - _sma(df["close"], long_period)
    ama = _sma(pdd, 10)
    return {"pdd": pdd.tolist(), "ama": ama.tolist()}


def _compute_roc(df: pd.DataFrame, period: int) -> dict[str, list]:
    roc = df["close"].pct_change(periods=period) * 100
    maroc = _sma(roc, 9)
    return {"roc": roc.tolist(), "maroc": maroc.tolist()}


def _compute_mtm(df: pd.DataFrame, period: int) -> dict[str, list]:
    mtm = df["close"] - df["close"].shift(period)
    mamtm = _sma(mtm, 9)
    return {"mtm": mtm.tolist(), "mamtm": mamtm.tolist()}


def _compute_bias(df: pd.DataFrame, period: int) -> dict[str, list]:
    ma = _sma(df["close"], period)
    bias = (df["close"] - ma) / ma * 100
    return {"bias": bias.tolist()}


def _compute_asi(df: pd.DataFrame, period: int) -> dict[str, list]:
    """Simplified ASI (Accumulation Swing Index)."""
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values
    n = len(c)
    si = np.zeros(n)

    for i in range(1, n):
        r1 = abs(h[i] - c[i - 1])
        r2 = abs(l[i] - c[i - 1])
        r3 = abs(h[i] - l[i])
        r4 = abs(c[i - 1] - o[i - 1])

        if r1 >= r2 and r1 >= r3:
            r = r1 + r2 / 2 + r4 / 4
        elif r2 >= r1 and r2 >= r3:
            r = r2 + r1 / 2 + r4 / 4
        else:
            r = r3 + r4 / 4

        if r == 0:
            si[i] = 0
        else:
            si[i] = 50 * (
                (c[i] - c[i - 1]) + 0.5 * (c[i] - o[i]) + 0.25 * (c[i - 1] - o[i - 1])
            ) / r * r1

    asi = pd.Series(si, index=df.index).cumsum()
    maasi = _sma(asi, period)
    return {"asi": asi.tolist(), "maasi": maasi.tolist()}


def _compute_emv(df: pd.DataFrame, period: int) -> dict[str, list]:
    dm = ((df["high"] + df["low"]) / 2) - ((df["high"].shift(1) + df["low"].shift(1)) / 2)
    br = df["volume"] / (df["high"] - df["low"]).replace(0, np.nan)
    emv = dm / br.replace(0, np.nan)
    maemv = _sma(emv, period)
    return {"emv": emv.tolist(), "maemv": maemv.tolist()}


def _compute_arbr(df: pd.DataFrame, period: int) -> dict[str, list]:
    ar = 100 * (
        (df["high"] - df["open"]).rolling(period).sum()
        / (df["open"] - df["low"]).rolling(period).sum().replace(0, np.nan)
    )
    br = 100 * (
        (df["high"] - df["close"].shift(1)).clip(lower=0).rolling(period).sum()
        / (df["close"].shift(1) - df["low"]).clip(lower=0).rolling(period).sum().replace(0, np.nan)
    )
    return {"ar": ar.tolist(), "br": br.tolist()}


def _compute_cr(df: pd.DataFrame, period: int) -> dict[str, list]:
    mid = (df["high"] + df["low"] + df["close"]) / 3
    p1 = (df["high"] - mid.shift(1)).clip(lower=0).rolling(period).sum()
    p2 = (mid.shift(1) - df["low"]).clip(lower=0).rolling(period).sum()
    cr = 100 * p1 / p2.replace(0, np.nan)
    ma1 = _sma(cr, 5)
    ma2 = _sma(cr, 10)
    ma3 = _sma(cr, 20)
    return {"cr": cr.tolist(), "ma1": ma1.tolist(), "ma2": ma2.tolist(), "ma3": ma3.tolist()}


def _compute_vr(df: pd.DataFrame, period: int) -> dict[str, list]:
    change = df["close"] - df["close"].shift(1)
    up_vol = df["volume"].where(change > 0, 0).rolling(period).sum()
    dn_vol = df["volume"].where(change < 0, 0).rolling(period).sum()
    eq_vol = df["volume"].where(change == 0, 0).rolling(period).sum()
    vr = 100 * (up_vol + eq_vol / 2) / (dn_vol + eq_vol / 2).replace(0, np.nan)
    return {"vr": vr.tolist()}


def _compute_obv(df: pd.DataFrame) -> dict[str, list]:
    sign = np.sign(df["close"].diff())
    obv = (sign * df["volume"]).cumsum()
    return {"obv": obv.tolist()}


def _compute_vwap(df: pd.DataFrame) -> dict[str, list]:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (tp * df["volume"]).cumsum() / df["volume"].cumsum().replace(0, np.nan)
    return {"vwap": vwap.tolist()}


def _compute_mv(df: pd.DataFrame, period: int) -> dict[str, list]:
    mv = _sma(df["volume"], period)
    return {"mv": mv.tolist()}


# ═══════════════════════════════════════════════════════════════════════════════
# Computation dispatcher
# ═══════════════════════════════════════════════════════════════════════════════

_COMPUTE_FN: dict[str, callable] = {
    "MA": lambda df, p: _compute_ma(df, **p),
    "EMA": lambda df, p: _compute_ema(df, **p),
    "BOLL": lambda df, p: _compute_boll(df, **p),
    "SAR": lambda df, p: _compute_sar(df, **p),
    "ATR": lambda df, p: _compute_atr(df, **p),
    "MACD": lambda df, p: _compute_macd(df, **p),
    "RSI": lambda df, p: _compute_rsi(df, **p),
    "KDJ": lambda df, p: _compute_kdj(df, **p),
    "WR": lambda df, p: _compute_wr(df, **p),
    "CCI": lambda df, p: _compute_cci(df, **p),
    "DMI": lambda df, p: _compute_dmi(df, **p),
    "TRIX": lambda df, p: _compute_trix(df, **p),
    "DMA": lambda df, p: _compute_dma(df, **p),
    "ROC": lambda df, p: _compute_roc(df, **p),
    "MTM": lambda df, p: _compute_mtm(df, **p),
    "BIAS": lambda df, p: _compute_bias(df, **p),
    "ASI": lambda df, p: _compute_asi(df, **p),
    "EMV": lambda df, p: _compute_emv(df, **p),
    "ARBR": lambda df, p: _compute_arbr(df, **p),
    "CR": lambda df, p: _compute_cr(df, **p),
    "DMIADX": lambda df, p: _compute_dmi(df, **p),
    "VR": lambda df, p: _compute_vr(df, **p),
    "OBV": lambda df, p: _compute_obv(df),
    "VWAP": lambda df, p: _compute_vwap(df),
    "MV": lambda df, p: _compute_mv(df, **p),
}


# ═══════════════════════════════════════════════════════════════════════════════
# Signal detection
# ═══════════════════════════════════════════════════════════════════════════════


def _detect_macd_signals(data: dict[str, list]) -> list[Signal]:
    """Detect MACD golden/death cross signals."""
    signals = []
    dif = data.get("dif", [])
    dea = data.get("dea", [])
    if len(dif) < 2 or len(dea) < 2:
        return signals

    for i in range(1, len(dif)):
        if dif[i] is None or dea[i] is None or dif[i - 1] is None or dea[i - 1] is None:
            continue
        # Golden cross: DIF crosses above DEA
        if dif[i - 1] <= dea[i - 1] and dif[i] > dea[i]:
            signals.append(Signal(
                type=SignalType.BUY,
                strength=70,
                reason="MACD 金叉 (DIF 上穿 DEA)",
            ))
        # Death cross: DIF crosses below DEA
        elif dif[i - 1] >= dea[i - 1] and dif[i] < dea[i]:
            signals.append(Signal(
                type=SignalType.SELL,
                strength=70,
                reason="MACD 死叉 (DIF 下穿 DEA)",
            ))
    return signals


def _detect_rsi_signals(data: dict[str, list]) -> list[Signal]:
    """Detect RSI overbought/oversold signals."""
    signals = []
    rsi = data.get("rsi", [])
    for i, val in enumerate(rsi):
        if val is None:
            continue
        if val < 30:
            signals.append(Signal(
                type=SignalType.BUY,
                strength=60,
                reason=f"RSI 超卖 ({val:.1f} < 30)",
            ))
        elif val > 70:
            signals.append(Signal(
                type=SignalType.SELL,
                strength=60,
                reason=f"RSI 超买 ({val:.1f} > 70)",
            ))
    return signals


def _detect_kdj_signals(data: dict[str, list]) -> list[Signal]:
    """Detect KDJ golden/death cross signals."""
    signals = []
    k = data.get("k", [])
    d = data.get("d", [])
    if len(k) < 2 or len(d) < 2:
        return signals

    for i in range(1, len(k)):
        if k[i] is None or d[i] is None or k[i - 1] is None or d[i - 1] is None:
            continue
        if k[i - 1] <= d[i - 1] and k[i] > d[i] and k[i] < 30:
            signals.append(Signal(
                type=SignalType.BUY,
                strength=65,
                reason=f"KDJ 金叉 (低位 K={k[i]:.1f})",
            ))
        elif k[i - 1] >= d[i - 1] and k[i] < d[i] and k[i] > 70:
            signals.append(Signal(
                type=SignalType.SELL,
                strength=65,
                reason=f"KDJ 死叉 (高位 K={k[i]:.1f})",
            ))
    return signals


def _detect_boll_signals(
    data: dict[str, list], close_series: pd.Series | None = None
) -> list[Signal]:
    """Detect Bollinger Band squeeze/breakout signals."""
    signals = []
    upper = data.get("upper", [])
    lower = data.get("lower", [])
    if close_series is None or len(upper) < 1:
        return signals

    close = close_series.tolist()
    for i in range(len(close)):
        if i >= len(upper) or i >= len(lower):
            break
        if close[i] is None or upper[i] is None or lower[i] is None:
            continue
        if close[i] <= lower[i]:
            signals.append(Signal(
                type=SignalType.BUY,
                strength=55,
                reason=f"价格触及布林下轨",
            ))
        elif close[i] >= upper[i]:
            signals.append(Signal(
                type=SignalType.SELL,
                strength=55,
                reason=f"价格触及布林上轨",
            ))
    return signals


_SIGNAL_DETECTORS: dict[str, callable] = {
    "MACD": _detect_macd_signals,
    "RSI": _detect_rsi_signals,
    "KDJ": _detect_kdj_signals,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Public API — IndicatorComputer
# ═══════════════════════════════════════════════════════════════════════════════


class IndicatorComputer:
    """Compute technical indicators from OHLCV data.

    Usage::

        computer = IndicatorComputer()
        result = computer.compute(df, "MACD", {"fast": 12, "slow": 26, "signal": 9})
        print(result.data)  # {"dif": [...], "dea": [...], "macd": [...]}
    """

    def compute(
        self,
        data: pd.DataFrame,
        indicator: str,
        params: dict[str, Any] | None = None,
    ) -> IndicatorResult:
        """Compute a single indicator.

        Args:
            data: OHLCV DataFrame with columns: open, high, low, close, volume.
            indicator: Indicator key from INDICATOR_LIBRARY (e.g., "MACD").
            params: Override default parameters. Missing params use defaults.

        Returns:
            IndicatorResult with computed data series and any detected signals.

        Raises:
            ValueError: If indicator is not found in the library.
        """
        if indicator not in INDICATOR_LIBRARY:
            raise ValueError(
                f"Unknown indicator {indicator!r}. "
                f"Available: {list(INDICATOR_LIBRARY.keys())}"
            )

        idef = INDICATOR_LIBRARY[indicator]
        merged_params = {**idef.params, **(params or {})}

        compute_fn = _COMPUTE_FN.get(indicator)
        if compute_fn is None:
            raise NotImplementedError(f"Indicator {indicator!r} not yet implemented")

        series_data = compute_fn(data, merged_params)

        # Detect signals if a detector exists
        signals: list[Signal] = []
        detector = _SIGNAL_DETECTORS.get(indicator)
        if detector:
            signals = detector(series_data)

        return IndicatorResult(
            name=indicator,
            params=merged_params,
            data=series_data,
            signals=signals,
        )

    def compute_batch(
        self,
        data: pd.DataFrame,
        indicators: list[str],
        params: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, IndicatorResult]:
        """Compute multiple indicators in one call.

        Args:
            data: OHLCV DataFrame.
            indicators: List of indicator keys.
            params: Per-indicator parameter overrides.

        Returns:
            Dict mapping indicator key → IndicatorResult.
        """
        results = {}
        for ind in indicators:
            ind_params = (params or {}).get(ind)
            results[ind] = self.compute(data, ind, ind_params)
        return results

    def detect_signals(
        self,
        data: pd.DataFrame,
        indicator: str,
        params: dict[str, Any] | None = None,
    ) -> list[Signal]:
        """Compute indicator and return only its trading signals."""
        result = self.compute(data, indicator, params)
        return result.signals
