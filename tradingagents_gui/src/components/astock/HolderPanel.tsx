/**
 * HolderPanel — 持仓股东面板（Phase 12.02）。
 *
 * 一个组件三种形态（由 FeatureRenderer 按 feature key 传入 mode）：
 *   - "num":      股东户数披露历史（holder_num）
 *   - "free":     十大流通股东（free_holders）
 *   - "increase": 股东增减持记录（holder_increase）
 *
 * 数据源：东财 datacenter / securities F10（已实测核实）；经
 * `FeatureDataTable` 渲染（排序 / 分页 / raw 降级内置）。
 */

import { FeatureDataTable } from "../shared/GenericDataTable";
import type { FeatureColumn } from "../../lib/types";

export type HolderPanelMode = "num" | "free" | "increase";

interface Props {
  mode: HolderPanelMode;
  data?: Record<string, unknown> | null;
  rawMd?: string;
  loading?: boolean;
}

const TITLES: Record<HolderPanelMode, string> = {
  num: "股东户数",
  free: "十大流通股东",
  increase: "股东增减持",
};

const NUM_COLUMNS: FeatureColumn[] = [
  { key: "end_date", label: "报告期", unit: "date", format: "date" },
  { key: "holder_num", label: "股东户数", unit: "count", format: "int" },
  { key: "holder_num_change", label: "较上期增减", unit: "count", format: "signed" },
  { key: "holder_num_ratio", label: "环比增幅", unit: "percent", format: "float2" },
  { key: "hold_notice_date", label: "公告日期", unit: "date", format: "date" },
];

const FREE_COLUMNS: FeatureColumn[] = [
  { key: "holder_rank", label: "排名", unit: "count", format: "int" },
  { key: "holder_name", label: "股东名称", unit: "text", format: "text" },
  { key: "hold_num_wan", label: "持股数量(万股)", unit: "万股", format: "float2" },
  { key: "free_ratio", label: "占流通股比", unit: "percent", format: "float2" },
  { key: "end_date", label: "报告期", unit: "date", format: "date" },
];

const INCREASE_COLUMNS: FeatureColumn[] = [
  { key: "notice_date", label: "公告日", unit: "date", format: "date" },
  { key: "holder_name", label: "股东名称", unit: "text", format: "text" },
  { key: "direction", label: "方向", unit: "text", format: "text" },
  { key: "change_num_wan", label: "变动股数(万股)", unit: "万股", format: "signed" },
  { key: "hold_ratio", label: "变动后持股比例", unit: "percent", format: "float2" },
];

const COLUMNS: Record<HolderPanelMode, FeatureColumn[]> = {
  num: NUM_COLUMNS,
  free: FREE_COLUMNS,
  increase: INCREASE_COLUMNS,
};

export default function HolderPanel({ mode, data, rawMd = "", loading = false }: Props) {
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="text-[12px] text-text-primary font-medium px-3 pt-3 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full bg-[#E040FB]" />
        {TITLES[mode]}
      </div>
      <FeatureDataTable
        columns={COLUMNS[mode]}
        data={data ?? undefined}
        rawMd={rawMd}
        loading={loading}
        emptyText={`暂无${TITLES[mode]}数据`}
      />
    </div>
  );
}
