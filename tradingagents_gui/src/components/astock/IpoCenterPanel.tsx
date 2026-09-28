/**
 * IpoCenterPanel — 新股中心面板（发行预告 + 上市预告）。
 *
 * Two sub-tables:
 * 1. IPO Declaration (新股发行预告): stocks pending subscription
 * 2. IPO Listing (新股上市预告): stocks listing soon
 */

import type {
  IpoDeclarationData,
  IpoDeclarationItem,
  IpoListingData,
  IpoListingItem,
} from "../../lib/types";
import { formatDateDisplay } from "../../lib/dateFormat";
import { useLanguage } from "../../lib/useLanguage";
import MarkdownRenderer from "../shared/Markdown";

interface Props {
  declarationData?: IpoDeclarationData;
  listingData?: IpoListingData;
  declarationMd: string;
  listingMd: string;
  onStockClick?: (ticker: string) => void;
}

const EMPTY_CELL = "—";

function TableCell({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-2.5 py-1.5 text-right tabular-nums text-[#D1D4DC] ${className}`}>{children ?? EMPTY_CELL}</td>;
}

function DeclarationRow({ item, index, onStockClick, lang }: { item: IpoDeclarationItem; index: number; onStockClick?: (t: string) => void; lang: string }) {
  return (
    <tr className="border-b border-[#1E222D]/60 last:border-0 hover:bg-[#2A2E39]/50">
      <td className="px-2.5 py-1.5 text-right text-[#787B86]">{index}</td>
      <td className="px-2.5 py-1.5 text-left">
        <button
          className="text-[#2962FF] hover:underline cursor-pointer bg-transparent border-0 p-0 font-mono"
          onClick={() => onStockClick?.(item.code)}
        >
          {item.code}
        </button>
      </td>
      <td className="px-2.5 py-1.5 text-left text-[#D1D4DC]">{item.name}</td>
      <td className="px-2.5 py-1.5 text-left text-[#D1D4DC]">{formatDateDisplay(item.subscribe_date, lang) || EMPTY_CELL}</td>
      <td className="px-2.5 py-1.5 text-left text-[#787B86] font-mono">{item.subscribe_code || EMPTY_CELL}</td>
      <TableCell>{item.price != null ? item.price.toFixed(2) : null}</TableCell>
      <TableCell>{item.volume_wan != null ? item.volume_wan.toFixed(2) : null}</TableCell>
      <TableCell>{item.online_volume_wan != null ? item.online_volume_wan.toFixed(2) : null}</TableCell>
      <TableCell>{item.subscribe_limit_wan != null ? item.subscribe_limit_wan.toFixed(2) : null}</TableCell>
      <TableCell>{item.pe_ratio != null ? item.pe_ratio.toFixed(2) : null}</TableCell>
      <td className="px-2.5 py-1.5 text-left text-[#787B86]">{formatDateDisplay(item.lottery_date, lang) || EMPTY_CELL}</td>
    </tr>
  );
}

function ListingRow({ item, index, onStockClick, lang }: { item: IpoListingItem; index: number; onStockClick?: (t: string) => void; lang: string }) {
  return (
    <tr className="border-b border-[#1E222D]/60 last:border-0 hover:bg-[#2A2E39]/50">
      <td className="px-2.5 py-1.5 text-right text-[#787B86]">{index}</td>
      <td className="px-2.5 py-1.5 text-left">
        <button
          className="text-[#2962FF] hover:underline cursor-pointer bg-transparent border-0 p-0 font-mono"
          onClick={() => onStockClick?.(item.code)}
        >
          {item.code}
        </button>
      </td>
      <td className="px-2.5 py-1.5 text-left text-[#D1D4DC]">{item.name}</td>
      <td className="px-2.5 py-1.5 text-left text-[#D1D4DC]">{formatDateDisplay(item.listing_date, lang) || EMPTY_CELL}</td>
      <TableCell>{item.price != null ? item.price.toFixed(2) : null}</TableCell>
      <TableCell>{item.volume_wan != null ? item.volume_wan.toFixed(2) : null}</TableCell>
      <TableCell>{item.online_volume_wan != null ? item.online_volume_wan.toFixed(2) : null}</TableCell>
      <TableCell>{item.pe_ratio != null ? item.pe_ratio.toFixed(2) : null}</TableCell>
      <td className="px-2.5 py-1.5 text-left text-[#787B86]">{formatDateDisplay(item.subscribe_date, lang) || EMPTY_CELL}</td>
      <td className="px-2.5 py-1.5 text-right text-[#D1D4DC] tabular-nums">
        {item.win_rate != null ? `${(item.win_rate * 100).toFixed(4)}%` : EMPTY_CELL}
      </td>
    </tr>
  );
}

export default function IpoCenterPanel({ declarationData, listingData, declarationMd, listingMd, onStockClick }: Props) {
  const lang = useLanguage();
  const declarations = declarationData?.items ?? [];
  const listings = listingData?.items ?? [];

  if (declarations.length === 0 && listings.length === 0) {
    if (declarationMd || listingMd) {
      return (
        <div className="h-full overflow-y-auto">
          <MarkdownRenderer markdown={`${declarationMd}\n\n${listingMd}`.trim()} className="p-3" />
        </div>
      );
    }
    return (
      <div className="flex items-center justify-center h-full text-[#787B86] text-xs">暂无新股数据</div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-4">
      {/* 新股发行预告 */}
      {declarations.length > 0 && (
        <div>
          <div className="text-[12px] text-[#D1D4DC] font-medium mb-2 flex items-center gap-2">
            <span className="w-1 h-3.5 rounded-full bg-[#2962FF]" />
            新股发行预告
            <span className="text-[10px] text-[#787B86] font-normal">（共 {declarations.length} 只）</span>
          </div>
          <div className="overflow-x-auto rounded border border-[#1E222D]">
            <table className="w-full text-[11px] border-collapse">
              <thead>
                <tr className="bg-[#1E222D]/80 border-b border-[#2A2E39]">
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">#</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">代码</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">简称</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">申购日</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">申购代码</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">申购价</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">发行量(万)</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">网上发行(万)</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">上限(万)</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">PE</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">中签公布日</th>
                </tr>
              </thead>
              <tbody>
                {declarations.map((item, i) => (
                  <DeclarationRow key={item.code} item={item} index={i + 1} onStockClick={onStockClick} lang={lang} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 新股上市预告 */}
      {listings.length > 0 && (
        <div>
          <div className="text-[12px] text-[#D1D4DC] font-medium mb-2 flex items-center gap-2">
            <span className="w-1 h-3.5 rounded-full bg-[#26A69A]" />
            新股上市预告
            <span className="text-[10px] text-[#787B86] font-normal">（共 {listings.length} 只）</span>
          </div>
          <div className="overflow-x-auto rounded border border-[#1E222D]">
            <table className="w-full text-[11px] border-collapse">
              <thead>
                <tr className="bg-[#1E222D]/80 border-b border-[#2A2E39]">
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">#</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">代码</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">简称</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">上市日</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">发行价</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">发行量(万)</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">网上发行(万)</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">PE</th>
                  <th className="px-2.5 py-1.5 text-left text-[#787B86] font-medium">申购日</th>
                  <th className="px-2.5 py-1.5 text-right text-[#787B86] font-medium">中签率%</th>
                </tr>
              </thead>
              <tbody>
                {listings.map((item, i) => (
                  <ListingRow key={item.code} item={item} index={i + 1} onStockClick={onStockClick} lang={lang} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
