import type { Channel } from "./conversation";

export interface Contact {
  id: string;
  org_id: string;
  name: string;
  phone: string | null;
  email: string | null;
  channel: Channel;
  conversation_count: number;
  last_contact_at: string | null;
}

export interface ContactConversationEntry {
  id: string;
  channel: Channel;
  status: string;
  last_message_at: string;
}

export interface ContactDetail extends Contact {
  conversations: ContactConversationEntry[];
}
