import { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Building2,
  DollarSign,
  Loader2,
  MessageSquare,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import { motion } from "framer-motion";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAdminAnalytics, useAdminDashboard } from "../../api/dashboard";
import { Card } from "../../components/ui/Card";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatsCard } from "../../components/shared/StatsCard";
import { EmptyState } from "../../components/shared/EmptyState";
import { itemFadeLeft, staggerContainer } from "../../lib/motion";
import { formatActionLabel, formatDateTime } from "../../lib/utils";
import type { ChannelBreakdownEntry, MessagesPerDayPoint } from "../../types/analytics";

// Time-window options for the analytics toggle. Kept as a constant so the
// backend param and UI label stay in sync.
const WINDOWS = [
  { days: 7, label: "7d" },
  { days: 30, label: "30d" },
  { days: 90, label: "90d" },
] as const;

// Brand-consistent palette used across charts. Deliberately hand-picked to
// stay readable in both light and dark mode.
const CHANNEL_COLORS: Record<string, string> = {
  webchat: "#6366f1", // indigo-500 — matches the primary CTA
  whatsapp: "#10b981", // emerald-500 — Meta's own brand green
  voice: "#f97316", // orange-500 — distinct enough to read at small sizes
};

const CHANNEL_LABELS: Record<string, string> = {
  webchat: "Web chat",
  whatsapp: "WhatsApp",
  voice: "Voice",
};

// Shorten "2026-07-22" → "Jul 22" for the x-axis. Keeps the axis narrow so
// 30 daily ticks fit on typical screen widths without rotating labels.
function formatDayShort(iso: string) {
  try {
    return new Date(iso + "T00:00:00Z").toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

// Custom tooltip so the chart matches the app's card/border styling instead
// of Recharts' default white box (which sticks out in dark mode).
function ChartTooltip({
  active,
  payload,
  label,
  labelFormatter,
  valueSuffix = "",
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string; dataKey?: string }>;
  label?: string;
  labelFormatter?: (label: string) => string;
  valueSuffix?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm dark:border-slate-700 dark:bg-slate-800/95">
      <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
        {labelFormatter && label ? labelFormatter(label) : label}
      </p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 text-xs">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-slate-600 dark:text-slate-300">
            {CHANNEL_LABELS[entry.dataKey ?? entry.name] ?? entry.name}
          </span>
          <span className="ml-auto font-mono font-semibold text-slate-900 dark:text-slate-100">
            {entry.value.toLocaleString()}
            {valueSuffix}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const [windowDays, setWindowDays] = useState<number>(30);
  const { data: adminData } = useAdminDashboard();
  const { data: analytics, isLoading, isError, refetch, isFetching } =
    useAdminAnalytics(windowDays);

  // Recharts wants the totals rendered as a percentage for the donut chart's
  // labels, so precompute the sum + map channel labels once per render.
  const channelTotal = useMemo(
    () => analytics?.channel_breakdown.reduce((sum, c) => sum + c.count, 0) ?? 0,
    [analytics],
  );

  const topOrgs = useMemo(() => analytics?.per_org.slice(0, 10) ?? [], [analytics]);

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
            Super Admin Dashboard
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Platform health across every organization at a glance.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Window toggle — same treatment as radio-group segments, but built
              from Buttons for keyboard/focus consistency with the rest of the
              app. */}
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 dark:border-slate-700 dark:bg-slate-800">
            {WINDOWS.map((w) => {
              const isActive = w.days === windowDays;
              return (
                <button
                  key={w.days}
                  type="button"
                  onClick={() => setWindowDays(w.days)}
                  className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                    isActive
                      ? "bg-indigo-500 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700/60"
                  }`}
                >
                  {w.label}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            title="Refresh analytics"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700/60"
          >
            {isFetching ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Refresh
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="mt-6 grid grid-cols-2 gap-6 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : isError || !analytics ? (
        <p className="mt-6 text-sm text-rose-600 dark:text-rose-400">
          Failed to load analytics.
        </p>
      ) : (
        <>
          {/* ─── KPI ROW ───────────────────────────────────────────── */}
          <motion.div
            className="mt-6 grid grid-cols-2 gap-6 lg:grid-cols-4"
            variants={staggerContainer(0.05)}
            initial="hidden"
            animate="show"
          >
            <motion.div variants={itemFadeLeft}>
              <StatsCard
                label={`Messages · ${windowDays}d`}
                value={analytics.kpis.total_messages.toLocaleString()}
                tone="indigo"
                icon={<MessageSquare className="h-5 w-5" />}
                hint={`${analytics.kpis.avg_messages_per_day.toLocaleString()} avg/day`}
              />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard
                label="Active orgs"
                value={analytics.kpis.active_orgs.toLocaleString()}
                tone="emerald"
                icon={<Building2 className="h-5 w-5" />}
                hint={`of ${adminData?.total_orgs ?? "-"} total`}
              />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard
                label="Escalation rate"
                value={`${analytics.kpis.escalation_rate_pct}%`}
                tone="rose"
                icon={<AlertTriangle className="h-5 w-5" />}
                hint={`${analytics.kpis.total_escalations.toLocaleString()} of ${analytics.kpis.total_conversations.toLocaleString()} convos`}
              />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard
                label="Est. LLM cost"
                value={`$${analytics.kpis.estimated_cost_usd.toFixed(2)}`}
                tone="blue"
                icon={<DollarSign className="h-5 w-5" />}
                hint={`~$${(analytics.kpis.estimated_cost_usd / Math.max(analytics.kpis.active_orgs, 1)).toFixed(2)}/org`}
              />
            </motion.div>
          </motion.div>

          {/* ─── CHARTS ROW ────────────────────────────────────────── */}
          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Area chart — messages/day stacked by channel. Takes 2/3 width. */}
            <Card
              title="Messages per day"
              className="lg:col-span-2"
              headerRight={
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400">
                  <TrendingUp className="h-3.5 w-3.5" />
                  Last {windowDays} days
                </span>
              }
            >
              <MessagesAreaChart data={analytics.messages_per_day} />
            </Card>

            {/* Channel breakdown donut. Takes remaining 1/3. */}
            <Card title="Channel breakdown">
              <ChannelDonut data={analytics.channel_breakdown} total={channelTotal} />
            </Card>
          </div>

          {/* ─── SECOND CHART ROW — top orgs by volume ─────────────── */}
          <Card title="Top 10 organizations by message volume" className="mt-6">
            {topOrgs.length === 0 ? (
              <EmptyState
                icon={<Activity className="h-5 w-5" />}
                title="No traffic in this window"
                description="Once your orgs start receiving messages, they'll show up here."
              />
            ) : (
              <TopOrgsChart data={topOrgs} />
            )}
          </Card>

          {/* ─── PER-ORG TABLE ─────────────────────────────────────── */}
          <Card title="Per-organization breakdown" className="mt-6">
            <PerOrgTable rows={analytics.per_org} />
          </Card>

          {/* ─── RECENT ACTIVITY (kept from prior dashboard) ───────── */}
          {adminData && (
            <Card title="Recent activity" className="mt-6">
              {adminData.recent_activity.length === 0 ? (
                <EmptyState
                  icon={<MessageSquare className="h-5 w-5" />}
                  title="No activity yet"
                />
              ) : (
                <ul className="space-y-1">
                  {adminData.recent_activity.map((entry, index) => (
                    <li
                      key={`${entry.action}-${entry.created_at}-${index}`}
                      className="flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors duration-150 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    >
                      <span className="h-2 w-2 shrink-0 rounded-full bg-indigo-500" />
                      <span className="flex-1 text-sm font-medium text-slate-700 dark:text-slate-200">
                        {formatActionLabel(entry.action)}
                      </span>
                      <span className="text-xs tabular-nums text-slate-400 dark:text-slate-500">
                        {formatDateTime(entry.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────

function MessagesAreaChart({ data }: { data: MessagesPerDayPoint[] }) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 10, left: 0, bottom: 0 }}>
          <defs>
            {(["webchat", "whatsapp", "voice"] as const).map((ch) => (
              <linearGradient key={ch} id={`grad-${ch}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHANNEL_COLORS[ch]} stopOpacity={0.5} />
                <stop offset="100%" stopColor={CHANNEL_COLORS[ch]} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.08} />
          <XAxis
            dataKey="date"
            tickFormatter={formatDayShort}
            tick={{ fontSize: 11, fill: "currentColor", opacity: 0.6 }}
            axisLine={false}
            tickLine={false}
            minTickGap={20}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "currentColor", opacity: 0.6 }}
            axisLine={false}
            tickLine={false}
            width={35}
          />
          <Tooltip
            content={<ChartTooltip labelFormatter={formatDayShort} />}
            cursor={{ stroke: "currentColor", strokeOpacity: 0.15 }}
          />
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            formatter={(v) => CHANNEL_LABELS[v as string] ?? v}
          />
          {(["webchat", "whatsapp", "voice"] as const).map((ch) => (
            <Area
              key={ch}
              type="monotone"
              dataKey={ch}
              stackId="1"
              stroke={CHANNEL_COLORS[ch]}
              strokeWidth={2}
              fill={`url(#grad-${ch})`}
              // Tiny animation delay so channels layer in visibly rather than
              // all appearing at once.
              animationDuration={600}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChannelDonut({
  data,
  total,
}: {
  data: ChannelBreakdownEntry[];
  total: number;
}) {
  if (total === 0) {
    return (
      <EmptyState
        icon={<Activity className="h-5 w-5" />}
        title="No messages yet"
        description="Send a message on any channel to see it appear here."
      />
    );
  }
  const chartData = data.map((d) => ({
    name: CHANNEL_LABELS[d.channel] ?? d.channel,
    channel: d.channel,
    value: d.count,
  }));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={chartData}
            innerRadius="55%"
            outerRadius="85%"
            paddingAngle={2}
            dataKey="value"
            nameKey="name"
            animationDuration={600}
          >
            {chartData.map((entry) => (
              <Cell key={entry.channel} fill={CHANNEL_COLORS[entry.channel]} stroke="none" />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            formatter={(v) => v}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function TopOrgsChart({
  data,
}: {
  data: Array<{ org_name: string; messages: number; escalation_rate_pct: number }>;
}) {
  return (
    <div className="h-80 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.08} />
          <XAxis
            type="number"
            tick={{ fontSize: 11, fill: "currentColor", opacity: 0.6 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="org_name"
            tick={{ fontSize: 12, fill: "currentColor", opacity: 0.8 }}
            axisLine={false}
            tickLine={false}
            width={140}
          />
          <Tooltip
            content={<ChartTooltip />}
            cursor={{ fill: "currentColor", fillOpacity: 0.05 }}
          />
          <Bar
            dataKey="messages"
            fill="#6366f1"
            radius={[0, 6, 6, 0]}
            animationDuration={600}
          >
            {data.map((row, i) => (
              // Fade darker for lower-ranking orgs — subtle visual weighting.
              <Cell
                key={row.org_name}
                fill={`rgba(99, 102, 241, ${1 - i * 0.06})`}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function PerOrgTable({
  rows,
}: {
  rows: Array<{
    org_id: string;
    org_name: string;
    is_active: boolean;
    messages: number;
    conversations: number;
    escalations: number;
    escalation_rate_pct: number;
    estimated_cost_usd: number;
  }>;
}) {
  if (rows.length === 0) {
    return (
      <EmptyState
        icon={<Building2 className="h-5 w-5" />}
        title="No organizations yet"
        description="Add an organization from the Organizations tab to start seeing analytics."
      />
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <th className="pb-3 pr-4">Organization</th>
            <th className="pb-3 pr-4 text-right">Messages</th>
            <th className="pb-3 pr-4 text-right">Conversations</th>
            <th className="pb-3 pr-4 text-right">Escalations</th>
            <th className="pb-3 pr-4 text-right">Escalation %</th>
            <th className="pb-3 text-right">Est. cost</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row) => (
            <tr
              key={row.org_id}
              className="group transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <td className="py-3 pr-4">
                <div className="flex items-center gap-2">
                  <span
                    className={`h-2 w-2 rounded-full ${
                      row.is_active
                        ? "bg-emerald-500"
                        : "bg-slate-300 dark:bg-slate-600"
                    }`}
                    title={row.is_active ? "Active" : "Inactive"}
                  />
                  <span className="font-medium text-slate-900 dark:text-slate-100">
                    {row.org_name}
                  </span>
                </div>
              </td>
              <td className="py-3 pr-4 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">
                {row.messages.toLocaleString()}
              </td>
              <td className="py-3 pr-4 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">
                {row.conversations.toLocaleString()}
              </td>
              <td className="py-3 pr-4 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">
                {row.escalations.toLocaleString()}
              </td>
              <td className="py-3 pr-4 text-right">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                    row.escalation_rate_pct > 20
                      ? "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300"
                      : row.escalation_rate_pct > 10
                      ? "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
                      : "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"
                  }`}
                >
                  {row.escalation_rate_pct}%
                </span>
              </td>
              <td className="py-3 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">
                ${row.estimated_cost_usd.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
