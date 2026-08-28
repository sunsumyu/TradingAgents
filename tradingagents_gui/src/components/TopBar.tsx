import { CandlestickChart } from "lucide-react";
import { useConfigStore } from "../stores/useConfigStore";

export default function TopBar() {
  const backendOnline = useConfigStore((s) => s.backendOnline);
  const backendStatus = useConfigStore((s) => s.backendStatus);

  const dotClass = backendOnline
    ? "bg-up"
    : backendStatus === "connecting"
      ? "bg-warn animate-pulse"
      : "bg-text-muted";

  const label = backendOnline
    ? "已连接"
    : backendStatus === "connecting"
      ? "连接中…"
      : "未连接";

  return (
    <header className="h-9 shrink-0 border-b border-line flex items-center px-4 bg-bg-secondary/60">
      <div className="flex items-center gap-2">
        <CandlestickChart size={15} className="text-accent" />
        <span className="text-[12px] font-medium text-text-primary">
          TradingAgents
        </span>
      </div>
      <div className="ml-auto flex items-center text-[11px] text-text-secondary">
        <span className={`dot ${dotClass}`} />
        {label}
      </div>
    </header>
  );
}
