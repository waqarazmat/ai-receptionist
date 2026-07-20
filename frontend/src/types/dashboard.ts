export interface RecentActivityEntry {
  action: string;
  target_id: string | null;
  user_id: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AdminDashboard {
  total_orgs: number;
  active_orgs: number;
  total_messages_today: number;
  total_escalations_pending: number;
  recent_activity: RecentActivityEntry[];
}

export interface RecentConversationEntry {
  id: string;
  contact_name: string;
  channel: string;
  status: string;
  last_message_at: string;
}

export interface OrgDashboard {
  messages_today: number;
  open_escalations: number;
  upcoming_appointments_24h: number;
  active_conversations: number;
  recent_conversations: RecentConversationEntry[];
}
