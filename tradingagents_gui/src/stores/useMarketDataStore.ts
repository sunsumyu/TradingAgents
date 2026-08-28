/**
 * useMarketDataStore — Zustand store for the market data view.
 *
 * Owns: data, isLoading, error for the /api/market-data endpoint.
 * Replaces two useState hooks lifted to App.tsx.
 */

import { create } from "zustand";
import { api } from "../lib/api";
import type { MarketDataResponse } from "../lib/types";

interface MarketDataState {
  data: MarketDataResponse | null;
  isLoading: boolean;
  error: string;
}

interface MarketDataActions {
  fetchMarketData: (ticker: string, date: string) => Promise<void>;
  reset: () => void;
}

const INITIAL_STATE: MarketDataState = {
  data: null,
  isLoading: false,
  error: "",
};

export const useMarketDataStore = create<MarketDataState & MarketDataActions>(
  (set) => ({
    ...INITIAL_STATE,

    fetchMarketData: async (ticker, date) => {
      set({ data: null, error: "", isLoading: true });
      try {
        const data = await api.getMarketData(ticker, date);
        set({ data });
      } catch (e) {
        set({ error: e instanceof Error ? e.message : String(e) });
      } finally {
        set({ isLoading: false });
      }
    },

    reset: () => set(INITIAL_STATE),
  }),
);
