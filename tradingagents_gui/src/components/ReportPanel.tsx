import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  Download,
  RefreshCw,
  Search,
  X,
  FileText,
  FileCode,
  Printer,
} from "lucide-react";
import { save } from "@tauri-apps/plugin-dialog";
import { writeTextFile } from "@tauri-apps/plugin-fs";
import { SignalBadge } from "./ui";
import { HighlightedText } from "./SmartHighlight";
import ReportCharts from "./ReportCharts";
import { buildExportHtml } from "../lib/html-export";

// ── Tab definitions ─────────────────────────────────────────────────────────────

const TABS: { key: string; label: string; section: string }[] = [
  { key: "analysts", label: "分析师", section: "analyst" },
  { key: "research", label: "研究", section: "research_decision" },
  { key: "trading", label: "交易", section: "trader_plan" },
  { key: "risk", label: "风控", section: "risk_decision" },
  { key: "portfolio", label: "投资决策", section: "final_decision" },
];

interface TocEntry {
  text: string;
  level: number;
}

/**
 * Extract heading entries from markdown for the TOC sidebar.
 */
function extractToc(md: string): TocEntry[] {
  const lines = md.split("\n");
  const toc: TocEntry[] = [];
  for (const line of lines) {
    const m = line.match(/^(#{1,4})\s+(.+?)\s*$/);
    if (!m) continue;
    const text = m[2];
    const level = m[1].length;
    if (text.length < 3) continue;
    if (/^[IVX]+\./.test(text)) continue;
    if (/^(Bear|Bull|Neutral|Trader|Researcher|Aggressive|Conservative)$/i.test(text)) continue;
    toc.push({ text, level });
  }
  return toc;
}

// ── Markdown component (styled) ────────────────────────────────────────────────

function Markdown({ content }: { content: string }) {
  return (
    <div className="prose-report max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 data-heading={String(children)}>{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 data-heading={String(children)}>{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 data-heading={String(children)}>{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 data-heading={String(children)}>{children}</h4>
          ),
          p: ({ children }) => <p><HighlightedText>{children}</HighlightedText></p>,
          li: ({ children }) => <li><HighlightedText>{children}</HighlightedText></li>,
          td: ({ children }) => <td><HighlightedText>{children}</HighlightedText></td>,
          th: ({ children }) => <th><HighlightedText>{children}</HighlightedText></th>,
          blockquote: ({ children }) => <blockquote><HighlightedText>{children}</HighlightedText></blockquote>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

// ── Draggable divider ──────────────────────────────────────────────────────────

function DragDivider({ onDrag }: { onDrag: (deltaX: number) => void }) {
  const dragging = useRef(false);
  const startX = useRef(0);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragging.current = true;
    startX.current = e.clientX;
    e.preventDefault();
  }, []);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const delta = e.clientX - startX.current;
      startX.current = e.clientX;
      onDrag(delta);
    };
    const onMouseUp = () => { dragging.current = false; };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, [onDrag]);

  return (
    <div
      className="w-1 shrink-0 cursor-col-resize hover:bg-accent/40 active:bg-accent/60 transition-colors"
      onMouseDown={onMouseDown}
    />
  );
}

// ── Search bar ─────────────────────────────────────────────────────────────────

function SearchBar({
  query,
  setQuery,
  matchCount,
  currentMatch,
  onPrev,
  onNext,
  onClose,
}: {
  query: string;
  setQuery: (q: string) => void;
  matchCount: number;
  currentMatch: number;
  onPrev: () => void;
  onNext: () => void;
  onClose: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <div className="h-9 shrink-0 border-b border-line flex items-center px-3 gap-2 bg-bg-secondary">
      <Search size={13} className="text-text-muted shrink-0" />
      <input
        ref={inputRef}
        className="input flex-1 !h-6 !text-[12px]"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="搜索报告内容..."
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.shiftKey ? onPrev() : onNext();
          }
          if (e.key === "Escape") onClose();
        }}
      />
      {query && (
        <>
          <span className="text-[11px] text-text-muted whitespace-nowrap">
            {matchCount > 0 ? `${currentMatch}/${matchCount}` : "无匹配"}
          </span>
          <button
            className="p-1 hover:bg-bg-hover rounded transition-colors"
            onClick={onPrev}
            disabled={matchCount === 0}
          >
            <ArrowUp size={12} className="text-text-secondary" />
          </button>
          <button
            className="p-1 hover:bg-bg-hover rounded transition-colors"
            onClick={onNext}
            disabled={matchCount === 0}
          >
            <ArrowDown size={12} className="text-text-secondary" />
          </button>
        </>
      )}
      <button
        className="p-1 hover:bg-bg-hover rounded transition-colors"
        onClick={onClose}
      >
        <X size={12} className="text-text-secondary" />
      </button>
    </div>
  );
}

// ── Save dropdown ──────────────────────────────────────────────────────────────

function SaveDropdown({
  ticker,
  signal,
  reportMd,
  sections,
  chartData,
  onClose,
}: {
  ticker: string;
  signal: string;
  reportMd: string;
  sections: Record<string, string>;
  chartData?: import("../lib/types").ChartData | null;
  onClose: () => void;
}) {
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onClose]);

  const defaultFilename = `${ticker}_analysis_${new Date().toISOString().slice(0, 10)}`;

  const saveMarkdown = async () => {
    console.log("[DEBUG] saveMarkdown called, save function:", typeof save);
    try {
      const filePath = await save({
        defaultPath: `${defaultFilename}.md`,
        filters: [{ name: "Markdown", extensions: ["md"] }],
      });
      console.log("[DEBUG] save returned:", filePath);
      if (filePath) {
        await writeTextFile(filePath, reportMd);
        console.log("[DEBUG] file written to:", filePath);
      }
    } catch (err) {
      console.error("[DEBUG] Save markdown failed:", err);
    }
    onClose();
  };

  const saveHtml = async () => {
    // Load ECharts: try build-time embed first, fall back to CDN
    let echartsJs = "";
    try {
      const { getEchartsMinJs } = await import("../lib/echarts-bundle");
      echartsJs = await getEchartsMinJs();
    } catch {
      try {
        const resp = await fetch("https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js");
        if (resp.ok) echartsJs = await resp.text();
      } catch {
        // Both unavailable — export without charts
      }
    }

    const html = buildExportHtml(ticker, signal, reportMd, chartData ?? null, echartsJs);
    try {
      const filePath = await save({
        defaultPath: `${defaultFilename}.html`,
        filters: [{ name: "HTML", extensions: ["html"] }],
      });
      if (filePath) {
        await writeTextFile(filePath, html);
      }
    } catch (err) {
      console.error("Save HTML failed:", err);
    }
    onClose();
  };

  const saveJson = async () => {
    const data = {
      ticker,
      signal,
      timestamp: new Date().toISOString(),
      report_md: reportMd,
      sections,
    };
    try {
      const filePath = await save({
        defaultPath: `${defaultFilename}.json`,
        filters: [{ name: "JSON", extensions: ["json"] }],
      });
      if (filePath) {
        await writeTextFile(filePath, JSON.stringify(data, null, 2));
      }
    } catch (err) {
      console.error("Save JSON failed:", err);
    }
    onClose();
  };

  return (
    <div
      ref={dropdownRef}
      className="absolute right-0 top-full mt-1 bg-bg-surface border border-line rounded shadow-lg z-50 py-1 min-w-[160px]"
    >
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-text-primary hover:bg-bg-hover transition-colors"
        onClick={saveMarkdown}
      >
        <FileText size={13} className="text-text-muted" />
        保存为 Markdown
      </button>
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-text-primary hover:bg-bg-hover transition-colors"
        onClick={saveHtml}
      >
        <FileCode size={13} className="text-text-muted" />
        保存为 HTML
      </button>
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-text-primary hover:bg-bg-hover transition-colors"
        onClick={saveJson}
      >
        <Download size={13} className="text-text-muted" />
        保存为 JSON
      </button>
      <div className="h-px bg-line my-1" />
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-[12px] text-text-primary hover:bg-bg-hover transition-colors"
        onClick={() => { window.print(); onClose(); }}
      >
        <Printer size={13} className="text-text-muted" />
        打印 / 导出 PDF
      </button>
    </div>
  );
}

// ── Props ──────────────────────────────────────────────────────────────────────

interface Props {
  ticker: string;
  signal: string;
  reportMd: string;
  sections: Record<string, string>;
  chartData?: import("../lib/types").ChartData | null;
  onBack: () => void;
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function ReportPanel({
  ticker,
  signal,
  reportMd,
  sections,
  chartData,
  onBack,
}: Props) {
  const [activeTab, setActiveTab] = useState("analysts");
  const [tocWidth, setTocWidth] = useState(220);
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSaveMenu, setShowSaveMenu] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  const tab = TABS.find((t) => t.key === activeTab)!;
  const content = sections[tab.section] ?? reportMd;

  const toc = useMemo(() => extractToc(content), [content]);

  // ── Search logic ───────────────────────────────────────────────────────────
  const [matchIndices, setMatchIndices] = useState<number[]>([]);
  const [currentMatchIdx, setCurrentMatchIdx] = useState(0);

  // Highlight search matches in the content
  const highlightedContent = useMemo(() => {
    if (!searchQuery) return content;
    try {
      const escaped = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const regex = new RegExp(`(${escaped})`, "gi");
      return content.replace(regex, `==${searchQuery}==`);
    } catch {
      return content;
    }
  }, [content, searchQuery]);

  // Count matches
  useEffect(() => {
    if (!searchQuery) {
      setMatchIndices([]);
      setCurrentMatchIdx(0);
      return;
    }
    try {
      const escaped = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const regex = new RegExp(escaped, "gi");
      const indices: number[] = [];
      let match;
      while ((match = regex.exec(content)) !== null) {
        indices.push(match.index);
      }
      setMatchIndices(indices);
      setCurrentMatchIdx(indices.length > 0 ? 1 : 0);
    } catch {
      setMatchIndices([]);
      setCurrentMatchIdx(0);
    }
  }, [searchQuery, content]);

  // Scroll to current match
  useEffect(() => {
    if (matchIndices.length === 0 || !scrollRef.current) return;
    // Use a timeout to ensure the DOM has updated with highlight marks
    const timer = setTimeout(() => {
      const el = contentRef.current?.querySelector<HTMLElement>(
        `[data-search-match="${currentMatchIdx}"]`
      );
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 100);
    return () => clearTimeout(timer);
  }, [currentMatchIdx, matchIndices]);

  const handleSearchPrev = useCallback(() => {
    setCurrentMatchIdx((i) => (i > 1 ? i - 1 : matchIndices.length));
  }, [matchIndices.length]);

  const handleSearchNext = useCallback(() => {
    setCurrentMatchIdx((i) => (i < matchIndices.length ? i + 1 : 1));
  }, [matchIndices.length]);

  const handleTocDrag = useCallback((delta: number) => {
    setTocWidth((w) => Math.min(Math.max(w + delta, 120), 400));
  }, []);

  const jumpToHeading = (text: string) => {
    const el = scrollRef.current?.querySelector<HTMLElement>(
      `[data-heading="${CSS.escape(text)}"]`,
    );
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Keyboard shortcut: Ctrl+F to open search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        e.preventDefault();
        setShowSearch(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="h-full flex flex-col">
      {/* ── Header ── */}
      <div className="h-11 shrink-0 border-b border-line flex items-center px-5">
        <h1 className="text-[18px] font-semibold text-text-primary">{ticker}</h1>
        <div className="ml-3">
          <SignalBadge signal={signal} />
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button className="btn-ghost" onClick={onBack}>
            <ArrowLeft size={13} />
            返回
          </button>
          <div className="relative">
            <button
              className="btn-ghost"
              onClick={() => setShowSaveMenu(!showSaveMenu)}
            >
              <Download size={13} />
              保存
            </button>
            {showSaveMenu && (
              <SaveDropdown
                ticker={ticker}
                signal={signal}
                reportMd={reportMd}
                sections={sections}
                chartData={chartData}
                onClose={() => setShowSaveMenu(false)}
              />
            )}
          </div>
          <button className="btn-primary" onClick={onBack}>
            <RefreshCw size={13} />
            重新分析
          </button>
        </div>
      </div>

      {/* ── Tab bar ── */}
      <div className="h-9 shrink-0 border-b border-line flex items-center px-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab ${activeTab === t.key ? "tab-active" : ""}`}
            onClick={() => setActiveTab(t.key)}
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto">
          <button
            className="p-1.5 hover:bg-bg-hover rounded transition-colors"
            onClick={() => setShowSearch(!showSearch)}
            title="搜索 (Ctrl+F)"
          >
            <Search size={14} className="text-text-secondary" />
          </button>
        </div>
      </div>

      {/* ── Search bar (conditional) ── */}
      {showSearch && (
        <SearchBar
          query={searchQuery}
          setQuery={setSearchQuery}
          matchCount={matchIndices.length}
          currentMatch={currentMatchIdx}
          onPrev={handleSearchPrev}
          onNext={handleSearchNext}
          onClose={() => { setShowSearch(false); setSearchQuery(""); }}
        />
      )}

      {/* ── Body ── */}
      <div className="flex-1 flex min-h-0">
        {/* TOC sidebar */}
        {toc.length > 0 && (
          <>
            <aside
              className="shrink-0 border-r border-line overflow-y-auto overflow-x-hidden py-3"
              style={{ width: tocWidth }}
            >
              <div className="px-3 text-[10px] uppercase tracking-wider text-text-muted mb-2">
                Index
              </div>
              {toc.map((e, i) => (
                <button
                  key={i}
                  className="block w-full text-left px-3 py-1 text-[11px] hover:bg-bg-hover rounded transition-colors truncate"
                  style={{ paddingLeft: 12 + (e.level - 1) * 10 }}
                  onClick={() => jumpToHeading(e.text)}
                  title={e.text}
                >
                  <span
                    className={
                      e.level <= 2 ? "text-text-primary font-medium" : "text-text-secondary"
                    }
                  >
                    {e.text}
                  </span>
                </button>
              ))}
            </aside>
            <DragDivider onDrag={handleTocDrag} />
          </>
        )}

        {/* Content */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {content ? (
            <div ref={contentRef} className="max-w-3xl mx-auto px-10 py-6">
              {chartData && <ReportCharts chartData={chartData} />}
              <Markdown content={highlightedContent} />
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-text-muted text-[13px]">
              （此阶段暂无内容）
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
