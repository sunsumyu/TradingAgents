import { ReactNode } from "react";

// ── Card ────────────────────────────────────────────────────────────────────────

export function Card({
  children,
  className = "",
  title,
  glow = false,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  glow?: boolean;
}) {
  return (
    <div className={`card p-3 ${glow ? "card-glow" : ""} ${className}`}>
      {title && (
        <>
          <div className="section-title">{title}</div>
          <div className="h-px bg-line mb-2" />
        </>
      )}
      {children}
    </div>
  );
}

// ── Spotlight hero (AceternityUI-style top radial glow) ────────────────────────

export function Spotlight({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-x-0 top-0 h-[420px] ${className}`}
      style={{
        background:
          "radial-gradient(ellipse 70% 55% at 50% -10%, rgba(41,98,255,0.16), transparent 70%)",
      }}
    />
  );
}

// ── Section label (accent bar) ──────────────────────────────────────────────────

export function SectionTitle({ children }: { children: ReactNode }) {
  return <div className="section-title">{children}</div>;
}

// ── Form row ────────────────────────────────────────────────────────────────────

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 text-[11px] text-text-secondary">{label}</span>
      {children}
    </div>
  );
}

// ── Signal badge ────────────────────────────────────────────────────────────────

export function SignalBadge({ signal }: { signal: string }) {
  const s = signal.toLowerCase();
  let cls = "bg-bg-surface text-text-secondary border border-line";
  if (s === "buy" || s === "overweight") cls = "bg-up/15 text-up border border-up/30 shadow-[0_0_12px_rgba(8,153,129,0.25)]";
  else if (s === "hold") cls = "bg-warn/15 text-warn border border-warn/30 shadow-[0_0_12px_rgba(214,168,70,0.2)]";
  else if (s === "sell" || s === "underweight") cls = "bg-down/15 text-down border border-down/30 shadow-[0_0_12px_rgba(242,54,69,0.25)]";
  return (
    <span className={`badge ${cls}`}>
      <span className="dot bg-current" />
      {signal}
    </span>
  );
}

// ── Progress bar ────────────────────────────────────────────────────────────────

export function ProgressBar({
  value,
  text,
}: {
  value: number; // 0..1
  text?: string;
}) {
  const pct = Math.round(value * 100);
  return (
    <div className="w-full h-[6px] bg-bg-surface rounded-full overflow-hidden relative">
      <div
        className="h-full rounded-full transition-all duration-500 ease-out-expo relative"
        style={{
          width: `${pct}%`,
          background: "linear-gradient(90deg, #1e53e5, #2962ff 60%, #5b8bff)",
          boxShadow: "0 0 10px rgba(41,98,255,0.55)",
        }}
      >
        {/* Shimmer highlight while active */}
        <div className="absolute inset-0 overflow-hidden rounded-full">
          <div className="absolute inset-y-0 w-1/3 animate-shimmer bg-gradient-to-r from-transparent via-white/30 to-transparent" />
        </div>
      </div>
      {text && (
        <span className="absolute right-0 -top-5 text-[11px] text-text-secondary">
          {text}
        </span>
      )}
    </div>
  );
}

// ── Spinner ─────────────────────────────────────────────────────────────────────

export function Spinner({ className = "w-3 h-3" }: { className?: string }) {
  return (
    <span
      className={`inline-block ${className} border-2 border-text-muted border-t-accent rounded-full animate-spin`}
    />
  );
}
