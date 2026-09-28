/**
 * HotStocksEnhancedPanel - 热门股票增强面板
 *
 * 参考通达信"增强选股"功能，展示4个维度的热门股票：
 * 1. 今日关注 - 按成交额排序的热门股票
 * 2. 北向青睐 - 持续获北向资金加仓的股票
 * 3. 龙虎活跃 - 龙虎榜机构席位活跃的股票
 * 4. 机构关注 - 分析师覆盖最多的股票
 */

import { useEffect, useState } from "react";
import { Loader2, Star, TrendingUp, DollarSign, Users } from "lucide-react";
import { api } from "../../lib/api";
import { formatDateDisplay } from "../../lib/dateFormat";
import { useLanguage } from "../../lib/useLanguage";
import type {
  HotStocksPanelResponse,
  HotStockItem,
  NorthboundFavoriteItem,
  DragonTigerActiveItem,
  InstitutionalAttentionItem,
} from "../../lib/types";

interface Props {
  onAnalyzeTicker?: (ticker: string) => void;
}

export default function HotStocksEnhancedPanel({ onAnalyzeTicker }: Props) {
  const lang = useLanguage();
  const [data, setData] = useState<HotStocksPanelResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const resp = await api.getHotStocksPanel();
        if (mounted) {
          setData(resp);
        }
      } catch (err: any) {
        if (mounted) {
          setError(err?.message ?? String(err));
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      mounted = false;
    };
  }, []);

  const toggleFavorite = (ticker: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) {
        next.delete(ticker);
      } else {
        next.add(ticker);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={24} className="animate-spin text-accent" />
        <span className="ml-2 text-text-secondary text-sm">正在加载热门股票数据...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <span className="text-down text-sm"> {error}</span>
        <button
          onClick={() => window.location.reload()}
          className="text-xs text-accent hover:underline"
        >
          重试
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64 text-text-secondary text-sm">
        暂无数据
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-text-primary">热门股票</h2>
        <span className="text-xs text-text-secondary">数据日期：{formatDateDisplay(data.date, lang)}</span>
      </div>

      {/* 4-section grid */}
      <div className="grid grid-cols-2 gap-4">
        {/* Section 1: 今日关注 */}
        <StockSection
          title="今日关注"
          subtitle="按成交额排序"
          icon={<TrendingUp size={14} className="text-accent" />}
          stocks={data.attention}
          renderRow={(item: HotStockItem) => (
            <tr key={item.ticker}>
              <td className="px-2 py-1.5 text-left font-mono text-xs">{item.ticker}</td>
              <td className="px-2 py-1.5 text-left text-xs">{item.name}</td>
              <td className="px-2 py-1.5 text-right text-xs">
                {item.change_pct != null && (
                  <span className={item.change_pct > 0 ? "text-up" : item.change_pct < 0 ? "text-down" : "text-text-secondary"}>
                    {item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
                  </span>
                )}
              </td>
              <td className="px-2 py-1.5 text-right text-xs tabular-nums">
                {item.volume_wan != null ? `${(item.volume_wan / 10000).toFixed(2)}亿` : "—"}
              </td>
              <td className="px-2 py-1.5 text-right">
                <button
                  onClick={() => toggleFavorite(item.ticker)}
                  className="text-text-muted hover:text-accent transition-colors"
                  title="加自选"
                >
                  <Star
                    size={14}
                    fill={favorites.has(item.ticker) ? "currentColor" : "none"}
                    className={favorites.has(item.ticker) ? "text-accent" : ""}
                  />
                </button>
              </td>
            </tr>
          )}
          onAnalyzeTicker={onAnalyzeTicker}
        />

        {/* Section 2: 北向青睐 */}
        <StockSection
          title="北向青睐"
          subtitle="持续获北向资金加仓"
          icon={<DollarSign size={14} className="text-accent" />}
          stocks={data.northbound}
          renderRow={(item: NorthboundFavoriteItem) => (
            <tr key={item.ticker}>
              <td className="px-2 py-1.5 text-left font-mono text-xs">{item.ticker}</td>
              <td className="px-2 py-1.5 text-left text-xs">{item.name}</td>
              <td className="px-2 py-1.5 text-right text-xs">
                {item.change_pct != null && (
                  <span className={item.change_pct > 0 ? "text-up" : item.change_pct < 0 ? "text-down" : "text-text-secondary"}>
                    {item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
                  </span>
                )}
              </td>
              <td className="px-2 py-1.5 text-right text-xs tabular-nums">
                {item.northbound_net_wan != null ? `${(item.northbound_net_wan / 10000).toFixed(2)}亿` : "—"}
              </td>
              <td className="px-2 py-1.5 text-right">
                <button
                  onClick={() => toggleFavorite(item.ticker)}
                  className="text-text-muted hover:text-accent transition-colors"
                  title="加自选"
                >
                  <Star
                    size={14}
                    fill={favorites.has(item.ticker) ? "currentColor" : "none"}
                    className={favorites.has(item.ticker) ? "text-accent" : ""}
                  />
                </button>
              </td>
            </tr>
          )}
          onAnalyzeTicker={onAnalyzeTicker}
        />

        {/* Section 3: 龙虎活跃 */}
        <StockSection
          title="龙虎活跃"
          subtitle="龙虎榜机构席位活跃"
          icon={<TrendingUp size={14} className="text-accent" />}
          stocks={data.dragon_tiger}
          renderRow={(item: DragonTigerActiveItem) => (
            <tr key={item.ticker}>
              <td className="px-2 py-1.5 text-left font-mono text-xs">{item.ticker}</td>
              <td className="px-2 py-1.5 text-left text-xs">{item.name}</td>
              <td className="px-2 py-1.5 text-right text-xs">
                {item.change_pct != null && (
                  <span className={item.change_pct > 0 ? "text-up" : item.change_pct < 0 ? "text-down" : "text-text-secondary"}>
                    {item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
                  </span>
                )}
              </td>
              <td className="px-2 py-1.5 text-right text-xs tabular-nums">
                {item.net_buy_wan != null ? `${(item.net_buy_wan / 10000).toFixed(2)}亿` : "—"}
              </td>
              <td className="px-2 py-1.5 text-right">
                <button
                  onClick={() => toggleFavorite(item.ticker)}
                  className="text-text-muted hover:text-accent transition-colors"
                  title="加自选"
                >
                  <Star
                    size={14}
                    fill={favorites.has(item.ticker) ? "currentColor" : "none"}
                    className={favorites.has(item.ticker) ? "text-accent" : ""}
                  />
                </button>
              </td>
            </tr>
          )}
          onAnalyzeTicker={onAnalyzeTicker}
        />

        {/* Section 4: 机构关注 */}
        <StockSection
          title="机构关注"
          subtitle="分析师覆盖最多"
          icon={<Users size={14} className="text-accent" />}
          stocks={data.institutional}
          renderRow={(item: InstitutionalAttentionItem) => (
            <tr key={item.ticker}>
              <td className="px-2 py-1.5 text-left font-mono text-xs">{item.ticker}</td>
              <td className="px-2 py-1.5 text-left text-xs">{item.name}</td>
              <td className="px-2 py-1.5 text-right text-xs">
                {item.change_pct != null && (
                  <span className={item.change_pct > 0 ? "text-up" : item.change_pct < 0 ? "text-down" : "text-text-secondary"}>
                    {item.change_pct > 0 ? "+" : ""}{item.change_pct.toFixed(2)}%
                  </span>
                )}
              </td>
              <td className="px-2 py-1.5 text-right text-xs tabular-nums">
                {item.analyst_count != null ? item.analyst_count : "—"}
              </td>
              <td className="px-2 py-1.5 text-right">
                <button
                  onClick={() => toggleFavorite(item.ticker)}
                  className="text-text-muted hover:text-accent transition-colors"
                  title="加自选"
                >
                  <Star
                    size={14}
                    fill={favorites.has(item.ticker) ? "currentColor" : "none"}
                    className={favorites.has(item.ticker) ? "text-accent" : ""}
                  />
                </button>
              </td>
            </tr>
          )}
          onAnalyzeTicker={onAnalyzeTicker}
        />
      </div>
    </div>
  );
}

// ── Stock Section Component ──────────────────────────────────────────────

interface StockSectionProps<T> {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  stocks: T[];
  renderRow: (item: T) => React.ReactNode;
  onAnalyzeTicker?: (ticker: string) => void;
}

function StockSection<T extends { ticker: string }>({
  title,
  subtitle,
  icon,
  stocks,
  renderRow,
}: StockSectionProps<T>) {
  const [showAll, setShowAll] = useState(false);
  const displayStocks = showAll ? stocks : stocks.slice(0, 10);

  return (
    <div className="border border-line rounded-lg bg-bg-secondary overflow-hidden">
      {/* Section header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-line bg-bg-tertiary">
        {icon}
        <h3 className="text-sm font-medium text-text-primary">{title}</h3>
        <span className="text-xs text-text-secondary">{subtitle}</span>
      </div>

      {/* Stock table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-line/50">
              <th className="px-2 py-1.5 text-left font-medium text-text-secondary">代码</th>
              <th className="px-2 py-1.5 text-left font-medium text-text-secondary">名称</th>
              <th className="px-2 py-1.5 text-right font-medium text-text-secondary">涨幅</th>
              <th className="px-2 py-1.5 text-right font-medium text-text-secondary">
                {title === "机构关注" ? "评级数" : "变化值"}
              </th>
              <th className="px-2 py-1.5 text-right font-medium text-text-secondary">自选</th>
            </tr>
          </thead>
          <tbody>
            {displayStocks.map((stock) => renderRow(stock))}
            {stocks.length === 0 && (
              <tr>
                <td colSpan={5} className="px-2 py-4 text-center text-text-muted text-xs">
                  暂无数据
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Show more button */}
      {stocks.length > 10 && (
        <div className="px-3 py-1.5 border-t border-line bg-bg-tertiary">
          <button
            onClick={() => setShowAll(!showAll)}
            className="text-xs text-accent hover:underline"
          >
            {showAll ? "收起" : `查看全部 (${stocks.length}只)`}
          </button>
        </div>
      )}
    </div>
  );
}
