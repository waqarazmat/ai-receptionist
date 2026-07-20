import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "../../stores/auth-store";
import type { UserRole } from "../../types/auth";

export interface ProtectedRouteProps {
  requiredRole: UserRole;
  children: ReactNode;
}

const DASHBOARD_BY_ROLE: Record<UserRole, string> = {
  super_admin: "/admin/dashboard",
  org_staff: "/org/dashboard",
};

export function ProtectedRoute({ requiredRole, children }: ProtectedRouteProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const role = useAuthStore((state) => state.user?.role);

  if (!isAuthenticated || !role) {
    return <Navigate to="/login" replace />;
  }

  if (role !== requiredRole) {
    return <Navigate to={DASHBOARD_BY_ROLE[role]} replace />;
  }

  return <>{children}</>;
}
