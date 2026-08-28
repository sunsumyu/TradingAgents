"""Chip (筹码) distribution estimation from historical OHLCV data.

Uses a simplified cost-weighted model with time decay.
"""

from __future__ import annotations

import logging
from typing import Annotated
from datetime import datetime, timedelta

import pandas as pd

from .utils import normalize_ticker

logger = logging.getLogger(__name__)


def get_chip_distribution(
    symbol: Annotated[str, "A-stock code"],
    curr_date: Annotated[str, "Current date YYYY-mm-dd"],
    days: Annotated[int, "Number of days to analyze for chip accumulation"] = 90,
) -> str:
    """Estimate chip (筹码) distribution from historical OHLCV data.

    Uses a simplified cost-weighted model:
    - Each day's volume is distributed across the price range (low..high)
    - Chips decay over time (older chips have less weight)
    - Output shows the % of chips at each price level
    """
    from .ohlcv import load_ohlcv_astock

    code = normalize_ticker(symbol)

    try:
        data = load_ohlcv_astock(code, curr_date)
        if data is None or data.empty:
            return f"无法获取 {code} 的历史数据"

        df = data.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date")

        curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
        cutoff = curr_dt - timedelta(days=days)
        df = df[df["Date"] <= pd.Timestamp(curr_dt)]
        df = df[df["Date"] >= pd.Timestamp(cutoff)]

        if df.empty:
            return f"{code} 在最近 {days} 天无交易数据"

        price_min = df["Low"].min()
        price_max = df["High"].max()
        if price_max <= price_min:
            return f"{code} 价格区间异常"

        num_bins = 20
        bin_edges = pd.RangeIndex(num_bins + 1).to_series().apply(
            lambda i: price_min + (price_max - price_min) * i / num_bins
        )
        chip_counts = [0.0] * num_bins

        for _, row in df.iterrows():
            day_high = row["High"]
            day_low = row["Low"]
            day_vol = row["Volume"]
            day_date = row["Date"]
            days_ago = (curr_dt - day_date).days
            decay = max(0.1, 1.0 - days_ago / (days * 1.5))

            for i in range(num_bins):
                bin_low, bin_high = bin_edges[i], bin_edges[i + 1]
                overlap_low = max(day_low, bin_low)
                overlap_high = min(day_high, bin_high)
                if overlap_high > overlap_low and day_high > day_low:
                    fraction = (overlap_high - overlap_low) / (day_high - day_low)
                    chip_counts[i] += fraction * day_vol * decay

        total = sum(chip_counts)
        if total <= 0:
            return f"{code} 筹码计算结果为空"

        chip_pct = [c / total * 100 for c in chip_counts]

        max_idx = chip_counts.index(max(chip_counts))
        peak_price = (bin_edges[max_idx] + bin_edges[max_idx + 1]) / 2

        avg_cost = sum(
            (bin_edges[i] + bin_edges[i + 1]) / 2 * chip_pct[i]
            for i in range(num_bins)
        ) / 100

        last_close = df["Close"].iloc[-1]
        profit_chips = sum(
            chip_pct[i]
            for i in range(num_bins)
            if (bin_edges[i] + bin_edges[i + 1]) / 2 < last_close
        )

        lines = [
            f"## 筹码分布分析: {code} (最近 {days} 天)",
            f"当前价: {last_close:.2f}",
            f"筹码峰值价: {peak_price:.2f}",
            f"平均成本: {avg_cost:.2f}",
            f"获利盘比例: {profit_chips:.1f}%",
            "",
            "价格区间 | 筹码占比 | 柱状图",
            "-" * 50,
        ]

        max_bar = 30
        for i in range(num_bins):
            price_mid = (bin_edges[i] + bin_edges[i + 1]) / 2
            pct = chip_pct[i]
            bar_len = int(pct / max(chip_pct) * max_bar) if max(chip_pct) > 0 else 0
            bar = "█" * bar_len
            marker = " ◄ 峰值" if i == max_idx else ""
            lines.append(f"  {price_mid:8.2f} | {pct:5.1f}% | {bar}{marker}")

        lines.extend([
            "",
            "### 筹码分析要点:",
            f"- 套牢盘 ({last_close:.2f} 以上): {100 - profit_chips:.1f}%",
            f"- 获利盘 ({last_close:.2f} 以下): {profit_chips:.1f}%",
            f"- 筹码集中度: 峰值在 {peak_price:.2f}",
        ])

        return "\n".join(lines)

    except Exception as e:
        return f"Error computing chip distribution for {code}: {str(e)}"
