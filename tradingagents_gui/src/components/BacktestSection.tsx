/**
 * BacktestSection - report-page entry for backtesting the current decision
 * (ticket #6).
 *
 * Runs the 1/3/5/10-day holding ladder in parallel, then shows a metric
 * comparison table plus a normalized cumulative-return chart. When the
 * backend answers 503 (akquant missing), shows install guidance instead of
 * an error crash.
 */

import { useCallback, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { FlaskConical, Loader2, PackageX, X } from "lucide-react";

import { api } from "../lib/api";
import type { BacktestResponse } from "../lib/types";
import { CHART_COLORS } from "../lib/echarts-theme";
import {
  backtestWindow,
  formatPct,
  formatRatio,
  HOLDING_DAY_OPTIONS,
  isInstallGuidanceError,
  normalizeCurve,
  signalToDecision,
} from "../lib/backtest-utils";

interface Props {
  ticker: string;
  signal: string;
  /** Analysis date (YYYY-MM-DD) from the config store. */
  analysisDate: string;
  onClose: () => void;
}

type ResultsByDays = Record<number, BacktestResponse>;

const SERIES_COLORS = [
  CHART_COLORS.blue,
  CHART_COLORS.green,
  CHART_COLORS.orange,
  CHART_COLORS.purple,
];

const METRIC_ROWS: {
  key: keyof BacktestResponse;
  label: string;
  kind: "pct" | "ratio" | "int";
}[] = [
  { key: "total_return", label: "总收益", kind: "pct" },
  { key: "annual_return", label: "年化收益", kind: "pct" },
  { key: "sharpe_ratio", label: "Sharpe", kind: "ratio" },
  { key: "max_drawdown", label: "最大回撤", kind: "pct" },
  { key: "win_rate", label: "胜率", kind: "pct" },
  { key: "total_trades", label: "交易数", kind: "int" },
];

function fmtCell(value: unknown, kind: "pct" | "ratio" | "int"): string {
  if (value == null) return "-";
  if (kind === "pct") return formatPct(value as number | null);
  if (kind === "ratio") return formatRatio(value as number | null);
  return String(value);
}

export default function BacktestSection({
  ticker,
  signal,
  analysisDate,
  onClose,
}: Props) {
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState<ResultsByDays>({});
  const [error, setError] = useState("");
  const [installHint, setInstallHint] = useState(false);

  const decision = signalToDecision(signal);
  const hasResults = Object.keys(results).length > 0;

  const runAll = useCallback(async () => {
    if (!ticker || !analysisDate) return;
    setRunning(true);
    setError("");
    setInstallHint(false);
    try {
      const responses = await Promise.all(
        HOLDING_DAY_OPTIONS.map(async (days) => {
          const window = backtestWindow(analysisDate, days);
          const resp = await api.runBacktest({
            ticker,
            start_date: window.start,
            end_date: window.end,
            decision,
            holding_days: days,
          });
          return [days, resp] as const;
        }),
      );
      setResults(Object.fromEntries(responses));
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (isInstallGuidanceError(msg)) {
        setInstallHint(true);
      } else {
        setError(msg);
      }
    } finally {
      setRunning(false);
    }
  }, [ticker, analysisDate, decision]);

  const chartOption = useMemo(() => {
    const series = Object.entries(results)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([daysStr, resp], i) => {
        const days = Number(daysStr);
        return {
          name: `持有 ${days} 天`,
          type: "line" as const,
          data: normalizeCurve(resp.equity_curve),
          lineStyle: { width: 1.6, color: SERIES_COLORS[i % SERIES_COLORS.length] },
          itemStyle: { color: SERIES_COLORS[i % SERIES_COLORS.length] },
          symbol: "none",
          connectNulls: true,
        };
      });
    return {
      animation: true,
      animationDuration: 500,
      tooltip: {
        trigger: "axis",
        valueFormatter: (v: unknown) =>
          typeof v === "number" ? `${v.toFixed(2)}%` : String(v ?? "-"),
      },
      legend: {
        textStyle: { color: "#787B86", fontSize: 11 },
        top: 0,
      },
      grid: { left: 60, right: 20, top: 30, bottom: 30 },
      xAxis: {
        type: "category",
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: { color: "#787B86", fontSize: 10 },
      },
      yAxis: {
        type: "value",
        axisLine: { lineStyle: { color: "#363A45" } },
        axisLabel: {
          color: "#787B86",
          fontSize: 10,
          formatter: (v: number) => `${v.toFixed(0)}%`,
        },
        splitLine: { lineStyle: { color: "#2A2E39" } },
      },
      series,
    };
  }, [results]);

  const sortedDays = useMemo(
    () => Object.keys(results).map(Number).sort((a, b) => a - b),
    [results],
  );

  return (
    <div className="border-b border-line bg-bg-secondary">
      <div className="flex items-center gap-2 px-5 h-9">
        <FlaskConical size={13} className="text-text-secondary" />
        <span className="text-[12px] font-medium text-text-primary">
          回测此决策
        </span>
        <span className="text-[11px] text-text-muted">
          {ticker} · {decision} · 分析日 {analysisDate || "-"}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button
            className="btn-primary !h-6 !text-[11px] flex items-center gap-1"
            onClick={runAll}
            disabled={running || !ticker || !analysisDate}
          >
            {running ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <FlaskConical size={11} />
            )}
            {running ? "回测中..." : hasResults ? "重新回测" : "开始回测"}
          </button>
          <button
            className="p-1.5 hover:bg-bg-hover rounded transition-colors"
            onClick={onClose}
            title="收起"
          >
            <X size={12} className="text-text-secondary" />
          </button>
        </div>
      </div>

      {/* Install guidance (503 - akquant missing) */}
      {installHint && (
        <div className="mx-5 mb-3 p-3 rounded border border-line bg-bg-surface flex items-start gap-2">
          <PackageX size={14} className="text-text-secondary mt-0.5 shrink-0" />
          <div className="text-[11px] leading-5 text-text-secondary">
            <div className="text-text-primary font-medium mb-1">
              回测引擎未安装
            </div>
            回测功能依赖 akquant（Rust 内核）。请在后端环境中执行：
            <code className="mx-1 px-1.5 py-0.5 rounded bg-bg-hover text-text-primary">
              pip install "tradingagents[backtest]"
            </code>
            或
            <code className="mx-1 px-1.5 py-0.5 rounded bg-bg-hover text-text-primary">
              pip install akquant akshare
            </code>
            ，然后重启后端服务。
          </div>
        </div>
      )}

      {/* Ordinary error */}
      {error && (
        <div className="mx-5 mb-3 p-3 rounded border border-line bg-bg-surface">
          <div className="text-[11px] leading-5 text-red-400">{error}</div>
        </div>
      )}

      {/* Missing analysis date */}
      {!error && !installHint && !running && !hasResults && !analysisDate && (
        <div className="mx-5 mb-3 text-[11px] text-text-muted">
          无法确定分析日期，请返回配置页确认日期后重试。
        </div>
      )}

      {/* HOLD decision note */}
      {hasResults && decision === "HOLD" && (
        <div className="mx-5 mb-3 text-[11px] text-text-muted">
          当前决策为 HOLD：策略不建仓，以下为对照参考（收益为零、无交易）。
        </div>
      )}

      {/* Metric comparison table */}
      {sortedDays.length > 0 && (
        <div className="mx-5 mb-3 overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-text-muted">
                <th className="text-left font-normal py-1.5 pr-4">指标</th>
                {sortedDays.map((d) => (
                  <th key={d} className="text-right font-normal py-1.5 px-3">
                    持有 {d} 天
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METRIC_ROWS.map((row) => (
                <tr key={String(row.key)} className="border-t border-line">
                  <td className="py-1.5 pr-4 text-text-secondary">
                    {row.label}
                  </td>
                  {sortedDays.map((d) => {
                    const value = results[d]?.[row.key];
                    const text = fmtCell(value, row.kind);
                    const positive =
                      row.kind === "pct" &&
                      typeof value === "number" &&
                      value > 0;
                    const negative =
                      row.kind === "pct" &&
                      typeof value === "number" &&
                      value < 0;
                    return (
                      <td
                        key={d}
                        className={`text-right py-1.5 px-3 font-mono ${
                          positive
                            ? "text-up"
                            : negative
                              ? "text-down"
                              : "text-text-primary"
                        }`}
                      >
                        {text}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Normalized cumulative return chart */}
      {sortedDays.length > 0 &&
        sortedDays.some((d) => normalizeCurve(results[d].equity_curve).length > 0) && (
          <div className="mx-5 mb-3">
            <ReactECharts
              option={chartOption}
              style={{ height: 220, width: "100%" }}
              notMerge
            />
          </div>
        )}
    </div>
  );
}
