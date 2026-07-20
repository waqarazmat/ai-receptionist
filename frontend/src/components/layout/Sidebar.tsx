import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Building2,
  Users,
  ScrollText,
  Inbox,
  CalendarClock,
  BookOpen,
  AlertTriangle,
  Contact,
  Settings,
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";
import { useEscalations } from "../../api/escalations";
import { useAuthStore } from "../../stores/auth-store";
import { useSidebarStore } from "../../stores/sidebar-store";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

const superAdminNav: NavItem[] = [
  { to: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/admin/organizations", label: "Organizations", icon: Building2 },
  { to: "/admin/users", label: "Users", icon: Users },
  { to: "/admin/audit-logs", label: "Audit Logs", icon: ScrollText },
];

const orgStaffNav: NavItem[] = [
  { to: "/org/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/org/inbox", label: "Inbox", icon: Inbox },
  { to: "/org/appointments", label: "Appointments", icon: CalendarClock },
  { to: "/org/knowledge-base", label: "Knowledge Base", icon: BookOpen },
  { to: "/org/escalations", label: "Escalations", icon: AlertTriangle },
  { to: "/org/contacts", label: "Contacts", icon: Contact },
  { to: "/org/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const role = useAuthStore((state) => state.user?.role);
  const isCollapsed = useSidebarStore((state) => state.isCollapsed);
  const toggle = useSidebarStore((state) => state.toggle);

  const navItems = role === "super_admin" ? superAdminNav : orgStaffNav;

  // Only relevant (and only queried) for org staff — this is what the
  // realtime escalation_created/escalation_picked_up handlers in
  // useRealtime keep fresh via query invalidation, so the badge updates
  // live without polling faster than the query's own refetchInterval.
  const { data: escalations } = useEscalations(role === "org_staff");
  const openEscalationCount = escalations?.length ?? 0;

  return (
    <aside
      className={`flex h-screen flex-col bg-[#0F172A] text-slate-300 transition-all duration-200 ${
        isCollapsed ? "w-16" : "w-64"
      }`}
    >
      <div className="flex h-16 items-center gap-2.5 border-b border-white/10 px-3">
        {/* App monogram */}
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold tracking-tight text-white shadow-sm">
          AR
        </div>
        {!isCollapsed && (
          <span className="flex-1 truncate text-sm font-semibold tracking-tight text-white">AI Receptionist</span>
        )}
        <button
          type="button"
          onClick={toggle}
          className="rounded-lg p-1.5 text-slate-400 transition-colors duration-150 hover:bg-white/5 hover:text-white"
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {navItems.map(({ to, label, icon: Icon }) => {
          const badgeCount = to === "/org/escalations" ? openEscalationCount : 0;
          return (
            <NavLink
              key={to}
              to={to}
              title={isCollapsed ? label : undefined}
              className={({ isActive }) =>
                // Hover background slides in from the left via a ::before that
                // scales on the X axis (origin-left), rather than appearing
                // instantly.
                `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-150 before:absolute before:inset-0 before:-z-10 before:origin-left before:scale-x-0 before:rounded-lg before:bg-white/5 before:transition-transform before:duration-200 hover:text-white hover:before:scale-x-100 ${
                  isActive ? "bg-white/5 text-white" : "text-slate-400"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {/* 3px active left-border indicator */}
                  <span
                    className={`absolute inset-y-1 left-0 w-[3px] rounded-r-full bg-indigo-500 transition-all duration-150 ${
                      isActive ? "opacity-100" : "opacity-0"
                    }`}
                  />
                  <span className="relative shrink-0">
                    <Icon className="h-5 w-5" />
                    {isCollapsed && badgeCount > 0 && (
                      <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-rose-500" />
                    )}
                  </span>
                  {!isCollapsed && (
                    <span className="flex flex-1 items-center justify-between">
                      {label}
                      {badgeCount > 0 && (
                        <span className="ml-2 rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white">
                          {badgeCount}
                        </span>
                      )}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Separator + footer region */}
      <div className="border-t border-white/10 px-3 py-3">
        {!isCollapsed ? (
          <p className="px-1 text-[11px] font-medium uppercase tracking-wider text-slate-500">
            {role === "super_admin" ? "Super Admin" : "Staff Workspace"}
          </p>
        ) : (
          <div className="mx-auto h-1.5 w-1.5 rounded-full bg-slate-600" />
        )}
      </div>
    </aside>
  );
}
