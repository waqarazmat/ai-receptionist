import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Appointment, AppointmentStatus } from "../types/appointment";

export interface AppointmentFilters {
  start_date?: string;
  end_date?: string;
  status?: AppointmentStatus | "all";
}

const APPOINTMENTS_BASE_KEY = ["appointments"] as const;
const appointmentsKey = (filters?: AppointmentFilters) =>
  [...APPOINTMENTS_BASE_KEY, filters?.start_date ?? "", filters?.end_date ?? "", filters?.status ?? "all"] as const;
const appointmentKey = (id: string) => [...APPOINTMENTS_BASE_KEY, id] as const;

export function useAppointments(filters?: AppointmentFilters) {
  return useQuery({
    queryKey: appointmentsKey(filters),
    queryFn: () =>
      apiClient
        .get<{ appointments: Appointment[] }>("/api/org/appointments", {
          params: {
            start_date: filters?.start_date,
            end_date: filters?.end_date,
            status: filters?.status && filters.status !== "all" ? filters.status : undefined,
          },
        })
        .then((r) => r.data.appointments),
  });
}

export function useAppointment(id: string | null) {
  return useQuery({
    queryKey: appointmentKey(id ?? ""),
    queryFn: () => apiClient.get<Appointment>(`/api/org/appointments/${id}`).then((r) => r.data),
    enabled: Boolean(id),
  });
}

export function useCancelAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiClient.put<Appointment>(`/api/org/appointments/${id}/cancel`).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: APPOINTMENTS_BASE_KEY }),
  });
}
