import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { User } from "../types/user";

/** Org-staff self-service teammate invite. Backend forces same org + role=org_staff. */
export function useInviteTeammate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { email: string }) =>
      apiClient.post<User>("/api/org/team/invite", data).then((r) => r.data),
    onSuccess: () => {
      // If the org-staff panel ever grows a "teammates" list, this is what
      // invalidates it. For now it's a no-op on any current query key.
      queryClient.invalidateQueries({ queryKey: ["team"] });
    },
  });
}
