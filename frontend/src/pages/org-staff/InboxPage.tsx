import { useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { MessageSquare } from "lucide-react";
import { useConversations } from "../../api/conversations";
import { useInboxStore, type StatusFilter } from "../../stores/inbox-store";
import { ConversationList } from "../../features/inbox/ConversationList";
import { ChatWindow } from "../../features/inbox/ChatWindow";
import { SearchInput } from "../../components/shared/SearchInput";
import { EmptyState } from "../../components/shared/EmptyState";
import { Skeleton } from "../../components/ui/Skeleton";

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "escalated", label: "Escalated" },
  { value: "resolved", label: "Resolved" },
];

export default function InboxPage() {
  // Socket connection + realtime listeners live at MainLayout level (see
  // AppRealtimeProvider) so escalation/message alerts fire app-wide, not
  // only while this specific page happens to be mounted.
  const [searchParams] = useSearchParams();

  const selectedConversationId = useInboxStore((state) => state.selectedConversationId);
  const statusFilter = useInboxStore((state) => state.statusFilter);
  const searchQuery = useInboxStore((state) => state.searchQuery);
  const setSelectedConversation = useInboxStore((state) => state.setSelectedConversation);
  const setFilter = useInboxStore((state) => state.setFilter);
  const setSearch = useInboxStore((state) => state.setSearch);

  // Deep-link support (Contacts/Dashboard/Escalations navigate here with
  // ?conversation={id}) — makes the link shareable/reload-safe, unlike
  // driving selection through Zustand alone.
  useEffect(() => {
    const conversationParam = searchParams.get("conversation");
    if (conversationParam) {
      setSelectedConversation(conversationParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const { data: conversations, isLoading } = useConversations({ status: statusFilter });

  const filteredConversations = useMemo(() => {
    if (!conversations) return [];
    const query = searchQuery.trim().toLowerCase();
    if (!query) return conversations;
    return conversations.filter((conversation) => conversation.contact_name.toLowerCase().includes(query));
  }, [conversations, searchQuery]);

  return (
    <div className="flex h-[calc(100vh-7rem)] overflow-hidden rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
      <div className="flex w-[30%] min-w-[280px] flex-col border-r border-slate-200 dark:border-slate-800">
        <div className="space-y-3 border-b border-slate-200 dark:border-slate-800 p-3">
          <SearchInput value={searchQuery} onChange={setSearch} placeholder="Search conversations…" />
          <div className="flex gap-1">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                type="button"
                onClick={() => setFilter(tab.value)}
                className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                  statusFilter === tab.value ? "bg-indigo-600 text-white" : "text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        {isLoading ? (
          <div className="space-y-3 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-start gap-3">
                <Skeleton className="mt-0.5 h-4 w-4 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3.5 w-2/3" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-4 w-20 rounded-full" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <ConversationList
            conversations={filteredConversations}
            selectedId={selectedConversationId}
            onSelect={setSelectedConversation}
          />
        )}
      </div>

      <div className="flex-1">
        {selectedConversationId ? (
          <ChatWindow conversationId={selectedConversationId} />
        ) : (
          <EmptyState
            icon={<MessageSquare className="h-10 w-10" />}
            title="Select a conversation"
            description="Choose a conversation from the list to view messages."
          />
        )}
      </div>
    </div>
  );
}
