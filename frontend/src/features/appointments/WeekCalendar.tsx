import { Globe, MessageCircle, Phone } from "lucide-react";
import type { Appointment, AppointmentStatus } from "../../types/appointment";
import type { Channel } from "../../types/conversation";
import { addDays, isSameDay } from "./date-utils";

const CALENDAR_START_HOUR = 7;
const CALENDAR_END_HOUR = 20;
const HOUR_HEIGHT_PX = 56;
const TOTAL_HOURS = CALENDAR_END_HOUR - CALENDAR_START_HOUR;

const CHANNEL_ICON: Record<Channel, typeof Globe> = {
  webchat: Globe,
  whatsapp: MessageCircle,
  voice: Phone,
};

const STATUS_STYLE: Record<AppointmentStatus, string> = {
  confirmed: "bg-indigo-100 border-indigo-400 text-indigo-900 dark:text-indigo-200",
  held: "bg-amber-100 border-amber-400 text-amber-900",
  cancelled: "bg-slate-100 dark:bg-slate-800 border-slate-300 text-slate-500 dark:text-slate-400 line-through",
};

function minutesFromCalendarStart(iso: string): number {
  const d = new Date(iso);
  return (d.getHours() - CALENDAR_START_HOUR) * 60 + d.getMinutes();
}

function formatHourLabel(hour: number): string {
  const displayHour = hour % 12 === 0 ? 12 : hour % 12;
  return `${displayHour}${hour < 12 ? "am" : "pm"}`;
}

export interface WeekCalendarProps {
  weekStart: Date;
  appointments: Appointment[];
  onSelect: (id: string) => void;
}

export function WeekCalendar({ weekStart, appointments, onSelect }: WeekCalendarProps) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i));
  const today = new Date();
  const hourMarks = Array.from({ length: TOTAL_HOURS }, (_, i) => CALENDAR_START_HOUR + i);

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
      <div className="grid min-w-[840px] grid-cols-[64px_repeat(7,1fr)]">
        <div className="border-b border-r border-slate-200 dark:border-slate-800" />
        {days.map((day) => (
          <div
            key={day.toISOString()}
            className={`border-b border-r border-slate-200 dark:border-slate-800 py-2 text-center last:border-r-0 ${
              isSameDay(day, today) ? "bg-indigo-50 dark:bg-indigo-500/15" : ""
            }`}
          >
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
              {day.toLocaleDateString(undefined, { weekday: "short" })}
            </p>
            <p className={`text-sm font-semibold ${isSameDay(day, today) ? "text-indigo-600" : "text-slate-900 dark:text-slate-100"}`}>
              {day.getDate()}
            </p>
          </div>
        ))}

        <div className="relative border-r border-slate-200 dark:border-slate-800" style={{ height: TOTAL_HOURS * HOUR_HEIGHT_PX }}>
          {hourMarks.map((hour) => (
            <div
              key={hour}
              className="absolute left-0 right-1 text-right text-[10px] text-slate-400 dark:text-slate-500"
              style={{ top: (hour - CALENDAR_START_HOUR) * HOUR_HEIGHT_PX - 6 }}
            >
              {formatHourLabel(hour)}
            </div>
          ))}
        </div>

        {days.map((day) => {
          const dayAppointments = appointments.filter((a) => isSameDay(new Date(a.start_time), day));
          return (
            <div
              key={day.toISOString()}
              className={`relative border-r border-slate-200 dark:border-slate-800 last:border-r-0 ${
                isSameDay(day, today) ? "bg-indigo-50/40" : ""
              }`}
              style={{ height: TOTAL_HOURS * HOUR_HEIGHT_PX }}
            >
              {hourMarks.map((hour) => (
                <div
                  key={hour}
                  className="absolute left-0 right-0 border-t border-slate-100 dark:border-slate-800"
                  style={{ top: (hour - CALENDAR_START_HOUR) * HOUR_HEIGHT_PX }}
                />
              ))}
              {dayAppointments.map((appointment) => {
                const top = Math.max(0, (minutesFromCalendarStart(appointment.start_time) / 60) * HOUR_HEIGHT_PX);
                const durationMinutes =
                  (new Date(appointment.end_time).getTime() - new Date(appointment.start_time).getTime()) / 60000;
                const height = Math.max(20, (durationMinutes / 60) * HOUR_HEIGHT_PX);
                const Icon = CHANNEL_ICON[appointment.channel];
                return (
                  <button
                    key={appointment.id}
                    type="button"
                    onClick={() => onSelect(appointment.id)}
                    className={`absolute left-1 right-1 overflow-hidden rounded-md border px-1.5 py-1 text-left text-[11px] leading-tight shadow-sm hover:brightness-95 ${STATUS_STYLE[appointment.status]}`}
                    style={{ top, height }}
                  >
                    <span className="flex items-center gap-1 font-medium">
                      <Icon className="h-3 w-3 shrink-0" />
                      {new Date(appointment.start_time).toLocaleTimeString(undefined, {
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </span>
                    <span className="block truncate">{appointment.service_name}</span>
                    <span className="block truncate opacity-80">{appointment.contact_name}</span>
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
