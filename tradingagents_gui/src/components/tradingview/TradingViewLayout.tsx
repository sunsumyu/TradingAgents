/**
 * TradingViewLayout — Full TradingView-style layout orchestrator.
 *
 * Assembles: ChartHeader + TimeframeSelector + DrawingToolbar + TradingViewChart + WatchlistPanel.
 * Also renders ECharts sub-panels (MACD, RSI, Bollinger) below the main chart.
 *
 * Supports timeframe switching: when the user clicks a different timeframe,
 * fresh chart data is fetched from /api/chart-data with the corresponding
 * day range, and all panels are updated.
 */

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Loader2, Camera, Image, Maximize2, Minimize2 } from "lucide-react";
import { api } from "../../lib/api";
import type { MacdData, RsiData, BollingerData } from "../../lib/types";
import { useChartStore } from "../../lib/useChartStore";
import { useRealtimePrices } from "../../lib/useRealtimePrices";
import { usePriceAlerts } from "../../lib/usePriceAlerts";
import type { CrosshairInfo, Timeframe } from "./types";
import { TIMEFRAME_DAYS, isMinuteTimeframe } from "./types";
import TradingViewChart from "./TradingViewChart";
import ChartHeader from "./ChartHeader";
import MultiChartLayout from "./MultiChartLayout";
import AlertPanel from "../astock/AlertPanel";
import TimeframeSelector from "./TimeframeSelector";
import ReplayControls from "./ReplayControls";
import IndicatorBar from "./IndicatorBar";
import DrawingToolbar from "./DrawingToolbar";
import WatchlistPanel from "./WatchlistPanel";
import SubPanels from "./SubPanels";
import {
  computeSmaSeries,
  computeMacdSeries,
  computeRsiSeries,
  loadIndicatorParams,
  saveIndicatorParams,
  type IndicatorParams,
} from "../../lib/chart-utils";

interface Props {
  kline: any | null;
  macd?: MacdData | null;
  rsi?: RsiData | null;
  bollinger?: BollingerData | null;
  ticker: string;
  name?: string;
}

export default function TradingViewLayout({
  kline: initialKline,
  bollinger: initialBollinger,
  ticker: initialTicker,
  name: initialName,
}: Props) {
  // ── Zustand store selectors ────────────────────────────────────────────────
  const crosshairInfo = useChartStore((s) => s.crosshairInfo);
  const activeTool = useChartStore((s) => s.activeTool);
  const timeframe = useChartStore((s) => s.timeframe);
  const activeOverlays = useChartStore((s) => s.activeOverlays);
  const isMultiChart = useChartStore((s) => s.isMultiChart);
  const isPlaying = useChartStore((s) => s.isPlaying);
  const replayDate = useChartStore((s) => s.replayDate);
  const ticker = useChartStore((s) => s.ticker);
  const stockName = useChartStore((s) => s.stockName);
  const kline = useChartStore((s) => s.kline);
  const bollinger = useChartStore((s) => s.bollinger);
  const isLoading = useChartStore((s) => s.isLoading);
  const loadError = useChartStore((s) => s.loadError);

  // Store actions
  const storeSetCrosshairInfo = useChartStore((s) => s.setCrosshairInfo);
  const storeSetActiveTool = useChartStore((s) => s.setActiveTool);
  const storeSetTimeframe = useChartStore((s) => s.setTimeframe);
  const storeToggleOverlay = useChartStore((s) => s.toggleOverlay);
  const storeSetMultiChart = useChartStore((s) => s.setMultiChart);
  const storeSetIsPlaying = useChartStore((s) => s.setIsPlaying);
  const storeSetReplayDate = useChartStore((s) => s.setReplayDate);
  const storeSetTicker = useChartStore((s) => s.setTicker);
  const storeSetKline = useChartStore((s) => s.setKline);
  const storeSetBollinger = useChartStore((s) => s.setBollinger);
  const storeSetLoading = useChartStore((s) => s.setLoading);
  const storeSetLoadError = useChartStore((s) => s.setLoadError);

  // UI-only state (not shared cross-component)
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isReplayVisible, setIsReplayVisible] = useState(false);
  const replayAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) setIsFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isFullscreen]);

  // Overlay toggle — delegated to store
  const handleToggleOverlay = useCallback((key: string) => {
    storeToggleOverlay(key);
  }, [storeToggleOverlay]);

  // AbortController for竞态处理 — cancel previous request when switching timeframes/tickers
  const abortRef = useRef<AbortController | null>(null);

  // Chart area container — used for screenshot export
  const chartAreaRef = useRef<HTMLDivElement>(null);

  // ── Screenshot export (client-side) ──────────────────────────────────────
  const handleScreenshot = useCallback(() => {
    const area = chartAreaRef.current;
    if (!area) return;

    // Collect canvases: ECharts main canvas(es) + drawing overlay canvas
    const echartsCanvases = Array.from(area.querySelectorAll<HTMLCanvasElement>(
      "canvas:not([data-drawing-canvas])",
    ));
    const drawingCanvas = area.querySelector<HTMLCanvasElement>("canvas[data-drawing-canvas]");
    if (echartsCanvases.length === 0) return;

    const dpr = window.devicePixelRatio || 1;
    // Output at 2x CSS pixels × devicePixelRatio for a crisp Retina image
    const w = Math.round(area.clientWidth * dpr * 2);
    const h = Math.round(area.clientHeight * dpr * 2);

    const out = document.createElement("canvas");
    out.width = w;
    out.height = h;
    const ctx = out.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#131722";
    ctx.fillRect(0, 0, w, h);

    // Composite: ECharts canvas(es) first, drawing overlay on top
    for (const src of [...echartsCanvases, ...(drawingCanvas ? [drawingCanvas] : [])]) {
      if (!src.width || !src.height) continue;
      ctx.drawImage(src, 0, 0, src.width, src.height, 0, 0, w, h);
    }

    const url = out.toDataURL("image/png");
    const link = document.createElement("a");
    link.href = url;
    link.download = `${ticker}_chart_${new Date().toISOString().slice(0, 10)}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [ticker]);

  // ── Server-side high-DPI export (ticket #7) ─────────────────────────────
  const [exporting, setExporting] = useState(false);
  const handleServerExport = useCallback(async () => {
    if (exporting) return;
    setExporting(true);
    try {
      const days = TIMEFRAME_DAYS[timeframe];
      const interval = isMinuteTimeframe(timeframe) ? timeframe : null;
      const blob = await api.exportChart({
        ticker,
        date: new Date().toISOString().slice(0, 10),
        days,
        interval,
        overlays: activeOverlays,
        width: 1920,
        height: 1080,
        dpi: 150,
      });
      // Save via Tauri dialog
      const { save } = await import("@tauri-apps/plugin-dialog");
      const { writeFile } = await import("@tauri-apps/plugin-fs");
      const filePath = await save({
        defaultPath: `${ticker}_chart_${new Date().toISOString().slice(0, 10)}.png`,
        filters: [{ name: "PNG Image", extensions: ["png"] }],
      });
      if (filePath) {
        const arrayBuffer = await blob.arrayBuffer();
        await writeFile(filePath, new Uint8Array(arrayBuffer));
      }
    } catch (err: any) {
      const msg = err?.message ?? String(err);
      if (msg.includes("503") || msg.includes("matplotlib") || msg.includes("pip install")) {
        alert("图表导出需要 matplotlib。\n请执行：pip install \"tradingagents[export]\"");
      } else {
        console.error("Chart export failed:", err);
      }
    } finally {
      setExporting(false);
    }
  }, [ticker, timeframe, activeOverlays, exporting]);

  // Sync initial props into Zustand store on mount
  useEffect(() => {
    storeSetTicker(initialTicker, initialName);
    storeSetKline(initialKline);
    storeSetBollinger(initialBollinger ?? null);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCrosshairMove = useCallback((info: CrosshairInfo | null) => {
    storeSetCrosshairInfo(info);
  }, [storeSetCrosshairInfo]);

  // ── Ticker switch handler (from Watchlist click) ───────────────────────────
  const handleTickerChange = useCallback(
    async (newTicker: string) => {
      if (newTicker === ticker) return; // already showing this ticker

      // Cancel any in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      storeSetTicker(newTicker);
      storeSetLoading(true);
      storeSetLoadError(null);

      const days = TIMEFRAME_DAYS[timeframe];
      const interval = isMinuteTimeframe(timeframe) ? timeframe : null;
      try {
        const data = await api.getChartData(newTicker, new Date().toISOString().slice(0, 10), days, controller.signal, interval);
        if (!controller.signal.aborted) {
          storeSetKline(data.kline ?? null);
          storeSetBollinger(data.bollinger ?? null);
          storeSetTicker(newTicker, undefined); // clear old name
        }
      } catch (err: any) {
        if (err.name !== "AbortError" && !controller.signal.aborted) {
          console.error("Failed to fetch chart data for", newTicker, err);
          storeSetLoadError(`加载 ${newTicker} 数据失败: ${err.message}`);
        }
      } finally {
        if (!controller.signal.aborted) {
          storeSetLoading(false);
        }
      }
    },
    [ticker, timeframe, storeSetTicker, storeSetLoading, storeSetLoadError, storeSetKline, storeSetBollinger],
  );

  // ── Timeframe switch handler ─────────────────────────────────────────────
  const handleTimeframeChange = useCallback(
    async (tf: Timeframe) => {
      if (tf === timeframe && !isLoading) return; // already showing this timeframe

      // Cancel any in-flight request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      storeSetTimeframe(tf);
      storeSetLoading(true);
      storeSetLoadError(null);

      const days = TIMEFRAME_DAYS[tf];
      const interval = isMinuteTimeframe(tf) ? tf : null;
      try {
        const data = await api.getChartData(ticker, new Date().toISOString().slice(0, 10), days, controller.signal, interval);
        if (!controller.signal.aborted) {
          storeSetKline(data.kline ?? null);
          storeSetBollinger(data.bollinger ?? null);
        }
      } catch (err: any) {
        if (err.name !== "AbortError" && !controller.signal.aborted) {
          console.error("Failed to fetch chart data:", err);
          storeSetLoadError(`加载${tf}周期数据失败: ${err.message}`);
        }
      } finally {
        if (!controller.signal.aborted) {
          storeSetLoading(false);
        }
      }
    },
    [timeframe, isLoading, ticker, storeSetTimeframe, storeSetLoading, storeSetLoadError, storeSetKline, storeSetBollinger],
  );

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => { abortRef.current?.abort(); replayAbortRef.current?.abort(); };
  }, []);

  // ── K-line replay date change handler ─────────────────────────────────────
  const handleReplayDateChange = useCallback(
    async (date: string) => {
      if (date === replayDate) return;

      replayAbortRef.current?.abort();
      const controller = new AbortController();
      replayAbortRef.current = controller;

      storeSetReplayDate(date);
      storeSetLoading(true);
      storeSetLoadError(null);

      const days = TIMEFRAME_DAYS[timeframe];
      const interval = isMinuteTimeframe(timeframe) ? timeframe : null;
      try {
        const data = await api.getChartData(ticker, date, days, controller.signal, interval);
        if (!controller.signal.aborted) {
          storeSetKline(data.kline ?? null);
          storeSetBollinger(data.bollinger ?? null);
        }
      } catch (err: any) {
        if (err.name !== "AbortError" && !controller.signal.aborted) {
          storeSetLoadError(`回放加载失败: ${err.message}`);
        }
      } finally {
        if (!controller.signal.aborted) storeSetLoading(false);
      }
    },
    [replayDate, ticker, timeframe, storeSetReplayDate, storeSetLoading, storeSetLoadError, storeSetKline, storeSetBollinger],
  );

  const handleReplayTogglePlay = useCallback(() => {
    storeSetIsPlaying(!isPlaying);
  }, [isPlaying, storeSetIsPlaying]);

  // Available dates from kline data (for the replay slider)
  const availableDates = useMemo(() => kline?.dates ?? [], [kline]);

  // ── Realtime quote for the current ticker ─────────────────────────────────
  // Drives the ChartHeader price tick + flash. The watchlist keeps its own
  // subscription for the full list; both share the same backend endpoint.
  const realtimeQuotes = useRealtimePrices([ticker]);
  const realtimeQuote = realtimeQuotes.get(ticker);

  // ── Price alerts ───────────────────────────────────────────────────────────
  const [showAlertPanel, setShowAlertPanel] = useState(false);
  const alertPanelRef = useRef<HTMLDivElement>(null);
  const { alerts, addAlert, removeAlert, toggleAlert, updateAlert } = usePriceAlerts(realtimeQuotes);

  // Close alert panel on outside click
  useEffect(() => {
    if (!showAlertPanel) return;
    const handler = (e: MouseEvent) => {
      if (alertPanelRef.current && !alertPanelRef.current.contains(e.target as Node)) {
        setShowAlertPanel(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showAlertPanel]);

  // ── Adjustable indicator params (MA/MACD/RSI), persisted to localStorage ──
  const [indicatorParams, setIndicatorParams] = useState<IndicatorParams>(loadIndicatorParams);

  const handleApplyParams = useCallback((next: IndicatorParams) => {
    setIndicatorParams(next);
    saveIndicatorParams(next);
  }, []);

  // Recompute MA/MACD/RSI from current kline closes - no refetch needed
  const closes = useMemo(
    () => (kline?.ohlc ?? []).map((row) => row[1]), // close is index 1
    [kline],
  );

  const maSeries = useMemo(() => {
    if (!kline?.ohlc?.length) return undefined;
    return {
      ma5: computeSmaSeries(closes, indicatorParams.ma.ma5),
      ma10: computeSmaSeries(closes, indicatorParams.ma.ma10),
      ma20: computeSmaSeries(closes, indicatorParams.ma.ma20),
      ma50: computeSmaSeries(closes, indicatorParams.ma.ma50),
    };
  }, [kline, closes, indicatorParams.ma]);

  const computedMacd = useMemo(
    () =>
      kline?.ohlc?.length
        ? { dates: kline.dates, ...computeMacdSeries(closes, indicatorParams.macd) }
        : null,
    [kline, closes, indicatorParams.macd],
  );

  const computedRsi = useMemo(
    () =>
      kline?.ohlc?.length
        ? { dates: kline.dates, values: computeRsiSeries(closes, indicatorParams.rsiPeriod) }
        : null,
    [kline, closes, indicatorParams.rsiPeriod],
  );

  // Compute latest price from kline, overlaid with the realtime quote when present
  const klineLatestPrice = kline?.ohlc?.length
    ? kline.ohlc[kline.ohlc.length - 1][1] // close is index 1
    : undefined;
  const latestPrice = realtimeQuote?.price ?? klineLatestPrice;
  const latestChange =
    realtimeQuote?.change ??
    (kline?.ohlc && kline.ohlc.length >= 2
      ? kline.ohlc[kline.ohlc.length - 1][1] - kline.ohlc[kline.ohlc.length - 2][1]
      : undefined);
  const latestChangePercent =
    realtimeQuote?.changePct ??
    (latestChange != null && kline?.ohlc && kline.ohlc.length >= 2
      ? (latestChange / kline.ohlc[kline.ohlc.length - 2][1]) * 100
      : undefined);

  return (
    <div className="flex flex-col h-full bg-[#131722]">
      {/* ── Chart Header ──────────────────────────────────────────────── */}
      <div className="relative">
        <ChartHeader
          ticker={ticker}
          name={stockName}
          crosshairInfo={crosshairInfo}
          latestPrice={latestPrice}
          latestChange={latestChange}
          latestChangePercent={latestChangePercent}
          alertCount={alerts.filter((a) => a.enabled).length}
          onToggleAlerts={() => setShowAlertPanel((v) => !v)}
          isMultiChart={isMultiChart}
          onToggleMultiChart={() => storeSetMultiChart(!isMultiChart)}
        />
        {/* Alert panel popover */}
        {showAlertPanel && (
          <div ref={alertPanelRef} className="absolute top-9 right-3 z-50">
            <AlertPanel
              alerts={alerts}
              prices={realtimeQuotes}
              currentTicker={ticker}
              currentPrice={latestPrice}
              onAdd={addAlert}
              onRemove={removeAlert}
              onToggle={toggleAlert}
              onUpdate={updateAlert}
              onClose={() => setShowAlertPanel(false)}
            />
          </div>
        )}
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      {isMultiChart ? (
        /* Multi-chart layout mode */
        <div className="flex-1 min-h-0">
          <MultiChartLayout initialTicker={ticker} />
        </div>
      ) : isFullscreen ? (
        /* Fullscreen: main chart only — timeframe switching and drawing still work */
        <div ref={chartAreaRef} className="flex-1 min-h-0 relative" data-chart-area>
          <div className="flex flex-col h-full">
            <TimeframeSelector current={timeframe} onChange={handleTimeframeChange} />
            <div className="flex-1 min-h-0 relative">
              <TradingViewChart
                data={kline}
                activeOverlays={activeOverlays}
                activeTool={activeTool}
                onCrosshairMove={handleCrosshairMove}
              />
            </div>
          </div>
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#131722]/80 z-10">
              <div className="flex items-center gap-2 text-[#787B86] text-sm">
                <Loader2 size={16} className="animate-spin" />
                正在加载 {timeframe} 周期数据…
              </div>
            </div>
          )}
          {loadError && !isLoading && (
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 px-3 py-1.5 rounded bg-[#F23645]/20 border border-[#F23645]/40 text-[#F23645] text-xs">
              {loadError}
              <button className="ml-2 underline" onClick={() => storeSetLoadError(null)}>
                ✕
              </button>
            </div>
          )}
          {/* Exit fullscreen */}
          <button
            onClick={() => setIsFullscreen(false)}
            className="absolute top-9 right-2 z-20 p-1.5 rounded bg-[#1E222D] border border-[#2B2B43] hover:bg-[#2A2E39] transition-colors"
            title="退出全屏 (ESC)"
          >
            <Minimize2 size={14} className="text-[#787B86]" />
          </button>
        </div>
      ) : (
      <div className="flex flex-1 min-h-0">
        {/* Left: Drawing Toolbar */}
        <DrawingToolbar activeTool={activeTool} onSelect={storeSetActiveTool} />

        {/* Center: Chart area */}
        <div className="flex flex-col flex-1 min-w-0">
          {/* Timeframe Selector */}
          <TimeframeSelector current={timeframe} onChange={handleTimeframeChange} />

          {/* K-line Replay Controls */}
          <ReplayControls
            currentDate={replayDate ?? (kline?.dates?.length ? kline.dates[kline.dates.length - 1] : "")}
            onDateChange={handleReplayDateChange}
            isPlaying={isPlaying}
            onTogglePlay={handleReplayTogglePlay}
            availableDates={availableDates}
            visible={isReplayVisible}
            onToggleVisible={() => setIsReplayVisible((v) => !v)}
          />

          {/* Overlay indicator toggle bar + screenshot */}
          <div className="flex items-center">
            <div className="flex-1 min-w-0">
              <IndicatorBar
                data={kline}
                activeOverlays={activeOverlays.map((k) => k.toUpperCase())}
                onToggleOverlay={(key) => handleToggleOverlay(key.toLowerCase())}
                params={indicatorParams}
                onApplyParams={handleApplyParams}
                maSeries={maSeries}
              />
            </div>
            <button
              onClick={handleScreenshot}
              className="p-1.5 rounded hover:bg-[#2A2E39] transition-colors shrink-0"
              title="快速截图（本地渲染）"
            >
              <Camera size={14} className="text-[#787B86]" />
            </button>
            <button
              onClick={handleServerExport}
              disabled={exporting}
              className="p-1.5 rounded hover:bg-[#2A2E39] transition-colors shrink-0"
              title="高清导出（服务端渲染 + 水印）"
            >
              {exporting
                ? <Loader2 size={14} className="text-[#787B86] animate-spin" />
                : <Image size={14} className="text-[#787B86]" />}
            </button>
            <button
              onClick={() => setIsFullscreen(true)}
              className="p-1.5 mr-1 rounded hover:bg-[#2A2E39] transition-colors shrink-0"
              title="全屏图表 (ESC 退出)"
            >
              <Maximize2 size={14} className="text-[#787B86]" />
            </button>
          </div>

          {/* Main chart with loading overlay */}
          <div ref={chartAreaRef} className="flex-1 min-h-0 relative" data-chart-area>
            <TradingViewChart
              data={kline}
              activeOverlays={activeOverlays}
              activeTool={activeTool}
              onCrosshairMove={handleCrosshairMove}
              maSeries={maSeries}
            />

            {/* Loading overlay */}
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-[#131722]/80 z-10">
                <div className="flex items-center gap-2 text-[#787B86] text-sm">
                  <Loader2 size={16} className="animate-spin" />
                  正在加载 {timeframe} 周期数据…
                </div>
              </div>
            )}

            {/* Error toast */}
            {loadError && !isLoading && (
              <div className="absolute top-2 left-1/2 -translate-x-1/2 z-10 px-3 py-1.5 rounded bg-[#F23645]/20 border border-[#F23645]/40 text-[#F23645] text-xs">
                {loadError}
                <button
                  className="ml-2 underline"
                  onClick={() => storeSetLoadError(null)}
                >
                  ✕
                </button>
              </div>
            )}
          </div>

          {/* Sub-panels: 3 switchable slots (MACD/RSI/BOLL/KDJ/WR/CCI) */}
          <SubPanels
            kline={kline}
            macd={computedMacd}
            rsi={computedRsi}
            bollinger={bollinger}
            crosshairTime={crosshairInfo?.time}
            params={indicatorParams}
            onApplyParams={handleApplyParams}
          />
        </div>

        {/* Right: Watchlist */}
        <div className="w-[220px] flex-shrink-0">
          <WatchlistPanel currentTicker={ticker} onSelect={handleTickerChange} />
        </div>
      </div>
      )}
    </div>
  );
}

