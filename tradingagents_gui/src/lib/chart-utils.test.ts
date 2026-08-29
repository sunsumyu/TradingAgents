import { describe, it, expect } from "vitest";
import {
  computeSmaSeries,
  computeMacdSeries,
  computeRsiSeries,
  computeWR,
  computeCCI,
  sanitizePeriod,
  getLatestIndicatorValue,
} from "./chart-utils";
import type { KlineData } from "./types";

// ── Helpers ─────────────────────────────────────────────────────────────────

function makeKline(ohlc: [number, number, number, number][]): KlineData {
  return {
    dates: ohlc.map((_, i) => `2026-01-${String(i + 1).padStart(2, "0")}`),
    ohlc,
    volumes: ohlc.map(() => 1000),
  };
}

const closes = [10, 11, 12, 11, 13, 14, 12, 15, 16, 14];

// ── computeSmaSeries ────────────────────────────────────────────────────────

describe("computeSmaSeries", () => {
  it("returns null for first (period-1) bars", () => {
    const result = computeSmaSeries(closes, 3);
    expect(result[0]).toBeNull();
    expect(result[1]).toBeNull();
    expect(result[2]).not.toBeNull();
  });

  it("computes correct SMA for period=3", () => {
    const result = computeSmaSeries(closes, 3);
    // index 2: (10+11+12)/3 = 11
    expect(result[2]).toBeCloseTo(11, 10);
    // index 3: (11+12+11)/3 = 11.333...
    expect(result[3]).toBeCloseTo(11.3333, 4);
  });

  it("handles period larger than data length", () => {
    const result = computeSmaSeries([1, 2, 3], 5);
    expect(result.every((v) => v === null)).toBe(true);
  });

  it("single element with period=1 returns that element", () => {
    const result = computeSmaSeries([42], 1);
    expect(result[0]).toBe(42);
  });

  it("all identical values", () => {
    const result = computeSmaSeries([5, 5, 5, 5], 2);
    expect(result[1]).toBe(5);
    expect(result[3]).toBe(5);
  });
});

// ── computeMacdSeries ──────────────────────────────────────────────────────

describe("computeMacdSeries", () => {
  it("returns arrays of same length as input", () => {
    const { macd, signal, histogram } = computeMacdSeries(closes, {
      fast: 3,
      slow: 5,
      signal: 3,
    });
    expect(macd.length).toBe(closes.length);
    expect(signal.length).toBe(closes.length);
    expect(histogram.length).toBe(closes.length);
  });

  it("histogram = macd - signal at every bar", () => {
    const { macd, signal, histogram } = computeMacdSeries(closes, {
      fast: 3,
      slow: 5,
      signal: 3,
    });
    for (let i = 0; i < closes.length; i++) {
      expect(histogram[i]).toBeCloseTo(macd[i] - signal[i], 10);
    }
  });

  it("constant input yields near-zero MACD", () => {
    const flat = new Array(20).fill(100);
    const { macd } = computeMacdSeries(flat, { fast: 12, slow: 26, signal: 9 });
    // With identical values, EMA_fast ≈ EMA_slow, so MACD ≈ 0
    expect(Math.abs(macd[19])).toBeLessThan(0.01);
  });
});

// ── computeRsiSeries ────────────────────────────────────────────────────────

describe("computeRsiSeries", () => {
  it("first bar is always 50", () => {
    const rsi = computeRsiSeries(closes, 14);
    expect(rsi[0]).toBe(50);
  });

  it("all-up prices → RSI approaches 100", () => {
    const up = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24];
    const rsi = computeRsiSeries(up, 14);
    // After warm-up, RSI should be very high
    expect(rsi[rsi.length - 1]).toBeGreaterThan(90);
  });

  it("all-down prices → RSI approaches 0", () => {
    const down = [24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10];
    const rsi = computeRsiSeries(down, 14);
    expect(rsi[rsi.length - 1]).toBeLessThan(10);
  });

  it("flat prices → RSI is 50", () => {
    const flat = new Array(20).fill(100);
    const rsi = computeRsiSeries(flat, 14);
    expect(rsi[rsi.length - 1]).toBe(50);
  });

  it("output length matches input", () => {
    const rsi = computeRsiSeries(closes, 6);
    expect(rsi.length).toBe(closes.length);
  });
});

// ── computeWR ──────────────────────────────────────────────────────────────

describe("computeWR", () => {
  function makeSimpleKline(prices: number[]): KlineData {
    // ohlc = [open, close, low, high]
    const ohlc = prices.map((p) => [p, p, p * 0.95, p * 1.05] as [number, number, number, number]);
    return makeKline(ohlc);
  }

  it("first (period-1) bars are null", () => {
    const data = makeSimpleKline(closes);
    const wr = computeWR(data, 3);
    expect(wr[0]).toBeNull();
    expect(wr[1]).toBeNull();
    expect(wr[2]).not.toBeNull();
  });

  it("close at high → WR near 0", () => {
    const ohlc: [number, number, number, number][] = [
      [12, 12, 10, 14],
      [12, 12, 10, 14],
      [12, 14, 10, 14], // close = HH across window
    ];
    const data = makeKline(ohlc);
    const wr = computeWR(data, 3);
    // WR = (HH - Close)/(HH - LL)*100 = (14 - 14)/(14 - 10)*100 = 0
    expect(wr[2]).toBeCloseTo(0, 5);
  });

  it("close at low → WR near 100", () => {
    const ohlc: [number, number, number, number][] = [
      [12, 12, 10, 14],
      [12, 12, 10, 14],
      [12, 10, 10, 14], // close = LL across window
    ];
    const data = makeKline(ohlc);
    const wr = computeWR(data, 3);
    // WR = (HH - Close)/(HH - LL)*100 = (14 - 10)/(14 - 10)*100 = 100
    expect(wr[2]).toBeCloseTo(100, 5);
  });

  it("flat window (HH === LL) → null (no division by zero)", () => {
    const ohlc: [number, number, number, number][] = [
      [10, 10, 10, 10],
      [10, 10, 10, 10],
      [10, 10, 10, 10],
    ];
    const data = makeKline(ohlc);
    const wr = computeWR(data, 3);
    expect(wr[2]).toBeNull();
  });

  it("all values in [0, 100]", () => {
    const data = makeKline(closes.map((c) => [c, c, c * 0.9, c * 1.1] as [number, number, number, number]));
    const wr = computeWR(data, 5);
    for (const v of wr) {
      if (v !== null) {
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(100);
      }
    }
  });
});

// ── computeCCI ─────────────────────────────────────────────────────────────

describe("computeCCI", () => {
  it("first (period-1) bars are null", () => {
    const ohlc: [number, number, number, number][] = closes.map((c) => [c, c, c * 0.95, c * 1.05]);
    const data = makeKline(ohlc);
    const cci = computeCCI(data, 5);
    expect(cci[0]).toBeNull();
    expect(cci[1]).toBeNull();
    expect(cci[2]).toBeNull();
    expect(cci[3]).toBeNull();
    expect(cci[4]).not.toBeNull();
  });

  it("flat prices → mean deviation = 0 → null (no division by zero)", () => {
    const ohlc: [number, number, number, number][] = Array.from({ length: 25 }, () => [100, 100, 100, 100]);
    const data = makeKline(ohlc);
    const cci = computeCCI(data, 20);
    // All TPs are equal → meanDev = 0 → null
    expect(cci[24]).toBeNull();
  });

  it("output length matches input", () => {
    const ohlc: [number, number, number, number][] = closes.map((c) => [c, c, c * 0.95, c * 1.05]);
    const data = makeKline(ohlc);
    const cci = computeCCI(data, 3);
    expect(cci.length).toBe(closes.length);
  });
});

// ── sanitizePeriod ──────────────────────────────────────────────────────────

describe("sanitizePeriod", () => {
  it("valid integer within range", () => {
    expect(sanitizePeriod(14, 10)).toBe(14);
  });

  it("float → fallback", () => {
    expect(sanitizePeriod(14.5, 10)).toBe(10);
  });

  it("string number → coerced", () => {
    expect(sanitizePeriod("7", 10)).toBe(7);
  });

  it("non-numeric string → fallback", () => {
    expect(sanitizePeriod("abc", 10)).toBe(10);
  });

  it("below min → fallback", () => {
    expect(sanitizePeriod(0, 10)).toBe(10);
  });

  it("above max → fallback", () => {
    expect(sanitizePeriod(999, 10)).toBe(10);
  });

  it("at boundaries", () => {
    expect(sanitizePeriod(1, 10)).toBe(1);
    expect(sanitizePeriod(250, 10)).toBe(250);
  });

  it("null/undefined → fallback", () => {
    expect(sanitizePeriod(null, 10)).toBe(10);
    expect(sanitizePeriod(undefined, 10)).toBe(10);
  });
});

// ── getLatestIndicatorValue ────────────────────────────────────────────────

describe("getLatestIndicatorValue", () => {
  it("returns last value formatted", () => {
    const data = makeKline([[10, 20, 5, 30]]);
    (data as any).ma5 = [null, null, 12.34];
    expect(getLatestIndicatorValue(data, "ma5")).toBe("12.34");
  });

  it("returns '—' for missing field", () => {
    const data = makeKline([[10, 20, 5, 30]]);
    expect(getLatestIndicatorValue(data, "ma5")).toBe("—");
  });

  it("returns '—' for empty array", () => {
    const data = makeKline([[10, 20, 5, 30]]);
    (data as any).ma5 = [];
    expect(getLatestIndicatorValue(data, "ma5")).toBe("—");
  });

  it("returns '—' when last value is null", () => {
    const data = makeKline([[10, 20, 5, 30]]);
    (data as any).ma5 = [10, null];
    expect(getLatestIndicatorValue(data, "ma5")).toBe("—");
  });
});
