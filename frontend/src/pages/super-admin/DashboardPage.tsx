import { AlertTriangle, Building2, CheckCircle2, MessageSquare } from "lucide-react";
import { motion } from "framer-motion";
import { useAdminDashboard } from "../../api/dashboard";
import { Card } from "../../components/ui/Card";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatsCard } from "../../components/shared/StatsCard";
import { EmptyState } from "../../components/shared/EmptyState";
import { itemFadeLeft, staggerContainer } from "../../lib/motion";
import { formatActionLabel, formatDateTime } from "../../lib/utils";

export default function DashboardPage() {
  const { data, isLoading, isError } = useAdminDashboard();

  return (
    <div>
      <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Super Admin Dashboard</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Platform health across every organization at a glance.</p>

      {isLoading ? (
        <div className="mt-6 grid grid-cols-2 gap-6 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : isError || !data ? (
        <p className="mt-6 text-sm text-rose-600 dark:text-rose-400">Failed to load dashboard.</p>
      ) : (
        <>
          <motion.div
            className="mt-6 grid grid-cols-2 gap-6 lg:grid-cols-4"
            variants={staggerContainer(0.05)}
            initial="hidden"
            animate="show"
          >
            <motion.div variants={itemFadeLeft}>
              <StatsCard label="Total Orgs" value={data.total_orgs} tone="indigo" icon={<Building2 className="h-5 w-5" />} />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard label="Active Orgs" value={data.active_orgs} tone="emerald" icon={<CheckCircle2 className="h-5 w-5" />} />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard label="Messages Today" value={data.total_messages_today} tone="blue" icon={<MessageSquare className="h-5 w-5" />} />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard label="Pending Escalations" value={data.total_escalations_pending} tone="rose" icon={<AlertTriangle className="h-5 w-5" />} />
            </motion.div>
          </motion.div>

          <Card title="Recent Activity" className="mt-6">
            {data.recent_activity.length === 0 ? (
              <EmptyState icon={<MessageSquare className="h-5 w-5" />} title="No activity yet" />
            ) : (
              <ul className="space-y-1">
                {data.recent_activity.map((entry, index) => (
                  <li
                    key={`${entry.action}-${entry.created_at}-${index}`}
                    className="flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors duration-150 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <span className="h-2 w-2 shrink-0 rounded-full bg-indigo-500" />
                    <span className="flex-1 text-sm font-medium text-slate-700 dark:text-slate-200">
                      {formatActionLabel(entry.action)}
                    </span>
                    <span className="text-xs tabular-nums text-slate-400 dark:text-slate-500">{formatDateTime(entry.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
