/**
 * DrawingManager — Canvas drawing primitives for lightweight-charts.
 *
 * Implements IPanePrimitive for trendlines, horizontal lines, rectangles,
 * and fibonacci retracement on the chart pane.
 */

import type {
  IChartApi,
  IPanePrimitive,
  IPrimitivePaneRenderer,
  IPanePrimitivePaneView,
  PaneAttachedParameter,
  ISeriesApi,
  SeriesType,
  LineStyle,
} from "lightweight-charts";
import type { CanvasRenderingTarget2D } from "fancy-canvas";
import type { DrawingTool } from "./types";

// ── Drawing data model ──────────────────────────────────────────────────────

export interface Drawing {
  id: string;
  type: DrawingTool;
  points: { time: string; price: number }[];
  color: string;
  lineWidth: number;
  lineStyle: LineStyle;
}

// ── PaneDrawingManager — the main IPanePrimitive ────────────────────────────

export class PaneDrawingManager implements IPanePrimitive {
  private _chart: IChartApi | null = null;
  private _series: ISeriesApi<SeriesType> | null = null;
  private _requestUpdate: (() => void) | null = null;
  private _drawings: Drawing[] = [];
  private _activeTool: DrawingTool = "crosshair";
  private _drawingInProgress: Drawing | null = null;
  private _onChange: ((drawings: Drawing[]) => void) | null = null;

  // ── Lifecycle ──────────────────────────────────────────────────────────

  attached(param: PaneAttachedParameter): void {
    this._chart = param.chart as IChartApi;
    this._requestUpdate = param.requestUpdate;
    this._series = this._chart
      .panes()[0]
      .getSeries()[0] as ISeriesApi<SeriesType>;
  }

  detached(): void {
    this._chart = null;
    this._series = null;
    this._requestUpdate = null;
  }

  // ── Public API ─────────────────────────────────────────────────────────

  setActiveTool(tool: DrawingTool): void {
    this._activeTool = tool;
  }

  getActiveTool(): DrawingTool {
    return this._activeTool;
  }

  setDrawings(drawings: Drawing[]): void {
    this._drawings = drawings;
    this._requestUpdate?.();
  }

  getDrawings(): Drawing[] {
    return this._drawings;
  }

  addDrawing(drawing: Drawing): void {
    this._drawings.push(drawing);
    this._onChange?.(this._drawings);
    this._requestUpdate?.();
  }

  removeDrawing(id: string): void {
    this._drawings = this._drawings.filter((d) => d.id !== id);
    this._onChange?.(this._drawings);
    this._requestUpdate?.();
  }

  clearDrawings(): void {
    this._drawings = [];
    this._onChange?.(this._drawings);
    this._requestUpdate?.();
  }

  onChange(callback: (drawings: Drawing[]) => void): void {
    this._onChange = callback;
  }

  // ── Mouse interaction ─────────────────────────────────────────────────

  hitTest(x: number, y: number): { externalId: string; zOrder: "bottom" | "normal" | "top" } | null {
    if (this._activeTool !== "crosshair") return null;

    const series = this._series;
    if (!series) return null;

    for (let i = this._drawings.length - 1; i >= 0; i--) {
      const drawing = this._drawings[i];
      const hit = this._hitTestDrawing(drawing, x, y);
      if (hit) return { externalId: drawing.id, zOrder: "normal" as const };
    }
    return null;
  }

  private _hitTestDrawing(drawing: Drawing, x: number, y: number): boolean {
    const series = this._series;
    if (!series) return false;

    const threshold = 6;

    if (drawing.type === "horizontal") {
      const price = drawing.points[0]?.price;
      if (price == null) return false;
      const priceY = series.priceToCoordinate(price);
      if (priceY == null) return false;
      return Math.abs(y - priceY) < threshold;
    }

    if (drawing.points.length >= 2) {
      const p1 = drawing.points[0];
      const p2 = drawing.points[1];
      const chart = this._chart;
      if (!chart) return false;

      const ts = chart.timeScale();
      const x1 = ts.timeToCoordinate(p1.time as any);
      const y1 = series.priceToCoordinate(p1.price);
      const x2 = ts.timeToCoordinate(p2.time as any);
      const y2 = series.priceToCoordinate(p2.price);

      if (x1 == null || y1 == null || x2 == null || y2 == null) return false;

      // Distance from point to line segment
      const dist = this._pointToSegmentDist(x, y, x1, y1, x2, y2);
      return dist < threshold;
    }

    return false;
  }

  private _pointToSegmentDist(
    px: number,
    py: number,
    x1: number,
    y1: number,
    x2: number,
    y2: number,
  ): number {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lenSq = dx * dx + dy * dy;
    if (lenSq === 0) return Math.hypot(px - x1, py - y1);
    let t = ((px - x1) * dx + (py - y1) * dy) / lenSq;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
  }

  // ── PaneViews ─────────────────────────────────────────────────────────

  paneViews(): readonly IPanePrimitivePaneView[] {
    return [new DrawingPaneView(this)];
  }

  // ── Internal drawing rendering ────────────────────────────────────────

  renderDrawings(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace(({ context: ctx, bitmapSize, horizontalPixelRatio, verticalPixelRatio }) => {
      ctx.save();
      ctx.scale(horizontalPixelRatio, verticalPixelRatio);

      for (const drawing of this._drawings) {
        this._renderDrawing(ctx, drawing, bitmapSize.width / horizontalPixelRatio, bitmapSize.height / verticalPixelRatio);
      }

      // Render in-progress drawing (rubber band)
      if (this._drawingInProgress) {
        this._renderDrawing(ctx, this._drawingInProgress, bitmapSize.width / horizontalPixelRatio, bitmapSize.height / verticalPixelRatio);
      }

      ctx.restore();
    });
  }

  private _renderDrawing(
    ctx: CanvasRenderingContext2D,
    drawing: Drawing,
    _width: number,
    _height: number,
  ): void {
    const series = this._series;
    const chart = this._chart;
    if (!series || !chart) return;

    ctx.strokeStyle = drawing.color;
    ctx.lineWidth = drawing.lineWidth;

    // Apply line style
    if (drawing.lineStyle === 1) {
      ctx.setLineDash([1, 3]);
    } else if (drawing.lineStyle === 2) {
      ctx.setLineDash([4, 4]);
    } else if (drawing.lineStyle === 3) {
      ctx.setLineDash([8, 4]);
    } else {
      ctx.setLineDash([]);
    }

    const ts = chart.timeScale();

    switch (drawing.type) {
      case "trendline":
        this._renderTrendline(ctx, drawing, series, ts);
        break;
      case "horizontal":
        this._renderHorizontalLine(ctx, drawing, series);
        break;
      case "rectangle":
        this._renderRectangle(ctx, drawing, series, ts);
        break;
      case "fibonacci":
        this._renderFibonacci(ctx, drawing, series, ts);
        break;
    }

    ctx.setLineDash([]);
  }

  private _renderTrendline(
    ctx: CanvasRenderingContext2D,
    drawing: Drawing,
    series: ISeriesApi<SeriesType>,
    ts: ReturnType<IChartApi["timeScale"]>,
  ): void {
    if (drawing.points.length < 2) return;
    const [p1, p2] = drawing.points;

    const x1 = ts.timeToCoordinate(p1.time as any);
    const y1 = series.priceToCoordinate(p1.price);
    const x2 = ts.timeToCoordinate(p2.time as any);
    const y2 = series.priceToCoordinate(p2.price);

    if (x1 == null || y1 == null || x2 == null || y2 == null) return;

    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();

    // Draw endpoint circles
    ctx.fillStyle = drawing.color;
    for (const [x, y] of [[x1, y1], [x2, y2]]) {
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  private _renderHorizontalLine(
    ctx: CanvasRenderingContext2D,
    drawing: Drawing,
    series: ISeriesApi<SeriesType>,
  ): void {
    if (drawing.points.length < 1) return;
    const price = drawing.points[0].price;
    const y = series.priceToCoordinate(price);
    if (y == null) return;

    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(ctx.canvas.width / (window.devicePixelRatio || 1), y);
    ctx.stroke();

    // Price label
    ctx.fillStyle = drawing.color;
    ctx.font = "10px monospace";
    const label = price.toFixed(2);
    const textWidth = ctx.measureText(label).width;
    ctx.fillRect(ctx.canvas.width / (window.devicePixelRatio || 1) - textWidth - 8, y - 8, textWidth + 6, 16);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText(label, ctx.canvas.width / (window.devicePixelRatio || 1) - textWidth - 5, y + 4);
  }

  private _renderRectangle(
    ctx: CanvasRenderingContext2D,
    drawing: Drawing,
    series: ISeriesApi<SeriesType>,
    ts: ReturnType<IChartApi["timeScale"]>,
  ): void {
    if (drawing.points.length < 2) return;
    const [p1, p2] = drawing.points;

    const x1 = ts.timeToCoordinate(p1.time as any);
    const y1 = series.priceToCoordinate(p1.price);
    const x2 = ts.timeToCoordinate(p2.time as any);
    const y2 = series.priceToCoordinate(p2.price);

    if (x1 == null || y1 == null || x2 == null || y2 == null) return;

    const left = Math.min(x1, x2);
    const top = Math.min(y1, y2);
    const w = Math.abs(x2 - x1);
    const h = Math.abs(y2 - y1);

    // Fill with translucent color
    ctx.fillStyle = this._hexToRgba(drawing.color, 0.1);
    ctx.fillRect(left, top, w, h);

    // Border
    ctx.strokeRect(left, top, w, h);
  }

  private _renderFibonacci(
    ctx: CanvasRenderingContext2D,
    drawing: Drawing,
    series: ISeriesApi<SeriesType>,
    ts: ReturnType<IChartApi["timeScale"]>,
  ): void {
    if (drawing.points.length < 2) return;
    const [p1, p2] = drawing.points;

    const x1 = ts.timeToCoordinate(p1.time as any);
    const y1 = series.priceToCoordinate(p1.price);
    const x2 = ts.timeToCoordinate(p2.time as any);
    const y2 = series.priceToCoordinate(p2.price);

    if (x1 == null || y1 == null || x2 == null || y2 == null) return;

    const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
    const levelColors = [
      "#787B86",
      "#F23645",
      "#FF6D00",
      "#F7B731",
      "#089981",
      "#2962FF",
      "#787B86",
    ];

    const high = Math.max(p1.price, p2.price);
    const low = Math.min(p1.price, p2.price);
    const range = high - low;
    const left = Math.min(x1, x2);
    const right = Math.max(x1, x2);

    for (let i = 0; i < levels.length; i++) {
      const price = high - range * levels[i];
      const y = series.priceToCoordinate(price);
      if (y == null) continue;

      ctx.strokeStyle = levelColors[i];
      ctx.lineWidth = 1;
      ctx.setLineDash([]);

      ctx.beginPath();
      ctx.moveTo(left, y);
      ctx.lineTo(right, y);
      ctx.stroke();

      // Level label
      ctx.fillStyle = levelColors[i];
      ctx.font = "9px monospace";
      ctx.fillText(`${(levels[i] * 100).toFixed(1)}%`, left - 40, y + 3);
    }

    // Restore original line style
    ctx.strokeStyle = drawing.color;
    ctx.lineWidth = drawing.lineWidth;
  }

  private _hexToRgba(hex: string, alpha: number): string {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
}

// ── DrawingPaneView — bridges the manager to the renderer ───────────────────

class DrawingPaneView implements IPanePrimitivePaneView {
  private _manager: PaneDrawingManager;

  constructor(manager: PaneDrawingManager) {
    this._manager = manager;
  }

  renderer(): IPrimitivePaneRenderer | null {
    return new DrawingRenderer(this._manager);
  }
}

// ── DrawingRenderer — does the actual Canvas 2D drawing ────────────────────

class DrawingRenderer implements IPrimitivePaneRenderer {
  private _manager: PaneDrawingManager;

  constructor(manager: PaneDrawingManager) {
    this._manager = manager;
  }

  draw(target: CanvasRenderingTarget2D): void {
    this._manager.renderDrawings(target);
  }
}
