export type EscalationPriority = "low" | "medium" | "high";
export type EscalationStatus = "pending" | "picked_up" | "resolved";

export interface Escalation {
  id: string;
  org_id: string;
  conversation_id: string;
  contact_name: string;
  reason: string;
  priority: EscalationPriority;
  status: EscalationStatus;
  assigned_to: string | null;
  created_at: string;
  resolved_at: string | null;
}
