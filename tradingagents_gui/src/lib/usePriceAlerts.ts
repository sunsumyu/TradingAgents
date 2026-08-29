/**
 * usePriceAlerts - manage price alerts and fire Tauri notifications.
 *
 * Local-first (ticket #12): alerts persist in localStorage and evaluate
 * against the realtime price feed offline. When the backend is
 * reachable, every semantic change bumps ``updated_at`` and schedules a
 * debounced PUT /api/alerts/sync (newer-wins merge + deletion
 * tombstones); the merged server state replaces local state without
 * firing notifications (the local price watcher is the only
 * notification source, so the server channel can't duplicate pops).
 *
 * - Accepts the realtime price map from useRealtimePrices
 * - Checks each enabled above/below alert against current price
 * - Fires a Tauri desktop notification on first trigger, marks alert as triggered
 * - Provides CRUD helpers for the alert management UI
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { isPermissionGranted, requestPermission, sendNotification } from "@tauri-apps/plugin-notification";
import type { RealtimePrice, PriceAlert } from "./types";
import { ALERTS_STORAGE_KEY } from "./types";
import {
  addTombstone,
  buildSyncPayload,
  fromServerAlerts,
  loadTombstones,
  saveTombstones,
  syncAlerts,
} from "./alert-sync";

function loadAlerts(): PriceAlert[] {
  try {
    const raw = localStorage.getItem(ALERTS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveAlerts(alerts: PriceAlert[]) {
  localStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(alerts));
}

function uid(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

function nowSec(): number {
  return Math.floor(Date.now() / 1000);
}

/** Bump updated_at on one alert (marks it as locally changed). */
function touched(alert: PriceAlert): PriceAlert {
  return { ...alert, updated_at: nowSec() };
}

export function usePriceAlerts(prices: Map<string, RealtimePrice>) {
  const [alerts, setAlerts] = useState<PriceAlert[]>(loadAlerts);
  const notifGranted = useRef(false);
  const firedRef = useRef<Set<string>>(new Set());
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const skipSyncRef = useRef(false);
  const tombstonesRef = useRef(loadTombstones());

  // Check notification permission once
  useEffect(() => {
    (async () => {
      let granted = await isPermissionGranted();
      if (!granted) {
        const result = await requestPermission();
        granted = result === "granted";
      }
      notifGranted.current = granted;
    })();
  }, []);

  // ── Persist + debounced server sync ────────────────────────────────────
  useEffect(() => {
    saveAlerts(alerts);

    // Server-originated updates (mount merge / sync response) must not
    // loop back into another sync.
    if (skipSyncRef.current) {
      skipSyncRef.current = false;
      return;
    }

    if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    syncTimerRef.current = setTimeout(async () => {
      const payload = buildSyncPayload(alerts, tombstonesRef.current);
      const serverAlerts = await syncAlerts(payload);
      if (serverAlerts !== null) {
        // Sync succeeded - the tombstones have been applied server-side
        tombstonesRef.current = [];
        saveTombstones([]);
        skipSyncRef.current = true;
        setAlerts(fromServerAlerts(serverAlerts, alerts));
      }
      // On failure the tombstone queue stays queued for the next change
    }, 500);

    return () => {
      if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    };
  }, [alerts]);

  // ── Initial sync on mount (pull server state, merge) ──────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const payload = buildSyncPayload(loadAlerts(), tombstonesRef.current);
      const serverAlerts = await syncAlerts(payload);
      if (!cancelled && serverAlerts !== null) {
        tombstonesRef.current = [];
        saveTombstones([]);
        skipSyncRef.current = true;
        setAlerts(fromServerAlerts(serverAlerts, loadAlerts()));
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Check alerts against prices
  useEffect(() => {
    if (prices.size === 0 || alerts.length === 0) return;

    for (const alert of alerts) {
      if (!alert.enabled || alert.triggered) continue;
      if (firedRef.current.has(alert.id)) continue;
      // Only the local price conditions evaluate here; server-only
      // conditions (indicator/cross/volume) wait for the backend check.
      if (alert.condition !== "above" && alert.condition !== "below") continue;

      const quote = prices.get(alert.ticker);
      if (!quote) continue;

      const crossed =
        (alert.condition === "above" && quote.price >= alert.target_price) ||
        (alert.condition === "below" && quote.price <= alert.target_price);

      if (crossed) {
        firedRef.current.add(alert.id);

        // Fire Tauri notification
        if (notifGranted.current) {
          const condText = alert.condition === "above" ? "突破" : "跌破";
          sendNotification({
            title: `价格预警 - ${alert.ticker}`,
            body: `${alert.name ?? alert.ticker} 已${condText} ${alert.target_price}，当前 ${quote.price}`,
          });
        }

        // Mark as triggered in state (bumps updated_at -> syncs to server)
        setAlerts((prev) =>
          prev.map((a) => (a.id === alert.id ? touched({ ...a, triggered: true }) : a)),
        );
      }
    }
  }, [prices, alerts]);

  // Reset triggered status when price moves back away from threshold
  useEffect(() => {
    if (firedRef.current.size === 0) return;

    let changed = false;
    const newFired = new Set(firedRef.current);

    for (const alert of alerts) {
      if (!alert.triggered || !alert.enabled) continue;
      if (alert.condition !== "above" && alert.condition !== "below") continue;
      const quote = prices.get(alert.ticker);
      if (!quote) continue;

      // Reset if price moved back with some hysteresis (1% buffer)
      const buffer = alert.target_price * 0.01;
      const safe =
        (alert.condition === "above" && quote.price < alert.target_price - buffer) ||
        (alert.condition === "below" && quote.price > alert.target_price + buffer);

      if (safe) {
        newFired.delete(alert.id);
        changed = true;
      }
    }

    if (changed) {
      firedRef.current = newFired;
      setAlerts((prev) =>
        prev.map((a) =>
          a.triggered && !newFired.has(a.id) ? touched({ ...a, triggered: false }) : a,
        ),
      );
    }
  }, [prices, alerts]);

  const addAlert = useCallback(
    (ticker: string, name: string | null, condition: "above" | "below", targetPrice: number) => {
      const alert: PriceAlert = {
        id: uid(),
        ticker: ticker.toUpperCase(),
        name,
        condition,
        target_price: targetPrice,
        enabled: true,
        triggered: false,
        created_at: new Date().toISOString(),
        updated_at: nowSec(),
      };
      setAlerts((prev) => [...prev, alert]);
    },
    [],
  );

  const removeAlert = useCallback((id: string) => {
    tombstonesRef.current = addTombstone(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
    firedRef.current.delete(id);
  }, []);

  const toggleAlert = useCallback((id: string) => {
    setAlerts((prev) =>
      prev.map((a) => {
        if (a.id !== id) return a;
        const next = touched({ ...a, enabled: !a.enabled });
        if (!next.enabled) firedRef.current.delete(id);
        return next;
      }),
    );
  }, []);

  const updateAlert = useCallback((id: string, targetPrice: number) => {
    setAlerts((prev) =>
      prev.map((a) =>
        a.id === id && a.target_price !== targetPrice
          ? touched({ ...a, target_price: targetPrice })
          : a,
      ),
    );
  }, []);

  const clearTriggered = useCallback(() => {
    firedRef.current.clear();
    setAlerts((prev) => prev.map((a) => (a.triggered ? touched({ ...a, triggered: false }) : a)));
  }, []);

  return { alerts, addAlert, removeAlert, toggleAlert, updateAlert, clearTriggered };
}
