import { Outlet, useLocation } from "react-router-dom";
import { useIsFetching } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { pageTransition } from "../../lib/motion";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { ToastContainer } from "../ui/Toast";
import { useAuthStore } from "../../stores/auth-store";
import { useSocket } from "../../hooks/useSocket";
import { useRealtime } from "../../hooks/useRealtime";
import { getPageTitle } from "../../lib/constants";

// Kept mounted for the whole org-staff session (not just while InboxPage
// happens to be open) so escalation/message alerts — the toast in
// useRealtime, the sidebar's escalation badge — fire regardless of which
// page staff are looking at.
function OrgStaffRealtimeConnection() {
  const role = useAuthStore((state) => state.user?.role);
  const accessToken = useAuthStore((state) => state.accessToken);
  const orgId = useAuthStore((state) => state.user?.org_id ?? null);
  const socket = useSocket(role === "org_staff" ? accessToken : null, orgId);
  useRealtime(socket);
  return null;
}

/** Thin indigo bar that sweeps across the very top whenever any TanStack Query
 * is in flight — a calm global "working…" signal. */
function GlobalFetchingBar() {
  const isFetching = useIsFetching();
  if (!isFetching) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[2000] h-0.5 overflow-hidden bg-indigo-100">
      <div className="animate-loading-bar h-full w-1/4 rounded-full bg-indigo-600" />
    </div>
  );
}

export function MainLayout() {
  const location = useLocation();
  // Re-key on the top-level route (e.g. "/org/inbox") so the page fades in on
  // real navigation — but NOT on sub-route changes like selecting an inbox
  // conversation (/org/inbox/:id), which would otherwise remount and lose the
  // split-pane state.
  const routeKey = location.pathname.split("/").slice(0, 3).join("/");

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <GlobalFetchingBar />
      <OrgStaffRealtimeConnection />
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header title={getPageTitle(location.pathname)} />
        <main className="flex-1 overflow-y-auto px-8 py-6">
          <motion.div
            key={routeKey}
            initial={pageTransition.initial}
            animate={pageTransition.animate}
            transition={pageTransition.transition}
            className="h-full"
          >
            <Outlet />
          </motion.div>
        </main>
      </div>
      <ToastContainer />
    </div>
  );
}
