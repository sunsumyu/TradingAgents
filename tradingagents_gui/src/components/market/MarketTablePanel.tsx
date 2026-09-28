/**
 * MarketTablePanel — 市场页通用结构化小表组（调研/统计等单表型 feature）。
 *
 * 每张表声明列定义并交给共享 FeatureDataTable（排序/分页/markdown 降级），
 * 页面只负责把 parser 输出的分区 items 映射进来。
 */

import type { FeatureColumn } from "../../lib/types";
import { FeatureDataTable } from "../shared/GenericDataTable";

export interface MarketTableSpec {
  title: string;
  accent: string;
  columns: FeatureColumn[];
  items: Record<string, unknown>[];
  emptyText?: string;
}

interface Props {
  rawMd: string;
  tables: MarketTableSpec[];
}

export default function MarketTablePanel({ rawMd, tables }: Props) {
  return (
    <div className="h-full overflow-y-auto" data-testid="market-table-panel">
      {tables.map((spec) => (
        <div key={spec.title} className="mb-4">
          <div className="text-[12px] text-[#D1D4DC] font-medium px-3 pt-3 flex items-center gap-2">
            <span className="w-1 h-3.5 rounded-full" style={{ backgroundColor: spec.accent }} />
            {spec.title}
          </div>
          <FeatureDataTable
            columns={spec.columns}
            data={{ items: spec.items }}
            rawMd={rawMd}
            emptyText={spec.emptyText ?? "暂无数据"}
          />
        </div>
      ))}
    </div>
  );
}
