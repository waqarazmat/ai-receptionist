import { createBrowserRouter, Navigate } from "react-router-dom";
import LoginPage from "./pages/auth/LoginPage";
import { MainLayout } from "./components/layout/MainLayout";
import { ProtectedRoute } from "./components/layout/ProtectedRoute";

import SuperAdminDashboardPage from "./pages/super-admin/DashboardPage";
import OrganizationsListPage from "./pages/super-admin/OrganizationsListPage";
import OrganizationDetailPage from "./pages/super-admin/OrganizationDetailPage";
import SetupWizardPage from "./pages/super-admin/SetupWizardPage";
import TestCenterPage from "./pages/super-admin/TestCenterPage";
import UsersManagementPage from "./pages/super-admin/UsersManagementPage";
import AuditLogsPage from "./pages/super-admin/AuditLogsPage";
import BillingAnalyticsPage from "./pages/super-admin/BillingAnalyticsPage";

import OrgDashboardPage from "./pages/org-staff/DashboardPage";
import InboxPage from "./pages/org-staff/InboxPage";
import AppointmentsPage from "./pages/org-staff/AppointmentsPage";
import KnowledgeBasePage from "./pages/org-staff/KnowledgeBasePage";
import EscalationsPage from "./pages/org-staff/EscalationsPage";
import ContactsPage from "./pages/org-staff/ContactsPage";
import SettingsPage from "./pages/org-staff/SettingsPage";
import OrgBillingPage from "./pages/org-staff/BillingPage";

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/login" replace /> },
  { path: "/login", element: <LoginPage /> },
  {
    path: "/admin",
    element: (
      <ProtectedRoute requiredRole="super_admin">
        <MainLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="dashboard" replace /> },
      { path: "dashboard", element: <SuperAdminDashboardPage /> },
      { path: "organizations", element: <OrganizationsListPage /> },
      { path: "organizations/:orgId", element: <OrganizationDetailPage /> },
      { path: "organizations/:orgId/setup", element: <SetupWizardPage /> },
      { path: "organizations/:orgId/test", element: <TestCenterPage /> },
      { path: "users", element: <UsersManagementPage /> },
      { path: "audit-logs", element: <AuditLogsPage /> },
      { path: "billing", element: <BillingAnalyticsPage /> },
    ],
  },
  {
    path: "/org",
    element: (
      <ProtectedRoute requiredRole="org_staff">
        <MainLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="dashboard" replace /> },
      { path: "dashboard", element: <OrgDashboardPage /> },
      { path: "inbox", element: <InboxPage /> },
      { path: "appointments", element: <AppointmentsPage /> },
      { path: "knowledge-base", element: <KnowledgeBasePage /> },
      { path: "escalations", element: <EscalationsPage /> },
      { path: "contacts", element: <ContactsPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "billing", element: <OrgBillingPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/login" replace /> },
]);
