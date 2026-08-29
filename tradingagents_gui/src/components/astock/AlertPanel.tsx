/**
 * AlertPanel - manage price alerts with add/remove/toggle/edit/history.
 *
 * Shows:
 * - Add form: ticker, condition (above/below), target price
 * - Alert list: each with ticker, condition, target, current price, status
 * - Toggle enable/disable, inline target-price edit, remove button
 * - Per-alert trigger history (lazy-loaded from the backend)
 *
 * Designed to be rendered inside a dialog/popover triggered from ChartHeader.
 */

import { useState, useEffect, useRef } from "react";
import { Plus, Trash2, Bell, BellOff, X, Edit2, Clock, ChevronDown } from "lucide-react";
import type { PriceAlert, RealtimePrice } from "../../lib/types";
import { getAlertHistory, type ServerAlertEvent } from "../../lib/alert-sync";

interface Props {
  alerts: PriceAlert[];
  prices: Map<string, RealtimePrice>;
  currentTicker: string;
  currentPrice?: number | null;
  onAdd: (ticker: string, name: string | null, condition: "above" | "below", targetPrice: number) => void;
  onRemove: (id: string) => void;
  onToggle: (id: string) => void;
  onUpdate: (id: string, targetPrice: number) => void;
  onClose: () => void;
}

/** Human label + color class for a condition value. */
function conditionLabel(condition: string): { text: string; cls: string } {
  switch (condition) {
    case "above": return { text: "↑ 高于", cls: "text-[#F23645]" };
    case "below": return { text: "↓ 低于", cls: "text-[#26A69A]" };
    case "indicator_above": return { text: "指标↑高", cls: "text-[#F23645]" };
    case "indicator_below": return { text: "指标↓低", cls: "text-[#26A69A]" };
    case "cross_above": return { text: "上穿", cls: "text-[#F23645]" };
    case "cross_below": return { text: "下穿", cls: "text-[#26A69A]" };
    case "volume_above": return { text: "量↑超", cls: "text-[#F23645]" };
    default: return { text: condition, cls: "text-[#787B86]" };
  }
}

function formatTime(epochSec: number): string {
  const d = new Date(epochSec * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AlertPanel({
  alerts,
  prices,
  currentTicker,
  currentPrice,
  onAdd,
  onRemove,
  onToggle,
  onUpdate,
  onClose,
}: Props) {
  const [ticker, setTicker] = useState(currentTicker);
  const [condition, setCondition] = useState<"above" | "below">("above");
  const [targetStr, setTargetStr] = useState(currentPrice != null ? String(currentPrice) : "");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTargetStr, setEditTargetStr] = useState("");
  const [historyId, setHistoryId] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const price = parseFloat(targetStr);
    if (!ticker.trim() || isNaN(price) || price <= 0) return;
    const quote = prices.get(ticker.toUpperCase());
    onAdd(ticker.toUpperCase(), quote?.name ?? null, condition, price);
    setTargetStr("");
  };

  return (
    <div className="bg-[#1E222D] border border-[#363A45] rounded-lg shadow-xl w-[360px] max-h-[420px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#363A45]">
        <div className="flex items-center gap-1.5 text-[13px] text-[#D1D4DC] font-medium">
          <Bell size={13} />
          价格预警
        </div>
        <button onClick={onClose} className="text-[#787B86] hover:text-[#D1D4DC] p-0.5">
          <X size={13} />
        </button>
      </div>

      {/* Add form */}
      <form onSubmit={handleSubmit} className="px-3 py-2 border-b border-[#363A45] space-y-2">
        <div className="flex gap-1.5">
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="代码"
            className="flex-1 bg-[#131722] border border-[#363A45] rounded px-2 py-1 text-[11px] text-[#D1D4DC] placeholder-[#4C525E] focus:outline-none focus:border-[#2962FF]"
          />
          <select
            value={condition}
            onChange={(e) => setCondition(e.target.value as "above" | "below")}
            className="bg-[#131722] border border-[#363A45] rounded px-2 py-1 text-[11px] text-[#D1D4DC] focus:outline-none focus:border-[#2962FF]"
          >
            <option value="above">高于</option>
            <option value="below">低于</option>
          </select>
          <input
            value={targetStr}
            onChange={(e) => setTargetStr(e.target.value)}
            placeholder="目标价"
            type="number"
            step="any"
            min="0"
            className="w-20 bg-[#131722] border border-[#363A45] rounded px-2 py-1 text-[11px] text-[#D1D4DC] placeholder-[#4C525E] focus:outline-none focus:border-[#2962FF]"
          />
          <button
            type="submit"
            className="bg-[#2962FF] hover:bg-[#1E54D0] text-white rounded px-2 py-1 text-[11px] transition-colors"
          >
            <Plus size={12} />
          </button>
        </div>
      </form>

      {/* Alert list */}
      <div className="flex-1 overflow-y-auto">
        {alerts.length === 0 ? (
          <div className="flex items-center justify-center h-20 text-[11px] text-[#4C525E]">
            暂无预警，添加一个试试
          </div>
        ) : (
          <div className="divide-y divide-[#363A45]/50">
            {alerts.map((alert) => (
              <AlertRow
                key={alert.id}
                alert={alert}
                prices={prices}
                editing={editingId === alert.id}
                editTargetStr={editTargetStr}
                showHistory={historyId === alert.id}
                onEditStart={() => {
                  setEditingId(alert.id);
                  setEditTargetStr(String(alert.target_price));
                }}
                onEditChange={setEditTargetStr}
                onEditSubmit={() => {
                  const price = parseFloat(editTargetStr);
                  if (!isNaN(price) && price > 0) onUpdate(alert.id, price);
                  setEditingId(null);
                }}
                onEditCancel={() => setEditingId(null)}
                onToggle={() => onToggle(alert.id)}
                onRemove={() => onRemove(alert.id)}
                onHistoryToggle={() =>
                  setHistoryId((cur) => (cur === alert.id ? null : alert.id))
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── One alert row + optional inline editor + history section ───────────────

function AlertRow({
  alert,
  prices,
  editing,
  editTargetStr,
  showHistory,
  onEditStart,
  onEditChange,
  onEditSubmit,
  onEditCancel,
  onToggle,
  onRemove,
  onHistoryToggle,
}: {
  alert: PriceAlert;
  prices: Map<string, RealtimePrice>;
  editing: boolean;
  editTargetStr: string;
  showHistory: boolean;
  onEditStart: () => void;
  onEditChange: (v: string) => void;
  onEditSubmit: () => void;
  onEditCancel: () => void;
  onToggle: () => void;
  onRemove: () => void;
  onHistoryToggle: () => void;
}) {
  const editInputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (editing) editInputRef.current?.focus();
  }, [editing]);

  const quote = prices.get(alert.ticker);
  const current = quote?.price;
  const cond = conditionLabel(alert.condition);
  const isPriceCondition = alert.condition === "above" || alert.condition === "below";

  return (
    <div className={alert.triggered ? "bg-[#FF9800]/5" : ""}>
      <div className="px-3 py-2 flex items-center gap-2">
        <button
          onClick={onToggle}
          className={`shrink-0 p-0.5 transition-colors ${
            alert.enabled ? "text-[#2962FF]" : "text-[#4C525E]"
          }`}
          title={alert.enabled ? "点击禁用" : "点击启用"}
        >
          {alert.enabled ? <Bell size={12} /> : <BellOff size={12} />}
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className="text-[#D1D4DC] font-medium">{alert.ticker}</span>
            {alert.name && (
              <span className="text-[#787B86] truncate">{alert.name}</span>
            )}
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-[#787B86] mt-0.5">
            <span className={cond.cls}>{cond.text}</span>
            {editing ? (
              <input
                ref={editInputRef}
                value={editTargetStr}
                onChange={(e) => onEditChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onEditSubmit();
                  if (e.key === "Escape") onEditCancel();
                }}
                onBlur={onEditSubmit}
                onClick={(e) => e.stopPropagation()}
                type="number"
                step="any"
                min="0"
                className="w-16 bg-[#131722] border border-[#2962FF] rounded px-1 py-0 text-[10px] text-[#D1D4DC] tabular-nums focus:outline-none"
              />
            ) : (
              <span className="tabular-nums">{alert.target_price}</span>
            )}
            {current != null && isPriceCondition && (
              <>
                <span>· 现价</span>
                <span className="tabular-nums text-[#D1D4DC]">{current.toFixed(2)}</span>
              </>
            )}
            {alert.triggered && (
              <span className="text-[#FF9800] font-medium">已触发</span>
            )}
          </div>
        </div>
        <button
          onClick={onEditStart}
          disabled={editing}
          className="shrink-0 text-[#4C525E] hover:text-[#D1D4DC] disabled:opacity-30 p-0.5 transition-colors"
          title="修改目标价"
        >
          <Edit2 size={11} />
        </button>
        <button
          onClick={onHistoryToggle}
          className={`shrink-0 p-0.5 transition-colors ${
            showHistory ? "text-[#2962FF]" : "text-[#4C525E] hover:text-[#D1D4DC]"
          }`}
          title="触发历史"
        >
          {showHistory ? <ChevronDown size={11} /> : <Clock size={11} />}
        </button>
        <button
          onClick={onRemove}
          className="shrink-0 text-[#4C525E] hover:text-[#F23645] p-0.5 transition-colors"
        >
          <Trash2 size={11} />
        </button>
      </div>
      {showHistory && <AlertHistorySection alertId={alert.id} />}
    </div>
  );
}

// ── Lazy-loaded trigger history ─────────────────────────────────────────────

function AlertHistorySection({ alertId }: { alertId: string }) {
  const [events, setEvents] = useState<ServerAlertEvent[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getAlertHistory(alertId).then((result) => {
      if (cancelled) return;
      setEvents(result);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [alertId]);

  if (loading) {
    return (
      <div className="px-8 py-2 text-[10px] text-[#4C525E]">加载历史中…</div>
    );
  }
  if (events === null) {
    return (
      <div className="px-8 py-2 text-[10px] text-[#4C525E]">历史不可用（后端离线）</div>
    );
  }
  if (events.length === 0) {
    return (
      <div className="px-8 py-2 text-[10px] text-[#4C525E]">暂无触发记录</div>
    );
  }

  return (
    <div className="px-8 py-1.5 space-y-1">
      {events.slice(0, 10).map((ev, i) => (
        <div key={i} className="flex items-center gap-2 text-[10px] text-[#787B86]">
          <span className="tabular-nums">{formatTime(ev.triggered_at)}</span>
          {ev.value != null && (
            <span className="tabular-nums text-[#D1D4DC]">{ev.value.toFixed(2)}</span>
          )}
        </div>
      ))}
    </div>
  );
}
