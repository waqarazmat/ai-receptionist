import { useCancelAppointment, useAppointment } from "../../api/appointments";
import { AppointmentStatusBadge } from "../../components/shared/StatusBadge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Spinner } from "../../components/ui/Spinner";
import { formatDateTime } from "../../lib/utils";
import type { Channel } from "../../types/conversation";

const CHANNEL_LABEL: Record<Channel, string> = {
  webchat: "Web Chat",
  whatsapp: "WhatsApp",
  voice: "Voice",
};

export interface AppointmentDetailModalProps {
  appointmentId: string | null;
  onClose: () => void;
}

export function AppointmentDetailModal({ appointmentId, onClose }: AppointmentDetailModalProps) {
  const { data: appointment, isLoading } = useAppointment(appointmentId);
  const cancelAppointment = useCancelAppointment();

  const durationMinutes = appointment
    ? Math.round((new Date(appointment.end_time).getTime() - new Date(appointment.start_time).getTime()) / 60000)
    : 0;

  return (
    <Modal isOpen={Boolean(appointmentId)} onClose={onClose} title="Appointment Details">
      {isLoading || !appointment ? (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-base font-semibold text-slate-900 dark:text-slate-100">{appointment.service_name}</p>
            <AppointmentStatusBadge status={appointment.status} />
          </div>

          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Contact</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{appointment.contact_name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Channel</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{CHANNEL_LABEL[appointment.channel]}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Date &amp; time</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{formatDateTime(appointment.start_time)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Duration</dt>
              <dd className="font-medium text-slate-900 dark:text-slate-100">{durationMinutes} min</dd>
            </div>
            {appointment.notes && (
              <div>
                <dt className="text-slate-500 dark:text-slate-400">Notes</dt>
                <dd className="mt-1 text-slate-700 dark:text-slate-200">{appointment.notes}</dd>
              </div>
            )}
          </dl>

          <div className="flex justify-end gap-2 border-t border-slate-200 dark:border-slate-800 pt-4">
            <Button type="button" variant="secondary" onClick={onClose}>
              Close
            </Button>
            {appointment.status !== "cancelled" && (
              <Button
                type="button"
                variant="danger"
                isLoading={cancelAppointment.isPending}
                onClick={() => cancelAppointment.mutate(appointment.id)}
              >
                Cancel Appointment
              </Button>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}
