export type Channel = "webchat" | "whatsapp" | "voice";
export type ConversationStatus = "active" | "escalated" | "resolved";

export interface Conversation {
  id: string;
  org_id: string;
  contact_id: string;
  contact_name: string;
  channel: Channel;
  status: ConversationStatus;
  assigned_to: string | null;
  last_message_at: string;
  unread_count: number;
  last_message_preview: string | null;
}
