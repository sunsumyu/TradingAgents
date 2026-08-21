import type { FundamentalsData } from "../../lib/types";

interface Props {
  data: FundamentalsData;
}

function formatNumber(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(1)}万`;
  return n.toLocaleString();
}

function formatPercent(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(2)}%`;
}

function Card({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-[#1E222D] rounded-lg border border-[#363A45] px-4 py-3 min-w-[140px]">
      <div className="text-[11px] text-[#787B86] mb-1">{label}</div>
      <div className="text-[14px] font-semibold" style={{ color: color || "#D1D4DC" }}>
        {value}
      </div>
    </div>
  );
}

export default function FundamentalCards({ data }: Props) {
  const name = data.name || data.sector || "";

  return (
    <div className="mb-3">
      {name && (
        <div className="text-[12px] text-[#787B86] mb-2 px-1">
          {name}
          {data.sector && <span className="ml-2 text-[#555]">| {data.sector}</span>}
          {data.industry && <span className="ml-1 text-[#555]">| {data.industry}</span>}
        </div>
      )}
      <div className="flex gap-3 flex-wrap">
        <Card label="市值" value={formatNumber(data.market_cap)} />
        <Card label="PE (TTM)" value={data.pe_ratio?.toFixed(1) ?? "—"} />
        <Card label="Forward PE" value={data.forward_pe?.toFixed(1) ?? "—"} />
        <Card label="PB" value={data.pb_ratio?.toFixed(2) ?? "—"} />
        <Card label="EPS (TTM)" value={data.eps_ttm?.toFixed(2) ?? "—"} />
        <Card label="股息率" value={formatPercent(data.dividend_yield)} />
        <Card label="Beta" value={data.beta?.toFixed(2) ?? "—"} />
        <Card label="52周最高" value={data.fifty_two_week_high?.toFixed(2) ?? "—"} color="#089981" />
        <Card label="52周最低" value={data.fifty_two_week_low?.toFixed(2) ?? "—"} color="#F23645" />
        <Card label="50日均线" value={data.fifty_day_average?.toFixed(2) ?? "—"} />
        <Card label="200日均线" value={data.two_hundred_day_average?.toFixed(2) ?? "—"} />
      </div>
    </div>
  );
}
