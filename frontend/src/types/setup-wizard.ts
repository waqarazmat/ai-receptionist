export type ApiKeyProvider =
  | "openai"
  | "anthropic"
  | "cohere"
  | "whatsapp"
  | "google_calendar"
  | "retell"
  | "groq"
  | "deepgram";

export interface BasicInfoStep {
  name: string;
  industry: string;
  timezone: string;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
}

export interface DayHours {
  open: string;
  close: string;
}

export interface WorkingHoursStep {
  hours: Record<string, DayHours>;
  holidays: string[];
}

export interface ChannelConfigStep {
  webchat: boolean;
  whatsapp: boolean;
  voice: boolean;
  is_trial: boolean;
}

export interface ApiKeysStepInput {
  provider: ApiKeyProvider;
  api_key: string;
}

export interface WhatsappConfigStepInput {
  // Sent independently — each inline field saves on its own.
  phone_number?: string;
  phone_number_id?: string;
}

export interface VoiceConfigStepInput {
  retell_agent_id: string;
  supported_languages: string[];
}

export interface KnowledgeChunkInput {
  content: string;
}

export interface KnowledgeBaseStep {
  name: string;
  chunks: KnowledgeChunkInput[];
}

export interface WebsiteCrawlRequest {
  url: string;
  knowledge_base_id?: string | null;
}

export interface WebsiteCrawlResult {
  knowledge_base_id: string;
  knowledge_base_name: string;
  provider: string;
  pages_crawled: number;
  chunks_created: number;
  replaced_chunks: number;
  errors: string[];
}

export interface BookingServiceInput {
  name: string;
  duration_minutes: number;
  buffer_minutes: number;
}

export interface BookingConfigStep {
  services: BookingServiceInput[];
  calendar_enabled: boolean;
}

export interface SystemPromptsStep {
  greeting: string;
  personality: string;
  escalation_rules: string;
  off_topic_response: string;
  // Free-form custom prompt appended to the assembled system prompt on the
  // backend (see backend/app/ai/prompts/receptionist_system.py). Optional —
  // wizard sends an empty string when unused.
  system_prompt?: string | null;
}

export interface StaffAccessStep {
  emails: string[];
}

export interface SetupStateResponse {
  setup_progress: Record<string, boolean>;
  setup_completed: boolean;
  basic_info: BasicInfoStep | null;
  working_hours: WorkingHoursStep | null;
  channels: ChannelConfigStep | null;
  api_keys_configured: ApiKeyProvider[];
  knowledge_base: KnowledgeBaseStep | null;
  booking: BookingConfigStep | null;
  system_prompts: SystemPromptsStep | null;
  staff_emails: string[];
  google_calendar_service_account_email: string | null;
  whatsapp_phone_number: string | null;
  whatsapp_phone_number_id: string | null;
  voice_retell_agent_id: string | null;
  voice_supported_languages: string[] | null;
}

export const WIZARD_STEP_KEYS = [
  "basic_info",
  "working_hours",
  "channels",
  "api_keys",
  "knowledge_base",
  "booking",
  "system_prompts",
  "staff",
] as const;

export type WizardStepKey = (typeof WIZARD_STEP_KEYS)[number] | "review";

export const WIZARD_STEPS: { key: WizardStepKey; label: string }[] = [
  { key: "basic_info", label: "Basic Info" },
  { key: "working_hours", label: "Working Hours" },
  { key: "channels", label: "Channels" },
  { key: "api_keys", label: "API Keys" },
  { key: "knowledge_base", label: "Knowledge Base" },
  { key: "booking", label: "Booking" },
  { key: "system_prompts", label: "System Prompts" },
  { key: "staff", label: "Staff Access" },
  { key: "review", label: "Review & Activate" },
];
