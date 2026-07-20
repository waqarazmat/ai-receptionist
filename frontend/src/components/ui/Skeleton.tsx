export interface SkeletonProps {
  className?: string;
}

/** Subtle pulsing placeholder for content that's loading. Prefer this over a
 * bare spinner for list/stat/table loading states; keep the Spinner for
 * button loading. */
export function Skeleton({ className = "" }: SkeletonProps) {
  return <div className={`animate-pulse rounded-md bg-slate-100 dark:bg-slate-800 ${className}`} aria-hidden="true" />;
}
