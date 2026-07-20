import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { AuditLogListResponse } from "../types/audit-log";

export interface AuditLogFilters {
  action?: string;
  start_date?: string;
  end_date?: string;
  page: number;
  page_size: number;
}

export function useAuditLogs(filters: AuditLogFilters) {
  return useQuery({
    queryKey: ["audit-logs", filters],
    queryFn: () =>
      apiClient
        .get<AuditLogListResponse>("/api/admin/audit-logs", {
          params: {
            action: filters.action || undefined,
            start_date: filters.start_date || undefined,
            end_date: filters.end_date || undefined,
            page: filters.page,
            page_size: filters.page_size,
          },
        })
        .then((r) => r.data),
  });
}
