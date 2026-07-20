import { Badge } from "../ui/Badge";
import type { AppointmentStatus } from "../../types/appointment";
import type { ConversationStatus } from "../../types/conversation";
import type { EscalationPriority } from "../../types/escalation";

export type SetupStatus = "complete" | "in_progress" | "not_started";

const SETUP_STATUS_CONFIG: Record<SetupStatus, { label: string; variant: "success" | "warning" | "neutral" }> = {
  complete: { label: "Complete", variant: "success" },
  in_progress: { label: "In Progress", variant: "warning" },
  not_started: { label: "Not Started", variant: "neutral" },
};

export interface StatusBadgeProps {
  status: SetupStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const { label, variant } = SETUP_STATUS_CONFIG[status];
  return <Badge variant={variant}>{label}</Badge>;
}

const CONVERSATION_STATUS_CONFIG: Record<ConversationStatus, { label: string; variant: "success" | "danger" | "neutral" }> = {
  active: { label: "Active", variant: "success" },
  escalated: { label: "Escalated", variant: "danger" },
  resolved: { label: "Resolved", variant: "neutral" },
};

export function ConversationStatusBadge({ status }: { status: ConversationStatus }) {
  const { label, variant } = CONVERSATION_STATUS_CONFIG[status];
  return <Badge variant={variant}>{label}</Badge>;
}

const ESCALATION_PRIORITY_CONFIG: Record<EscalationPriority, { label: string; variant: "danger" | "warning" | "info" }> = {
  high: { label: "High", variant: "danger" },
  medium: { label: "Medium", variant: "warning" },
  low: { label: "Low", variant: "info" },
};

export function EscalationPriorityBadge({ priority }: { priority: EscalationPriority }) {
  const { label, variant } = ESCALATION_PRIORITY_CONFIG[priority];
  return <Badge variant={variant}>{label}</Badge>;
}

const APPOINTMENT_STATUS_CONFIG: Record<AppointmentStatus, { label: string; variant: "success" | "warning" | "neutral" }> = {
  confirmed: { label: "Confirmed", variant: "success" },
  held: { label: "Held", variant: "warning" },
  cancelled: { label: "Cancelled", variant: "neutral" },
};

export function AppointmentStatusBadge({ status }: { status: AppointmentStatus }) {
  const { label, variant } = APPOINTMENT_STATUS_CONFIG[status];
  return <Badge variant={variant}>{label}</Badge>;
}
