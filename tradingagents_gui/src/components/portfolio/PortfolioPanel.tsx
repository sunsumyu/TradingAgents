/**
 * PortfolioPanel — Simulated paper trading portfolio (Phase 6, ticket 6.04).
 *
 * Shows positions with P&L, trade dialog, trade history, and NAV chart.
 */

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ArrowUpDown, RotateCcw, X } from "lucide-react";
import ReactECharts from "echarts-for-react";
import { api } from "../../lib/api";
import type { PortfolioResponse, TradeRecord, NavPoint } from "../../lib/types";
import { Card } from "../ui";

// ── Trade Dialog ────────────────────────────────────────────────────────────

interface TradeDialogProps {
  ticker: string;
  name?: string;
  onTrade: (action: "buy" | "sell", qty: number, price: number, reason: string) => Promise<void>;
  onClose: () => void;
}

function TradeDialog({ ticker, name, onTrade, onClose }: TradeDialogProps) {
  const [action, setAction] = useState<"buy" | "sell">("buy");
  const [qty, setQty] = useState("100");
  const [price, setPrice] = useState("");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    const q = parseInt(qty, 10);
    const p = parseFloat(price);
    if (!q || q <= 0) { setError("数量必须大于0"); return; }
    if (!p || p <= 0) { setError("价格必须大于0"); return; }

    setLoading(true);
    setError("");
    try {
      await onTrade(action, q, p, reason);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-bg-secondary border border-line rounded-lg p-4 w-80 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-[13px] font-medium text-text-primary">
            交易 {ticker} {name ? `(${name})` : ""}
          </span>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X size={14} />
          </button>
        </div>

        {/* Buy/Sell toggle */}
        <div className="flex gap-2 mb-3">
          {(["buy", "sell"] as const).map((a) => (
            <button
              key={a}
              className={`flex-1 py-1.5 text-[12px] rounded border transition-colors ${
                action === a
                  ? a === "buy"
                    ? "bg-up/15 border-up/40 text-up"
                    : "bg-down/15 border-down/40 text-down"
                  : "border-line text-text-secondary hover:bg-bg-hover"
              }`}
              onClick={() => setAction(a)}
            >
              {a === "buy" ? "买入" : "卖出"}
            </button>
          ))}
        </div>

        <div className="space-y-2">
          <div>
            <label className="text-[11px] text-text-secondary">数量（股）</label>
            <input
              type="number"
              className="input w-full mt-0.5"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              min="1"
              step="100"
            />
          </div>
          <div>
            <label className="text-[11px] text-text-secondary">价格（元）</label>
            <input
              type="number"
              className="input w-full mt-0.5"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="留空使用最新价"
              step="0.01"
            />
          </div>
          <div>
            <label className="text-[11px] text-text-secondary">原因（可选）</label>
            <input
              type="text"
              className="input w-full mt-0.5"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="如：AI信号-强烈买入"
            />
          </div>
        </div>

        {error && (
          <div className="mt-2 text-[11px] text-down">{error}</div>
        )}

        <button
          className={`w-full mt-3 py-2 text-[12px] font-medium rounded transition-colors ${
            action === "buy"
              ? "bg-up text-white hover:bg-up/80"
              : "bg-down text-white hover:bg-down/80"
          }`}
          onClick={handleSubmit}
          disabled={loading}
        >
          {loading ? "执行中..." : action === "buy" ? "确认买入" : "确认卖出"}
        </button>
      </div>
    </div>
  );
}

// ── NAV Chart ───────────────────────────────────────────────────────────────

function NavChart({ data }: { data: NavPoint[] }) {
  if (data.length < 2) return null;

  const option = {
    grid: { top: 8, right: 8, bottom: 24, left: 48 },
    xAxis: {
      type: "category" as const,
      data: data.map((d) => d.date),
      axisLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 10 },
    },
    yAxis: {
      type: "value" as const,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "#2B2B43" } },
      axisLabel: { color: "#787B86", fontSize: 10, formatter: (v: number) => `${(v / 10000).toFixed(0)}万` },
    },
    series: [{
      type: "line" as const,
      data: data.map((d) => d.nav),
      smooth: true,
      symbol: "none",
      lineStyle: { color: "#2962FF", width: 1.5 },
      areaStyle: {
        color: {
          type: "linear" as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: "rgba(41,98,255,0.2)" },
            { offset: 1, color: "rgba(41,98,255,0)" },
          ],
        },
      },
    }],
    tooltip: {
      trigger: "axis" as const,
      backgroundColor: "#1E222D",
      borderColor: "#2B2B43",
      textStyle: { color: "#D1D4DC", fontSize: 11 },
      formatter: (params: any) => {
        const p = params[0];
        return `${p.name}<br/>净值: ¥${Number(p.value).toLocaleString()}`;
      },
    },
  };

  return <ReactECharts option={option} style={{ height: 160 }} />;
}

// ── Main Component ──────────────────────────────────────────────────────────

interface Props {
  onBack: () => void;
}

export default function PortfolioPanel({ onBack }: Props) {
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [navHistory, setNavHistory] = useState<NavPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"positions" | "history">("positions");
  const [tradeDialog, setTradeDialog] = useState<{ ticker: string; name?: string } | null>(null);
  const [sortKey, setSortKey] = useState<"pnl_pct" | "pnl" | "market_value">("pnl_pct");
  const [sortAsc, setSortAsc] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [p, h, n] = await Promise.all([
        api.getPortfolio(),
        api.getPortfolioHistory(),
        api.getPortfolioNav(),
      ]);
      setPortfolio(p);
      setTrades(h);
      setNavHistory(n.nav_history);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleTrade = useCallback(async (action: "buy" | "sell", qty: number, price: number, reason: string) => {
    if (!tradeDialog) return;
    const p = await api.portfolioTrade(tradeDialog.ticker, action, qty, price, tradeDialog.name, reason);
    setPortfolio(p);
    const [h, n] = await Promise.all([api.getPortfolioHistory(), api.getPortfolioNav()]);
    setTrades(h);
    setNavHistory(n.nav_history);
  }, [tradeDialog]);

  const handleReset = useCallback(async () => {
    if (!confirm("确认重置组合？所有持仓和交易记录将清空。")) return;
    const p = await api.resetPortfolio();
    setPortfolio(p);
    setTrades([]);
    setNavHistory([]);
  }, []);

  const sortedPositions = portfolio
    ? [...portfolio.positions].sort((a, b) => {
        const av = a[sortKey] ?? 0;
        const bv = b[sortKey] ?? 0;
        return sortAsc ? av - bv : bv - av;
      })
    : [];

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-text-secondary text-[13px]">
        加载中...
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="h-10 shrink-0 border-b border-line flex items-center px-4 bg-bg-secondary/60">
        <button className="btn-ghost text-[12px]" onClick={onBack}>
          <ArrowLeft size={13} />
          返回
        </button>
        <span className="ml-3 text-[13px] font-medium text-text-primary">模拟组合</span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Summary cards */}
        {portfolio && (
          <div className="grid grid-cols-4 gap-3">
            <Card>
              <div className="text-[11px] text-text-secondary">总资产</div>
              <div className="text-[16px] font-medium text-text-primary mt-1">
                ¥{portfolio.total_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </Card>
            <Card>
              <div className="text-[11px] text-text-secondary">总盈亏</div>
              <div className={`text-[16px] font-medium mt-1 ${portfolio.total_pnl >= 0 ? "text-up" : "text-down"}`}>
                {portfolio.total_pnl >= 0 ? "+" : ""}¥{portfolio.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </Card>
            <Card>
              <div className="text-[11px] text-text-secondary">收益率</div>
              <div className={`text-[16px] font-medium mt-1 ${portfolio.total_pnl_pct >= 0 ? "text-up" : "text-down"}`}>
                {portfolio.total_pnl_pct >= 0 ? "+" : ""}{portfolio.total_pnl_pct.toFixed(2)}%
              </div>
            </Card>
            <Card>
              <div className="text-[11px] text-text-secondary">可用现金</div>
              <div className="text-[16px] font-medium text-text-primary mt-1">
                ¥{portfolio.cash.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </div>
            </Card>
          </div>
        )}

        {/* NAV chart */}
        {navHistory.length >= 2 && (
          <Card title="收益曲线">
            <NavChart data={navHistory} />
          </Card>
        )}

        {/* Positions / History tabs */}
        <div className="flex items-center gap-2 border-b border-line pb-1">
          {(["positions", "history"] as const).map((tab) => (
            <button
              key={tab}
              className={`px-3 py-1 text-[12px] rounded transition-colors ${
                activeTab === tab
                  ? "bg-accent/15 text-accent"
                  : "text-text-secondary hover:text-text-primary"
              }`}
              onClick={() => setActiveTab(tab)}
            >
              {tab === "positions" ? "持仓" : `交易记录 (${trades.length})`}
            </button>
          ))}
          <div className="ml-auto flex gap-1">
            <button
              className="text-[11px] text-text-secondary hover:text-down flex items-center gap-1"
              onClick={handleReset}
              title="重置组合"
            >
              <RotateCcw size={11} />
              重置
            </button>
          </div>
        </div>

        {/* Positions table */}
        {activeTab === "positions" && (
          <Card>
            {sortedPositions.length === 0 ? (
              <div className="text-center py-8 text-text-muted text-[12px]">
                暂无持仓，点击「交易」按钮开始模拟交易
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="border-b border-line">
                      <th className="text-left py-1.5 font-medium text-text-secondary">代码</th>
                      <th className="text-left py-1.5 font-medium text-text-secondary">名称</th>
                      <th className="text-right py-1.5 font-medium text-text-secondary">数量</th>
                      <th className="text-right py-1.5 font-medium text-text-secondary">成本</th>
                      <th className="text-right py-1.5 font-medium text-text-secondary">现价</th>
                      <th
                        className="text-right py-1.5 font-medium text-text-secondary cursor-pointer hover:text-text-primary"
                        onClick={() => setSortKey((k) => { setSortAsc(k === "market_value"); return "market_value"; })}
                      >
                        市值 <ArrowUpDown size={9} className="inline" />
                      </th>
                      <th
                        className="text-right py-1.5 font-medium text-text-secondary cursor-pointer hover:text-text-primary"
                        onClick={() => setSortKey((k) => { setSortAsc(k === "pnl"); return "pnl"; })}
                      >
                        盈亏 <ArrowUpDown size={9} className="inline" />
                      </th>
                      <th
                        className="text-right py-1.5 font-medium text-text-secondary cursor-pointer hover:text-text-primary"
                        onClick={() => setSortKey((k) => { setSortAsc(k === "pnl_pct"); return "pnl_pct"; })}
                      >
                        收益率 <ArrowUpDown size={9} className="inline" />
                      </th>
                      <th className="w-16" />
                    </tr>
                  </thead>
                  <tbody>
                    {sortedPositions.map((pos) => (
                      <tr key={pos.ticker} className="border-b border-line/50 hover:bg-bg-hover">
                        <td className="py-1.5 font-mono text-accent">{pos.ticker}</td>
                        <td className="py-1.5">{pos.name || "—"}</td>
                        <td className="py-1.5 text-right tabular-nums">{pos.quantity}</td>
                        <td className="py-1.5 text-right tabular-nums">{pos.avg_cost.toFixed(2)}</td>
                        <td className="py-1.5 text-right tabular-nums">
                          {pos.current_price != null ? pos.current_price.toFixed(2) : "—"}
                        </td>
                        <td className="py-1.5 text-right tabular-nums">
                          ¥{pos.market_value.toLocaleString()}
                        </td>
                        <td className={`py-1.5 text-right tabular-nums ${pos.pnl >= 0 ? "text-up" : "text-down"}`}>
                          {pos.pnl >= 0 ? "+" : ""}{pos.pnl.toFixed(2)}
                        </td>
                        <td className={`py-1.5 text-right tabular-nums ${pos.pnl_pct >= 0 ? "text-up" : "text-down"}`}>
                          {pos.pnl_pct >= 0 ? "+" : ""}{pos.pnl_pct.toFixed(2)}%
                        </td>
                        <td className="py-1.5 text-right">
                          <button
                            className="text-[11px] text-accent hover:underline"
                            onClick={() => setTradeDialog({ ticker: pos.ticker, name: pos.name })}
                          >
                            交易
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )}

        {/* Trade history */}
        {activeTab === "history" && (
          <Card>
            {trades.length === 0 ? (
              <div className="text-center py-8 text-text-muted text-[12px]">
                暂无交易记录
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="border-b border-line">
                      <th className="text-left py-1.5 font-medium text-text-secondary">时间</th>
                      <th className="text-left py-1.5 font-medium text-text-secondary">代码</th>
                      <th className="text-left py-1.5 font-medium text-text-secondary">操作</th>
                      <th className="text-right py-1.5 font-medium text-text-secondary">数量</th>
                      <th className="text-right py-1.5 font-medium text-text-secondary">价格</th>
                      <th className="text-right py-1.5 font-medium text-text-secondary">金额</th>
                      <th className="text-left py-1.5 font-medium text-text-secondary">原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((t) => (
                      <tr key={t.id} className="border-b border-line/50 hover:bg-bg-hover">
                        <td className="py-1.5 text-text-secondary">{t.timestamp.slice(0, 16)}</td>
                        <td className="py-1.5 font-mono text-accent">{t.ticker}</td>
                        <td className={`py-1.5 font-medium ${t.action === "buy" ? "text-up" : "text-down"}`}>
                          {t.action === "buy" ? "买入" : "卖出"}
                        </td>
                        <td className="py-1.5 text-right tabular-nums">{t.quantity}</td>
                        <td className="py-1.5 text-right tabular-nums">{t.price.toFixed(2)}</td>
                        <td className="py-1.5 text-right tabular-nums">¥{t.total.toLocaleString()}</td>
                        <td className="py-1.5 text-text-secondary truncate max-w-[200px]">{t.reason || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )}

        {error && (
          <div className="px-3 py-2 rounded bg-down/10 border border-down/30 text-down text-[12px]">
            {error}
          </div>
        )}
      </div>

      {/* Trade dialog */}
      {tradeDialog && (
        <TradeDialog
          ticker={tradeDialog.ticker}
          name={tradeDialog.name}
          onTrade={handleTrade}
          onClose={() => setTradeDialog(null)}
        />
      )}
    </div>
  );
}
