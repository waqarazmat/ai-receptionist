import type { ReactNode } from "react";

export interface CardProps {
  title?: string;
  children: ReactNode;
  className?: string;
  /** Interactive cards (list rows, clickable tiles) get a hover shadow lift.
   * Leave off for static display cards. */
  interactive?: boolean;
  /** Slot in the card header (right-aligned), e.g. a filter chip, a legend,
   * or a "Last 30 days" hint next to the title. */
  headerRight?: ReactNode;
}

export function Card({
  title,
  children,
  className = "",
  interactive = false,
  headerRight,
}: CardProps) {
  return (
    <div
      className={`rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 ${
        interactive
          ? "transition-all duration-200 hover:border-indigo-200 hover:shadow-md dark:hover:border-indigo-500/40"
          : ""
      } ${className}`}
    >
      {title && (
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-6 py-4 dark:border-slate-800">
          <h3 className="text-lg font-medium tracking-tight text-slate-800 dark:text-slate-100">{title}</h3>
          {headerRight}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
}
