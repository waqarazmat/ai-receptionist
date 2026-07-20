import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useContact } from "../../api/contacts";
import { ConversationStatusBadge } from "../../components/shared/StatusBadge";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { formatDateTime } from "../../lib/utils";

export interface ContactDetailModalProps {
  contactId: string | null;
  onClose: () => void;
}

export function ContactDetailModal({ contactId, onClose }: ContactDetailModalProps) {
  const { data: contact, isLoading } = useContact(contactId);
  const navigate = useNavigate();

  function openConversation(conversationId: string) {
    navigate(`/org/inbox?conversation=${conversationId}`);
  }

  return (
    <Modal isOpen={Boolean(contactId)} onClose={onClose} title="Contact Details">
      {isLoading || !contact ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">{contact.name}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 capitalize">{contact.channel}</p>
          </div>

          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Phone</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{contact.phone ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Email</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{contact.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Conversations</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{contact.conversation_count}</dd>
            </div>
          </dl>

          <div>
            <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">Conversation history</p>
            {contact.conversations.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">No conversations yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800 rounded-lg border border-slate-200 dark:border-slate-800">
                {contact.conversations.map((conv) => (
                  <li key={conv.id}>
                    <button
                      type="button"
                      onClick={() => openConversation(conv.id)}
                      className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    >
                      <span className="flex items-center gap-2">
                        <ConversationStatusBadge status={conv.status as "active" | "escalated" | "resolved"} />
                        <span className="text-slate-500 dark:text-slate-400">{formatDateTime(conv.last_message_at)}</span>
                      </span>
                      <ArrowRight className="h-3.5 w-3.5 text-slate-400 dark:text-slate-500" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}
