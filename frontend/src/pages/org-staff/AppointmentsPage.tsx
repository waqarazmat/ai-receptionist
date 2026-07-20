import { useMemo, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Globe, List, MessageCircle, Phone } from "lucide-react";
import { useAppointments } from "../../api/appointments";
import { DataTable, type DataTableColumn } from "../../components/shared/DataTable";
import { EmptyState } from "../../components/shared/EmptyState";
import { AppointmentStatusBadge } from "../../components/shared/StatusBadge";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Select } from "../../components/ui/Select";
import { Spinner } from "../../components/ui/Spinner";
import { AppointmentDetailModal } from "../../features/appointments/AppointmentDetailModal";
import { addDays, formatWeekRangeLabel, isSameDay, startOfWeek } from "../../features/appointments/date-utils";
import { WeekCalendar } from "../../features/appointments/WeekCalendar";
import { formatDateTime } from "../../lib/utils";
import type { Appointment, AppointmentStatus } from "../../types/appointment";
import type { Channel } from "../../types/conversation";

type ViewMode = "calendar" | "list";

const STATUS_OPTIONS: { value: AppointmentStatus | "all"; label: string }[] = [
  { value: "all", label: "All statuses" },
  { value: "confirmed", label: "Confirmed" },
  { value: "held", label: "Held" },
  { value: "cancelled", label: "Cancelled" },
];

const CHANNEL_ICON: Record<Channel, typeof Globe> = {
  webchat: Globe,
  whatsapp: MessageCircle,
  voice: Phone,
};

function toDateInputValue(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export default function AppointmentsPage() {
  const [view, setView] = useState<ViewMode>("calendar");
  const [statusFilter, setStatusFilter] = useState<AppointmentStatus | "all">("all");
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()));
  const today = useMemo(() => new Date(), []);
  const [listStartDate, setListStartDate] = useState(() => toDateInputValue(today));
  const [listEndDate, setListEndDate] = useState(() => toDateInputValue(addDays(today, 30)));
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const startDate = view === "calendar" ? weekStart.toISOString() : new Date(listStartDate).toISOString();
  const endDate =
    view === "calendar"
      ? addDays(weekStart, 7).toISOString()
      : addDays(new Date(listEndDate), 1).toISOString(); // inclusive of the selected end day

  const { data: appointments = [], isLoading } = useAppointments({
    start_date: startDate,
    end_date: endDate,
    status: statusFilter,
  });

  const todaysUpcoming = useMemo(
    () =>
      appointments.filter(
        (a) => a.status !== "cancelled" && isSameDay(new Date(a.start_time), today) && new Date(a.start_time) >= today,
      ),
    [appointments, today],
  );

  const columns: DataTableColumn<Appointment>[] = [
    { header: "Contact", accessor: (row) => row.contact_name },
    { header: "Service", accessor: (row) => row.service_name },
    {
      header: "Date & Time",
      accessor: (row) => (
        <span className={isSameDay(new Date(row.start_time), today) ? "font-medium text-indigo-700 dark:text-indigo-300" : undefined}>
          {formatDateTime(row.start_time)}
          {isSameDay(new Date(row.start_time), today) && (
            <span className="ml-2 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700 dark:text-indigo-300">
              TODAY
            </span>
          )}
        </span>
      ),
    },
    {
      header: "Duration",
      accessor: (row) =>
        `${Math.round((new Date(row.end_time).getTime() - new Date(row.start_time).getTime()) / 60000)} min`,
    },
    { header: "Status", accessor: (row) => <AppointmentStatusBadge status={row.status} /> },
    {
      header: "Channel",
      accessor: (row) => {
        const Icon = CHANNEL_ICON[row.channel];
        return (
          <span className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
            <Icon className="h-4 w-4" />
            {row.channel}
          </span>
        );
      },
    },
  ];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Appointments</h2>
          {todaysUpcoming.length > 0 && (
            <p className="mt-1 text-sm text-indigo-700 dark:text-indigo-300">
              {todaysUpcoming.length} more appointment{todaysUpcoming.length === 1 ? "" : "s"} today
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-slate-300 bg-white dark:bg-slate-900 p-0.5">
            <button
              type="button"
              onClick={() => setView("calendar")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${
                view === "calendar" ? "bg-indigo-600 text-white" : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              <CalendarDays className="h-4 w-4" />
              Calendar
            </button>
            <button
              type="button"
              onClick={() => setView("list")}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium ${
                view === "list" ? "bg-indigo-600 text-white" : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              }`}
            >
              <List className="h-4 w-4" />
              List
            </button>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        {view === "calendar" ? (
          <div className="flex items-center gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={() => setWeekStart(addDays(weekStart, -7))}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setWeekStart(startOfWeek(new Date()))}>
              Today
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => setWeekStart(addDays(weekStart, 7))}>
              <ChevronRight className="h-4 w-4" />
            </Button>
            <p className="ml-1 text-sm font-medium text-slate-700 dark:text-slate-200">{formatWeekRangeLabel(weekStart)}</p>
          </div>
        ) : (
          <>
            <Input
              label="From"
              type="date"
              value={listStartDate}
              onChange={(e) => setListStartDate(e.target.value)}
              className="w-40"
            />
            <Input
              label="To"
              type="date"
              value={listEndDate}
              onChange={(e) => setListEndDate(e.target.value)}
              className="w-40"
            />
          </>
        )}

        <Select
          label="Status"
          options={STATUS_OPTIONS}
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as AppointmentStatus | "all")}
          className="w-40"
        />
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        ) : appointments.length === 0 ? (
          <EmptyState
            icon={<CalendarDays className="h-10 w-10" />}
            title="No appointments"
            description="Nothing matches the current filters."
          />
        ) : view === "calendar" ? (
          <WeekCalendar weekStart={weekStart} appointments={appointments} onSelect={setSelectedId} />
        ) : (
          <DataTable
            columns={columns}
            data={appointments}
            keyExtractor={(row) => row.id}
            onRowClick={(row) => setSelectedId(row.id)}
          />
        )}
      </div>

      <AppointmentDetailModal appointmentId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
