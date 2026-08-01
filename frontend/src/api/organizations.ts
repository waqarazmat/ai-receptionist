import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  OrgChannelStatus,
  Organization,
  OrganizationCreateInput,
  OrganizationUpdateInput,
} from "../types/organization";

const ORGANIZATIONS_KEY = ["organizations"] as const;
const organizationKey = (orgId: string) => ["organizations", orgId] as const;
const orgChannelStatusKey = (orgId: string) => ["organizations", orgId, "channels"] as const;

export function useOrganizations() {
  return useQuery({
    queryKey: ORGANIZATIONS_KEY,
    queryFn: () =>
      apiClient
        .get<{ organizations: Organization[] }>("/api/admin/organizations")
        .then((r) => r.data.organizations),
  });
}

export function useOrganization(orgId: string) {
  return useQuery({
    queryKey: organizationKey(orgId),
    queryFn: () => apiClient.get<Organization>(`/api/admin/organizations/${orgId}`).then((r) => r.data),
    enabled: Boolean(orgId),
  });
}

export function useOrgChannelStatus(orgId: string) {
  return useQuery({
    queryKey: orgChannelStatusKey(orgId),
    queryFn: () =>
      apiClient.get<OrgChannelStatus>(`/api/admin/organizations/${orgId}/channels`).then((r) => r.data),
    enabled: Boolean(orgId),
  });
}

export interface VoiceProvisionResult {
  retell_agent_id: string | null;
  provisioned: boolean;
  llm_websocket_url?: string;
  webhook_url?: string;
  warning?: string;
}

export function useProvisionVoiceAgent(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient
        .post<VoiceProvisionResult>(`/api/admin/organizations/${orgId}/voice/provision`, {})
        .then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orgChannelStatusKey(orgId) }),
  });
}

export function useCreateVoiceAgent(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiClient
        .post<VoiceProvisionResult>(`/api/admin/organizations/${orgId}/voice/create-agent`, {})
        .then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: orgChannelStatusKey(orgId) }),
  });
}

export interface WebCallToken {
  access_token: string;
  call_id: string;
}

export function useCreateWebCall(orgId: string) {
  return useMutation({
    mutationFn: () =>
      apiClient
        .post<WebCallToken>(`/api/admin/organizations/${orgId}/voice/web-call`, {})
        .then((r) => r.data),
  });
}

export function useCreateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: OrganizationCreateInput) =>
      apiClient.post<Organization>("/api/admin/organizations", data).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ORGANIZATIONS_KEY }),
  });
}

export function useUpdateOrganization(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: OrganizationUpdateInput) =>
      apiClient.put<Organization>(`/api/admin/organizations/${orgId}`, data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ORGANIZATIONS_KEY });
      queryClient.invalidateQueries({ queryKey: organizationKey(orgId) });
    },
  });
}

export function useDeleteOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orgId: string) => apiClient.delete<Organization>(`/api/admin/organizations/${orgId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ORGANIZATIONS_KEY }),
  });
}
