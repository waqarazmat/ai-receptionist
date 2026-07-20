export type UserRole = "super_admin" | "org_staff";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  org_id: string | null;
  org_name: string | null;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserInviteInput {
  email: string;
  org_id: string;
}

export interface UserUpdateInput {
  is_active?: boolean;
  org_id?: string;
}

export interface UserListFilters {
  q?: string;
  org_id?: string;
  role?: UserRole;
  is_active?: boolean;
}
