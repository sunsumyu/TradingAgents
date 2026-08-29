/**
 * LockupPanel — lockup expiry calendar with history + future batches.
 *
 * Two sections:
 * - Future batches (if any): highlighted warning row
 * - History batches: table with date, type, quantity, ratio
 */

import type { LockupExpiryData } from "../../lib/types";

interface Props {
  data: LockupExpiryData;
  rawMd: string;
}

function fmtQty(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (v >= 1e4) return `${(v / 1e4).toFixed(1)}万`;
  return v.toLocaleString();
}

function fmtRatio(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

export default function LockupPanel({ data, rawMd }: Props) {
  const { batches, future_batches, has_future } = data;

  if (!batches.length && !future_batches.length) {
    return (
      <div className="h-full overflow-y-auto">
        {rawMd ? (
          <pre className="text-[11px] text-[#787B86] p-3 whitespace-pre-wrap leading-relaxed">
            {rawMd}
          </pre>
        ) : (
          <div className="flex items-center justify-center h-full text-[#787B86] text-xs">
            暂无解禁数据
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-3">
      {/* Future batches warning */}
      {has_future && future_batches.length > 0 && (
        <div>
          <div className="text-[11px] text-[#FF9800] mb-1 flex items-center gap-1">
            <span>⚠</span> 未来 90 天待解禁 ({future_batches.length} 批)
          </div>
          <div className="bg-[#FF9800]/10 rounded border border-[#FF9800]/30 overflow-hidden">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-[#FF9800]/20">
                  <th className="text-left px-2.5 py-1 text-[#FF9800] font-medium">日期</th>
                  <th className="text-left px-2.5 py-1 text-[#FF9800] font-medium">类型</th>
                  <th className="text-right px-2.5 py-1 text-[#FF9800] font-medium">数量</th>
                  <th className="text-right px-2.5 py-1 text-[#FF9800] font-medium">占比</th>
                </tr>
              </thead>
              <tbody>
                {future_batches.map((b) => (
                  <tr key={b.date} className="border-b border-[#FF9800]/10 last:border-0">
                    <td className="px-2.5 py-1 text-[#D1D4DC]">{b.date}</td>
                    <td className="px-2.5 py-1 text-[#787B86]">{b.shares_type || "—"}</td>
                    <td className="px-2.5 py-1 text-right tabular-nums text-[#D1D4DC]">
                      {fmtQty(b.quantity)}
                    </td>
                    <td className="px-2.5 py-1 text-right tabular-nums text-[#FF9800]">
                      {fmtRatio(b.ratio)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!has_future && (
        <div className="text-[11px] text-[#26A69A] flex items-center gap-1">
          <span>✓</span> 未来 90 天无待解禁
        </div>
      )}

      {/* History batches */}
      {batches.length > 0 && (
        <div>
          <div className="text-[11px] text-[#787B86] mb-1">
            历史解禁记录 ({batches.length} 批)
          </div>
          <div className="bg-[#1E222D] rounded border border-[#363A45] overflow-hidden">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="border-b border-[#363A45]">
                  <th className="text-left px-2.5 py-1 text-[#787B86] font-medium">日期</th>
                  <th className="text-left px-2.5 py-1 text-[#787B86] font-medium">类型</th>
                  <th className="text-right px-2.5 py-1 text-[#787B86] font-medium">数量</th>
                  <th className="text-right px-2.5 py-1 text-[#787B86] font-medium">占比</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.date} className="border-b border-[#363A45]/50 last:border-0">
                    <td className="px-2.5 py-1 text-[#D1D4DC]">{b.date}</td>
                    <td className="px-2.5 py-1 text-[#787B86]">{b.shares_type || "—"}</td>
                    <td className="px-2.5 py-1 text-right tabular-nums text-[#D1D4DC]">
                      {fmtQty(b.quantity)}
                    </td>
                    <td className="px-2.5 py-1 text-right tabular-nums text-[#D1D4DC]">
                      {fmtRatio(b.ratio)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
