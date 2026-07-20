import { Globe, MessageCircle, Phone } from "lucide-react";
import { motion } from "framer-motion";
import type { Channel, Conversation } from "../../types/conversation";
import { ConversationStatusBadge } from "../../components/shared/StatusBadge";
import { EmptyState } from "../../components/shared/EmptyState";
import { itemFadeUp, staggerContainer } from "../../lib/motion";
import { formatDateTime } from "../../lib/utils";

// Each channel gets its own accent — the channel icon tint plus the color the
// left border transitions to on hover.
const CHANNEL_META: Record<Channel, { icon: typeof Globe; hoverBorder: string; text: string }> = {
  webchat: { icon: Globe, hoverBorder: "hover:border-indigo-500", text: "text-indigo-500" },
  whatsapp: { icon: MessageCircle, hoverBorder: "hover:border-emerald-500", text: "text-emerald-500" },
  voice: { icon: Phone, hoverBorder: "hover:border-purple-500", text: "text-purple-500" },
};

export interface ConversationListProps {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function ConversationList({ conversations, selectedId, onSelect }: ConversationListProps) {
  if (conversations.length === 0) {
    return <EmptyState title="No conversations" description="Nothing matches the current filters." />;
  }

  return (
    <motion.ul
      className="divide-y divide-slate-100 dark:divide-slate-800 overflow-y-auto"
      variants={staggerContainer(0.03)}
      initial="hidden"
      animate="show"
    >
      {conversations.map((conversation) => {
        const meta = CHANNEL_META[conversation.channel];
        const ChannelIcon = meta.icon;
        const isSelected = conversation.id === selectedId;

        return (
          <motion.li key={conversation.id} variants={itemFadeUp}>
            <button
              type="button"
              onClick={() => onSelect(conversation.id)}
              className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-all duration-150 ${
                isSelected
                  ? "border-l-4 border-indigo-600 bg-indigo-50 dark:bg-indigo-500/15"
                  : `border-l-2 border-slate-200 dark:border-slate-800 hover:border-l-4 ${meta.hoverBorder} hover:bg-slate-50 dark:hover:bg-slate-800/50`
              }`}
            >
              <ChannelIcon className={`mt-0.5 h-4 w-4 shrink-0 ${meta.text}`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">{conversation.contact_name}</p>
                  <span className="shrink-0 text-xs text-slate-400 dark:text-slate-500">
                    {formatDateTime(conversation.last_message_at)}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-sm text-slate-500 dark:text-slate-400">
                  {conversation.last_message_preview ?? "No messages yet"}
                </p>
                <div className="mt-1.5 flex items-center gap-2">
                  <ConversationStatusBadge status={conversation.status} />
                  {conversation.unread_count > 0 && (
                    <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-indigo-600 px-1.5 text-xs font-medium text-white">
                      {conversation.unread_count}
                    </span>
                  )}
                </div>
              </div>
            </button>
          </motion.li>
        );
      })}
    </motion.ul>
  );
}
