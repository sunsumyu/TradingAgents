/**
 * useAnalysisStore — Zustand store for the analysis lifecycle.
 *
 * Owns: phase, events, streaming text, report, error, task ID, checkpoint.
 * Replaces 7 useState + 2 useRef hooks lifted to App.tsx.
 * Manages SSE stream open/close and report polling internally.
 */

import { create } from "zustand";
import { api } from "../lib/api";
import type { AnalysisConfig, ProgressEvent, ReportResponse } from "../lib/types";

export type Phase =
  | "config"
  | "market_data"
  | "analyzing"
  | "report"
  | "error"
  | "screener"
  | "portfolio";

interface CheckpointInfo {
  has_checkpoint: boolean;
  step: number | null;
}

interface AnalysisState {
  phase: Phase;
  events: ProgressEvent[];
  streamingText: string;
  streamingAgent: string;
  report: ReportResponse | null;
  error: string;
  taskId: string | null;
  checkpointInfo: CheckpointInfo | null;
  /** Internal — not exposed to components, used for SSE cleanup. */
  _closeStream: (() => void) | null;
}

interface AnalysisActions {
  navigateTo: (phase: Phase) => void;
  startAnalysis: (config: AnalysisConfig, resume?: boolean) => Promise<void>;
  cancelAnalysis: () => void;
  fetchCheckpoint: (ticker: string) => Promise<void>;
  reset: () => void;
}

const INITIAL_STATE: AnalysisState = {
  phase: "config",
  events: [],
  streamingText: "",
  streamingAgent: "",
  report: null,
  error: "",
  taskId: null,
  checkpointInfo: null,
  _closeStream: null,
};

// ── Helpers ─────────────────────────────────────────────────────────────────

/** Poll the report endpoint up to 240 times (5 s apart = 20 min max). */
async function pollReport(
  taskId: string,
  set: (partial: Partial<AnalysisState>) => void,
) {
  for (let i = 0; i < 240; i++) {
    try {
      const r = await api.getReport(taskId);
      set({ report: r, phase: "report" });
      return;
    } catch (e) {
      if (e instanceof Error && e.message === "Report not ready yet") {
        await new Promise((res) => setTimeout(res, 5000));
        continue;
      }
      set({
        error: e instanceof Error ? e.message : String(e),
        phase: "error",
      });
      return;
    }
  }
  set({
    error: "分析超时：后端在 20 分钟内未完成，请检查后端日志",
    phase: "error",
  });
}

// ── Store ───────────────────────────────────────────────────────────────────

export const useAnalysisStore = create<AnalysisState & AnalysisActions>(
  (set, get) => ({
    ...INITIAL_STATE,

    navigateTo: (phase) => set({ phase }),

    startAnalysis: async (config, resume = false) => {
      // Close any previous stream
      get()._closeStream?.();

      set({
        events: [],
        error: "",
        phase: "analyzing",
        streamingText: "",
        streamingAgent: "",
        taskId: null,
        report: null,
      });

      try {
        const resp = await api.startAnalysis(config, resume);
        set({ taskId: resp.task_id });

        // Open SSE stream
        const close = api.openProgressStream(
          resp.task_id,
          (ev) => {
            set((s) => ({
              events: [...s.events.slice(-199), ev],
            }));
            // Clear streaming text on agent switch
            if (ev.status === "in_progress" && ev.agent !== "System") {
              const prev = get().streamingAgent;
              if (prev !== ev.agent) set({ streamingText: "" });
              set({ streamingAgent: ev.agent });
            }
          },
          () => pollReport(resp.task_id, set),
          (msg) => {
            set({ error: msg, phase: "error" });
          },
          (agent, token) => {
            set((s) => ({
              streamingAgent: agent,
              streamingText: s.streamingText + token,
            }));
          },
        );

        set({ _closeStream: close });
      } catch (e) {
        const msg =
          e instanceof TypeError
            ? "无法连接后端服务（127.0.0.1:8420）。请运行 `python start_gui.py` 启动后端后再试。"
            : e instanceof Error
              ? e.message
              : String(e);
        set({ error: msg, phase: "error" });
      }
    },

    cancelAnalysis: () => {
      get()._closeStream?.();
      set({
        phase: "config",
        _closeStream: null,
        taskId: null,
      });
    },

    fetchCheckpoint: async (ticker) => {
      try {
        const info = await api.getCheckpoint(ticker);
        set({ checkpointInfo: info });
      } catch {
        set({ checkpointInfo: null });
      }
    },

    reset: () => {
      get()._closeStream?.();
      set({ ...INITIAL_STATE, _closeStream: null });
    },
  }),
);
