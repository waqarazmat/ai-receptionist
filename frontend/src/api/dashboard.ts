import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { AdminDashboard, OrgDashboard } from "../types/dashboard";
import type { AnalyticsResponse } from "../types/analytics";

export function useAdminDashboard() {
  return useQuery({
    queryKey: ["admin-dashboard"],
    queryFn: () => apiClient.get<AdminDashboard>("/api/admin/dashboard").then((r) => r.data),
  });
}

export function useAdminAnalytics(days: number = 30) {
  return useQuery({
    queryKey: ["admin-analytics", days],
    queryFn: () =>
      apiClient
        .get<AnalyticsResponse>("/api/admin/dashboard/analytics", { params: { days } })
        .then((r) => r.data),
    // Rollups don't change every second — cache for a minute to keep the
    // dashboard snappy on tab-switches without hitting the backend for
    // every render.
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useOrgDashboard() {
  return useQuery({
    queryKey: ["org-dashboard"],
    queryFn: () => apiClient.get<OrgDashboard>("/api/org/dashboard").then((r) => r.data),
    refetchInterval: 30000,
  });
}
