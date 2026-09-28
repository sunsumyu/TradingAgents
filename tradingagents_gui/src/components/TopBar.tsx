import { CandlestickChart, LayoutDashboard, ArrowLeft } from "lucide-react";
import { useConfigStore } from "../stores/useConfigStore";
import { useAnalysisStore } from "../stores/useAnalysisStore";

export default function TopBar() {
  const backendOnline = useConfigStore((s) => s.backendOnline);
  const backendStatus = useConfigStore((s) => s.backendStatus);
  const phase = useAnalysisStore((s) => s.phase);
  const navigateTo = useAnalysisStore((s) => s.navigateTo);

  const dotClass = backendOnline
    ? "bg-up shadow-glow-green"
    : backendStatus === "connecting"
      ? "bg-warn animate-pulse"
      : "bg-text-muted";

  const label = backendOnline
    ? "已连接"
    : backendStatus === "connecting"
      ? "连接中…"
      : "未连接";

  return (
    <header className="h-10 shrink-0 glass border-b border-line flex items-center px-5 relative z-10">
      <div className="flex items-center gap-2.5">
        <div className="p-1.5 rounded-lg bg-accent/10">
          <CandlestickChart size={16} className="text-accent-light" />
        </div>
        <span className="text-[13px] font-bold tracking-tight">
          <span className="text-text-primary">Trading</span>
          <span className="gradient-text-accent">Agents</span>
        </span>
      </div>
      <div className="ml-auto flex items-center text-[11px] text-text-secondary gap-2">
        {phase === "market_overview" && (
          <button
            onClick={() => navigateTo("config")}
            className="flex items-center gap-1 px-2 py-1 rounded bg-accent/10 text-accent-light hover:bg-accent/20 transition-colors"
            title="返回主页"
          >
            <ArrowLeft size={13} />
            <span>返回</span>
          </button>
        )}
        <button
          onClick={() => navigateTo(phase === "market_overview" ? "config" : "market_overview")}
          className="flex items-center gap-1 px-2 py-1 rounded hover:bg-white/5 transition-colors text-text-secondary hover:text-text-primary"
          title={phase === "market_overview" ? "返回主页" : "市场全景图"}
        >
          <LayoutDashboard size={13} />
          <span>{phase === "market_overview" ? "市场" : "市场"}</span>
        </button>
        <span className={`dot ${dotClass}`} />
        <span>{label}</span>
      </div>
    </header>
  );
}
