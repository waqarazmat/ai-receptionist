import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { BillingAnalyticsResponse, OrgBillingSnapshot } from "../types/billing";

/** Super-admin: platform-wide, or scoped to one org when `orgId` is set. */
export function useAdminBillingAnalytics(days: number = 30, orgId: string | null = null) {
  return useQuery({
    queryKey: ["admin-billing", days, orgId ?? "all"],
    queryFn: () => {
      const params: Record<string, string | number> = { days };
      if (orgId) params.org_id = orgId;
      return apiClient
        .get<BillingAnalyticsResponse>("/api/admin/billing/analytics", { params })
        .then((r) => r.data);
    },
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });
}

/** Org-staff: current-month snapshot for their own org. */
export function useOrgBilling() {
  return useQuery({
    queryKey: ["org-billing"],
    queryFn: () =>
      apiClient.get<OrgBillingSnapshot>("/api/org/billing/current").then((r) => r.data),
    staleTime: 60_000,
  });
}
