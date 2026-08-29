/**
 * DrawingToolbar — Vertical toolbar on left side for drawing tool selection.
 * TradingView-style tool selection sidebar.
 */

import {
  MousePointer2,
  TrendingUp,
  Minus,
  Square,
  GitBranch,
} from "lucide-react";
import type { DrawingTool } from "./types";

interface ToolDef {
  id: DrawingTool;
  icon: React.ReactNode;
  label: string;
}

const TOOLS: ToolDef[] = [
  { id: "crosshair", icon: <MousePointer2 size={16} />, label: "Crosshair" },
  { id: "trendline", icon: <TrendingUp size={16} />, label: "Trendline" },
  { id: "horizontal", icon: <Minus size={16} />, label: "Horizontal Line" },
  { id: "rectangle", icon: <Square size={16} />, label: "Rectangle" },
  { id: "fibonacci", icon: <GitBranch size={16} />, label: "Fibonacci" },
];

interface Props {
  activeTool: DrawingTool;
  onSelect: (tool: DrawingTool) => void;
}

export default function DrawingToolbar({ activeTool, onSelect }: Props) {
  return (
    <div className="flex flex-col items-center gap-1 py-2 px-1 bg-[#131722] border-r border-[#2B2B43] w-10 select-none">
      {TOOLS.map((tool) => {
        const active = tool.id === activeTool;
        return (
          <button
            key={tool.id}
            onClick={() => onSelect(tool.id)}
            title={tool.label}
            className="w-8 h-8 flex items-center justify-center rounded transition-colors"
            style={{
              color: active ? "#D1D4DC" : "#787B86",
              backgroundColor: active ? "#2A2E39" : "transparent",
            }}
            onMouseEnter={(e) => {
              if (!active) {
                e.currentTarget.style.color = "#D1D4DC";
                e.currentTarget.style.backgroundColor = "#1E222D";
              }
            }}
            onMouseLeave={(e) => {
              if (!active) {
                e.currentTarget.style.color = "#787B86";
                e.currentTarget.style.backgroundColor = "transparent";
              }
            }}
          >
            {tool.icon}
          </button>
        );
      })}
    </div>
  );
}
