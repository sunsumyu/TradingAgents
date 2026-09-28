/**
 * MarginTradingPanel — 融资融券面板。
 *
 * Three sections:
 * 1. Detail ranking table (top 50)
 * 2. Market statistics time series (ECharts line/area chart)
 * 3. Industry distribution (ECharts bar chart) — placeholder until backend aggregation
 */

import { useEffect, useRef } from "react";
import { formatDateShort } from "../../lib/dateFormat";
import { useLanguage } from "../../lib/useLanguage";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  data: any;
  rawMd: string;
  feature: string;
}

function fmtYi(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v / 1e8).toFixed(2)}亿`;
}

function fmtWan(v: number | null | undefined): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1e4) return `${(v / 1e4).toFixed(2)}亿`;
  return `${v.toFixed(0)}万`;
}

function signColor(v: number): string {
  return v > 0 ? "text-[#F23645]" : v < 0 ? "text-[#26A69A]" : "text-[#787B86]";
}

function MarketStatChart({ data, lang }: { data: { items: Array<{ date: string; margin_balance: number; margin_buy: number; short_qty: number; short_balance: number; total_balance: number }> }; lang: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !data.items?.length) return;
    let chart: any;
    import("echarts").then(({ init }) => {
      chart = init(ref.current!);
      const dates = data.items.map((d) => formatDateShort(d.date, lang));
      const balances = data.items.map((d) => ((d.margin_balance ?? 0) / 1e8));
      chart.setOption({
        tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
        grid: { left: 50, right: 20, top: 10, bottom: 30 },
        xAxis: { type: "category", data: dates, axisLabel: { color: "#787B86", fontSize: 10 } },
        yAxis: { type: "value", name: "亿", nameTextStyle: { color: "#787B86" }, axisLabel: { color: "#787B86" }, splitLine: { lineStyle: { color: "#1E222D" } } },
        series: [{ type: "line", data: balances, smooth: true, showSymbol: false, lineStyle: { color: "#2962FF", width: 2 }, areaStyle: { color: { type: "linear", x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: "rgba(41,98,255,0.3)" }, { offset: 1, color: "rgba(41,98,255,0.02)" }] } } }],
      });
    });
    return () => { chart?.dispose(); };
  }, [data]);

  return <div ref={ref} className="w-full h-[180px]" />;
}

export default function MarginTradingPanel({ data, rawMd, feature }: Props) {
  const lang = useLanguage();
  // Determine which sub-data to show based on feature
  const items = data?.items ?? [];
  const market = data?.market ?? "—";

  if (!items.length && !rawMd) {
    return (
      <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
        暂无融资融券数据
      </div>
    );
  }

  if (!items.length && rawMd) {
    return <div className="h-full overflow-y-auto"><MarkdownRenderer markdown={rawMd} className="p-3" /></div>;
  }

  // margin_detail: show ranking table
  if (feature === "margin_detail") {
    return (
      <div className="h-full overflow-y-auto p-3 space-y-4">
        <div>
          <div className="text-[12px] text-[#D1D4DC] font-medium mb-2 flex items-center gap-2">
            <span className="w-1 h-3.5 rounded-full bg-[#2962FF]" />
            融资融券明细（{market}）
            <span className="text-[10px] text-[#787B86] font-normal">（共 {data?.total ?? items.length} 只，展示前 50）</span>
          </div>
          <div className="overflow-x-auto rounded border border-[#1E222D]">
            <table className="w-full text-[11px] border-collapse">
              <thead>
                <tr className="bg-[#1E222D]/80 border-b border-[#2A2E39]">
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">#</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">代码</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">简称</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">融资余额</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">融资买入</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">融资偿还</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">净买入</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">融券余量</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">融券卖出</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">融券偿还</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">净卖出</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item: any, i: number) => (
                  <tr key={item.code} className="border-b border-[#1E222D]/60 last:border-0 hover:bg-[#2A2E39]/50">
                    <td className="px-2.5 py-1.5 text-right text-[#787B86]">{i + 1}</td>
                    <td className="px-2.5 py-1.5 text-left font-mono text-[#D1D4DC]">{item.code}</td>
                    <td className="px-2.5 py-1.5 text-left text-[#D1D4DC]">{item.name}</td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-[#D1D4DC]">{fmtYi(item.margin_balance)}</td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-[#D1D4DC]">{fmtYi(item.margin_buy)}</td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-[#D1D4DC]">{fmtYi(item.margin_repay)}</td>
                    <td className={`px-2.5 py-1.5 text-right tabular-nums font-medium ${signColor(item.net_buy ?? 0)}`}>{fmtYi(item.net_buy)}</td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-[#787B86]">{fmtWan(item.short_qty)}</td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-[#787B86]">{fmtWan(item.short_sell)}</td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-[#787B86]">{fmtWan(item.short_repay)}</td>
                    <td className={`px-2.5 py-1.5 text-right tabular-nums ${signColor(item.net_short ?? 0)}`}>{fmtWan(item.net_short)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  // margin_market_stat: show market stat chart
  if (feature === "margin_market_stat") {
    return (
      <div className="h-full overflow-y-auto p-3 space-y-4">
        <div>
          <div className="text-[12px] text-[#D1D4DC] font-medium mb-2 flex items-center gap-2">
            <span className="w-1 h-3.5 rounded-full bg-[#26A69A]" />
            融资融券市场统计
            <span className="text-[10px] text-[#787B86] font-normal">（近 {items.length} 个交易日）</span>
          </div>
          <div className="rounded border border-[#1E222D] bg-[#131722] p-2">
            <MarketStatChart data={{ items }} lang={lang} />
          </div>
        </div>
      </div>
    );
  }

  // margin_industry: show industry distribution
  if (feature === "margin_industry") {
    return (
      <div className="h-full overflow-y-auto p-3 space-y-4">
        <div>
          <div className="text-[12px] text-[#D1D4DC] font-medium mb-2 flex items-center gap-2">
            <span className="w-1 h-3.5 rounded-full bg-[#FF9800]" />
            融资融券行业分布
          </div>
          <div className="overflow-x-auto rounded border border-[#1E222D]">
            <table className="w-full text-[11px] border-collapse">
              <thead>
                <tr className="bg-[#1E222D]/80 border-b border-[#2A2E39]">
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">行业</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">融资余额占比%</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">融券余额占比%</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item: any, i: number) => (
                  <tr key={item.industry || i} className="border-b border-[#1E222D]/60 last:border-0 hover:bg-[#2A2E39]/50">
                    <td className="px-2.5 py-1.5 text-left text-[#D1D4DC]">{item.industry}</td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-[#D1D4DC]">{item.margin_ratio_pct?.toFixed(2) ?? "—"}</td>
                    <td className="px-2.5 py-1.5 text-right tabular-nums text-[#D1D4DC]">{item.short_ratio_pct?.toFixed(2) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  // Fallback
  return <div className="h-full overflow-y-auto p-3"><MarkdownRenderer markdown={rawMd} /></div>;
}
