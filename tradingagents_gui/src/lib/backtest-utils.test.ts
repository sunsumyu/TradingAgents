import { describe, expect, it } from "vitest";

import {
  backtestWindow,
  HOLDING_DAY_OPTIONS,
  isInstallGuidanceError,
  normalizeCurve,
  signalToDecision,
} from "./backtest-utils";

describe("signalToDecision", () => {
  it("maps Buy/Overweight to BUY", () => {
    expect(signalToDecision("Buy")).toBe("BUY");
    expect(signalToDecision("Overweight")).toBe("BUY");
  });

  it("maps Sell/Underweight to SELL", () => {
    expect(signalToDecision("Sell")).toBe("SELL");
    expect(signalToDecision("Underweight")).toBe("SELL");
  });

  it("maps everything else to HOLD", () => {
    expect(signalToDecision("Hold")).toBe("HOLD");
    expect(signalToDecision("")).toBe("HOLD");
    expect(signalToDecision("Unknown")).toBe("HOLD");
  });
});

describe("backtestWindow", () => {
  it("starts at the analysis date and ends at 2x holding days + 10", () => {
    const w = backtestWindow("2026-01-10", 5);
    expect(w.start).toBe("2026-01-10");
    expect(w.end).toBe("2026-01-30");
  });

  it("scales the window with holding days", () => {
    const w = backtestWindow("2026-01-10", 10);
    expect(w.end).toBe("2026-02-09");
  });

  it("handles month/year rollover", () => {
    const w = backtestWindow("2026-12-25", 3);
    expect(w.end).toBe("2027-01-10");
  });
});

describe("normalizeCurve", () => {
  it("converts equity values to cumulative return percent from first point", () => {
    const out = normalizeCurve([
      { date: "2026-01-05", value: 100_000 },
      { date: "2026-01-06", value: 102_000 },
      { date: "2026-01-07", value: 99_000 },
    ]);
    expect(out).toEqual([
      ["2026-01-05", 0],
      ["2026-01-06", 2],
      ["2026-01-07", -1],
    ]);
  });

  it("returns empty array for empty/short curves", () => {
    expect(normalizeCurve([])).toEqual([]);
    expect(normalizeCurve([{ date: "2026-01-05", value: 100 }])).toEqual([]);
  });

  it("guards against zero base value", () => {
    const out = normalizeCurve([
      { date: "2026-01-05", value: 0 },
      { date: "2026-01-06", value: 5 },
    ]);
    expect(out).toEqual([]);
  });
});

describe("isInstallGuidanceError", () => {
  it("detects akquant and pip install hints", () => {
    expect(
      isInstallGuidanceError(
        "Backtesting engine not available: akquant is not installed. Install with: pip install akquant",
      ),
    ).toBe(true);
  });

  it("rejects ordinary errors", () => {
    expect(isInstallGuidanceError("Backtest failed: network error")).toBe(false);
    expect(isInstallGuidanceError("")).toBe(false);
  });
});

describe("HOLDING_DAY_OPTIONS", () => {
  it("exposes the agreed 1/3/5/10 day ladder", () => {
    expect(HOLDING_DAY_OPTIONS).toEqual([1, 3, 5, 10]);
  });
});
