/**
 * AlertPanel — manage price alerts with add/remove/toggle.
 *
 * Shows:
 * - Add form: ticker, condition (above/below), target price
 * - Alert list: each with ticker, condition, target, current price, status
 * - Toggle enable/disable, remove button
 *
 * Designed to be rendered inside a dialog/popover triggered from ChartHeader.
 */

import { useState } from "react";
import { Plus, Trash2, Bell, BellOff, X } from "lucide-react";
import type { PriceAlert, RealtimePrice } from "../../lib/types";

interface Props {
  alerts: PriceAlert[];
  prices: Map<string, RealtimePrice>;
  currentTicker: string;
  currentPrice?: number | null;
  onAdd: (ticker: string, name: string | null, condition: "above" | "below", targetPrice: number) => void;
  onRemove: (id: string) => void;
  onToggle: (id: string) => void;
  onClose: () => void;
}

export default function AlertPanel({
  alerts,
  prices,
  currentTicker,
  currentPrice,
  onAdd,
  onRemove,
  onToggle,
  onClose,
}: Props) {
  const [ticker, setTicker] = useState(currentTicker);
  const [condition, setCondition] = useState<"above" | "below">("above");
  const [targetStr, setTargetStr] = useState(currentPrice != null ? String(currentPrice) : "");

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
            {alerts.map((alert) => {
              const quote = prices.get(alert.ticker);
              const current = quote?.price;
              return (
                <div
                  key={alert.id}
                  className={`px-3 py-2 flex items-center gap-2 ${
                    alert.triggered ? "bg-[#FF9800]/5" : ""
                  }`}
                >
                  <button
                    onClick={() => onToggle(alert.id)}
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
                      <span className={alert.condition === "above" ? "text-[#F23645]" : "text-[#26A69A]"}>
                        {alert.condition === "above" ? "↑ 高于" : "↓ 低于"}
                      </span>
                      <span className="tabular-nums">{alert.target_price}</span>
                      {current != null && (
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
                    onClick={() => onRemove(alert.id)}
                    className="shrink-0 text-[#4C525E] hover:text-[#F23645] p-0.5 transition-colors"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
