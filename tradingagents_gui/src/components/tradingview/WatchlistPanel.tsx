/**
 * WatchlistPanel — Right sidebar watchlist with grouped tickers.
 *
 * Groups are persisted in localStorage under the phase-4 spec key
 * "tradingagents_watchlist_groups". The first group ("自选股") is
 * always present and cannot be deleted; its tickers receive any
 * items orphaned by a group deletion.
 *
 * Each group is collapsible/expandable with state also persisted.
 * Tickers can be moved between groups via a small dropdown that
 * appears on hover. No drag-and-drop — keeps the compact sidebar simple.
 */

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { Plus, X, ChevronDown, ChevronRight, Edit2, Trash2, MoreHorizontal } from "lucide-react";
import type { WatchlistItem, WatchlistGroup } from "./types";
import { COLORS } from "./chart-theme";
import { useRealtimePrices } from "../../lib/useRealtimePrices";
import {
  loadWatchlistGroups,
  saveWatchlistGroups,
} from "./watchlist-store";

// ── Props ───────────────────────────────────────────────────────────────────

interface Props {
  onSelect: (ticker: string) => void;
  currentTicker?: string;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function WatchlistPanel({ onSelect, currentTicker }: Props) {
  const [groups, setGroups] = useState<WatchlistGroup[]>(() => loadWatchlistGroups());
  const [input, setInput] = useState("");
  // Which group is receiving the next "Add ticker" action
  const [activeGroupId, setActiveGroupId] = useState<string>(() => groups[0]?.id ?? "");
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState("");
  const editInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    saveWatchlistGroups(groups);
  }, [groups]);

  useEffect(() => {
    if (editingGroupId) editInputRef.current?.focus();
  }, [editingGroupId]);

  // ── Realtime quotes (HTTP polling, 5s) ───────────────────────────────────
  const allTickers = useMemo(
    () => groups.flatMap((g) => g.items.map((i) => i.ticker)),
    [groups],
  );
  const realtimePrices = useRealtimePrices(allTickers);

  /** Merge the polled snapshot onto stored items (polled data wins). */
  const priceFor = useCallback(
    (ticker: string): WatchlistItem | null => {
      const rt = realtimePrices.get(ticker);
      if (!rt) return null;
      return {
        ticker,
        lastPrice: rt.price,
        change: rt.change,
        changePercent: rt.changePct,
        name: rt.name ?? undefined,
      };
    },
    [realtimePrices],
  );

  // ── Ticker operations ────────────────────────────────────────────────────

  const addItem = useCallback(() => {
    const ticker = input.trim().toUpperCase();
    if (!ticker) return;
    setGroups((prev) =>
      prev.map((g) => {
        if (g.id !== activeGroupId) return g;
        if (g.items.some((i) => i.ticker === ticker)) return g;
        return { ...g, items: [...g.items, { ticker }] };
      }),
    );
    setInput("");
  }, [input, activeGroupId]);

  const removeItem = useCallback((ticker: string) => {
    setGroups((prev) =>
      prev.map((g) => ({ ...g, items: g.items.filter((i) => i.ticker !== ticker) })),
    );
  }, []);

  const moveItem = useCallback((fromGroupId: string, toGroupId: string, ticker: string) => {
    if (fromGroupId === toGroupId) return;
    setGroups((prev) => {
      let movedItem: WatchlistItem | undefined;
      const next = prev.map((g) => {
        if (g.id === fromGroupId) {
          movedItem = g.items.find((i) => i.ticker === ticker);
          return { ...g, items: g.items.filter((i) => i.ticker !== ticker) };
        }
        return g;
      });
      if (!movedItem) return prev;
      return next.map((g) => {
        if (g.id !== toGroupId) return g;
        if (g.items.some((i) => i.ticker === ticker)) return g;
        return { ...g, items: [...g.items, movedItem!] };
      });
    });
  }, []);

  // ── Group operations ─────────────────────────────────────────────────────

  const addGroup = useCallback(() => {
    const id = `g_${Date.now()}`;
    setGroups((prev) => [...prev, { id, name: `分组${prev.length}`, items: [], collapsed: false }]);
  }, []);

  const removeGroup = useCallback(
    (groupId: string) => {
      const defaultGroup = groups[0];
      if (!defaultGroup || groupId === defaultGroup.id) return; // can't delete default
      setGroups((prev) => {
        const deleted = prev.find((g) => g.id === groupId);
        const itemsToKeep = deleted?.items ?? [];
        return prev
          .filter((g) => g.id !== groupId)
          .map((g) =>
            g.id === defaultGroup.id
              ? {
                  ...g,
                  items: [
                    ...g.items,
                    ...itemsToKeep.filter((i) => !g.items.some((x) => x.ticker === i.ticker)),
                  ],
                }
              : g,
          );
      });
    },
    [groups],
  );

  const toggleCollapse = useCallback((groupId: string) => {
    setGroups((prev) =>
      prev.map((g) => (g.id === groupId ? { ...g, collapsed: !g.collapsed } : g)),
    );
  }, []);

  const renameGroup = useCallback(
    (groupId: string) => {
      const trimmed = editingName.trim();
      if (!trimmed) return;
      setGroups((prev) => prev.map((g) => (g.id === groupId ? { ...g, name: trimmed } : g)));
      setEditingGroupId(null);
    },
    [editingName],
  );

  // Total count across all groups
  const totalCount = groups.reduce((s, g) => s + g.items.length, 0);

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full bg-[#131722] border-l border-[#2B2B43] text-xs">
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-8 border-b border-[#2B2B43]">
        <span className="text-[#787B86] font-medium">Watchlist</span>
        <span className="text-[#787B86] text-[10px]">{totalCount}</span>
      </div>

      {/* Add ticker input */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-[#2B2B43]">
        <select
          value={activeGroupId}
          onChange={(e) => setActiveGroupId(e.target.value)}
          className="bg-[#1E222D] text-[#D1D4DC] text-[10px] px-1 py-1 rounded border border-[#2B2B43] focus:outline-none focus:border-[#2962FF] w-[72px] truncate"
          title="添加到哪个分组"
        >
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addItem()}
          placeholder="Add ticker..."
          className="flex-1 bg-[#1E222D] text-[#D1D4DC] text-xs px-2 py-1 rounded border border-[#2B2B43] focus:outline-none focus:border-[#2962FF] placeholder:text-[#787B86]"
        />
        <button
          onClick={addItem}
          className="p-1 text-[#787B86] hover:text-[#D1D4DC] transition-colors"
        >
          <Plus size={14} />
        </button>
      </div>

      {/* Groups list */}
      <div className="flex-1 overflow-y-auto">
        {groups.map((group) => (
          <div key={group.id} className="border-b border-[#2B2B43]">
            {/* Group header */}
            <div
              className="flex items-center h-7 px-2 gap-1 cursor-pointer hover:bg-[#1E222D] transition-colors select-none"
              onClick={() => toggleCollapse(group.id)}
            >
              {group.collapsed ? (
                <ChevronRight size={10} className="text-[#787B86] shrink-0" />
              ) : (
                <ChevronDown size={10} className="text-[#787B86] shrink-0" />
              )}

              {editingGroupId === group.id ? (
                <input
                  ref={editInputRef}
                  value={editingName}
                  onChange={(e) => setEditingName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") renameGroup(group.id);
                    if (e.key === "Escape") setEditingGroupId(null);
                  }}
                  onBlur={() => renameGroup(group.id)}
                  onClick={(e) => e.stopPropagation()}
                  className="flex-1 bg-[#1E222D] text-[#D1D4DC] text-[11px] px-1 py-0.5 rounded border border-[#2962FF] focus:outline-none"
                />
              ) : (
                <span className="flex-1 text-[11px] font-medium text-[#787B86] truncate">
                  {group.name}
                </span>
              )}

              <span className="text-[9px] text-[#4C525E] tabular-nums">{group.items.length}</span>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingGroupId(group.id);
                  setEditingName(group.name);
                }}
                className="p-0.5 text-[#787B86] hover:text-[#D1D4DC] transition-colors"
                title="重命名分组"
              >
                <Edit2 size={9} />
              </button>

              {group.id !== groups[0]?.id && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeGroup(group.id);
                  }}
                  className="p-0.5 text-[#787B86] hover:text-[#F23645] transition-colors"
                  title="删除分组（标的回流到自选股）"
                >
                  <Trash2 size={9} />
                </button>
              )}
            </div>

            {/* Column headers (shown when expanded and has items) */}
            {!group.collapsed && group.items.length > 0 && (
              <div className="grid grid-cols-[1fr_60px_50px_40px] px-3 py-1 text-[10px] text-[#787B86] border-t border-[#2B2B43]">
                <span>Symbol</span>
                <span className="text-right">Last</span>
                <span className="text-right">Chg</span>
                <span className="text-right">Chg%</span>
              </div>
            )}

            {/* Ticker rows */}
            {!group.collapsed && (
              <>
                {group.items.map((item) => (
                  <TickerRow
                    key={item.ticker}
                    item={priceFor(item.ticker) ?? item}
                    isActive={item.ticker === currentTicker}
                    groupId={group.id}
                    allGroups={groups}
                    onSelect={onSelect}
                    onRemove={removeItem}
                    onMove={moveItem}
                  />
                ))}
              </>
            )}
          </div>
        ))}

        {/* Add-group button */}
        <button
          onClick={addGroup}
          className="w-full flex items-center justify-center gap-1 py-1.5 text-[10px] text-[#787B86] hover:bg-[#1E222D] hover:text-[#D1D4DC] transition-colors"
        >
          <Plus size={10} />
          新建分组
        </button>
      </div>
    </div>
  );
}

// ── Ticker row with move-to-group dropdown ─────────────────────────────────

function TickerRow({
  item,
  isActive,
  groupId,
  allGroups,
  onSelect,
  onRemove,
  onMove,
}: {
  item: WatchlistItem;
  isActive: boolean;
  groupId: string;
  allGroups: WatchlistGroup[];
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => void;
  onMove: (fromGroupId: string, toGroupId: string, ticker: string) => void;
}) {
  const [showMove, setShowMove] = useState(false);
  const moveRef = useRef<HTMLDivElement>(null);

  // Close move dropdown on outside click
  useEffect(() => {
    if (!showMove) return;
    const handler = (e: MouseEvent) => {
      if (!moveRef.current?.contains(e.target as Node)) setShowMove(false);
    };
    window.addEventListener("mousedown", handler);
    return () => window.removeEventListener("mousedown", handler);
  }, [showMove]);

  const isPositive = (item.changePercent ?? 0) >= 0;
  const changeColor = isPositive ? COLORS.up : COLORS.down;
  const otherGroups = allGroups.filter((g) => g.id !== groupId);

  return (
    <div
      onClick={() => onSelect(item.ticker)}
      className="grid grid-cols-[1fr_60px_50px_40px] items-center px-3 py-1.5 cursor-pointer transition-colors group"
      style={{
        backgroundColor: isActive ? "#2A2E39" : "transparent",
      }}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = "#1E222D";
      }}
      onMouseLeave={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = "transparent";
      }}
    >
      <div className="flex items-center gap-1 min-w-0">
        <span className="font-medium text-[#D1D4DC] truncate">{item.ticker}</span>

        {/* Move-to dropdown trigger */}
        {otherGroups.length > 0 && (
          <div ref={moveRef} className="relative">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowMove((v) => !v);
              }}
              className="opacity-0 group-hover:opacity-100 text-[#787B86] hover:text-[#D1D4DC] transition-all p-0"
              title="移动到其他分组"
            >
              <MoreHorizontal size={10} />
            </button>
            {showMove && (
              <div className="absolute top-4 left-0 z-20 min-w-[80px] py-1 rounded bg-[#1E222D] border border-[#2B2B43] shadow-lg">
                {otherGroups.map((g) => (
                  <button
                    key={g.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onMove(groupId, g.id, item.ticker);
                      setShowMove(false);
                    }}
                    className="block w-full text-left px-2 py-1 text-[10px] text-[#D1D4DC] hover:bg-[#2A2E39] transition-colors"
                  >
                    → {g.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove(item.ticker);
          }}
          className="opacity-0 group-hover:opacity-100 text-[#787B86] hover:text-[#F23645] transition-all"
        >
          <X size={10} />
        </button>
      </div>
      <span className="text-right font-mono text-[#D1D4DC]">
        {item.lastPrice?.toFixed(2) ?? "—"}
      </span>
      <span className="text-right font-mono" style={{ color: changeColor }}>
        {item.change != null
          ? `${item.change >= 0 ? "+" : ""}${item.change.toFixed(2)}`
          : "—"}
      </span>
      <span className="text-right font-mono" style={{ color: changeColor }}>
        {item.changePercent != null
          ? `${item.changePercent >= 0 ? "+" : ""}${item.changePercent.toFixed(2)}%`
          : "—"}
      </span>
    </div>
  );
}
