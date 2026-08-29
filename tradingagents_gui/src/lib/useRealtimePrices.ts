/**
 * useRealtimePrices - realtime watchlist quotes with transport fallback.
 *
 * Preferred transport: WebSocket (ws://127.0.0.1:8420/ws/realtime, server
 * pushes every ~3s). If the socket errors or closes without a clean exit,
 * the hook falls back to HTTP polling (POST /api/realtime-prices, 5s) and
 * retries the WebSocket 5 seconds later. Both adapters produce the same
 * {ticker -> RealtimePrice} snapshot, so consumers cannot tell which
 * transport is active - only the push cadence changes.
 *
 * Lifecycle rules (inherited from the polling v1 hook):
 *   - unmount stops everything and aborts the in-flight poll
 *   - a change in the ticker list resubscribes / restarts the poll cycle
 *   - transport failures are silent - the previous snapshot is kept
 */

import { useEffect, useState } from "react";
import { api } from "./api";
import type { RealtimePrice } from "./types";

const WS_URL = "ws://127.0.0.1:8420/ws/realtime";
const WS_RECONNECT_DELAY_MS = 5000;
export const REALTIME_POLL_INTERVAL_MS = 5000;

export function useRealtimePrices(tickers: string[], enabled: boolean = true) {
  const [prices, setPrices] = useState<Map<string, RealtimePrice>>(new Map());
  const tickersKey = [...tickers].sort().join(","); // stable identity for the effect

  useEffect(() => {
    if (!enabled || tickers.length === 0) return;

    let disposed = false;
    let ws: WebSocket | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let pollController: AbortController | null = null;
    let usingWebSocket = false;

    const applySnapshot = (data: Record<string, RealtimePrice>) => {
      if (disposed) return;
      setPrices(new Map(Object.entries(data)));
    };

    // ── HTTP polling fallback ────────────────────────────────────────────
    const pollOnce = async () => {
      if (disposed || usingWebSocket) return;
      pollController = new AbortController();
      try {
        const data = await api.getRealtimePrices(tickers, pollController.signal);
        if (!disposed && !usingWebSocket) applySnapshot(data);
      } catch {
        // silent degradation - keep the last snapshot
      }
    };

    const startPolling = () => {
      if (pollTimer || disposed || usingWebSocket) return;
      void pollOnce();
      pollTimer = setInterval(() => void pollOnce(), REALTIME_POLL_INTERVAL_MS);
    };

    const stopPolling = () => {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = null;
      pollController?.abort();
    };

    // ── WebSocket preferred transport ────────────────────────────────────
    const connectWebSocket = () => {
      if (disposed || usingWebSocket) return;
      try {
        ws = new WebSocket(WS_URL);
      } catch {
        scheduleReconnect();
        return;
      }

      ws.onopen = () => {
        if (disposed) return;
        usingWebSocket = true;
        stopPolling(); // seamless switch: keep showing pushed data only
        ws?.send(JSON.stringify({ tickers }));
      };

      ws.onmessage = (e) => {
        if (disposed) return;
        try {
          const data = JSON.parse(e.data);
          if (data && typeof data === "object") applySnapshot(data);
        } catch {
          /* malformed frame - ignore */
        }
      };

      // Called from onerror/onclose: degrade to polling now, retry the
      // socket after a delay.
      const fallback = () => {
        if (disposed) return;
        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
        usingWebSocket = false;
        ws = null;
        startPolling();
        scheduleReconnect();
      };

      ws.onclose = fallback;
      ws.onerror = () => {
        // onclose always fires after onerror; only degrade there.
      };
    };

    const scheduleReconnect = () => {
      if (reconnectTimer || disposed) return;
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectWebSocket();
      }, WS_RECONNECT_DELAY_MS);
    };

    // ── Start: try WebSocket first; while CONNECTING, poll so the first
    // paint does not wait for the handshake. If the socket opens, polling
    // stops (onopen). If it fails, polling simply continues.
    startPolling();
    connectWebSocket();

    return () => {
      disposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      stopPolling();
      if (ws) {
        // Prevent the fallback handler from restarting polling post-dispose.
        ws.onclose = null;
        ws.onerror = null;
        ws.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickersKey, enabled]);

  return prices;
}
