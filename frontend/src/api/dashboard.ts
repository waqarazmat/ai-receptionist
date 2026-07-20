import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { AdminDashboard, OrgDashboard } from "../types/dashboard";

export function useAdminDashboard() {
  return useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: () => apiClient.get<AdminDashboard>("/api/admin/dashboard").then((r) => r.data),
  });
}

export function useOrgDashboard() {
  return useQuery({
    queryKey: ["org-dashboard"],
    queryFn: () => apiClient.get<OrgDashboard>("/api/org/dashboard").then((r) => r.data),
    refetchInterval: 30000,
  });
}
