/**
 * Alert sync helpers (ticket #12) - pure functions + tombstone queue.
 *
 * The GUI is local-first: alerts live in localStorage and evaluate
 * against the realtime price feed. When the backend is reachable, a
 * debounced PUT /api/alerts/sync pushes the full client state plus
 * deletion tombstones; the server merges (newer-wins-by-updated_at)
 * and returns the authoritative state.
 *
 * Condition mapping: the GUI only creates "above"/"below" price alerts;
 * the server's 7 condition types round-trip transparently (unknown
 * conditions render as their raw value and never evaluate locally).
 */

import type { PriceAlert } from "./types";

const BASE_URL = "http://127.0.0.1:8420";
const TOMBSTONES_KEY = "tradingagents_alert_tombstones";

// ── Server-facing types ──────────────────────────────────────────────────────

export interface ServerAlert {
  id: string;
  ticker: string;
  condition: string;
  threshold: number;
  indicator: string | null;
  message: string;
  enabled: boolean;
  triggered: boolean;
  created_at: number;
  triggered_at: number | null;
  updated_at: number;
}

export interface SyncPayload {
  alerts: ServerAlert[];
  deleted: { id: string; deleted_at: number }[];
}

export interface ServerAlertEvent {
  alert_id: string;
  ticker: string;
  condition: string;
  value: number | null;
  message: string;
  triggered_at: number;
}

// ── Condition mapping ────────────────────────────────────────────────────────

/** Map a local condition to the server's AlertCondition value. */
export function toServerCondition(condition: string): string {
  if (condition === "above") return "price_above";
  if (condition === "below") return "price_below";
  return condition;
}

/** Map a server AlertCondition value back to a local condition. */
export function fromServerCondition(condition: string): string {
  if (condition === "price_above") return "above";
  if (condition === "price_below") return "below";
  return condition;
}

// ── Payload construction (pure) ─────────────────────────────────────────────

/** Build the PUT /api/alerts/sync payload from local state + tombstones. */
export function buildSyncPayload(
  alerts: PriceAlert[],
  deleted: { id: string; deleted_at: number }[],
): SyncPayload {
  const now = Math.floor(Date.now() / 1000);
  return {
    alerts: alerts.map((a) => ({
      id: a.id,
      ticker: a.ticker,
      condition: toServerCondition(a.condition),
      threshold: a.target_price,
      indicator: null,
      message: "",
      enabled: a.enabled,
      triggered: a.triggered ?? false,
      created_at: a.created_at ? Math.floor(new Date(a.created_at).getTime() / 1000) : 0,
      triggered_at: null,
      updated_at: a.updated_at ?? now,
    })),
    deleted,
  };
}

/**
 * Convert server alerts back to local PriceAlerts, preserving local
 * display names by id (the server does not store names).
 */
export function fromServerAlerts(
  serverAlerts: ServerAlert[],
  prevAlerts: PriceAlert[],
): PriceAlert[] {
  const prevNames = new Map(prevAlerts.map((a) => [a.id, a.name ?? null]));
  return serverAlerts.map((s) => ({
    id: s.id,
    ticker: s.ticker,
    name: prevNames.get(s.id) ?? null,
    condition: fromServerCondition(s.condition),
    target_price: s.threshold,
    enabled: s.enabled,
    triggered: s.triggered,
    created_at: new Date(s.created_at * 1000).toISOString(),
    updated_at: s.updated_at,
  }));
}

// ── Tombstone queue (localStorage) ───────────────────────────────────────────

export interface AlertTombstone {
  id: string;
  deleted_at: number;
}

export function loadTombstones(): AlertTombstone[] {
  try {
    const raw = localStorage.getItem(TOMBSTONES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveTombstones(tombstones: AlertTombstone[]) {
  try {
    localStorage.setItem(TOMBSTONES_KEY, JSON.stringify(tombstones));
  } catch {
    // ignore persistence failures
  }
}

export function addTombstone(id: string): AlertTombstone[] {
  const next = [
    ...loadTombstones().filter((t) => t.id !== id),
    { id, deleted_at: Math.floor(Date.now() / 1000) },
  ];
  saveTombstones(next);
  return next;
}

// ── HTTP round-trips ─────────────────────────────────────────────────────────

/** PUT /api/alerts/sync - push local state, return merged server state. */
export async function syncAlerts(
  payload: SyncPayload,
): Promise<ServerAlert[] | null> {
  try {
    const resp = await fetch(`${BASE_URL}/api/alerts/sync`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(5000),
    });
    if (!resp.ok) return null;
    const data = (await resp.json()) as { alerts: ServerAlert[] };
    return data.alerts ?? [];
  } catch {
    return null; // offline / backend down - local-first continues
  }
}

/** GET /api/alerts/{id}/history - trigger history for one alert. */
export async function getAlertHistory(id: string): Promise<ServerAlertEvent[] | null> {
  try {
    const resp = await fetch(`${BASE_URL}/api/alerts/${encodeURIComponent(id)}/history`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!resp.ok) return null;
    return (await resp.json()) as ServerAlertEvent[];
  } catch {
    return null;
  }
}
