import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { api } from "./lib/api";
import {
  DEFAULT_CONFIG,
  latestTradingDate,
  loadConfig,
  saveConfig,
  type AnalysisConfig,
  type ProgressEvent,
  type ReportResponse,
} from "./lib/types";
import TopBar from "./components/TopBar";
import ConfigPanel from "./components/ConfigPanel";
import ProgressPanel from "./components/ProgressPanel";

const ReportPanel = lazy(() => import("./components/ReportPanel"));

type Phase = "config" | "analyzing" | "report" | "error";

/** How many times to retry the health check on mount before declaring failure. */
const HEALTH_RETRIES = 6;
/** Delay between retries in ms. */
const HEALTH_RETRY_DELAY = 2000;

export default function App() {
  const [config, setConfig] = useState<AnalysisConfig>(() => loadConfig());
  // Always start at config — never restore a stale phase from a previous session
  const [phase, setPhase] = useState<Phase>("config");
  const [backendOnline, setBackendOnline] = useState(false);
  /**
   * "connecting"  — first mount, still retrying health checks.
   * "failed"      — all retries exhausted, backend truly unreachable.
   * "idle"        — user manually clicked 测试连接 (no auto-retry needed).
   *
   * When `connecting`, the UI shows a blue info banner ("正在连接后端…") and
   * the TopBar shows a pulsing amber dot.  Only after all retries are
   * exhausted does it flip to "failed" and show the yellow warning banner.
   */
  const [backendStatus, setBackendStatus] = useState<"connecting" | "failed" | "idle">("connecting");
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [streamingText, setStreamingText] = useState("");
  const [streamingAgent, setStreamingAgent] = useState("");
  const taskIdRef = useRef<string | null>(null);
  const closeStreamRef = useRef<(() => void) | null>(null);

  // ── Load config from YAML on mount ──────────────────────────────────────
  useEffect(() => {
    const loadYamlConfig = async () => {
      try {
        const result = await api.loadConfig();
        if (result.config) {
          // Merge YAML config with defaults, always use today's date
          const merged = { ...DEFAULT_CONFIG, ...result.config, date: latestTradingDate() } as AnalysisConfig;
          setConfig(merged);
          saveConfig(merged); // Also save to localStorage
        }
      } catch (e) {
        console.log("No YAML config found, using defaults");
      }
    };
    loadYamlConfig();
  }, []);

  // ── Config persistence ────────────────────────────────────────────────────
  const handleConfigChange = useCallback((next: AnalysisConfig) => {
    setConfig(next);
    saveConfig(next);
    // Also save to YAML
    api.saveConfig(next as unknown as Record<string, unknown>).catch(console.error);
  }, []);

  // ── Health check (auto-retry on mount + manual) ────────────────────────
  const checkHealth = useCallback(async () => {
    const ok = await api.healthCheck();
    setBackendOnline(ok);
    return ok;
  }, []);

  // Auto-retry on mount: the backend may still be importing modules when the
  // GUI launches.  Retry up to HEALTH_RETRIES times before giving up.
  useEffect(() => {
    let cancelled = false;
    let attempt = 0;

    const tryConnect = async () => {
      while (attempt < HEALTH_RETRIES && !cancelled) {
        attempt++;
        setBackendStatus("connecting");
        const ok = await api.healthCheck();
        if (cancelled) return;
        if (ok) {
          setBackendOnline(true);
          setBackendStatus("idle");
          return;
        }
        // Not yet — wait before retrying.
        await new Promise((r) => setTimeout(r, HEALTH_RETRY_DELAY));
      }
      // All retries exhausted.
      if (!cancelled) {
        setBackendOnline(false);
        setBackendStatus("failed");
      }
    };

    tryConnect();
    return () => { cancelled = true; };
  }, [checkHealth]);

  // ── Start analysis ────────────────────────────────────────────────────────
  const startAnalysis = useCallback(async () => {
    saveConfig(config);
    setEvents([]);
    setError("");
    setPhase("analyzing");
    try {
      const resp = await api.startAnalysis(config);
      taskIdRef.current = resp.task_id;

      // Open SSE stream
      setStreamingText("");
      setStreamingAgent("");
      closeStreamRef.current?.();
      closeStreamRef.current = api.openProgressStream(
        resp.task_id,
        (ev) => {
          setEvents((prev) => [...prev.slice(-199), ev]);
          // Clear streaming text on agent switch
          if (ev.status === "in_progress" && ev.agent !== "System") {
            setStreamingAgent((prev) => {
              if (prev !== ev.agent) setStreamingText("");
              return ev.agent;
            });
          }
        },
        () => pollReport(resp.task_id),
        (msg) => {
          setError(msg);
          setPhase("error");
        },
        (agent, token) => {
          setStreamingAgent(agent);
          setStreamingText((prev) => prev + token);
        },
      );
    } catch (e) {
      // A TypeError from fetch() means the request never reached the backend
      // (connection refused / server down) — the raw "Failed to fetch" message
      // is cryptic, so surface an actionable hint instead.
      const msg =
        e instanceof TypeError
          ? "无法连接后端服务（127.0.0.1:8420）。请运行 `python start_gui.py` 启动后端后再试。"
          : e instanceof Error
            ? e.message
            : String(e);
      setError(msg);
      setPhase("error");
    }
  }, [config]);

  // ── Poll final report (up to 20 min) ─────────────────────────────────────
  const pollReport = useCallback(async (taskId: string) => {
    for (let i = 0; i < 240; i++) {
      try {
        const r = await api.getReport(taskId);
        setReport(r);
        setPhase("report");
        return;
      } catch (e) {
        if (e instanceof Error && e.message === "Report not ready yet") {
          await new Promise((res) => setTimeout(res, 5000));
          continue;
        }
        setError(e instanceof Error ? e.message : String(e));
        setPhase("error");
        return;
      }
    }
    setError("分析超时：后端在 20 分钟内未完成，请检查后端日志");
    setPhase("error");
  }, []);

  // ── Cancellation (local only, like the Rust GUI) ─────────────────────────
  const cancelAnalysis = useCallback(() => {
    closeStreamRef.current?.();
    closeStreamRef.current = null;
    taskIdRef.current = null;
    setPhase("config");
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => closeStreamRef.current?.();
  }, []);

  return (
    <div className="h-full flex flex-col">
      <TopBar backendOnline={backendOnline} backendStatus={backendStatus} />

      {phase === "config" && (
        <ConfigPanel
          config={config}
          onChange={handleConfigChange}
          backendOnline={backendOnline}
          backendStatus={backendStatus}
          onTestConnection={checkHealth}
          onAnalyze={startAnalysis}
          onMarketData={() => { /* TODO: implement market data panel */ }}
          onFetchModels={async (provider, proxyUrl, apiKey) => {
            const m = await api.getModels(provider, proxyUrl, apiKey);
            return { quick: m.quick, deep: m.deep };
          }}
        />
      )}

      {phase === "analyzing" && (
        <ProgressPanel
          ticker={config.ticker}
          date={config.date}
          events={events}
          selectedAnalysts={config.analysts}
          onCancel={cancelAnalysis}
          streamingText={streamingText}
          streamingAgent={streamingAgent}
        />
      )}

      {phase === "report" && report && (
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-text-secondary">加载中...</div>}>
          <ReportPanel
            ticker={report.ticker}
            signal={report.signal}
            reportMd={report.report_md}
            sections={report.sections}
            chartData={report.chart_data}
            onBack={() => setPhase("config")}
          />
        </Suspense>
      )}

      {phase === "error" && (
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <div className="text-down text-[14px]">{error}</div>
          <button className="btn-ghost" onClick={() => setPhase("config")}>
            返回配置
          </button>
        </div>
      )}
    </div>
  );
}
