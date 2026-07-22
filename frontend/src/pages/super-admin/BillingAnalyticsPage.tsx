import { useMemo, useState } from "react";
import {
  Activity,
  Building2,
  DollarSign,
  Loader2,
  MessageSquare,
  RefreshCw,
  TrendingUp,
  Wallet,
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
import { useAdminBillingAnalytics } from "../../api/billing";
import { useOrganizations } from "../../api/organizations";
import { Card } from "../../components/ui/Card";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatsCard } from "../../components/shared/StatsCard";
import { EmptyState } from "../../components/shared/EmptyState";
import { itemFadeLeft, staggerContainer } from "../../lib/motion";

const WINDOWS = [
  { days: 7, label: "7d" },
  { days: 30, label: "30d" },
  { days: 90, label: "90d" },
] as const;

// Provider brand-adjacent colors — mirror the main dashboard's palette so
// the two pages feel like one family.
const PROVIDER_COLORS: Record<string, string> = {
  anthropic: "#d97706", // amber-600 — Anthropic's brand orange
  openai: "#059669", // emerald-600 — OpenAI's mark green
  cohere: "#7c3aed", // violet-600 — Cohere's mark purple
};
const CHANNEL_COLORS: Record<string, string> = {
  webchat: "#6366f1",
  whatsapp: "#10b981",
  voice: "#f97316",
};
const CHANNEL_LABELS: Record<string, string> = {
  webchat: "Web chat",
  whatsapp: "WhatsApp",
  voice: "Voice",
};
const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  cohere: "Cohere",
};

function usdShort(v: number) {
  if (v >= 1000) return `$${(v / 1000).toFixed(1)}k`;
  if (v >= 100) return `$${v.toFixed(0)}`;
  return `$${v.toFixed(2)}`;
}

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

function ChartTooltip({
  active,
  payload,
  label,
  labelFormatter,
  valuePrefix = "",
  nameFormatter,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string; dataKey?: string }>;
  label?: string;
  labelFormatter?: (label: string) => string;
  valuePrefix?: string;
  nameFormatter?: (name: string) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm dark:border-slate-700 dark:bg-slate-800/95">
      {label && (
        <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          {labelFormatter ? labelFormatter(label) : label}
        </p>
      )}
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center gap-2 text-xs">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-slate-600 dark:text-slate-300">
            {nameFormatter?.(entry.dataKey ?? entry.name) ?? entry.name}
          </span>
          <span className="ml-auto font-mono font-semibold text-slate-900 dark:text-slate-100">
            {valuePrefix}
            {Number(entry.value).toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function BillingAnalyticsPage() {
  const [windowDays, setWindowDays] = useState<number>(30);
  const [orgFilter, setOrgFilter] = useState<string>("all"); // "all" or an org id

  const { data: orgs } = useOrganizations();
  const orgIdParam = orgFilter === "all" ? null : orgFilter;
  const { data, isLoading, isError, refetch, isFetching } = useAdminBillingAnalytics(
    windowDays,
    orgIdParam,
  );

  const selectedOrgName = useMemo(() => {
    if (orgFilter === "all") return "All organizations";
    return orgs?.find((o) => o.id === orgFilter)?.name ?? "Unknown organization";
  }, [orgFilter, orgs]);

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Wallet className="h-6 w-6 text-indigo-500" />
            <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              Billing Analytics
            </h2>
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Estimated LLM + external API spend across every organization.{" "}
            <span className="italic">All figures are estimates.</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Org selector */}
          <div className="relative">
            <select
              value={orgFilter}
              onChange={(e) => setOrgFilter(e.target.value)}
              className="appearance-none rounded-lg border border-slate-200 bg-white px-4 py-1.5 pr-9 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700/60"
            >
              <option value="all">All organizations</option>
              {(orgs ?? []).map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
            <Building2 className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Window toggle */}
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

      {orgFilter !== "all" && (
        <p className="mt-3 rounded-lg border border-indigo-200 bg-indigo-50/50 px-3 py-2 text-xs font-medium text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300">
          Viewing: <strong>{selectedOrgName}</strong>. Clear filter to see platform totals.
        </p>
      )}

      {isLoading ? (
        <div className="mt-6 grid grid-cols-2 gap-6 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : isError || !data ? (
        <p className="mt-6 text-sm text-rose-600 dark:text-rose-400">
          Failed to load billing analytics.
        </p>
      ) : (
        <>
          {/* KPI ROW */}
          <motion.div
            className="mt-6 grid grid-cols-2 gap-6 lg:grid-cols-4"
            variants={staggerContainer(0.05)}
            initial="hidden"
            animate="show"
          >
            <motion.div variants={itemFadeLeft}>
              <StatsCard
                label={`Total spend · ${windowDays}d`}
                value={`~$${data.kpis.total_usd.toFixed(2)}`}
                tone="indigo"
                icon={<DollarSign className="h-5 w-5" />}
                hint={`$${data.kpis.cost_per_message_usd.toFixed(4)} per message`}
              />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard
                label="AI messages"
                value={data.kpis.total_ai_messages.toLocaleString()}
                tone="blue"
                icon={<MessageSquare className="h-5 w-5" />}
                hint="Billable AI replies"
              />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard
                label="LLM tokens cost"
                value={`~$${(data.kpis.llm_input_usd + data.kpis.llm_output_usd).toFixed(2)}`}
                tone="amber"
                icon={<Activity className="h-5 w-5" />}
                hint={`In: $${data.kpis.llm_input_usd.toFixed(2)} · Out: $${data.kpis.llm_output_usd.toFixed(2)}`}
              />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard
                label="External APIs"
                value={`~$${data.kpis.external_api_usd.toFixed(2)}`}
                tone="rose"
                icon={<TrendingUp className="h-5 w-5" />}
                hint="Retell, WhatsApp, etc."
              />
            </motion.div>
          </motion.div>

          {/* CHARTS ROW */}
          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card
              title="Daily spend"
              className="lg:col-span-2"
              headerRight={
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400">
                  <TrendingUp className="h-3.5 w-3.5" />
                  Last {windowDays} days · estimated
                </span>
              }
            >
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.cost_by_day}>
                    <defs>
                      <linearGradient id="spend-gradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#6366f1" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
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
                      width={50}
                      tickFormatter={usdShort}
                    />
                    <Tooltip
                      content={
                        <ChartTooltip
                          labelFormatter={formatDayShort}
                          valuePrefix="~$"
                          nameFormatter={() => "Spend"}
                        />
                      }
                      cursor={{ stroke: "currentColor", strokeOpacity: 0.15 }}
                    />
                    <Area
                      type="monotone"
                      dataKey="total_usd"
                      stroke="#6366f1"
                      strokeWidth={2}
                      fill="url(#spend-gradient)"
                      animationDuration={600}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card title="By provider">
              {data.cost_by_provider.length === 0 ? (
                <EmptyState
                  icon={<Activity className="h-5 w-5" />}
                  title="No usage yet"
                  description="Spend will appear here once AI messages are sent."
                />
              ) : (
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={data.cost_by_provider.map((p) => ({
                          name: PROVIDER_LABELS[p.provider] ?? p.provider,
                          providerKey: p.provider,
                          value: p.total_usd,
                        }))}
                        innerRadius="55%"
                        outerRadius="85%"
                        paddingAngle={2}
                        dataKey="value"
                        nameKey="name"
                        animationDuration={600}
                      >
                        {data.cost_by_provider.map((p) => (
                          <Cell
                            key={p.provider}
                            fill={PROVIDER_COLORS[p.provider] ?? "#94a3b8"}
                            stroke="none"
                          />
                        ))}
                      </Pie>
                      <Tooltip content={<ChartTooltip valuePrefix="~$" />} />
                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
          </div>

          {/* CHANNEL BREAKDOWN */}
          <Card title="By channel" className="mt-6">
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={data.cost_by_channel.map((c) => ({
                    name: CHANNEL_LABELS[c.channel] ?? c.channel,
                    channelKey: c.channel,
                    value: c.total_usd,
                  }))}
                  layout="vertical"
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.08} />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: "currentColor", opacity: 0.6 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={usdShort}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fontSize: 12, fill: "currentColor", opacity: 0.8 }}
                    axisLine={false}
                    tickLine={false}
                    width={100}
                  />
                  <Tooltip
                    content={<ChartTooltip valuePrefix="~$" />}
                    cursor={{ fill: "currentColor", fillOpacity: 0.05 }}
                  />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} animationDuration={600}>
                    {data.cost_by_channel.map((c) => (
                      <Cell key={c.channel} fill={CHANNEL_COLORS[c.channel] ?? "#94a3b8"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* PER-ORG TABLE — only useful when viewing all orgs */}
          {orgFilter === "all" && (
            <Card title="Per-organization breakdown" className="mt-6">
              {data.per_org.length === 0 ? (
                <EmptyState
                  icon={<Building2 className="h-5 w-5" />}
                  title="No organization activity in this window"
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:border-slate-700 dark:text-slate-400">
                        <th className="pb-3 pr-4">Organization</th>
                        <th className="pb-3 pr-4">Plan</th>
                        <th className="pb-3 pr-4">Provider</th>
                        <th className="pb-3 pr-4 text-right">AI messages</th>
                        <th className="pb-3 pr-4 text-right">LLM in</th>
                        <th className="pb-3 pr-4 text-right">LLM out</th>
                        <th className="pb-3 pr-4 text-right">External</th>
                        <th className="pb-3 text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {data.per_org.map((row) => (
                        <tr
                          key={row.org_id}
                          className="group cursor-pointer transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
                          onClick={() => setOrgFilter(row.org_id)}
                          title="Click to filter to this org"
                        >
                          <td className="py-3 pr-4 font-medium text-slate-900 dark:text-slate-100">
                            {row.org_name}
                          </td>
                          <td className="py-3 pr-4">
                            <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium capitalize text-slate-700 dark:bg-slate-700/50 dark:text-slate-200">
                              {row.plan}
                            </span>
                          </td>
                          <td className="py-3 pr-4">
                            <span
                              className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold"
                              style={{
                                backgroundColor: `${PROVIDER_COLORS[row.provider] ?? "#94a3b8"}20`,
                                color: PROVIDER_COLORS[row.provider] ?? "#64748b",
                              }}
                            >
                              {PROVIDER_LABELS[row.provider] ?? row.provider}
                            </span>
                          </td>
                          <td className="py-3 pr-4 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">
                            {row.ai_messages.toLocaleString()}
                          </td>
                          <td className="py-3 pr-4 text-right font-mono tabular-nums text-slate-500 dark:text-slate-400">
                            ~${row.llm_input_usd.toFixed(2)}
                          </td>
                          <td className="py-3 pr-4 text-right font-mono tabular-nums text-slate-500 dark:text-slate-400">
                            ~${row.llm_output_usd.toFixed(2)}
                          </td>
                          <td className="py-3 pr-4 text-right font-mono tabular-nums text-slate-500 dark:text-slate-400">
                            ~${row.external_api_usd.toFixed(2)}
                          </td>
                          <td className="py-3 text-right font-mono font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                            ~${row.total_usd.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}
