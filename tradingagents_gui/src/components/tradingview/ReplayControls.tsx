/**
 * ReplayControls — K-line replay time slider (Phase 7).
 *
 * A compact toolbar that lets the user pick a historical date and
 * "play forward" bar-by-bar, simulating what the chart looked like
 * on that date. Each tick updates the chart date, which re-fetches
 * data as-of that date from /api/chart-data.
 *
 * Design: sits below the TimeframeSelector, collapsible via a toggle.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Calendar, Pause, Play, SkipBack, SkipForward } from "lucide-react";

// ── Types ───────────────────────────────────────────────────────────────────

interface Props {
  /** Currently displayed date (YYYY-MM-DD). */
  currentDate: string;
  /** Callback when the user picks a new replay date. */
  onDateChange: (date: string) => void;
  /** Whether replay is currently playing. */
  isPlaying: boolean;
  /** Toggle play/pause. */
  onTogglePlay: () => void;
  /** Available dates from the current chart data (sorted ascending). */
  availableDates: string[];
  /** Whether the controls are visible. */
  visible: boolean;
  /** Toggle visibility. */
  onToggleVisible: () => void;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function dateToSlider(date: string, dates: string[]): number {
  const idx = dates.indexOf(date);
  return idx >= 0 ? idx : dates.length - 1;
}

function sliderToDate(slider: number, dates: string[]): string {
  return dates[Math.min(Math.max(0, slider), dates.length - 1)] ?? "";
}

// ── Component ───────────────────────────────────────────────────────────────

export default function ReplayControls({
  currentDate,
  onDateChange,
  isPlaying,
  onTogglePlay,
  availableDates,
  visible,
  onToggleVisible,
}: Props) {
  const sliderRef = useRef<HTMLInputElement>(null);
  const [localSlider, setLocalSlider] = useState(() =>
    dateToSlider(currentDate, availableDates)
  );
  const [playSpeed, setPlaySpeed] = useState(500); // ms per bar

  // Sync slider with external date changes
  useEffect(() => {
    setLocalSlider(dateToSlider(currentDate, availableDates));
  }, [currentDate, availableDates]);

  // Play loop
  const playTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (isPlaying && availableDates.length > 0) {
      playTimerRef.current = setInterval(() => {
        setLocalSlider((prev) => {
          const next = prev + 1;
          if (next >= availableDates.length) {
            onTogglePlay(); // stop at end
            return prev;
          }
          onDateChange(sliderToDate(next, availableDates));
          return next;
        });
      }, playSpeed);
    }
    return () => {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    };
  }, [isPlaying, playSpeed, availableDates, onDateChange, onTogglePlay]);

  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseInt(e.target.value, 10);
      setLocalSlider(val);
      onDateChange(sliderToDate(val, availableDates));
    },
    [availableDates, onDateChange],
  );

  const handleStepBack = useCallback(() => {
    setLocalSlider((prev) => {
      const next = Math.max(0, prev - 1);
      onDateChange(sliderToDate(next, availableDates));
      return next;
    });
  }, [availableDates, onDateChange]);

  const handleStepForward = useCallback(() => {
    setLocalSlider((prev) => {
      const next = Math.min(availableDates.length - 1, prev + 1);
      onDateChange(sliderToDate(next, availableDates));
      return next;
    });
  }, [availableDates, onDateChange]);

  if (!visible) {
    return (
      <button
        onClick={onToggleVisible}
        className="p-1 rounded hover:bg-[#2A2E39] transition-colors"
        title="K线回放"
      >
        <Calendar size={13} className="text-[#787B86]" />
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1E222D] border-b border-[#2B2B43] text-xs">
      {/* Toggle button */}
      <button
        onClick={onToggleVisible}
        className="p-1 rounded hover:bg-[#2A2E39] transition-colors shrink-0"
        title="收起回放控制"
      >
        <Calendar size={12} className="text-[#2962FF]" />
      </button>

      {/* Playback controls */}
      <button
        onClick={handleStepBack}
        className="p-1 rounded hover:bg-[#2A2E39] transition-colors"
        title="后退一步"
        disabled={localSlider <= 0}
      >
        <SkipBack size={12} className="text-[#787B86]" />
      </button>

      <button
        onClick={onTogglePlay}
        className="p-1 rounded hover:bg-[#2A2E39] transition-colors"
        title={isPlaying ? "暂停" : "播放"}
      >
        {isPlaying ? (
          <Pause size={12} className="text-[#2962FF]" />
        ) : (
          <Play size={12} className="text-[#787B86]" />
        )}
      </button>

      <button
        onClick={handleStepForward}
        className="p-1 rounded hover:bg-[#2A2E39] transition-colors"
        title="前进一步"
        disabled={localSlider >= availableDates.length - 1}
      >
        <SkipForward size={12} className="text-[#787B86]" />
      </button>

      {/* Speed selector */}
      <select
        className="bg-[#131722] border border-[#2B2B43] rounded px-1 py-0.5 text-[10px] text-[#787B86] outline-none"
        value={playSpeed}
        onChange={(e) => setPlaySpeed(parseInt(e.target.value, 10))}
      >
        <option value={1000}>0.5x</option>
        <option value={500}>1x</option>
        <option value={250}>2x</option>
        <option value={100}>5x</option>
      </select>

      {/* Date slider */}
      <div className="flex-1 flex items-center gap-2 min-w-0">
        <input
          ref={sliderRef}
          type="range"
          className="flex-1 h-1 accent-[#2962FF] cursor-pointer"
          min={0}
          max={Math.max(0, availableDates.length - 1)}
          value={localSlider}
          onChange={handleSliderChange}
        />
        <span className="text-[#D1D4DC] font-mono text-[11px] shrink-0 w-20 text-center">
          {sliderToDate(localSlider, availableDates) || "—"}
        </span>
      </div>

      {/* Bar count */}
      <span className="text-[#787B86] text-[10px] shrink-0">
        {localSlider + 1}/{availableDates.length}
      </span>
    </div>
  );
}
