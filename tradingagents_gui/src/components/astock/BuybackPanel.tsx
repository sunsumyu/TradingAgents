/**
 * BuybackPanel — 股票回购面板（Phase 12.03）。
 *
 * 数据来自东财 RPTA_WEB_GPHG（最新公告一批，按回购金额降序），
 * 经 `FeatureDataTable` 渲染。
 */

import { FeatureDataTable } from "../shared/GenericDataTable";
import type { FeatureColumn } from "../../lib/types";

interface Props {
  data?: Record<string, unknown> | null;
  rawMd?: string;
  loading?: boolean;
}

const COLUMNS: FeatureColumn[] = [
  { key: "notice_date", label: "公告日", unit: "date", format: "date" },
  { key: "code", label: "代码", unit: "text", format: "text" },
  { key: "name", label: "简称", unit: "text", format: "text" },
  { key: "amount_wan", label: "回购金额(万)", unit: "万元", format: "float2" },
  { key: "shares_wan", label: "回购数量(万股)", unit: "万股", format: "float2" },
  { key: "price_low", label: "最低价", unit: "元", format: "float2" },
  { key: "price_high", label: "最高价", unit: "元", format: "float2" },
  { key: "price", label: "市价", unit: "元", format: "float2" },
  { key: "change_pct", label: "涨跌幅", unit: "percent", format: "float2" },
];

export default function BuybackPanel({ data, rawMd = "", loading = false }: Props) {
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="text-[12px] text-text-primary font-medium px-3 pt-3 flex items-center gap-2">
        <span className="w-1 h-3.5 rounded-full bg-[#26A69A]" />
        股票回购
      </div>
      <FeatureDataTable
        columns={COLUMNS}
        data={data ?? undefined}
        rawMd={rawMd}
        loading={loading}
        emptyText="暂无回购数据"
      />
    </div>
  );
}
