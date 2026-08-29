/**
 * Unit tests for watchlist-store merge logic (ticket #5).
 *
 * Tests the pure function `mergeWatchlistStates` which implements
 * newer-wins-by-updated_at merging between local and remote states.
 */

import { describe, it, expect } from "vitest";
import {
  mergeWatchlistStates,
  type SyncWatchlistState,
} from "./watchlist-store";

// ── Helpers ──────────────────────────────────────────────────────────────────

function group(
  id: string,
  name: string,
  items: { ticker: string; updated_at: number }[],
  updated_at: number,
): SyncWatchlistState["groups"][0] {
  return {
    id,
    name,
    updated_at,
    items: items.map((i) => ({
      ...i,
      name: "",
      position: 0,
    })),
  };
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe("mergeWatchlistStates", () => {
  it("remote-only groups appear in merged result", () => {
    const local: SyncWatchlistState = { groups: [] };
    const remote: SyncWatchlistState = {
      groups: [group("g1", "远程组", [{ ticker: "600519", updated_at: 100 }], 100)],
    };
    const merged = mergeWatchlistStates(local, remote);
    expect(merged.groups).toHaveLength(1);
    expect(merged.groups[0].id).toBe("g1");
    expect(merged.groups[0].items[0].ticker).toBe("600519");
  });

  it("local-only groups appear in merged result", () => {
    const local: SyncWatchlistState = {
      groups: [group("g1", "自选股", [{ ticker: "000858", updated_at: 100 }], 100)],
    };
    const remote: SyncWatchlistState = { groups: [] };
    const merged = mergeWatchlistStates(local, remote);
    expect(merged.groups).toHaveLength(1);
    expect(merged.groups[0].items[0].ticker).toBe("000858");
  });

  it("newer group name wins (remote newer)", () => {
    const local: SyncWatchlistState = {
      groups: [group("g1", "旧名", [], 100)],
    };
    const remote: SyncWatchlistState = {
      groups: [group("g1", "新名", [], 200)],
    };
    const merged = mergeWatchlistStates(local, remote);
    expect(merged.groups[0].name).toBe("新名");
  });

  it("newer group name wins (local newer)", () => {
    const local: SyncWatchlistState = {
      groups: [group("g1", "本地新名", [], 300)],
    };
    const remote: SyncWatchlistState = {
      groups: [group("g1", "远程旧名", [], 100)],
    };
    const merged = mergeWatchlistStates(local, remote);
    expect(merged.groups[0].name).toBe("本地新名");
  });

  it("ties go to remote (remote wins on equal updated_at)", () => {
    const local: SyncWatchlistState = {
      groups: [group("g1", "本地", [], 100)],
    };
    const remote: SyncWatchlistState = {
      groups: [group("g1", "远程", [], 100)],
    };
    const merged = mergeWatchlistStates(local, remote);
    expect(merged.groups[0].name).toBe("远程");
  });

  it("item merge: newer ticker name wins", () => {
    const local: SyncWatchlistState = {
      groups: [group("g1", "组", [
        { ticker: "600519", updated_at: 100 },
      ], 100)],
    };
    const remote: SyncWatchlistState = {
      groups: [group("g1", "组", [
        { ticker: "600519", updated_at: 200 },
      ], 100)],
    };
    // Remote item is newer → its data should survive merge
    const merged = mergeWatchlistStates(local, remote);
    expect(merged.groups[0].items).toHaveLength(1);
    expect(merged.groups[0].items[0].updated_at).toBe(200);
  });

  it("item merge: no duplicates for same ticker", () => {
    const local: SyncWatchlistState = {
      groups: [group("g1", "组", [
        { ticker: "600519", updated_at: 100 },
      ], 100)],
    };
    const remote: SyncWatchlistState = {
      groups: [group("g1", "组", [
        { ticker: "600519", updated_at: 150 },
      ], 100)],
    };
    const merged = mergeWatchlistStates(local, remote);
    expect(merged.groups[0].items).toHaveLength(1);
  });

  it("shared group: winner's items are authoritative (ties → remote)", () => {
    // When both sides have the same group, the winning side (newer
    // updated_at, ties → remote) provides the items. The losing side's
    // items are discarded — the winning snapshot is authoritative.
    const local: SyncWatchlistState = {
      groups: [group("g1", "组", [
        { ticker: "600519", updated_at: 100 },
      ], 100)],
    };
    const remote: SyncWatchlistState = {
      groups: [group("g1", "组", [
        { ticker: "000858", updated_at: 100 },
      ], 100)],
    };
    // Ties → remote wins
    const merged = mergeWatchlistStates(local, remote);
    const tickers = merged.groups[0].items.map((i) => i.ticker);
    expect(tickers).toEqual(["000858"]);
  });

  it("local-only group: all local items preserved", () => {
    const local: SyncWatchlistState = {
      groups: [group("g1", "组", [
        { ticker: "600519", updated_at: 100 },
        { ticker: "000858", updated_at: 100 },
      ], 100)],
    };
    const remote: SyncWatchlistState = { groups: [] };
    const merged = mergeWatchlistStates(local, remote);
    const tickers = merged.groups[0].items.map((i) => i.ticker).sort();
    expect(tickers).toEqual(["000858", "600519"]);
  });

  it("cross-group: both groups exist, items union across sides", () => {
    // The pure merge function unions items by ticker. Cross-group item
    // removal (moves) are handled server-side via deleted_items tombstones
    // in the sync protocol, not in this snapshot merge.
    const local: SyncWatchlistState = {
      groups: [
        group("g1", "自选股", [{ ticker: "600519", updated_at: 100 }], 100),
      ],
    };
    const remote: SyncWatchlistState = {
      groups: [
        group("g2", "次选", [{ ticker: "600519", updated_at: 200 }], 200),
      ],
    };
    const merged = mergeWatchlistStates(local, remote);
    const g1 = merged.groups.find((g) => g.id === "g1");
    const g2 = merged.groups.find((g) => g.id === "g2");
    // Both groups persist; item appears in both (newer side wins the ticker data)
    expect(g1).toBeDefined();
    expect(g2).toBeDefined();
    expect(g2?.items.map((i) => i.ticker)).toContain("600519");
    // g1 still has 600519 because the pure merge doesn't know about tombstones
    expect(g1?.items.map((i) => i.ticker)).toContain("600519");
  });

  it("cross-group move via sync: local wins the group when newer", () => {
    // When the user moves an item in the UI, the local state has the
    // item in g2 (newer). The merge picks local g1 (newer, empty) over
    // remote g1 (older, has 600519). Cross-device item deletion requires
    // server-side tombstones (syncToServer), not snapshot merge.
    const local: SyncWatchlistState = {
      groups: [
        group("g1", "自选股", [], 200),
        group("g2", "次选", [{ ticker: "600519", updated_at: 200 }], 200),
      ],
    };
    const remote: SyncWatchlistState = {
      groups: [
        group("g1", "自选股", [{ ticker: "600519", updated_at: 100 }], 100),
      ],
    };
    const merged = mergeWatchlistStates(local, remote);
    const g1 = merged.groups.find((g) => g.id === "g1");
    const g2 = merged.groups.find((g) => g.id === "g2");
    // Local g1 (newer, empty) wins → 600519 not in g1
    expect(g1?.items.map((i) => i.ticker)).not.toContain("600519");
    expect(g2?.items.map((i) => i.ticker)).toContain("600519");
  });

  it("inputs are not mutated", () => {
    const local: SyncWatchlistState = {
      groups: [group("g1", "组", [
        { ticker: "600519", updated_at: 100 },
      ], 100)],
    };
    const remote: SyncWatchlistState = {
      groups: [group("g1", "组", [
        { ticker: "000858", updated_at: 200 },
      ], 200)],
    };
    const localSnapshot = JSON.stringify(local);
    const remoteSnapshot = JSON.stringify(remote);
    mergeWatchlistStates(local, remote);
    expect(JSON.stringify(local)).toBe(localSnapshot);
    expect(JSON.stringify(remote)).toBe(remoteSnapshot);
  });
});
