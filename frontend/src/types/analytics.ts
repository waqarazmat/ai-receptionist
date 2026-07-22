export interface AnalyticsKpis {
  total_messages: number;
  active_orgs: number;
  total_conversations: number;
  total_escalations: number;
  escalation_rate_pct: number;
  avg_messages_per_day: number;
  estimated_cost_usd: number;
}

export interface MessagesPerDayPoint {
  date: string; // ISO YYYY-MM-DD
  webchat: number;
  whatsapp: number;
  voice: number;
}

export interface ChannelBreakdownEntry {
  channel: "webchat" | "whatsapp" | "voice";
  count: number;
}

export interface OrgAnalyticsRow {
  org_id: string;
  org_name: string;
  is_active: boolean;
  messages: number;
  conversations: number;
  escalations: number;
  escalation_rate_pct: number;
  estimated_cost_usd: number;
}

export interface AnalyticsResponse {
  window_days: number;
  generated_at: string;
  kpis: AnalyticsKpis;
  messages_per_day: MessagesPerDayPoint[];
  channel_breakdown: ChannelBreakdownEntry[];
  per_org: OrgAnalyticsRow[];
}
