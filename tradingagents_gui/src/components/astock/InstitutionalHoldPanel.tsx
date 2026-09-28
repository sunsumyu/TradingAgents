/**
 * InstitutionalHoldPanel — 机构持股面板.
 *
 * Sample consumer of GenericDataTable (ticket 05): the backend
 * `institutional_hold` parser (ticket 06) returns `{ items, total }`, so this
 * panel only declares its columns and hands the rows over — no bespoke table
 * code. `kind: "raw"` / missing items degrade to markdown via the shared
 * component (with the "未结构化" badge).
 */

import { FeatureDataTable } from "../shared/GenericDataTable";
import type { FeatureColumn } from "../../lib/types";

interface Props {
  data?: Record<string, unknown>;
  rawMd: string;
}

const COLUMNS: FeatureColumn[] = [
  { key: "code", label: "代码", unit: "text", format: "text" },
  { key: "name", label: "名称", unit: "text", format: "text" },
  { key: "industry", label: "行业", unit: "text", format: "text" },
  { key: "inst_count", label: "机构数", unit: "count", format: "int" },
  { key: "shares_wan", label: "持仓(万股)", unit: "万股", format: "float2" },
  { key: "market_value_wan", label: "市值(万元)", unit: "万元", format: "float2" },
  { key: "total_pct", label: "占总股本", unit: "percent", format: "float2" },
  { key: "float_pct", label: "占流通A股", unit: "percent", format: "float2" },
  { key: "change_wan", label: "较上期", unit: "万股", format: "signed" },
  { key: "position_type", label: "仓位类型", unit: "text", format: "text" },
];

export default function InstitutionalHoldPanel({ data, rawMd }: Props) {
  if (!rawMd && !data) {
    return (
      <div className="flex items-center justify-center h-full text-text-muted text-xs">
        暂无机构持股数据
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="text-[12px] text-text-primary font-medium px-3 pt-3 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full bg-[#E040FB]" />
        机构持股
      </div>
      <FeatureDataTable
        columns={COLUMNS}
        data={data}
        rawMd={rawMd}
        emptyText="暂无机构持股数据"
      />
    </div>
  );
}
