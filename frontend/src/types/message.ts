import type { Channel } from "./conversation";

export type MessageRole = "customer" | "ai" | "staff";

export interface Message {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  channel: Channel;
  created_at: string;
}
