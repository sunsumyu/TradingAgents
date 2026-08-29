/**
 * SmartHighlight — Post-processes markdown content to add visual annotations
 * for trading signals, financial metrics, risk levels, and key conclusions.
 */
import React from "react";

// ── Signal detection ───────────────────────────────────────────────────────────

const SIGNAL_PATTERNS: { pattern: RegExp; signal: "buy" | "sell" | "hold" }[] = [
  // English
  { pattern: /\b(BUY|Strong Buy|Long)\b/gi, signal: "buy" },
  { pattern: /\b(SELL|Strong Sell|Short|Underweight)\b/gi, signal: "sell" },
  { pattern: /\b(HOLD|Neutral|Overweight|Equal-weight)\b/gi, signal: "hold" },
  // Chinese
  { pattern: /(买入|增持|看多|做多|强烈买入)/g, signal: "buy" },
  { pattern: /(卖出|减持|看空|做空|强烈卖出)/g, signal: "sell" },
  { pattern: /(持有|中性|观望|观望不动)/g, signal: "hold" },
];

// ── Risk level detection ───────────────────────────────────────────────────────

const RISK_PATTERNS: { pattern: RegExp; level: "high" | "medium" | "low" }[] = [
  { pattern: /(高风险|重大风险|严重警告|Critical|High Risk)/gi, level: "high" },
  { pattern: /(中等风险|需关注|注意|Medium Risk|Caution)/gi, level: "medium" },
  { pattern: /(低风险|安全|稳健|Low Risk|Safe)/gi, level: "low" },
];

// ── Financial metric detection ─────────────────────────────────────────────────

const METRIC_PATTERNS: RegExp[] = [
  // Percentages
  /(\d+\.?\d*\s*%)/g,
  // Revenue/earnings with currency
  /(\$[\d,.]+\s*(?:B|M|K|billion|million|亿|万)?)/g,
  // PE ratio
  /(P\/E\s*(?:ratio)?\s*[:：]?\s*\d+\.?\d*)/gi,
  // Numbers with Chinese units
  /(\d+\.?\d*\s*(?:亿|万|百万|千万))/g,
];

// ── Action item detection ──────────────────────────────────────────────────────

const ACTION_PATTERNS: RegExp[] = [
  // Trading actions
  /(FINAL\s+TRANSACTION\s+PROPOSAL\s*:\s*\w+)/gi,
  /(最终交易建议\s*[:：]\s*\S+)/g,
  // Position sizing
  /(Position\s+Sizing\s*[:：].+?)(?=\n|$)/gi,
  /(仓位\s*(?:配置|建议|比例)\s*[:：].+?)(?=\n|$)/g,
];

// ── CSS classes for highlights ─────────────────────────────────────────────────

const SIGNAL_STYLES: Record<string, string> = {
  buy: "inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold bg-up/20 text-up border border-up/30",
  sell: "inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold bg-down/20 text-down border border-down/30",
  hold: "inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold bg-yellow/20 text-yellow border border-yellow/30",
};

const RISK_STYLES: Record<string, string> = {
  high: "inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold bg-down/20 text-down border border-down/30",
  medium: "inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold bg-yellow/20 text-yellow border border-yellow/30",
  low: "inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-bold bg-up/20 text-up border border-up/30",
};

// ── React element wrapper ──────────────────────────────────────────────────────

let _key = 0;
function wrap(text: string, className: string, title?: string): React.ReactNode {
  return (
    <span key={`hl-${_key++}`} className={className} title={title}>
      {text}
    </span>
  );
}

// ── Main processing function ───────────────────────────────────────────────────

/**
 * Process a text node and return highlighted React nodes.
 * This is used as a custom renderer in react-markdown.
 */
export function highlightText(text: string): React.ReactNode {
  // We process the text through multiple passes.
  // Each pass wraps matches in styled spans.
  // To avoid nested spans, we work on an array of segments.

  interface Segment {
    text: string;
    highlighted: boolean;
    className?: string;
    title?: string;
  }

  let segments: Segment[] = [{ text, highlighted: false }];

  // Pass 0: Search highlight (==text== markers) — highest priority
  const searchPattern = /==(.+?)==/g;
  {
    const next: Segment[] = [];
    for (const seg of segments) {
      if (seg.highlighted) {
        next.push(seg);
        continue;
      }
      const parts = seg.text.split(searchPattern);
      for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
          next.push({ text: parts[i], highlighted: false });
        } else {
          next.push({
            text: parts[i],
            highlighted: true,
            className: "bg-yellow/40 text-yellow rounded px-0.5 -mx-0.5",
            title: "搜索匹配",
          });
        }
      }
    }
    segments = next;
  }

  // Pass 1: Signal detection
  for (const { pattern, signal } of SIGNAL_PATTERNS) {
    const next: Segment[] = [];
    for (const seg of segments) {
      if (seg.highlighted) {
        next.push(seg);
        continue;
      }
      const parts = seg.text.split(pattern);
      for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
          next.push({ text: parts[i], highlighted: false });
        } else {
          next.push({
            text: parts[i],
            highlighted: true,
            className: SIGNAL_STYLES[signal],
            title: signal === "buy" ? "买入信号" : signal === "sell" ? "卖出信号" : "持有信号",
          });
        }
      }
    }
    segments = next;
  }

  // Pass 2: Risk detection
  for (const { pattern, level } of RISK_PATTERNS) {
    const next: Segment[] = [];
    for (const seg of segments) {
      if (seg.highlighted) {
        next.push(seg);
        continue;
      }
      const parts = seg.text.split(pattern);
      for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
          next.push({ text: parts[i], highlighted: false });
        } else {
          next.push({
            text: parts[i],
            highlighted: true,
            className: RISK_STYLES[level],
            title: `风险等级: ${level}`,
          });
        }
      }
    }
    segments = next;
  }

  // Pass 3: Financial metrics (subtle highlight)
  for (const pattern of METRIC_PATTERNS) {
    const next: Segment[] = [];
    for (const seg of segments) {
      if (seg.highlighted) {
        next.push(seg);
        continue;
      }
      const parts = seg.text.split(pattern);
      for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
          next.push({ text: parts[i], highlighted: false });
        } else {
          next.push({
            text: parts[i],
            highlighted: true,
            className: "text-accent font-medium",
            title: "财务指标",
          });
        }
      }
    }
    segments = next;
  }

  // Pass 4: Action items (bold + background)
  for (const pattern of ACTION_PATTERNS) {
    const next: Segment[] = [];
    for (const seg of segments) {
      if (seg.highlighted) {
        next.push(seg);
        continue;
      }
      const parts = seg.text.split(pattern);
      for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
          next.push({ text: parts[i], highlighted: false });
        } else {
          next.push({
            text: parts[i],
            highlighted: true,
            className: "inline-flex items-center px-2 py-0.5 rounded bg-accent/15 text-accent font-bold border border-accent/30",
            title: "交易行动项",
          });
        }
      }
    }
    segments = next;
  }

  // Convert segments to React nodes
  const nodes: React.ReactNode[] = [];
  for (const seg of segments) {
    if (!seg.text) continue;
    if (seg.highlighted && seg.className) {
      nodes.push(wrap(seg.text, seg.className, seg.title));
    } else {
      nodes.push(seg.text);
    }
  }

  return nodes.length === 1 ? nodes[0] : <>{nodes}</>;
}

/**
 * Custom text renderer for react-markdown that applies smart highlighting.
 */
export function HighlightedText({ children }: { children: React.ReactNode }) {
  if (typeof children === "string") {
    return <>{highlightText(children)}</>;
  }
  return <>{children}</>;
}
