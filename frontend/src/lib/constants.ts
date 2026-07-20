export const PAGE_TITLES: Record<string, string> = {
  "/admin/dashboard": "Super Admin Dashboard",
  "/admin/organizations": "Organizations",
  "/admin/users": "Users",
  "/admin/audit-logs": "Audit Logs",
  "/org/dashboard": "Org Staff Dashboard",
  "/org/inbox": "Inbox",
  "/org/appointments": "Appointments",
  "/org/knowledge-base": "Knowledge Base",
  "/org/escalations": "Escalations",
  "/org/contacts": "Contacts",
  "/org/settings": "Settings",
};

export function getPageTitle(pathname: string): string {
  if (PAGE_TITLES[pathname]) {
    return PAGE_TITLES[pathname];
  }
  if (/^\/admin\/organizations\/[^/]+\/setup$/.test(pathname)) {
    return "Organization Setup";
  }
  if (/^\/admin\/organizations\/[^/]+\/test$/.test(pathname)) {
    return "Test Center";
  }
  if (/^\/admin\/organizations\/[^/]+$/.test(pathname)) {
    return "Organization Details";
  }
  const lastSegment = pathname.split("/").filter(Boolean).pop() ?? "Dashboard";
  return lastSegment
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export const INDUSTRIES = [
  "Dental",
  "Medical",
  "Salon & Spa",
  "Legal",
  "Real Estate",
  "Home Services",
  "Fitness",
  "Veterinary",
  "Retail",
  "Other",
];

export const TIMEZONES: string[] =
  typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : ["UTC"];
