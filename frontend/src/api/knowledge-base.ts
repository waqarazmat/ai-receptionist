import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { ChunkInput, KnowledgeChunk, OrgKnowledgeBase } from "../types/knowledge-base";

const KNOWLEDGE_BASE_KEY = ["org-knowledge-base"] as const;

export function useOrgKnowledgeBase() {
  return useQuery({
    queryKey: KNOWLEDGE_BASE_KEY,
    queryFn: () => apiClient.get<OrgKnowledgeBase>("/api/org/knowledge-base").then((r) => r.data),
  });
}

export function useAddChunk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChunkInput) =>
      apiClient.post<KnowledgeChunk>("/api/org/knowledge-base/chunks", data).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KNOWLEDGE_BASE_KEY }),
  });
}

export function useUpdateChunk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ChunkInput }) =>
      apiClient.put<KnowledgeChunk>(`/api/org/knowledge-base/chunks/${id}`, data).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KNOWLEDGE_BASE_KEY }),
  });
}

export function useDeleteChunk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiClient.delete(`/api/org/knowledge-base/chunks/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KNOWLEDGE_BASE_KEY }),
  });
}
