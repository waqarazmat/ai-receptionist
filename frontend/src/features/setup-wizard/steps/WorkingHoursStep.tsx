import { useState, type FormEvent } from "react";
import { Plus, X } from "lucide-react";
import { useSaveWorkingHours } from "../../../api/setup-wizard";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Switch } from "../../../components/ui/Switch";
import { StepCard } from "../StepCard";
import { StepFooter } from "../StepFooter";
import type { StepComponentProps } from "../types";

const DAYS: { key: string; label: string }[] = [
  { key: "monday", label: "Monday" },
  { key: "tuesday", label: "Tuesday" },
  { key: "wednesday", label: "Wednesday" },
  { key: "thursday", label: "Thursday" },
  { key: "friday", label: "Friday" },
  { key: "saturday", label: "Saturday" },
  { key: "sunday", label: "Sunday" },
];

interface DayState {
  open: boolean;
  openTime: string;
  closeTime: string;
}

function buildInitialDays(hours: Record<string, { open: string; close: string }> | undefined) {
  const initial: Record<string, DayState> = {};
  for (const { key } of DAYS) {
    const saved = hours?.[key];
    initial[key] = saved
      ? { open: true, openTime: saved.open, closeTime: saved.close }
      : { open: false, openTime: "09:00", closeTime: "17:00" };
  }
  return initial;
}

export function WorkingHoursStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const [days, setDays] = useState<Record<string, DayState>>(() =>
    buildInitialDays(setupState.working_hours?.hours),
  );
  const [holidays, setHolidays] = useState<string[]>(setupState.working_hours?.holidays ?? []);
  const [newHoliday, setNewHoliday] = useState("");

  const saveWorkingHours = useSaveWorkingHours(orgId);

  const updateDay = (key: string, patch: Partial<DayState>) =>
    setDays((prev) => ({ ...prev, [key]: { ...prev[key], ...patch } }));

  const addHoliday = () => {
    if (newHoliday && !holidays.includes(newHoliday)) {
      setHolidays((prev) => [...prev, newHoliday].sort());
      setNewHoliday("");
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const hours: Record<string, { open: string; close: string }> = {};
    for (const { key } of DAYS) {
      const day = days[key];
      if (day.open) {
        hours[key] = { open: day.openTime, close: day.closeTime };
      }
    }
    saveWorkingHours.mutate({ hours, holidays }, { onSuccess: onNext });
  };

  return (
    <StepCard
      title="Working Hours"
      description="Set when the AI receptionist should treat the business as open — used for booking availability and after-hours messaging."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="divide-y divide-slate-100 dark:divide-slate-800 rounded-lg border border-slate-200 dark:border-slate-800">
          {DAYS.map(({ key, label }) => {
            const day = days[key];
            return (
              <div key={key} className="flex flex-wrap items-center gap-4 px-4 py-3">
                <div className="flex w-36 items-center gap-3">
                  <Switch checked={day.open} onChange={(open) => updateDay(key, { open })} label={label} />
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</span>
                </div>
                {day.open ? (
                  <div className="flex items-center gap-2">
                    <Input
                      type="time"
                      value={day.openTime}
                      onChange={(e) => updateDay(key, { openTime: e.target.value })}
                    />
                    <span className="text-sm text-slate-400 dark:text-slate-500">to</span>
                    <Input
                      type="time"
                      value={day.closeTime}
                      onChange={(e) => updateDay(key, { closeTime: e.target.value })}
                    />
                  </div>
                ) : (
                  <span className="text-sm text-slate-400 dark:text-slate-500">Closed</span>
                )}
              </div>
            );
          })}
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">Holidays</p>
          <div className="flex items-center gap-2">
            <Input type="date" value={newHoliday} onChange={(e) => setNewHoliday(e.target.value)} />
            <Button type="button" variant="secondary" onClick={addHoliday}>
              <Plus className="h-4 w-4" />
              Add
            </Button>
          </div>
          {holidays.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-2">
              {holidays.map((date) => (
                <li
                  key={date}
                  className="flex items-center gap-2 rounded-lg bg-slate-100 dark:bg-slate-800 px-3 py-1 text-sm text-slate-700 dark:text-slate-200"
                >
                  {date}
                  <button
                    type="button"
                    onClick={() => setHolidays((prev) => prev.filter((d) => d !== date))}
                    className="text-slate-400 dark:text-slate-500 hover:text-red-600"
                    aria-label={`Remove ${date}`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <StepFooter onBack={onBack} isSaving={saveWorkingHours.isPending} />
      </form>
    </StepCard>
  );
}
