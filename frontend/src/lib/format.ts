/**
 * Shared formatting helpers. Kept as pure functions so tests can hit every
 * branch without React state.
 */

/**
 * Human-readable relative timestamp: "just now", "5m ago", "3h ago",
 * "12d ago", "2mo ago", or a locale date string past a year.
 *
 * Used in UsersManagementPage for `last_login`. Behaviour is deliberately
 * coarse — precision isn't valuable in an admin table, but consistent
 * bucketing is.
 */
export function formatRelative(iso: string | null): string {
  if (!iso) return "Never";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "Never";
  const diff = Date.now() - then;
  if (diff < 0) return "just now";
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return new Date(iso).toLocaleDateString();
}
