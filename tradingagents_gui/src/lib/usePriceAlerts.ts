/**
 * usePriceAlerts — manage price alerts and fire Tauri notifications.
 *
 * - Persists alerts in localStorage
 * - Accepts the realtime price map from useRealtimePrices
 * - Checks each enabled alert against current price
 * - Fires a Tauri desktop notification on first trigger, marks alert as triggered
 * - Provides CRUD helpers for the alert management UI
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { isPermissionGranted, requestPermission, sendNotification } from "@tauri-apps/plugin-notification";
import type { RealtimePrice, PriceAlert } from "./types";
import { ALERTS_STORAGE_KEY } from "./types";

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

export function usePriceAlerts(prices: Map<string, RealtimePrice>) {
  const [alerts, setAlerts] = useState<PriceAlert[]>(loadAlerts);
  const notifGranted = useRef(false);
  const firedRef = useRef<Set<string>>(new Set());

  // Persist on change
  useEffect(() => {
    saveAlerts(alerts);
  }, [alerts]);

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

  // Check alerts against prices
  useEffect(() => {
    if (prices.size === 0 || alerts.length === 0) return;

    for (const alert of alerts) {
      if (!alert.enabled || alert.triggered) continue;
      if (firedRef.current.has(alert.id)) continue;

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
            title: `价格预警 — ${alert.ticker}`,
            body: `${alert.name ?? alert.ticker} 已${condText} ${alert.target_price}，当前 ${quote.price}`,
          });
        }

        // Mark as triggered in state
        setAlerts((prev) =>
          prev.map((a) => (a.id === alert.id ? { ...a, triggered: true } : a)),
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
        prev.map((a) => (a.triggered && newFired.has(a.id) ? a : { ...a, triggered: false })),
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
      };
      setAlerts((prev) => [...prev, alert]);
    },
    [],
  );

  const removeAlert = useCallback((id: string) => {
    setAlerts((prev) => prev.filter((a) => a.id !== id));
    firedRef.current.delete(id);
  }, []);

  const toggleAlert = useCallback((id: string) => {
    setAlerts((prev) =>
      prev.map((a) => {
        if (a.id !== id) return a;
        const next = { ...a, enabled: !a.enabled };
        if (!next.enabled) firedRef.current.delete(id);
        return next;
      }),
    );
  }, []);

  const clearTriggered = useCallback(() => {
    firedRef.current.clear();
    setAlerts((prev) => prev.map((a) => ({ ...a, triggered: false })));
  }, []);

  return { alerts, addAlert, removeAlert, toggleAlert, clearTriggered };
}
