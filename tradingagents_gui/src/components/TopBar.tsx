import { CandlestickChart } from "lucide-react";
import { useConfigStore } from "../stores/useConfigStore";

export default function TopBar() {
  const backendOnline = useConfigStore((s) => s.backendOnline);
  const backendStatus = useConfigStore((s) => s.backendStatus);

  const dotClass = backendOnline
    ? "bg-up shadow-[0_0_8px_rgba(8,153,129,0.7)]"
    : backendStatus === "connecting"
      ? "bg-warn animate-pulse shadow-[0_0_8px_rgba(214,168,70,0.6)]"
      : "bg-text-muted";

  const label = backendOnline
    ? "已连接"
    : backendStatus === "connecting"
      ? "连接中…"
      : "未连接";

  return (
    <header className="h-9 shrink-0 glass border-b border-line flex items-center px-4 relative z-10">
      <div className="flex items-center gap-2">
        <CandlestickChart size={15} className="text-accent drop-shadow-[0_0_6px_rgba(41,98,255,0.6)]" />
        <span className="text-[12px] font-semibold tracking-tight">
          <span className="text-text-primary">Trading</span>
          <span className="gradient-text-accent">Agents</span>
        </span>
      </div>
      <div className="ml-auto flex items-center text-[11px] text-text-secondary">
        <span className={`dot ${dotClass}`} />
        {label}
      </div>
    </header>
  );
}
