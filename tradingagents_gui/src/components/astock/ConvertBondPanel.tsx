/**
 * ConvertBondPanel — 可转债列表面板（Phase 12.06）。
 *
 * 数据来自东财 RPT_BOND_CB_LIST（1059 只全量，默认按申购日降序），
 * 经 `FeatureDataTable` 渲染（排序 / 分页 / raw 降级内置）。
 */

import { FeatureDataTable } from "../shared/GenericDataTable";
import type { FeatureColumn } from "../../lib/types";

interface Props {
  data?: Record<string, unknown> | null;
  rawMd?: string;
  loading?: boolean;
}

const COLUMNS: FeatureColumn[] = [
  { key: "bond_code", label: "转债代码", unit: "text", format: "text" },
  { key: "bond_name", label: "转债简称", unit: "text", format: "text" },
  { key: "market", label: "市场", unit: "text", format: "text" },
  { key: "stock_code", label: "正股代码", unit: "text", format: "text" },
  { key: "stock_name", label: "正股简称", unit: "text", format: "text" },
  { key: "rating", label: "评级", unit: "text", format: "text" },
  { key: "issue_scale_yi", label: "规模(亿元)", unit: "亿元", format: "float2" },
  { key: "convert_price", label: "转股价", unit: "元", format: "float2" },
  { key: "bond_price", label: "最新价", unit: "元", format: "float2" },
  { key: "public_start_date", label: "申购日", unit: "date", format: "date" },
  { key: "listing_date", label: "上市日", unit: "date", format: "date" },
  { key: "expire_date", label: "到期日", unit: "date", format: "date" },
];

export default function ConvertBondPanel({ data, rawMd = "", loading = false }: Props) {
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="text-[12px] text-text-primary font-medium px-3 pt-3 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full bg-[#7E57C2]" />
        可转债列表
      </div>
      <FeatureDataTable
        columns={COLUMNS}
        data={data ?? undefined}
        rawMd={rawMd}
        loading={loading}
        emptyText="暂无可转债数据"
      />
    </div>
  );
}
