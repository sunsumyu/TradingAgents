/**
 * RightInfoPanel — 对标通达信右侧信息栏完整实现。
 *
 * Self-sufficient: fetches its own data from the backend API when the
 * quote prop is not provided. This ensures the panel always shows data
 * even if the realtime WebSocket hook fails.
 *
 * Shows:
 * - 五档买卖盘 (bid/ask 5 levels)
 * - 委比/委差
 * - 现价/涨跌/涨幅
 * - 总量/外盘/内盘/换手
 * - PE/PB/总市值/流通值
 * - 财务摘要 (营收/净利润)
 * - 股东变动
 * - 基金持仓
 * - 分红信息
 */

import { useState, useEffect } from "react";
import type { RealtimePrice, FundamentalsData } from "../../lib/types";
import { api } from "../../lib/api";

interface StockInfoData {
  financial?: {
    revenue?: { value: number; yoy?: number };
    net_profit?: { value: number; yoy?: number };
    non_recurring?: { value: number };
    cash?: { value: number };
  };
  shareholder?: {
    shareholders?: Array<{
      name: string;
      change: string;
      method: string;
      period?: string;
    }>;
  };
  fund?: {
    funds?: Array<{
      name: string;
      pct: number;
      value: number;
    }>;
    total_funds?: number;
  };
  dividend?: {
    dividends?: Array<{
      date: string;
      dividend: string;
      status: string;
    }>;
  };
  announcements?: {
    announcements?: Array<{
      date: string;
      title: string;
      url?: string;
    }>;
  };
}

interface Props {
  quote?: RealtimePrice;
  fundamentals?: FundamentalsData;
  ticker?: string;
}

function signColor(v: number): string {
  return v > 0 ? "text-[#F23645]" : v < 0 ? "text-[#26A69A]" : "text-[#787B86]";
}

function fmtVol(v: number | undefined | null): string {
  if (!v) return "--";
  if (v >= 10000) return (v / 10000).toFixed(2) + "万";
  return String(v);
}

function fmtYi(v: number | undefined | null): string {
  if (!v) return "--";
  return v.toFixed(2) + "亿";
}

export default function RightInfoPanel({ quote: _quote, fundamentals, ticker }: Props) {
  const [stockInfo, setStockInfo] = useState<StockInfoData | null>(null);
  const [localQuote, setLocalQuote] = useState<RealtimePrice | null>(null);

  // Fetch stock info when ticker changes
  useEffect(() => {
    if (!ticker) return;
    console.log('[RightInfoPanel] fetching stock info for', ticker);
    api.getStockInfo(ticker)
      .then(data => {
        console.log('[RightInfoPanel] got stock info:', Object.keys(data));
        setStockInfo(data);
      })
      .catch(err => {
        console.warn('[RightInfoPanel] stock info failed:', err);
        setStockInfo(null);
      });
  }, [ticker]);

  // Always fetch quote directly on a timer (every 5 seconds)
  useEffect(() => {
    if (!ticker) return;
    console.log('[RightInfoPanel] starting auto-refresh for', ticker);

    const fetchQuote = () => {
      api.getRealtimePrices([ticker])
        .then(data => {
          const q = data[ticker];
          if (q) {
            console.log('[RightInfoPanel] auto-refresh got:', q.price, 'bid1:', q.bid1_price);
            setLocalQuote(q);
          }
        })
        .catch(err => {
          console.warn('[RightInfoPanel] auto-refresh failed:', err);
        });
    };

    fetchQuote(); // initial fetch
    const timer = setInterval(fetchQuote, 5000); // refresh every 5 seconds

    return () => {
      console.log('[RightInfoPanel] stopping auto-refresh for', ticker);
      clearInterval(timer);
    };
  }, [ticker]);

  // Always use locally fetched quote (auto-refreshes every 5s)
  const effectiveQuote = localQuote;

  if (!effectiveQuote) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#787B86] text-xs gap-2">
        <span>暂无行情数据 {ticker ? `(${ticker})` : ''}</span>
      </div>
    );
  }

  // 计算委比
  const bidVol = (effectiveQuote.bid1_vol || 0) + (effectiveQuote.bid2_vol || 0) + (effectiveQuote.bid3_vol || 0) + (effectiveQuote.bid4_vol || 0) + (effectiveQuote.bid5_vol || 0);
  const askVol = (effectiveQuote.ask1_vol || 0) + (effectiveQuote.ask2_vol || 0) + (effectiveQuote.ask3_vol || 0) + (effectiveQuote.ask4_vol || 0) + (effectiveQuote.ask5_vol || 0);
  const totalVol = bidVol + askVol;
  const weiBi = totalVol > 0 ? ((bidVol - askVol) / totalVol * 100).toFixed(2) : "0.00";
  const weiCha = bidVol - askVol;

  return (
    <div className="h-full overflow-y-auto bg-[#0D1117] text-[11px]">
      {/* 五档盘口 */}
      <div className="border-b border-[#1E222D]">
        <div className="px-2 py-1 bg-[#131722] text-[#787B86] font-medium">五档盘口</div>
        <table className="w-full">
          <tbody>
            {/* 卖五 to 卖一 */}
            {[
              { price: effectiveQuote.ask5_price, vol: effectiveQuote.ask5_vol },
              { price: effectiveQuote.ask4_price, vol: effectiveQuote.ask4_vol },
              { price: effectiveQuote.ask3_price, vol: effectiveQuote.ask3_vol },
              { price: effectiveQuote.ask2_price, vol: effectiveQuote.ask2_vol },
              { price: effectiveQuote.ask1_price, vol: effectiveQuote.ask1_vol },
            ].map((item, i) => (
              <tr key={`ask${5 - i}`} className="border-b border-[#1E222D]/30">
                <td className="px-2 py-0.5 text-[#787B86]">卖{5 - i}</td>
                <td className="px-1 py-0.5 text-right text-[#26A69A] tabular-nums">{item.price?.toFixed(2) || "--"}</td>
                <td className="px-2 py-0.5 text-right text-[#787B86] tabular-nums">{fmtVol(item.vol)}</td>
              </tr>
            ))}
            {/* 买一到买五 */}
            {[
              { price: effectiveQuote.bid1_price, vol: effectiveQuote.bid1_vol },
              { price: effectiveQuote.bid2_price, vol: effectiveQuote.bid2_vol },
              { price: effectiveQuote.bid3_price, vol: effectiveQuote.bid3_vol },
              { price: effectiveQuote.bid4_price, vol: effectiveQuote.bid4_vol },
              { price: effectiveQuote.bid5_price, vol: effectiveQuote.bid5_vol },
            ].map((item, i) => (
              <tr key={`bid${i + 1}`} className="border-b border-[#1E222D]/30">
                <td className="px-2 py-0.5 text-[#787B86]">买{i + 1}</td>
                <td className="px-1 py-0.5 text-right text-[#F23645] tabular-nums">{item.price?.toFixed(2) || "--"}</td>
                <td className="px-2 py-0.5 text-right text-[#787B86] tabular-nums">{fmtVol(item.vol)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 委比/委差 */}
      <div className="border-b border-[#1E222D] px-2 py-1 flex justify-between">
        <span className="text-[#787B86]">委比</span>
        <span className={signColor(Number(weiBi))}>{weiBi}%</span>
      </div>
      <div className="border-b border-[#1E222D] px-2 py-1 flex justify-between">
        <span className="text-[#787B86]">委差</span>
        <span className={signColor(weiCha)}>{fmtVol(weiCha)}</span>
      </div>

      {/* 现价/涨跌/涨幅 */}
      <div className="border-b border-[#1E222D] px-2 py-1.5">
        <div className="flex items-baseline gap-2">
          <span className="text-[16px] font-bold tabular-nums text-[#D1D4DC]">{effectiveQuote.price.toFixed(2)}</span>
          <span className={`text-[12px] tabular-nums ${signColor(effectiveQuote.change)}`}>
            {effectiveQuote.change > 0 ? "+" : ""}{effectiveQuote.change.toFixed(2)}
          </span>
          <span className={`text-[12px] tabular-nums ${signColor(effectiveQuote.changePct)}`}>
            {effectiveQuote.changePct > 0 ? "+" : ""}{effectiveQuote.changePct.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* 总量/外盘/内盘/换手 */}
      <div className="border-b border-[#1E222D]">
        <div className="px-2 py-1 flex justify-between">
          <span className="text-[#787B86]">总量</span>
          <span className="text-[#D1D4DC] tabular-nums">{fmtVol(effectiveQuote.volume)}</span>
        </div>
        <div className="px-2 py-1 flex justify-between border-t border-[#1E222D]/30">
          <span className="text-[#787B86]">外盘</span>
          <span className="text-[#F23645] tabular-nums">{fmtVol(effectiveQuote.outer_disc)}</span>
        </div>
        <div className="px-2 py-1 flex justify-between border-t border-[#1E222D]/30">
          <span className="text-[#787B86]">内盘</span>
          <span className="text-[#26A69A] tabular-nums">{fmtVol(effectiveQuote.inner_disc)}</span>
        </div>
        <div className="px-2 py-1 flex justify-between border-t border-[#1E222D]/30">
          <span className="text-[#787B86]">换手</span>
          <span className="text-[#D1D4DC] tabular-nums">{effectiveQuote.turnover_pct?.toFixed(2) || "--"}%</span>
        </div>
      </div>

      {/* PE/PB/总市值/流通值 */}
      <div className="px-2 py-1">
        <div className="flex justify-between">
          <span className="text-[#787B86]">PE(TTM)</span>
          <span className="text-[#D1D4DC] tabular-nums">{effectiveQuote.pe_ttm?.toFixed(2) || fundamentals?.pe_ratio?.toFixed(2) || "--"}</span>
        </div>
        <div className="flex justify-between border-t border-[#1E222D]/30 mt-1 pt-1">
          <span className="text-[#787B86]">PB</span>
          <span className="text-[#D1D4DC] tabular-nums">{effectiveQuote.pb?.toFixed(2) || fundamentals?.pb_ratio?.toFixed(2) || "--"}</span>
        </div>
        <div className="flex justify-between border-t border-[#1E222D]/30 mt-1 pt-1">
          <span className="text-[#787B86]">总市值</span>
          <span className="text-[#D1D4DC] tabular-nums">{fmtYi(effectiveQuote.mcap_yi)}</span>
        </div>
        <div className="flex justify-between border-t border-[#1E222D]/30 mt-1 pt-1">
          <span className="text-[#787B86]">流通值</span>
          <span className="text-[#D1D4DC] tabular-nums">{fmtYi(effectiveQuote.float_mcap_yi)}</span>
        </div>
      </div>

      {/* 财务摘要 */}
      {stockInfo?.financial && (
        <div className="border-t border-[#1E222D] px-2 py-1">
          <div className="text-[#787B86] font-medium mb-1">财务摘要</div>
          {stockInfo.financial.revenue && (
            <div className="flex justify-between">
              <span className="text-[#787B86]">营收</span>
              <span className="text-[#D1D4DC] tabular-nums">
                {stockInfo.financial.revenue.value.toFixed(2)}亿
                {stockInfo.financial.revenue.yoy ? (
                  <span className={signColor(stockInfo.financial.revenue.yoy)}>
                    {" "}{stockInfo.financial.revenue.yoy > 0 ? "+" : ""}{stockInfo.financial.revenue.yoy.toFixed(1)}%
                  </span>
                ) : null}
              </span>
            </div>
          )}
          {stockInfo.financial.net_profit && (
            <div className="flex justify-between border-t border-[#1E222D]/30 mt-1 pt-1">
              <span className="text-[#787B86]">净利润</span>
              <span className={`tabular-nums ${signColor(stockInfo.financial.net_profit.value)}`}>
                {stockInfo.financial.net_profit.value.toFixed(2)}亿
                {stockInfo.financial.net_profit.yoy ? (
                  <span className={signColor(stockInfo.financial.net_profit.yoy)}>
                    {" "}{stockInfo.financial.net_profit.yoy > 0 ? "+" : ""}{stockInfo.financial.net_profit.yoy.toFixed(1)}%
                  </span>
                ) : null}
              </span>
            </div>
          )}
        </div>
      )}

      {/* 基金持仓 */}
      {stockInfo?.fund?.funds && stockInfo.fund.funds.length > 0 && (
        <div className="border-t border-[#1E222D] px-2 py-1">
          <div className="text-[#787B86] font-medium mb-1">基金持仓 ({stockInfo.fund.total_funds}家)</div>
          {stockInfo.fund.funds.slice(0, 3).map((f, i) => (
            <div key={i} className="flex justify-between text-[10px]">
              <span className="text-[#D1D4DC] truncate">{f.name}</span>
              <span className="text-[#787B86] tabular-nums ml-2">{f.pct.toFixed(2)}%</span>
            </div>
          ))}
        </div>
      )}

      {/* 分红 */}
      {stockInfo?.dividend?.dividends && stockInfo.dividend.dividends.length > 0 && (
        <div className="border-t border-[#1E222D] px-2 py-1">
          <div className="text-[#787B86] font-medium mb-1">分红</div>
          {stockInfo.dividend.dividends.slice(0, 2).map((d, i) => (
            <div key={i} className="flex justify-between text-[10px]">
              <span className="text-[#787B86]">{d.date}</span>
              <span className="text-[#D1D4DC] tabular-nums">派息{d.dividend}元</span>
            </div>
          ))}
        </div>
      )}

      {/* 股东变动 */}
      {stockInfo?.shareholder?.shareholders && stockInfo.shareholder.shareholders.length > 0 && (
        <div className="border-t border-[#1E222D] px-2 py-1">
          <div className="text-[#787B86] font-medium mb-1">股东变动</div>
          {stockInfo.shareholder.shareholders.slice(0, 3).map((s, i) => (
            <div key={i} className="text-[10px] py-0.5">
              <div className="flex justify-between">
                <span className="text-[#D1D4DC] truncate">{s.name}</span>
                <span className={`tabular-nums ml-2 ${s.change.includes('增持') ? 'text-[#F23645]' : 'text-[#26A69A]'}`}>
                  {s.change}
                </span>
              </div>
              <div className="text-[#787B86] text-[9px]">{s.method} {s.period}</div>
            </div>
          ))}
        </div>
      )}

      {/* 最新公告 */}
      {stockInfo?.announcements?.announcements && stockInfo.announcements.announcements.length > 0 && (
        <div className="border-t border-[#1E222D] px-2 py-1">
          <div className="text-[#787B86] font-medium mb-1">最新公告</div>
          {stockInfo.announcements.announcements.slice(0, 3).map((a, i) => (
            <div key={i} className="text-[10px] py-0.5">
              <div className="text-[#D1D4DC] truncate" title={a.title}>
                {a.title.replace(/^[^:]+:/, '')}
              </div>
              <div className="text-[#787B86] text-[9px]">{a.date}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
