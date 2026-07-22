// Mirror of backend responses in app/services/billing_service.py.
// Kept loose (no discriminated unions) because the payload evolves as we
// tune the cost model — an over-tight type here would need churn on every
// tuning PR without adding safety.

export interface BillingKpis {
  total_ai_messages: number;
  total_usd: number;
  llm_input_usd: number;
  llm_output_usd: number;
  external_api_usd: number;
  cost_per_message_usd: number;
}

export interface BillingDailyPoint {
  date: string;
  total_usd: number;
}

export interface BillingProviderEntry {
  provider: string;
  total_usd: number;
}

export interface BillingChannelEntry {
  channel: string;
  total_usd: number;
}

export interface OrgBillingRow {
  org_id: string;
  org_name: string;
  plan: string;
  provider: string;
  ai_messages: number;
  llm_input_usd: number;
  llm_output_usd: number;
  external_api_usd: number;
  total_usd: number;
  channels: Record<string, number>;
}

export interface BillingAnalyticsResponse {
  window_days: number;
  generated_at: string;
  org_id: string | null;
  kpis: BillingKpis;
  cost_by_day: BillingDailyPoint[];
  cost_by_provider: BillingProviderEntry[];
  cost_by_channel: BillingChannelEntry[];
  per_org: OrgBillingRow[];
}

// ─── Org-staff snapshot ───────────────────────────────────────────

export interface PlanInfo {
  key: "free" | "starter" | "pro" | "enterprise" | string;
  display_name: string;
  monthly_message_quota: number;
  price_usd_monthly: number;
  features: string[];
}

export interface UsageInfo {
  messages_used: number;
  messages_quota: number;
  percent_used: number;
  ai_messages_this_month: number;
}

export interface ProviderInfo {
  key: string;
  model: string;
  llm_input_price_per_1k: number;
  llm_output_price_per_1k: number;
  input_tokens_per_message: number;
  output_tokens_per_message: number;
}

export interface ChannelCostEntry {
  channel: string;
  ai_messages: number;
  total_usd: number;
}

export interface OrgBillingSnapshot {
  org_id: string;
  generated_at: string;
  month_start: string;
  plan: PlanInfo;
  usage: UsageInfo;
  provider: ProviderInfo;
  channel_extras_per_msg: Record<string, number>;
  cost_this_month: {
    llm_input_usd: number;
    llm_output_usd: number;
    external_api_usd: number;
    total_usd: number;
    by_channel: ChannelCostEntry[];
  };
}
