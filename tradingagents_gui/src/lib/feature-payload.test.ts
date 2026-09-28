import { describe, expect, it } from "vitest";

import { formatFeatureCell, type FeatureColumn } from "./types";

describe("formatFeatureCell", () => {
  it("renders blanks as em dash", () => {
    const col: FeatureColumn = { key: "x", label: "X" };
    expect(formatFeatureCell(null, col)).toBe("—");
    expect(formatFeatureCell(undefined, col)).toBe("—");
    expect(formatFeatureCell("", col)).toBe("—");
  });

  it("applies int format by default", () => {
    const col: FeatureColumn = { key: "x", label: "X", format: "int" };
    expect(formatFeatureCell(1234.6, col)).toBe("1235");
  });

  it("applies float2 and float4", () => {
    expect(formatFeatureCell(1.23456, { key: "x", label: "X", format: "float2" })).toBe("1.23");
    expect(formatFeatureCell(1.23456, { key: "x", label: "X", format: "float4" })).toBe("1.2346");
  });

  it("prefixes + for positive signed values only", () => {
    const col: FeatureColumn = { key: "x", label: "X", format: "signed" };
    expect(formatFeatureCell(300, col)).toBe("+300");
    expect(formatFeatureCell(-300, col)).toBe("-300");
    expect(formatFeatureCell(0, col)).toBe("0");
  });

  it("appends % for percent unit", () => {
    const col: FeatureColumn = { key: "x", label: "X", unit: "percent", format: "float2" };
    expect(formatFeatureCell(3.5, col)).toBe("3.50%");
  });

  it("passes dates and text through", () => {
    expect(formatFeatureCell("2026-09-27", { key: "d", label: "D", unit: "date" })).toBe("2026-09-27");
    expect(formatFeatureCell("贵州茅台", { key: "n", label: "N" })).toBe("贵州茅台");
  });
});
