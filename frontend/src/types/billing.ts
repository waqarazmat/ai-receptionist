// Mirror of the backend billing_service.py responses.
// Kept loose (no discriminated unions) because the payload evolves as we
// tune the cost model — an over-tight type here would need churn on every
// tuning PR without adding safety.

export interface BillingTotals {
  messages: number;
  llm_usd: number;
  external_usd: number;
  total_usd: number;
}

export interface BillingProviderEntry {
  provider: string;
  total_usd: number;
}

export interface BillingChannelEntry {
  channel: string;
  messages: number;
  llm_usd: number;
  external_usd: number;
  total_usd: number;
}

export interface BillingDailyPoint {
  date: string;
  webchat: number;
  whatsapp: number;
  voice: number;
  total: number;
}

export interface OrgBillingRow {
  org_id: string;
  org_name: string;
  plan: string;
  primary_provider: string;
  messages: number;
  llm_usd: number;
  external_usd: number;
  total_usd: number;
  by_channel: Record<string, { messages: number; total_usd: number }>;
}

export interface PricingNotes {
  input_tokens_per_msg: number;
  output_tokens_per_msg: number;
  channel_extra_usd_per_msg: Record<string, number>;
  provider_model_map: Record<string, string>;
  model_input_price_per_1k: Record<string, number>;
  model_output_price_per_1k: Record<string, number>;
}

export interface BillingAnalyticsResponse {
  window_days: number;
  generated_at: string;
  org_id: string | null;
  totals: BillingTotals;
  by_provider: BillingProviderEntry[];
  by_channel: BillingChannelEntry[];
  daily: BillingDailyPoint[];
  per_org: OrgBillingRow[];
  pricing_notes: PricingNotes;
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
  messages_this_month: number;
  quota: number;
  percent_used: number;
}

export interface OrgBillingSnapshot {
  plan: PlanInfo;
  usage: UsageInfo;
  current_month_costs: BillingTotals;
  by_channel: BillingChannelEntry[];
  daily: BillingDailyPoint[];
  pricing_notes: PricingNotes;
}
