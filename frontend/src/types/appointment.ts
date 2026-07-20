import type { Channel } from "./conversation";

export type AppointmentStatus = "held" | "confirmed" | "cancelled";

export interface Appointment {
  id: string;
  org_id: string;
  contact_id: string;
  contact_name: string;
  channel: Channel;
  conversation_id: string | null;
  service_name: string;
  start_time: string;
  end_time: string;
  status: AppointmentStatus;
  google_event_id: string | null;
  notes: string | null;
}
