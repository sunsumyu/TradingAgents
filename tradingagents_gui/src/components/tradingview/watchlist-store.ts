/**
 * Watchlist group persistence — localStorage-backed store shared by
 * WatchlistPanel (UI) and any other consumer that needs the grouped list.
 *
 * Storage key: "tradingagents_watchlist_groups" (per phase-4 spec).
 * Legacy flat lists under "tradingagents_watchlist" are migrated on first
 * load; the legacy key is left untouched as a backup.
 */

import type { WatchlistGroup, WatchlistItem } from "./types";

export const WATCHLIST_GROUPS_KEY = "tradingagents_watchlist_groups";
export const DEFAULT_GROUP_NAME = "自选股";

let idCounter = 0;
function newGroupId(): string {
  idCounter += 1;
  return `g_${Date.now().toString(36)}_${idCounter}`;
}

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
