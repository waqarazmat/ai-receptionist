import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Escalation } from "../types/escalation";

const ESCALATIONS_KEY = ["escalations"] as const;

export function useEscalations(enabled = true) {
  return useQuery({
    queryKey: ESCALATIONS_KEY,
    queryFn: () =>
      apiClient.get<{ escalations: Escalation[] }>("/api/org/escalations").then((r) => r.data.escalations),
    refetchInterval: 30000,
    enabled,
  });
}

export function usePickUpEscalation(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.post<Escalation>(`/api/org/escalations/${id}/pickup`).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ESCALATIONS_KEY }),
  });
}
