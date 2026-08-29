/**
 * Unit tests for alert-sync pure functions (ticket #12).
 *
 * Covers condition mapping, payload construction, server->local
 * conversion, and the tombstone queue (localStorage-backed).
 */

import { describe, it, expect, beforeEach } from "vitest";
import {
  toServerCondition,
  fromServerCondition,
  buildSyncPayload,
  fromServerAlerts,
  loadTombstones,
  addTombstone,
  type ServerAlert,
} from "./alert-sync";
import type { PriceAlert } from "./types";

// ── Fixtures ─────────────────────────────────────────────────────────────────

function localAlert(overrides: Partial<PriceAlert> = {}): PriceAlert {
  return {
    id: "a1",
    ticker: "600519",
    name: "贵州茅台",
    condition: "above",
    target_price: 1800,
    enabled: true,
    triggered: false,
    created_at: "2026-08-29T00:00:00.000Z",
    ...overrides,
  };
}

function serverAlert(overrides: Partial<ServerAlert> = {}): ServerAlert {
  return {
    id: "a1",
    ticker: "600519",
    condition: "price_above",
    threshold: 1800,
    indicator: null,
    message: "",
    enabled: true,
    triggered: false,
    created_at: 1000,
    triggered_at: null,
    updated_at: 100,
    ...overrides,
  };
}

// ── Condition mapping ────────────────────────────────────────────────────────

describe("condition mapping", () => {
  it("maps local above/below to server price conditions", () => {
    expect(toServerCondition("above")).toBe("price_above");
    expect(toServerCondition("below")).toBe("price_below");
  });

  it("round-trips server conditions transparently", () => {
    expect(fromServerCondition("price_above")).toBe("above");
    expect(fromServerCondition("price_below")).toBe("below");
    expect(fromServerCondition("indicator_above")).toBe("indicator_above");
    expect(fromServerCondition("cross_below")).toBe("cross_below");
  });

  it("unknown local conditions pass through unchanged", () => {
    expect(toServerCondition("volume_above")).toBe("volume_above");
  });
});

// ── Payload construction ─────────────────────────────────────────────────────

describe("buildSyncPayload", () => {
  it("maps local alerts to server shape", () => {
    const payload = buildSyncPayload(
      [localAlert({ triggered: true, updated_at: 500 })],
      [],
    );
    expect(payload.alerts).toHaveLength(1);
    const alert = payload.alerts[0];
    expect(alert.condition).toBe("price_above");
    expect(alert.threshold).toBe(1800);
    expect(alert.triggered).toBe(true);
    expect(alert.updated_at).toBe(500);
    expect(alert.created_at).toBe(
      Math.floor(new Date("2026-08-29T00:00:00.000Z").getTime() / 1000),
    );
  });

  it("missing updated_at defaults to now", () => {
    const payload = buildSyncPayload([localAlert()], []);
    const now = Math.floor(Date.now() / 1000);
    expect(payload.alerts[0].updated_at).toBeGreaterThanOrEqual(now - 5);
    expect(payload.alerts[0].updated_at).toBeLessThanOrEqual(now + 5);
  });

  it("carries tombstones verbatim", () => {
    const payload = buildSyncPayload([], [
      { id: "a2", deleted_at: 300 },
    ]);
    expect(payload.deleted).toEqual([{ id: "a2", deleted_at: 300 }]);
  });
});

// ── Server -> local conversion ───────────────────────────────────────────────

describe("fromServerAlerts", () => {
  it("converts server alerts and preserves local names", () => {
    const result = fromServerAlerts(
      [serverAlert()],
      [localAlert({ name: "本地名称" })],
    );
    expect(result).toHaveLength(1);
    expect(result[0].condition).toBe("above");
    expect(result[0].target_price).toBe(1800);
    expect(result[0].name).toBe("本地名称");
    expect(result[0].created_at).toBe(new Date(1000 * 1000).toISOString());
    expect(result[0].updated_at).toBe(100);
  });

  it("unknown server conditions keep their raw value", () => {
    const result = fromServerAlerts(
      [serverAlert({ condition: "indicator_below", indicator: "RSI" })],
      [],
    );
    expect(result[0].condition).toBe("indicator_below");
    expect(result[0].name).toBeNull();
  });

  it("server alerts not present locally get no name", () => {
    const result = fromServerAlerts([serverAlert()], []);
    expect(result[0].name).toBeNull();
  });
});

// ── Tombstone queue ──────────────────────────────────────────────────────────

describe("tombstone queue", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("starts empty", () => {
    expect(loadTombstones()).toEqual([]);
  });

  it("addTombstone appends and persists", () => {
    const next = addTombstone("a1");
    expect(next).toHaveLength(1);
    expect(next[0].id).toBe("a1");
    expect(next[0].deleted_at).toBeGreaterThan(0);
    expect(loadTombstones()).toHaveLength(1);
  });

  it("addTombstone dedupes by id", () => {
    addTombstone("a1");
    addTombstone("a1");
    addTombstone("a2");
    const stored = loadTombstones();
    expect(stored).toHaveLength(2);
    expect(stored.map((t) => t.id).sort()).toEqual(["a1", "a2"]);
  });

  it("corrupted storage falls back to empty", () => {
    localStorage.setItem("tradingagents_alert_tombstones", "not json");
    expect(loadTombstones()).toEqual([]);
  });
});
