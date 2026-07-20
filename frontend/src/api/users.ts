import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";
import type {
  User,
  UserInviteInput,
  UserListFilters,
  UserUpdateInput,
} from "../types/user";

const USERS_KEY = ["users"] as const;
const usersListKey = (filters: UserListFilters) => [...USERS_KEY, filters] as const;
const userKey = (userId: string) => [...USERS_KEY, userId] as const;

function toParams(filters: UserListFilters) {
  const params: Record<string, string> = {};
  if (filters.q) params.q = filters.q;
  if (filters.org_id) params.org_id = filters.org_id;
  if (filters.role) params.role = filters.role;
  if (filters.is_active !== undefined) params.is_active = String(filters.is_active);
  return params;
}

export function useUsers(filters: UserListFilters = {}) {
  return useQuery({
    queryKey: usersListKey(filters),
    queryFn: () =>
      apiClient
        .get<{ users: User[] }>("/api/admin/users", { params: toParams(filters) })
        .then((r) => r.data.users),
  });
}

export function useUser(userId: string) {
  return useQuery({
    queryKey: userKey(userId),
    queryFn: () => apiClient.get<User>(`/api/admin/users/${userId}`).then((r) => r.data),
    enabled: Boolean(userId),
  });
}

export function useInviteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UserInviteInput) =>
      apiClient.post<User>("/api/admin/users", data).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: USERS_KEY }),
  });
}

export function useUpdateUser(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UserUpdateInput) =>
      apiClient.patch<User>(`/api/admin/users/${userId}`, data).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: USERS_KEY });
      queryClient.invalidateQueries({ queryKey: userKey(userId) });
    },
  });
}
