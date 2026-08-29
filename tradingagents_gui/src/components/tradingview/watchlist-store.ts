/**
 * Watchlist group persistence — localStorage-backed store shared by
 * WatchlistPanel (UI) and any other consumer that needs the grouped list.
 *
 * Storage key: "tradingagents_watchlist_groups" (per phase-4 spec).
 * Legacy flat lists under "tradingagents_watchlist" are migrated on first
 * load; the legacy key is left untouched as a backup.
 *
 * Ticket #5 adds server sync: the pure function `mergeWatchlistStates`
 * implements newer-wins-by-updated_at merging, and `syncToServer` /
 * `loadFromServer` handle the HTTP round-trips.
 */

import type { WatchlistGroup, WatchlistItem } from "./types";

export const WATCHLIST_GROUPS_KEY = "tradingagents_watchlist_groups";
export const DEFAULT_GROUP_NAME = "自选股";

// ── Extended types for sync ──────────────────────────────────────────────────

export interface SyncWatchlistItem extends WatchlistItem {
  updated_at: number;
}

export interface SyncWatchlistGroup extends Omit<WatchlistGroup, "items"> {
  updated_at: number;
  items: SyncWatchlistItem[];
}

export interface SyncWatchlistState {
  groups: SyncWatchlistGroup[];
}

export interface SyncPutPayload {
  groups: SyncWatchlistGroup[];
  deleted_group_ids: string[];
  deleted_items: { group_id: string; ticker: string; updated_at: number }[];
}

// ── ID generation ────────────────────────────────────────────────────────────

let idCounter = 0;
function newGroupId(): string {
  idCounter += 1;
  return `g_${Date.now().toString(36)}_${idCounter}`;
}

// ── Pure merge function ──────────────────────────────────────────────────────

/**
 * Merge two watchlist states using newer-wins-by-updated_at.
 *
 * Algorithm:
 * 1. Union of all group IDs across both sides.
 * 2. For each group: if only one side has it, take that side. If both have it,
 *    the side with the newer `updated_at` wins (ties → remote wins, since
 *    remote reflects a committed server state).
 * 3. For items within the winning group: same newer-wins merge by ticker key.
 * 4. Returns a new state without mutating inputs.
 */
export function mergeWatchlistStates(
  local: SyncWatchlistState,
  remote: SyncWatchlistState,
): SyncWatchlistState {
  const remoteGroupMap = new Map<string, SyncWatchlistGroup>();
  for (const g of remote.groups) {
    remoteGroupMap.set(g.id, g);
  }

  const remoteItemMap = new Map<string, SyncWatchlistItem>();
  for (const g of remote.groups) {
    for (const item of g.items) {
      remoteItemMap.set(`${g.id}:${item.ticker}`, item);
    }
  }

  const mergedGroupMap = new Map<string, SyncWatchlistGroup>();

  // Build metadata map: for each group, pick the side with newer updated_at
  // for group-level fields (name, position, collapsed). Items are merged
  // separately below regardless of which side "won" the group metadata.
  for (const rg of remote.groups) {
    const lg = local.groups.find((g) => g.id === rg.id);
    if (!lg) {
      mergedGroupMap.set(rg.id, rg);
      continue;
    }
    // Both sides have this group — newer wins for metadata (ties → remote)
    const winner = rg.updated_at >= lg.updated_at ? rg : lg;
    mergedGroupMap.set(rg.id, winner);
  }

  // Add local-only groups
  for (const lg of local.groups) {
    if (!remoteGroupMap.has(lg.id)) {
      mergedGroupMap.set(lg.id, lg);
    }
  }

  // For shared groups (exist on both sides), the winning group's items
  // are authoritative — the newer updated_at represents the latest
  // complete snapshot. For local-only or remote-only groups, take all
  // items from that side.
  const result: SyncWatchlistGroup[] = [];
  for (const [groupId, group] of mergedGroupMap) {
    const localGroup = local.groups.find((g) => g.id === groupId);
    const remoteGroup = remote.groups.find((g) => g.id === groupId);

    const isShared = localGroup && remoteGroup;
    let items: SyncWatchlistItem[];

    if (isShared) {
      // Winner's items are the authoritative snapshot
      items = group.items.map((item) => ({
        ...item,
        updated_at: (item as SyncWatchlistItem).updated_at ?? 0,
      }));
    } else if (localGroup && !remoteGroup) {
      // Local-only group: take local items
      items = localGroup.items.map((item) => ({
        ...item,
        updated_at: (item as SyncWatchlistItem).updated_at ?? 0,
      }));
    } else {
      // Remote-only group: take remote items
      items = (remoteGroup ?? group).items.map((item) => ({
        ...item,
        updated_at: (item as SyncWatchlistItem).updated_at ?? 0,
      }));
    }

    result.push({
      ...group,
      items,
    });
  }

  return { groups: result };
}

// ── LocalStorage persistence ─────────────────────────────────────────────────

/** Load groups, creating the default group / migrating legacy data as needed. */
export function loadWatchlistGroups(): WatchlistGroup[] {
  try {
    const raw = localStorage.getItem(WATCHLIST_GROUPS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed.map((g: any) => ({
          id: typeof g.id === "string" ? g.id : newGroupId(),
          name: String(g.name ?? DEFAULT_GROUP_NAME),
          items: Array.isArray(g.items) ? g.items : [],
          collapsed: Boolean(g.collapsed),
        }));
      }
    }
  } catch {
    // corrupted storage — fall through to migration/default
  }

  // Migrate legacy flat watchlist if present
  const legacy = loadLegacyWatchlist();
  const groups: WatchlistGroup[] = [
    { id: newGroupId(), name: DEFAULT_GROUP_NAME, items: legacy, collapsed: false },
  ];
  saveWatchlistGroups(groups);
  return groups;
}

export function saveWatchlistGroups(groups: WatchlistGroup[]) {
  try {
    localStorage.setItem(WATCHLIST_GROUPS_KEY, JSON.stringify(groups));
  } catch {
    // ignore persistence failures
  }
}

function loadLegacyWatchlist(): WatchlistItem[] {
  try {
    const raw = localStorage.getItem("tradingagents_watchlist");
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

// ── Server sync ──────────────────────────────────────────────────────────────

const BASE_URL = "http://127.0.0.1:8420";

/**
 * Load watchlist state from the server, merging with local state.
 * Returns the merged result; does NOT save to localStorage — caller decides.
 */
export async function loadFromServer(
  localGroups: WatchlistGroup[],
): Promise<WatchlistGroup[]> {
  try {
    const resp = await fetch(`${BASE_URL}/api/watchlist`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!resp.ok) return localGroups;
    const remote: SyncWatchlistState = await resp.json();

    const localWithTs: SyncWatchlistState = {
      groups: localGroups.map((g) => ({
        ...g,
        updated_at: Math.floor(Date.now() / 1000),
        items: g.items.map((item) => ({
          ...item,
          updated_at: Math.floor(Date.now() / 1000),
        })),
      })),
    };

    const merged = mergeWatchlistStates(localWithTs, remote);
    return merged.groups.map((g) => ({
      id: g.id,
      name: g.name,
      items: g.items,
      collapsed: g.collapsed,
    }));
  } catch {
    // network error — return local state unchanged
    return localGroups;
  }
}

/**
 * Push the current local state to the server for merge.
 * Returns the server's merged result, or null on failure.
 */
export async function syncToServer(
  localGroups: WatchlistGroup[],
  deletedGroupIds: string[] = [],
  deletedItems: { group_id: string; ticker: string }[] = [],
): Promise<SyncWatchlistState | null> {
  try {
    const now = Math.floor(Date.now() / 1000);
    const payload: SyncPutPayload = {
      groups: localGroups.map((g) => ({
        ...g,
        updated_at: now,
        items: g.items.map((item) => ({
          ...item,
          updated_at: now,
        })),
      })),
      deleted_group_ids: deletedGroupIds,
      deleted_items: deletedItems.map((d) => ({
        ...d,
        updated_at: now,
      })),
    };

    const resp = await fetch(`${BASE_URL}/api/watchlist`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(5000),
    });
    if (!resp.ok) return null;
    return (await resp.json()) as SyncWatchlistState;
  } catch {
    return null;
  }
}
