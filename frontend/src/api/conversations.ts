import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Conversation, ConversationStatus } from "../types/conversation";
import type { Message } from "../types/message";

export interface ConversationFilters {
  status?: ConversationStatus | "all";
}

const conversationsKey = (filters?: ConversationFilters) =>
  ["conversations", filters?.status ?? "all"] as const;
const conversationKey = (id: string) => ["conversations", id] as const;
const messagesKey = (id: string) => ["conversations", id, "messages"] as const;

export function useConversations(filters?: ConversationFilters) {
  return useQuery({
    queryKey: conversationsKey(filters),
    queryFn: () =>
      apiClient
        .get<{ conversations: Conversation[] }>("/api/org/conversations", {
          params: filters?.status && filters.status !== "all" ? { status: filters.status } : undefined,
        })
        .then((r) => r.data.conversations),
    refetchInterval: 30000,
  });
}

export function useConversation(id: string | null) {
  return useQuery({
    queryKey: conversationKey(id ?? ""),
    queryFn: () => apiClient.get<Conversation>(`/api/org/conversations/${id}`).then((r) => r.data),
    enabled: Boolean(id),
  });
}

export function useConversationMessages(id: string | null) {
  return useQuery({
    queryKey: messagesKey(id ?? ""),
    queryFn: () =>
      apiClient
        .get<{ messages: Message[] }>(`/api/org/conversations/${id}/messages`)
        .then((r) => r.data.messages),
    enabled: Boolean(id),
  });
}

export function useSendStaffMessage(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) =>
      apiClient
        .post<Message>(`/api/org/conversations/${conversationId}/messages`, { content })
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: messagesKey(conversationId) });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}

export function useTakeOverConversation(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<Conversation>(`/api/org/conversations/${conversationId}/takeover`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: conversationKey(conversationId) });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}

export function useReleaseConversation(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<Conversation>(`/api/org/conversations/${conversationId}/release`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: conversationKey(conversationId) });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}

export function useResolveConversation(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient.post<Conversation>(`/api/org/conversations/${conversationId}/resolve`).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: conversationKey(conversationId) });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
