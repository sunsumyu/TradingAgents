"""Pure numerical computations for technical indicators.

MA, EMA, KDJ — no I/O, no vendor calls.
"""

from __future__ import annotations


def compute_ma(closes: list[float], period: int) -> list[float | None]:
    """Compute a simple moving average over close prices.

    Returns a list of the same length as ``closes``, with ``None`` for
    positions where not enough data is available.
    """
    result: list[float | None] = []
    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        else:
            window = closes[i - period + 1 : i + 1]
            result.append(round(sum(window) / period, 2))
    return result


def compute_ema(closes: list[float], period: int) -> list[float | None]:
    """Compute an exponential moving average over close prices.

    Returns a list of the same length as ``closes``, with ``None`` for
    positions where not enough data is available.
    """
    if len(closes) < period:
        return [None] * len(closes)

    result: list[float | None] = []
    sma_seed = sum(closes[:period]) / period
    multiplier = 2.0 / (period + 1)

    for i in range(len(closes)):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            result.append(round(sma_seed, 2))
        else:
            prev = result[-1]
            if prev is None:
                result.append(round(closes[i], 2))
            else:
                val = (closes[i] - prev) * multiplier + prev
                result.append(round(val, 2))
    return result


def compute_kdj(
    highs: list[float], lows: list[float], closes: list[float], period: int = 9
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Compute KDJ indicator (K, D, J lines).

    RSV = (Close - Low_n) / (High_n - Low_n) * 100
    K = 2/3 * prev_K + 1/3 * RSV  (initial K = 50)
    D = 2/3 * prev_D + 1/3 * K    (initial D = 50)
    J = 3 * K - 2 * D

    Returns three lists of the same length as the inputs, with ``None``
    for positions where not enough data is available.
    """
    n = len(closes)
    k_vals: list[float | None] = []
    d_vals: list[float | None] = []
    j_vals: list[float | None] = []

    prev_k = 50.0
    prev_d = 50.0

    for i in range(n):
        if i < period - 1:
            k_vals.append(None)
            d_vals.append(None)
            j_vals.append(None)
            continue

        window_high = max(highs[i - period + 1 : i + 1])
        window_low = min(lows[i - period + 1 : i + 1])

        if window_high == window_low:
            rsv = 50.0
        else:
            rsv = (closes[i] - window_low) / (window_high - window_low) * 100.0

        k = 2.0 / 3.0 * prev_k + 1.0 / 3.0 * rsv
        d = 2.0 / 3.0 * prev_d + 1.0 / 3.0 * k
        j = 3.0 * k - 2.0 * d

        k_vals.append(round(k, 2))
        d_vals.append(round(d, 2))
        j_vals.append(round(j, 2))

        prev_k = k
        prev_d = d

    return k_vals, d_vals, j_vals
