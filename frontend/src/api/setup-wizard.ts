import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Organization } from "../types/organization";
import type {
  ApiKeysStepInput,
  BasicInfoStep,
  BookingConfigStep,
  ChannelConfigStep,
  KnowledgeBaseStep,
  SetupStateResponse,
  StaffAccessStep,
  SystemPromptsStep,
  VoiceConfigStepInput,
  WebsiteCrawlRequest,
  WebsiteCrawlResult,
  WhatsappConfigStepInput,
  WorkingHoursStep,
} from "../types/setup-wizard";

const setupWizardKey = (orgId: string) => ["setup-wizard", orgId] as const;

function useInvalidateAfterSave(orgId: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: setupWizardKey(orgId) }),
      // refetchType: "all" also refetches the org list query even while it has
      // no active observer (e.g. while the admin is still on the wizard page) —
      // otherwise it's just marked stale and shows old data until next mount.
      queryClient.invalidateQueries({ queryKey: ["organizations"], refetchType: "all" }),
      queryClient.invalidateQueries({ queryKey: ["organizations", orgId], refetchType: "all" }),
    ]);
}

export function useSetupState(orgId: string) {
  return useQuery({
    queryKey: setupWizardKey(orgId),
    queryFn: () =>
      apiClient.get<SetupStateResponse>(`/api/admin/organizations/${orgId}/setup`).then((r) => r.data),
    enabled: Boolean(orgId),
  });
}

export function useSaveBasicInfo(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: BasicInfoStep) =>
      apiClient
        .put<Organization>(`/api/admin/organizations/${orgId}/setup/basic-info`, data)
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useSaveWorkingHours(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: WorkingHoursStep) =>
      apiClient
        .put<Organization>(`/api/admin/organizations/${orgId}/setup/working-hours`, data)
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useSaveChannels(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: ChannelConfigStep) =>
      apiClient
        .put<Organization>(`/api/admin/organizations/${orgId}/setup/channels`, data)
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useSaveApiKey(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: ApiKeysStepInput) =>
      apiClient
        .post<{ provider: string; is_active: boolean }>(
          `/api/admin/organizations/${orgId}/setup/api-keys`,
          data,
        )
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useSaveWhatsappConfig(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: WhatsappConfigStepInput) =>
      apiClient
        .put<{ phone_number: string | null; phone_number_id: string | null }>(
          `/api/admin/organizations/${orgId}/setup/whatsapp-config`,
          data,
        )
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useSaveVoiceConfig(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: VoiceConfigStepInput) =>
      apiClient
        .put<{ retell_agent_id: string | null }>(`/api/admin/organizations/${orgId}/setup/voice-config`, data)
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useSaveKnowledgeBase(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: KnowledgeBaseStep) =>
      apiClient
        .put<Organization>(`/api/admin/organizations/${orgId}/setup/knowledge-base`, data)
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useCrawlWebsite(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: WebsiteCrawlRequest) =>
      apiClient
        .post<WebsiteCrawlResult>(`/api/admin/organizations/${orgId}/setup/knowledge-base/crawl`, data)
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useSaveBookingConfig(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: BookingConfigStep) =>
      apiClient
        .put<Organization>(`/api/admin/organizations/${orgId}/setup/booking`, data)
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useSaveSystemPrompts(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: SystemPromptsStep) =>
      apiClient
        .put<Organization>(`/api/admin/organizations/${orgId}/setup/system-prompts`, data)
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useSaveStaffAccess(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: (data: StaffAccessStep) =>
      apiClient
        .put<{ emails: string[] }>(`/api/admin/organizations/${orgId}/setup/staff`, data)
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}

export function useActivateOrg(orgId: string) {
  const invalidate = useInvalidateAfterSave(orgId);
  return useMutation({
    mutationFn: () =>
      apiClient
        .post<Organization>(`/api/admin/organizations/${orgId}/setup/activate`, {})
        .then((r) => r.data),
    onSuccess: invalidate,
  });
}
