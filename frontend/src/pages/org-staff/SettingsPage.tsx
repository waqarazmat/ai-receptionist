import { Globe, Info, MessageCircle, Phone } from "lucide-react";
import { useOrgSettings } from "../../api/settings";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";

const DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

const CHANNEL_META = [
  { key: "webchat" as const, label: "Web Chat", icon: Globe },
  { key: "whatsapp" as const, label: "WhatsApp", icon: MessageCircle },
  { key: "voice" as const, label: "Voice", icon: Phone },
];

export default function SettingsPage() {
  const { data: org, isLoading, isError } = useOrgSettings();

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (isError || !org) {
    return <p className="text-sm text-red-600 dark:text-red-400">Failed to load organization settings.</p>;
  }

  return (
    <div>
      <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Settings</h2>

      <div className="mt-2 flex items-start gap-2 rounded-lg border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <p>This is a read-only view. Contact your platform admin to make changes to any of these settings.</p>
      </div>

      <div className="mt-6 space-y-6">
        <Card title="Organization">
          <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">Name</dt>
              <dd className="mt-1 text-sm text-slate-900 dark:text-slate-100">{org.name}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">Industry</dt>
              <dd className="mt-1 text-sm text-slate-900 dark:text-slate-100">{org.industry}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">Timezone</dt>
              <dd className="mt-1 text-sm text-slate-900 dark:text-slate-100">{org.timezone}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">Address</dt>
              <dd className="mt-1 text-sm text-slate-900 dark:text-slate-100">{org.address ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">Phone</dt>
              <dd className="mt-1 text-sm text-slate-900 dark:text-slate-100">{org.phone ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-slate-400 dark:text-slate-500">Email</dt>
              <dd className="mt-1 text-sm text-slate-900 dark:text-slate-100">{org.email ?? "—"}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Working Hours">
          {DAY_ORDER.every((day) => !org.working_hours.hours[day]) ? (
            <p className="text-sm text-slate-500 dark:text-slate-400">No working hours configured.</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {DAY_ORDER.map((day) => {
                const hours = org.working_hours.hours[day];
                return (
                  <li key={day} className="flex items-center justify-between py-2 text-sm">
                    <span className="capitalize text-slate-700 dark:text-slate-200">{day}</span>
                    <span className={hours ? "text-slate-900 dark:text-slate-100" : "text-slate-400 dark:text-slate-500"}>
                      {hours ? `${hours.open} – ${hours.close}` : "Closed"}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
          {org.working_hours.holidays.length > 0 && (
            <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
              Holidays: {org.working_hours.holidays.join(", ")}
            </p>
          )}
        </Card>

        <Card title="Channels">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {CHANNEL_META.map(({ key, label, icon: Icon }) => {
              const enabled = org.channels_enabled[key];
              return (
                <div key={key} className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-800 p-3">
                  <span className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
                    <Icon className="h-4 w-4 text-slate-400 dark:text-slate-500" />
                    {label}
                  </span>
                  <Badge variant={enabled ? "success" : "neutral"}>{enabled ? "Enabled" : "Disabled"}</Badge>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </div>
  );
}
