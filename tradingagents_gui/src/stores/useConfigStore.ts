/**
 * useConfigStore — Zustand store for configuration, backend health, and models.
 *
 * Owns: config, backendOnline, backendStatus.
 * Replaces two useState hooks + health check logic lifted to App.tsx.
 */

import { create } from "zustand";
import { api } from "../lib/api";
import {
  DEFAULT_CONFIG,
  latestTradingDate,
  loadConfig as loadLocalConfig,
  saveConfig as saveLocalConfig,
  type AnalysisConfig,
} from "../lib/types";

/** How many times to retry the health check on mount before declaring failure. */
const HEALTH_RETRIES = 6;
/** Delay between retries in ms. */
const HEALTH_RETRY_DELAY = 2000;

interface ConfigState {
  config: AnalysisConfig;
  backendOnline: boolean;
  backendStatus: "connecting" | "failed" | "idle";
}

interface ConfigActions {
  updateConfig: (config: AnalysisConfig) => void;
  loadConfig: () => Promise<void>;
  testConnection: () => Promise<boolean>;
  connectWithRetry: () => Promise<void>;
  reset: () => void;
}

const INITIAL_STATE: ConfigState = {
  config: loadLocalConfig(),
  backendOnline: false,
  backendStatus: "connecting",
};

export const useConfigStore = create<ConfigState & ConfigActions>((set, get) => ({
  ...INITIAL_STATE,

  updateConfig: (next) => {
    set({ config: next });
    saveLocalConfig(next);
    api.saveConfig(next as unknown as Record<string, unknown>).catch(console.error);
  },

  loadConfig: async () => {
    let serverDate = "";
    try {
      serverDate = await api.getToday();
    } catch { /* ignore */ }

    try {
      const result = await api.loadConfig();
      if (result.config) {
        const merged = { ...DEFAULT_CONFIG, ...result.config, date: serverDate || latestTradingDate() } as AnalysisConfig;
        set({ config: merged });
        saveLocalConfig(merged);
        return;
      }
    } catch {
      // No YAML config found, using defaults
    }
    if (serverDate) {
      const prev = get().config;
      const next = { ...prev, date: serverDate };
      set({ config: next });
      saveLocalConfig(next);
    }
  },

  testConnection: async () => {
    const ok = await api.healthCheck();
    set({ backendOnline: ok, backendStatus: ok ? "idle" : "failed" });
    return ok;
  },

  connectWithRetry: async () => {
    let attempt = 0;
    set({ backendStatus: "connecting" });
    while (attempt < HEALTH_RETRIES) {
      attempt++;
      const ok = await api.healthCheck();
      if (ok) {
        set({ backendOnline: true, backendStatus: "idle" });
        return;
      }
      await new Promise((r) => setTimeout(r, HEALTH_RETRY_DELAY));
    }
    set({ backendOnline: false, backendStatus: "failed" });
  },

  reset: () => set(INITIAL_STATE),
}));
