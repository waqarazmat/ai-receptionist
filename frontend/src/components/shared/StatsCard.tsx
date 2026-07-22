import { useEffect, useRef, useState, type ReactNode } from "react";

type StatTone = "indigo" | "emerald" | "amber" | "rose" | "blue" | "slate";

const TONE_STYLES: Record<StatTone, string> = {
  indigo: "bg-indigo-50 text-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-400",
  emerald: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400",
  amber: "bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400",
  rose: "bg-rose-50 text-rose-600 dark:bg-rose-500/10 dark:text-rose-400",
  blue: "bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400",
  slate: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

export interface StatsCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  /** Soft colored circle behind the icon. */
  tone?: StatTone;
  /** Small caption under the value — e.g. "42 avg/day" or "of 12 total". */
  hint?: string;
}

export function StatsCard({ label, value, icon, tone = "indigo", hint }: StatsCardProps) {
  // Brief scale pulse whenever the value changes (e.g. a realtime count bump).
  const [pulse, setPulse] = useState(false);
  const prev = useRef(value);
  useEffect(() => {
    if (prev.current !== value) {
      prev.current = value;
      setPulse(true);
      const timer = setTimeout(() => setPulse(false), 320);
      return () => clearTimeout(timer);
    }
  }, [value]);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
        {icon && (
          <span className={`flex h-9 w-9 items-center justify-center rounded-full ${TONE_STYLES[tone]}`}>
            {icon}
          </span>
        )}
      </div>
      <p className="mt-3">
        <span
          className={`inline-block text-3xl font-bold tabular-nums tracking-tight text-slate-900 dark:text-slate-50 ${
            pulse ? "animate-stat-pulse" : ""
          }`}
        >
          {value}
        </span>
      </p>
      {hint && (
        <p className="mt-1 text-xs font-medium text-slate-400 dark:text-slate-500">
          {hint}
        </p>
      )}
    </div>
  );
}
