export interface Organization {
  id: string;
  name: string;
  slug: string;
  industry: string;
  timezone: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
  is_trial: boolean;
  channels_enabled: {
    webchat: boolean;
    whatsapp: boolean;
    voice: boolean;
  };
  setup_completed: boolean;
  message_count: number;
  escalation_count: number;
  created_at: string;
}

export interface OrgProfile {
  id: string;
  name: string;
  industry: string;
  timezone: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  working_hours: {
    hours: Record<string, { open: string; close: string } | null>;
    holidays: string[];
  };
  channels_enabled: {
    webchat: boolean;
    whatsapp: boolean;
    voice: boolean;
  };
}

export interface OrgChannelStatus {
  webchat: {
    enabled: boolean;
    configured: boolean;
  };
  whatsapp: {
    enabled: boolean;
    configured: boolean;
    phone_number: string | null;
  };
  voice: {
    enabled: boolean;
    configured: boolean;
    agent_id: string | null;
    phone_number: string | null;
    retell_agent_id: string | null;
    // Whether Retell's Custom LLM URL for this agent points at this backend.
    // null when it couldn't be checked (no API key / agent id / Retell down).
    provisioned: boolean | null;
  };
}

export interface OrganizationCreateInput {
  name: string;
  industry: string;
  timezone: string;
}

export interface OrganizationUpdateInput {
  name?: string;
  industry?: string;
  timezone?: string;
  address?: string;
  phone?: string;
  email?: string;
  is_active?: boolean;
  is_trial?: boolean;
}
