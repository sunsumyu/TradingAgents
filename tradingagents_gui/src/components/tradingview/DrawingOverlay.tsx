/**
 * DrawingOverlay — Transparent canvas overlay for drawing tools.
 *
 * When activeTool is "crosshair", pointer events pass through to ECharts.
 * When a drawing tool is active, this overlay captures mouse events and
 * renders trendlines, horizontal lines, rectangles, and fibonacci retracements.
 */

import { useRef, useState, useCallback, useEffect } from "react";
import type { DrawingTool } from "./types";

export interface DrawingShape {
  id: string;
  type: DrawingTool;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
}

interface Props {
  activeTool: DrawingTool;
  /** Change of this value clears all drawings and history (e.g. ticker switch). */
  resetKey?: string;
  onToolConsumed?: () => void; // called after a drawing is placed
}

const COLORS: Record<DrawingTool, string> = {
  crosshair: "#787B86",
  trendline: "#2962FF",
  horizontal: "#F7B731",
  rectangle: "#089981",
  fibonacci: "#E040FB",
};

const MAX_HISTORY = 50;

export default function DrawingOverlay({ activeTool, resetKey, onToolConsumed }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [drawings, setDrawings] = useState<DrawingShape[]>([]);
  // Undo/redo stacks: history holds past states, future holds undone states.
  const historyRef = useRef<DrawingShape[][]>([]);
  const futureRef = useRef<DrawingShape[][]>([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [currentPoint, setCurrentPoint] = useState<{ x: number; y: number } | null>(null);

  const isCrosshair = activeTool === "crosshair";

  // Record current drawings into the undo stack (called BEFORE mutating).
  const pushHistory = useCallback((snapshot: DrawingShape[]) => {
    historyRef.current = [...historyRef.current.slice(-(MAX_HISTORY - 1)), snapshot];
    futureRef.current = []; // new action invalidates redo
  }, []);

  const undo = useCallback(() => {
    const prev = historyRef.current.pop();
    if (!prev) return;
    setDrawings((current) => {
      futureRef.current = [...futureRef.current, current];
      return prev;
    });
  }, []);

  const redo = useCallback(() => {
    const next = futureRef.current.pop();
    if (!next) return;
    setDrawings((current) => {
      historyRef.current = [...historyRef.current, current];
      return next;
    });
  }, []);

  // Ctrl+Z undo, Ctrl+Y / Ctrl+Shift+Z redo
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      const key = e.key.toLowerCase();
      if (key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (key === "y" || (key === "z" && e.shiftKey)) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [undo, redo]);

  // Clear all drawings and history when resetKey changes (e.g. ticker switch)
  useEffect(() => {
    setDrawings([]);
    historyRef.current = [];
    futureRef.current = [];
  }, [resetKey]);

  // Redraw all drawings + in-progress shape
  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    ctx.clearRect(0, 0, rect.width, rect.height);

    // Draw completed shapes
    for (const shape of drawings) {
      drawShape(ctx, shape);
    }

    // Draw in-progress shape
    if (isDrawing && startPoint && currentPoint) {
      drawShape(ctx, {
        id: "_temp",
        type: activeTool,
        x1: startPoint.x,
        y1: startPoint.y,
        x2: currentPoint.x,
        y2: currentPoint.y,
        color: COLORS[activeTool],
      });
    }
  }, [drawings, isDrawing, startPoint, currentPoint, activeTool]);

  useEffect(() => {
    redraw();
  }, [redraw]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver(() => redraw());
    ro.observe(container);
    return () => ro.disconnect();
  }, [redraw]);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (isCrosshair) return;
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      setIsDrawing(true);
      setStartPoint({ x, y });
      setCurrentPoint({ x, y });
    },
    [isCrosshair],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing) return;
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      setCurrentPoint({ x, y });
    },
    [isDrawing],
  );

  const handleMouseUp = useCallback(() => {
    if (!isDrawing || !startPoint || !currentPoint) return;
    const dx = Math.abs(currentPoint.x - startPoint.x);
    const dy = Math.abs(currentPoint.y - startPoint.y);
    if (dx > 5 || dy > 5) {
      const newShape: DrawingShape = {
        id: `drawing_${Date.now()}`,
        type: activeTool,
        x1: startPoint.x,
        y1: startPoint.y,
        x2: currentPoint.x,
        y2: currentPoint.y,
        color: COLORS[activeTool],
      };
      setDrawings((prev) => {
        pushHistory(prev);
        return [...prev, newShape];
      });
      onToolConsumed?.();
    }
    setIsDrawing(false);
    setStartPoint(null);
    setCurrentPoint(null);
  }, [isDrawing, startPoint, currentPoint, activeTool, onToolConsumed, pushHistory]);

  const handleDoubleClick = useCallback(() => {
    // Clear all drawings (undoable)
    setDrawings((prev) => {
      if (prev.length === 0) return prev;
      pushHistory(prev);
      return [];
    });
  }, [pushHistory]);

  return (
    <div
      ref={containerRef}
      style={{
        position: "absolute",
        inset: 0,
        zIndex: isCrosshair ? -1 : 5,
        cursor: isCrosshair ? "default" : "crosshair",
        pointerEvents: isCrosshair ? "none" : "auto",
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onDoubleClick={handleDoubleClick}
    >
      <canvas
        ref={canvasRef}
        data-drawing-canvas=""
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
}

// ── Drawing primitives ──────────────────────────────────────────────────────

function drawShape(ctx: CanvasRenderingContext2D, shape: DrawingShape) {
  ctx.save();
  ctx.strokeStyle = shape.color;
  ctx.lineWidth = 1.5;

  switch (shape.type) {
    case "trendline":
      drawTrendline(ctx, shape);
      break;
    case "horizontal":
      drawHorizontalLine(ctx, shape);
      break;
    case "rectangle":
      drawRectangle(ctx, shape);
      break;
    case "fibonacci":
      drawFibonacci(ctx, shape);
      break;
  }

  ctx.restore();
}

function drawTrendline(ctx: CanvasRenderingContext2D, shape: DrawingShape) {
  ctx.beginPath();
  ctx.moveTo(shape.x1, shape.y1);
  ctx.lineTo(shape.x2, shape.y2);
  ctx.stroke();

  // Endpoint dots
  ctx.fillStyle = shape.color;
  for (const [x, y] of [[shape.x1, shape.y1], [shape.x2, shape.y2]]) {
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawHorizontalLine(ctx: CanvasRenderingContext2D, shape: DrawingShape) {
  const y = shape.y1; // use y1 as the price level
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(0, y);
  ctx.lineTo(ctx.canvas.width / window.devicePixelRatio, y);
  ctx.stroke();
  ctx.setLineDash([]);

  // Price label
  ctx.fillStyle = shape.color;
  ctx.font = "10px monospace";
  const label = `y=${y.toFixed(0)}`;
  const tw = ctx.measureText(label).width;
  ctx.fillRect(ctx.canvas.width / window.devicePixelRatio - tw - 8, y - 8, tw + 6, 16);
  ctx.fillStyle = "#FFFFFF";
  ctx.fillText(label, ctx.canvas.width / window.devicePixelRatio - tw - 5, y + 4);
}

function drawRectangle(ctx: CanvasRenderingContext2D, shape: DrawingShape) {
  const left = Math.min(shape.x1, shape.x2);
  const top = Math.min(shape.y1, shape.y2);
  const w = Math.abs(shape.x2 - shape.x1);
  const h = Math.abs(shape.y2 - shape.y1);

  // Fill
  const r = parseInt(shape.color.slice(1, 3), 16);
  const g = parseInt(shape.color.slice(3, 5), 16);
  const b = parseInt(shape.color.slice(5, 7), 16);
  ctx.fillStyle = `rgba(${r},${g},${b},0.1)`;
  ctx.fillRect(left, top, w, h);

  // Border
  ctx.strokeRect(left, top, w, h);
}

function drawFibonacci(ctx: CanvasRenderingContext2D, shape: DrawingShape) {
  const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  const levelColors = [
    "#787B86", "#F23645", "#FF6D00", "#F7B731", "#089981", "#2962FF", "#787B86",
  ];

  const high = Math.min(shape.y1, shape.y2); // y is inverted in canvas
  const low = Math.max(shape.y1, shape.y2);
  const range = low - high;
  const left = Math.min(shape.x1, shape.x2);
  const right = Math.max(shape.x1, shape.x2);

  for (let i = 0; i < levels.length; i++) {
    const y = high + range * levels[i];
    ctx.strokeStyle = levelColors[i];
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(right, y);
    ctx.stroke();

    // Label
    ctx.fillStyle = levelColors[i];
    ctx.font = "9px monospace";
    ctx.fillText(`${(levels[i] * 100).toFixed(1)}%`, left - 42, y + 3);
  }
}
