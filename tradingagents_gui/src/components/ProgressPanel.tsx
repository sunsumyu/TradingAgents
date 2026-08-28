import { Fragment, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { Card, ProgressBar, Spinner } from "./ui";
import { useAnalysisStore } from "../stores/useAnalysisStore";

// ── Team definitions (mirrors the Rust GUI's AGENT_TEAMS) ───────────────────────

const TEAMS: { name: string; agents: [string, string][] }[] = [
  {
    name: "分析师团队",
    agents: [
      ["market", "Market Analyst"],
      ["social", "Sentiment Analyst"],
      ["news", "News Analyst"],
      ["fundamentals", "Fundamentals Analyst"],
    ],
  },
  {
    name: "研究团队",
    agents: [
      ["research", "Bull vs Bear Debate"],
      ["research_manager", "Research Manager"],
    ],
  },
  { name: "交易团队", agents: [["trader", "Trader"]] },
  { name: "风控团队", agents: [["risk", "Risk Management"]] },
  { name: "投资组合经理", agents: [["portfolio", "Portfolio Manager"]] },
];

// Normalise backend agent names back to team keys (mirrors build_map in Rust).
function agentKey(name: string): string {
  switch (name) {
    case "Market Analyst":
      return "market";
    case "Sentiment Analyst":
      return "social";
    case "News Analyst":
      return "news";
    case "Fundamentals Analyst":
      return "fundamentals";
    case "Research Manager":
      return "research_manager";
    case "Bull vs Bear Debate":
    case "Bull Researcher":
    case "Bear Researcher":
      return "research";
    case "Trader":
      return "trader";
    case "Risk Management":
    case "Aggressive Analyst":
    case "Conservative Analyst":
    case "Neutral Analyst":
      return "risk";
    case "Portfolio Manager":
    case "Final Decision":
      return "portfolio";
    default:
      return name;
  }
}

function statusColor(status: string): string {
  switch (status) {
    case "completed":
      return "text-up";
    case "in_progress":
      return "text-accent";
    case "error":
      return "text-down";
    default:
      return "text-text-muted";
  }
}

function statusIcon(status: string) {
  switch (status) {
    case "completed":
      return "✓";
    case "in_progress":
      return "●";
    case "error":
      return "✗";
    default:
      return "○";
  }
}

interface Props {
  ticker: string;
  date: string;
  selectedAnalysts: string[];
}

export default function ProgressPanel({
  ticker,
  date,
  selectedAnalysts,
}: Props) {
  const events = useAnalysisStore((s) => s.events);
  const streamingText = useAnalysisStore((s) => s.streamingText);
  const streamingAgent = useAnalysisStore((s) => s.streamingAgent);
  const cancelAnalysis = useAnalysisStore((s) => s.cancelAnalysis);
  const [elapsed, setElapsed] = useState("0:00");
  const logRef = useRef<HTMLDivElement>(null);

  // Elapsed timer
  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => {
      const s = Math.floor((Date.now() - start) / 1000);
      setElapsed(`${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`);
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [events]);

  // status map: agentKey -> {status, message}
  const statusMap = new Map<string, { status: string; message: string }>();
  for (const ev of events) {
    statusMap.set(agentKey(ev.agent), { status: ev.status, message: ev.message });
  }

  // Overall progress: teams where all agents completed / total teams
  const completedTeams = TEAMS.filter((t) =>
    t.agents.every(([k]) => statusMap.get(k)?.status === "completed"),
  ).length;
  const progress = completedTeams / TEAMS.length;

  // Log lines
  const logs = events
    .map((ev) => `[${ev.timestamp.slice(11, 19)}] ${ev.agent} | ${ev.status} — ${ev.message}`)
    .reverse()
    .slice(0, 25);

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-8 py-6">
          {/* Header */}
          <div className="flex items-baseline gap-3 mb-4">
            <h1 className="text-[22px] font-semibold text-text-primary">{ticker}</h1>
            <span className="text-[12px] text-text-secondary">{date}</span>
            <span className="ml-auto text-[12px] text-text-muted">
              {elapsed}
            </span>
          </div>

          <div className="mb-6">
            <ProgressBar value={progress} text={`${Math.round(progress * 100)}%`} />
          </div>

          {/* Agent teams */}
          <div className="space-y-3">
            {TEAMS.map((team) => {
              const agents =
                team.name === "分析师团队"
                  ? team.agents.filter(([k]) => selectedAnalysts.includes(k))
                  : team.agents;
              if (agents.length === 0) return null;

              const allDone = agents.every(
                ([k]) => statusMap.get(k)?.status === "completed",
              );
              const anyActive = agents.some(
                ([k]) => statusMap.get(k)?.status === "in_progress",
              );
              const barColor = allDone
                ? "bg-up"
                : anyActive
                  ? "bg-accent"
                  : "bg-line";

              return (
                <Card key={team.name} className="!p-0 overflow-hidden">
                  <div className="flex">
                    <div className={`w-[3px] shrink-0 ${barColor}`} />
                    <div className="flex-1 p-3">
                      <div className="text-[12px] font-medium text-text-primary mb-2">
                        {team.name}
                      </div>
                      {agents.map(([key, label]) => {
                        const st = statusMap.get(key)?.status ?? "pending";
                        const msg = statusMap.get(key)?.message;
                        return (
                          <Fragment key={key}>
                            <div className="flex items-center gap-2 py-0.5 text-[11px]">
                              <span className={`w-3 text-center ${statusColor(st)}`}>
                                {st === "in_progress" ? <Spinner className="w-2.5 h-2.5" /> : statusIcon(st)}
                              </span>
                              <span
                                className={
                                  st === "completed"
                                    ? "text-text-muted"
                                    : st === "in_progress"
                                      ? "text-accent"
                                      : "text-text-secondary"
                                }
                              >
                                {label}
                              </span>
                              {msg && (
                                <span className="text-text-muted truncate ml-2">
                                  {msg}
                                </span>
                              )}
                            </div>
                            {st === "in_progress" && streamingAgent === key && streamingText && (
                              <div className="ml-5 mb-1 max-h-32 overflow-y-auto rounded bg-surface-elevated/60 p-2 text-[10px] leading-relaxed text-text-muted font-mono whitespace-pre-wrap">
                                {streamingText}
                                <span className="animate-pulse text-accent">▌</span>
                              </div>
                            )}
                          </Fragment>
                        );
                      })}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      </div>

      {/* Log viewer */}
      <div className="border-t border-line bg-bg-secondary/50">
        <div className="max-w-4xl mx-auto px-8 py-3">
          <div className="text-[10px] uppercase tracking-wider text-text-muted mb-1.5">
            Log
          </div>
          <div ref={logRef} className="h-28 overflow-y-auto font-mono text-[10px] leading-relaxed text-text-muted">
            {logs.map((l, i) => (
              <div key={i}>{l}</div>
            ))}
          </div>
          <div className="flex justify-end mt-2">
            <button className="btn-danger" onClick={cancelAnalysis}>
              <X size={12} />
              取消分析
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
