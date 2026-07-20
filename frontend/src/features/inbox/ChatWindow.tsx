import { useEffect, useRef, useState } from "react";
import { Send, UserX } from "lucide-react";
import {
  useConversation,
  useConversationMessages,
  useReleaseConversation,
  useResolveConversation,
  useSendStaffMessage,
  useTakeOverConversation,
} from "../../api/conversations";
import { useEscalations } from "../../api/escalations";
import { useInboxStore } from "../../stores/inbox-store";
import { Button } from "../../components/ui/Button";
import { Textarea } from "../../components/ui/Textarea";
import { Spinner } from "../../components/ui/Spinner";
import { ConversationStatusBadge } from "../../components/shared/StatusBadge";
import { MessageBubble } from "./MessageBubble";
import { TakeoverBanner } from "./TakeoverBanner";

const CHANNEL_LABEL: Record<string, string> = {
  webchat: "Web Chat",
  whatsapp: "WhatsApp",
  voice: "Voice",
};

/** Three staggered pulsing dots inside a message-style bubble. */
function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-1 rounded-xl bg-slate-100 dark:bg-slate-800 px-4 py-3">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400"
            style={{ animationDelay: `${i * 200}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

export interface ChatWindowProps {
  conversationId: string;
}

export function ChatWindow({ conversationId }: ChatWindowProps) {
  const { data: conversation } = useConversation(conversationId);
  const { data: messages, isLoading } = useConversationMessages(conversationId);
  const { data: escalations } = useEscalations();
  const sendMessage = useSendStaffMessage(conversationId);
  const takeOver = useTakeOverConversation(conversationId);
  const release = useReleaseConversation(conversationId);
  const resolve = useResolveConversation(conversationId);
  const isTyping = useInboxStore((state) => state.typingByConversation[conversationId]);

  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isTyping]);

  function handleSend() {
    const content = draft.trim();
    if (!content || sendMessage.isPending) return;
    setDraft("");
    sendMessage.mutate(content);
  }

  if (!conversation) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const activeEscalation = escalations?.find(
    (escalation) => escalation.conversation_id === conversationId && escalation.status !== "resolved",
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{conversation.contact_name}</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">{CHANNEL_LABEL[conversation.channel] ?? conversation.channel}</p>
        </div>
        <div className="flex items-center gap-2">
          <ConversationStatusBadge status={conversation.status} />
          {conversation.status !== "resolved" && (
            <Button size="sm" variant="secondary" isLoading={resolve.isPending} onClick={() => resolve.mutate()}>
              Resolve
            </Button>
          )}
        </div>
      </div>

      {conversation.assigned_to === null ? (
        <TakeoverBanner
          escalationReason={activeEscalation?.reason}
          onTakeOver={() => takeOver.mutate()}
          isTakingOver={takeOver.isPending}
        />
      ) : (
        <div className="flex items-center justify-between gap-4 border-b border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/15 px-4 py-3">
          <p className="text-sm font-medium text-indigo-800 dark:text-indigo-200">You're handling this conversation</p>
          <Button size="sm" variant="ghost" isLoading={release.isPending} onClick={() => release.mutate()}>
            <UserX className="h-4 w-4" />
            Release to AI
          </Button>
        </div>
      )}

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : (
          messages?.map((message) => <MessageBubble key={message.id} message={message} />)
        )}
        {isTyping && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      <div className="flex items-end gap-2 border-t border-slate-200 dark:border-slate-800 p-3">
        <div className="flex-1">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            rows={1}
            placeholder="Type a reply…"
          />
        </div>
        <Button onClick={handleSend} isLoading={sendMessage.isPending} disabled={!draft.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
