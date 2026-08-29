import { useCallback, useRef, useState } from "react";
import { ArrowLeft, ArrowUpDown, Search, Sparkles } from "lucide-react";
import { api } from "../../lib/api";
import type { ScreenerResultItem, ScreenerResponse } from "../../lib/types";
import { Card } from "../ui";

// ── Hot query presets ───────────────────────────────────────────────────────

const HOT_QUERIES = [
  "北向连续加仓且PE<20的消费股",
  "高人气龙头股",
  "龙虎榜净买入前10",
  "低PEG成长股",
  "概念板块龙头",
  "高股息蓝筹",
];

// ── Column definitions ──────────────────────────────────────────────────────

type SortKey = "score" | "ticker" | "name" | "pe" | "change_pct";

interface Column {
  key: SortKey;
  label: string;
  width: string;
  align: "left" | "right";
  format?: (item: ScreenerResultItem) => string;
}

const COLUMNS: Column[] = [
  { key: "score", label: "匹配度", width: "w-16", align: "right", format: (i) => `${i.score}` },
  { key: "ticker", label: "代码", width: "w-20", align: "left" },
  { key: "name", label: "名称", width: "w-28", align: "left" },
  { key: "pe", label: "PE(TTM)", width: "w-20", align: "right", format: (i) => i.pe != null ? i.pe.toFixed(1) : "—" },
  { key: "change_pct", label: "涨跌%", width: "w-20", align: "right", format: (i) => i.change_pct != null ? `${i.change_pct >= 0 ? "+" : ""}${i.change_pct.toFixed(2)}%` : "—" },
];

// ── Score bar ───────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? "bg-up" : score >= 50 ? "bg-warn" : "bg-text-muted";
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-10 h-1.5 bg-bg-surface rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-[11px] text-text-secondary tabular-nums">{score}</span>
    </div>
  );
}

// ── Main component ──────────────────────────────────────────────────────────

interface Props {
  onBack: () => void;
  onAnalyzeTicker: (ticker: string) => void;
}

export default function ScreenerPanel({ onBack, onAnalyzeTicker }: Props) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ScreenerResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortAsc, setSortAsc] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleSearch = useCallback(async (q?: string) => {
    const searchQuery = q ?? query;
    if (!searchQuery.trim()) return;

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setLoading(true);
    setError("");
    setResult(null);
    setSelected(new Set());

    try {
      const resp = await api.runScreener(searchQuery, 30, undefined, ctrl.signal);
      setResult(resp);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [query]);

  const toggleSort = useCallback((key: SortKey) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortAsc((a) => !a);
        return key;
      }
      setSortAsc(key === "ticker" || key === "name");
      return key;
    });
  }, []);

  const toggleSelect = useCallback((ticker: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (!result) return;
    setSelected((prev) => {
      if (prev.size === result.results.length) return new Set();
      return new Set(result.results.map((r) => r.ticker));
    });
  }, [result]);

  // Sort results
  const sortedResults = result
    ? [...result.results].sort((a, b) => {
        const av = a[sortKey] ?? (sortKey === "score" ? 0 : sortKey === "ticker" || sortKey === "name" ? "" : Infinity);
        const bv = b[sortKey] ?? (sortKey === "score" ? 0 : sortKey === "ticker" || sortKey === "name" ? "" : Infinity);
        if (typeof av === "string" && typeof bv === "string") {
          return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
        }
        const an = Number(av);
        const bn = Number(bv);
        return sortAsc ? an - bn : bn - an;
      })
    : [];

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="h-10 shrink-0 border-b border-line flex items-center px-4 bg-bg-secondary/60">
        <button className="btn-ghost text-[12px]" onClick={onBack}>
          <ArrowLeft size={13} />
          返回
        </button>
        <span className="ml-3 text-[13px] font-medium text-text-primary">自然语言选股</span>
        {result && (
          <span className="ml-2 text-[11px] text-text-secondary">
            找到 {result.count} 只
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Search box */}
        <Card>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
              <input
                type="text"
                className="input w-full pl-8 text-[13px]"
                placeholder="输入选股条件，如「PE<20的消费股」「北向连续加仓」..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                disabled={loading}
              />
            </div>
            <button
              className="btn-primary !px-4 text-[12px]"
              onClick={() => handleSearch()}
              disabled={loading || !query.trim()}
            >
              {loading ? (
                <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <Sparkles size={13} />
                  搜索
                </>
              )}
            </button>
          </div>

          {/* Hot queries */}
          <div className="flex flex-wrap gap-1.5 mt-2">
            {HOT_QUERIES.map((hq) => (
              <button
                key={hq}
                className="px-2 py-0.5 text-[11px] rounded bg-bg-surface border border-line text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"
                onClick={() => { setQuery(hq); handleSearch(hq); }}
                disabled={loading}
              >
                {hq}
              </button>
            ))}
          </div>
        </Card>

        {/* Error */}
        {error && (
          <div className="px-3 py-2 rounded bg-down/10 border border-down/30 text-down text-[12px]">
            {error}
          </div>
        )}

        {/* LLM suggestion */}
        {result?.suggestion && (
          <div className="px-3 py-2 rounded bg-accent/10 border border-accent/30 text-[12px] text-text-secondary">
            <Sparkles size={12} className="inline mr-1 text-accent" />
            {result.suggestion}
          </div>
        )}

        {/* Parsed criteria */}
        {result?.parsed_criteria.filters && result.parsed_criteria.filters.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {result.parsed_criteria.filters.map((f, i) => (
              <span key={i} className="px-2 py-0.5 text-[11px] rounded-full bg-bg-surface border border-line text-text-secondary">
                {f.field} {f.operator} {String(f.value)}
                {f.period ? ` (${f.period})` : ""}
              </span>
            ))}
          </div>
        )}

        {/* Results table */}
        {sortedResults.length > 0 && (
          <Card title={`结果 (${sortedResults.length}只)`}>
            {/* Toolbar */}
            <div className="flex items-center gap-2 mb-2">
              <button
                className="text-[11px] text-text-secondary hover:text-text-primary"
                onClick={toggleSelectAll}
              >
                {selected.size === sortedResults.length ? "取消全选" : "全选"}
              </button>
              {selected.size > 0 && (
                <span className="text-[11px] text-accent">已选 {selected.size} 只</span>
              )}
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-line">
                    <th className="w-8 py-1.5" />
                    {COLUMNS.map((col) => (
                      <th
                        key={col.key}
                        className={`py-1.5 font-medium text-text-secondary cursor-pointer hover:text-text-primary ${col.width} ${
                          col.align === "right" ? "text-right" : "text-left"
                        }`}
                        onClick={() => toggleSort(col.key)}
                      >
                        <span className="inline-flex items-center gap-1">
                          {col.label}
                          {sortKey === col.key && (
                            <ArrowUpDown size={10} className="text-accent" />
                          )}
                        </span>
                      </th>
                    ))}
                    <th className="w-16 py-1.5 text-right" />
                  </tr>
                </thead>
                <tbody>
                  {sortedResults.map((item) => (
                    <tr
                      key={item.ticker}
                      className={`border-b border-line/50 hover:bg-bg-hover transition-colors ${
                        selected.has(item.ticker) ? "bg-accent/5" : ""
                      }`}
                    >
                      <td className="py-1.5 text-center">
                        <input
                          type="checkbox"
                          className="accent-accent"
                          checked={selected.has(item.ticker)}
                          onChange={() => toggleSelect(item.ticker)}
                        />
                      </td>
                      {COLUMNS.map((col) => (
                        <td
                          key={col.key}
                          className={`py-1.5 ${
                            col.align === "right" ? "text-right tabular-nums" : ""
                          } ${
                            col.key === "ticker" ? "font-mono text-accent" : ""
                          } ${
                            col.key === "change_pct" && item.change_pct != null
                              ? item.change_pct > 0
                                ? "text-up"
                                : item.change_pct < 0
                                  ? "text-down"
                                  : "text-text-secondary"
                              : ""
                          }`}
                        >
                          {col.key === "score" ? (
                            <ScoreBar score={item.score} />
                          ) : col.format ? (
                            col.format(item)
                          ) : (
                            String(item[col.key as keyof ScreenerResultItem] ?? "—")
                          )}
                        </td>
                      ))}
                      <td className="py-1.5 text-right">
                        <button
                          className="text-[11px] text-accent hover:underline"
                          onClick={() => onAnalyzeTicker(item.ticker)}
                          title="分析此股票"
                        >
                          分析
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        {/* Empty state */}
        {!loading && result && result.results.length === 0 && !error && (
          <div className="text-center py-12 text-text-secondary text-[13px]">
            未找到符合条件的股票，请尝试调整搜索条件
          </div>
        )}

        {/* Initial state */}
        {!loading && !result && !error && (
          <div className="text-center py-16 text-text-muted text-[13px]">
            <Sparkles size={24} className="mx-auto mb-3 text-accent/50" />
            <p>输入自然语言选股条件，AI 将帮你筛选</p>
            <p className="mt-1 text-[11px]">支持：PE、北向资金、概念板块、龙虎榜、盈利预测等</p>
          </div>
        )}
      </div>
    </div>
  );
}
