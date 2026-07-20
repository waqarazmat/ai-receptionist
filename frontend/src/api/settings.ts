import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { OrgProfile } from "../types/organization";

export function useOrgSettings() {
  return useQuery({
    queryKey: ["org-settings"],
    queryFn: () => apiClient.get<OrgProfile>("/api/org/settings").then((r) => r.data),
  });
}
