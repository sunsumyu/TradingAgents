/**
 * DragonActivityPanel — 龙虎榜「席位活跃度 / 股票活跃度」结构化表。
 *
 * 后端 seat_activity / stock_activity parser 返回 `{ period, items, total }`,
 * 面板只声明列定义，交给共享 FeatureDataTable 渲染；kind:"raw" 或缺失时
 * 自动降级为 markdown（带「未结构化」角标）。
 */

import type { FeatureColumn } from "../../lib/types";
import { FeatureDataTable } from "../shared/GenericDataTable";

interface Props {
  data?: Record<string, unknown>;
  rawMd: string;
  title: string;
  accent: string;
  columns: FeatureColumn[];
  emptyText: string;
}

export function SeatActivityPanel({
  data,
  rawMd,
}: {
  data?: Record<string, unknown>;
  rawMd: string;
}) {
  const columns: FeatureColumn[] = [
    { key: "name", label: "营业部", unit: "text", format: "text" },
    { key: "turnover_wan", label: "龙虎榜成交额(万)", unit: "万元", format: "float2" },
    { key: "appear_count", label: "上榜次数", unit: "count", format: "int" },
    { key: "buy_amount_wan", label: "买入额(万)", unit: "万元", format: "float2" },
    { key: "sell_amount_wan", label: "卖出额(万)", unit: "万元", format: "float2" },
    { key: "net_buy_wan", label: "净买入额(万)", unit: "万元", format: "signed" },
  ];
  return (
    <DragonActivityPanel
      data={data}
      rawMd={rawMd}
      title="席位活跃度"
      accent="#FF9800"
      columns={columns}
      emptyText="暂无席位活跃度数据"
    />
  );
}

export function StockActivityPanel({
  data,
  rawMd,
}: {
  data?: Record<string, unknown>;
  rawMd: string;
}) {
  const columns: FeatureColumn[] = [
    { key: "code", label: "代码", unit: "text", format: "text" },
    { key: "name", label: "简称", unit: "text", format: "text" },
    { key: "last_appear_date", label: "最近上榜日", unit: "date", format: "date" },
    { key: "turnover_wan", label: "龙虎榜成交额(万)", unit: "万元", format: "float2" },
    { key: "appear_count", label: "上榜次数", unit: "count", format: "int" },
  ];
  return (
    <DragonActivityPanel
      data={data}
      rawMd={rawMd}
      title="股票活跃度"
      accent="#2962FF"
      columns={columns}
      emptyText="暂无股票活跃度数据"
    />
  );
}

function DragonActivityPanel({ data, rawMd, title, accent, columns, emptyText }: Props) {
  const period = typeof data?.period === "string" ? data.period : "";
  return (
    <div className="h-full flex flex-col">
      <div className="text-[12px] text-[#D1D4DC] font-medium px-3 pt-3 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full" style={{ backgroundColor: accent }} />
        {title}
        {period && <span className="text-[10px] text-[#787B86] font-normal">（{period}）</span>}
      </div>
      <FeatureDataTable
        columns={columns}
        data={data}
        rawMd={rawMd}
        emptyText={emptyText}
      />
    </div>
  );
}
