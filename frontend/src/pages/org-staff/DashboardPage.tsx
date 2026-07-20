import { AlertTriangle, CalendarClock, MessageSquare, Users } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useOrgDashboard } from "../../api/dashboard";
import { Card } from "../../components/ui/Card";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatsCard } from "../../components/shared/StatsCard";
import { EmptyState } from "../../components/shared/EmptyState";
import { itemFadeLeft, staggerContainer } from "../../lib/motion";
import { formatDateTime } from "../../lib/utils";

const CHANNEL_DOT: Record<string, string> = {
  webchat: "bg-indigo-500",
  whatsapp: "bg-emerald-500",
  voice: "bg-purple-500",
};

export default function DashboardPage() {
  const { data, isLoading, isError } = useOrgDashboard();
  const navigate = useNavigate();

  function openConversation(conversationId: string) {
    navigate(`/org/inbox?conversation=${conversationId}`);
  }

  return (
    <div>
      <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Dashboard</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Your workspace activity for today.</p>

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
              <StatsCard label="Inbound Messages Today" value={data.messages_today} tone="blue" icon={<MessageSquare className="h-5 w-5" />} />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard label="Open Escalations" value={data.open_escalations} tone="rose" icon={<AlertTriangle className="h-5 w-5" />} />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard label="Upcoming Appointments (24h)" value={data.upcoming_appointments_24h} tone="amber" icon={<CalendarClock className="h-5 w-5" />} />
            </motion.div>
            <motion.div variants={itemFadeLeft}>
              <StatsCard label="Active Conversations" value={data.active_conversations} tone="indigo" icon={<Users className="h-5 w-5" />} />
            </motion.div>
          </motion.div>

          <Card title="Recent Conversations" className="mt-6">
            {data.recent_conversations.length === 0 ? (
              <EmptyState icon={<MessageSquare className="h-5 w-5" />} title="No conversations yet" />
            ) : (
              <ul className="space-y-1">
                {data.recent_conversations.map((conversation) => (
                  <li key={conversation.id}>
                    <button
                      type="button"
                      onClick={() => openConversation(conversation.id)}
                      className="flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left transition-colors duration-150 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    >
                      <span
                        className={`h-2 w-2 shrink-0 rounded-full ${CHANNEL_DOT[conversation.channel] ?? "bg-slate-400"}`}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-slate-700 dark:text-slate-200">{conversation.contact_name}</p>
                        <p className="text-xs capitalize text-slate-400 dark:text-slate-500">
                          {conversation.channel} · {conversation.status}
                        </p>
                      </div>
                      <span className="shrink-0 text-xs tabular-nums text-slate-400 dark:text-slate-500">
                        {formatDateTime(conversation.last_message_at)}
                      </span>
                    </button>
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
