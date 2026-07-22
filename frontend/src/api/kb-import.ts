import { useMutation } from "@tanstack/react-query";
import { apiClient } from "./client";

export interface BulkImportInput {
  format: "csv" | "markdown" | "text";
  content: string;
  knowledge_base_id?: string | null;
}

export interface BulkImportResult {
  knowledge_base_id: string;
  knowledge_base_name: string;
  chunks_created: number;
  errors: string[];
}

export function useBulkImportKnowledge(orgId: string) {
  return useMutation({
    mutationFn: (data: BulkImportInput) =>
      apiClient
        .post<BulkImportResult>(`/api/admin/organizations/${orgId}/knowledge-base/import`, data)
        .then((r) => r.data),
  });
}
