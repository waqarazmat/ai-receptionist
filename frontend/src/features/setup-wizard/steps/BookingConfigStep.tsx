import { useState, type FormEvent } from "react";
import { Calendar, Plus, Trash2 } from "lucide-react";
import { useSaveBookingConfig } from "../../../api/setup-wizard";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { Switch } from "../../../components/ui/Switch";
import { StepCard } from "../StepCard";
import { StepFooter } from "../StepFooter";
import type { StepComponentProps } from "../types";

interface ServiceRow {
  name: string;
  duration_minutes: number;
  buffer_minutes: number;
}

export function BookingConfigStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const booking = setupState.booking;
  const [services, setServices] = useState<ServiceRow[]>(
    booking?.services.length ? booking.services : [{ name: "", duration_minutes: 30, buffer_minutes: 10 }],
  );
  const [calendarEnabled, setCalendarEnabled] = useState(booking?.calendar_enabled ?? false);

  const saveBookingConfig = useSaveBookingConfig(orgId);

  const updateService = (index: number, patch: Partial<ServiceRow>) =>
    setServices((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));

  const removeService = (index: number) => setServices((prev) => prev.filter((_, i) => i !== index));

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const validServices = services.filter((s) => s.name.trim());
    saveBookingConfig.mutate(
      { services: validServices, calendar_enabled: calendarEnabled },
      { onSuccess: onNext },
    );
  };

  return (
    <StepCard
      title="Booking Configuration"
      description="Define the services customers can book and whether appointments sync to a calendar."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-3">
          {services.map((service, index) => (
            <div key={index} className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
              <Input
                label="Service name"
                value={service.name}
                onChange={(e) => updateService(index, { name: e.target.value })}
                className="min-w-[10rem] flex-1"
              />
              <Input
                label="Duration (min)"
                type="number"
                min={5}
                value={service.duration_minutes}
                onChange={(e) => updateService(index, { duration_minutes: Number(e.target.value) })}
                className="w-32"
              />
              <Input
                label="Buffer (min)"
                type="number"
                min={0}
                value={service.buffer_minutes}
                onChange={(e) => updateService(index, { buffer_minutes: Number(e.target.value) })}
                className="w-32"
              />
              <button
                type="button"
                onClick={() => removeService(index)}
                className="rounded-lg p-2 text-slate-400 dark:text-slate-500 hover:bg-red-50 hover:text-red-600"
                aria-label="Remove service"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>

        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={() => setServices((prev) => [...prev, { name: "", duration_minutes: 30, buffer_minutes: 10 }])}
        >
          <Plus className="h-4 w-4" />
          Add Service
        </Button>

        <div className="flex items-center justify-between rounded-lg border border-slate-200 dark:border-slate-800 p-4">
          <div>
            <p className="text-sm font-medium text-slate-900 dark:text-slate-100">Google Calendar Integration</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">Sync confirmed bookings to a connected calendar.</p>
          </div>
          <Switch checked={calendarEnabled} onChange={setCalendarEnabled} label="Enable Google Calendar" />
        </div>

        {calendarEnabled && (
          <div className="flex items-center gap-2 rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-500 dark:text-slate-400">
            <Calendar className="h-4 w-4 shrink-0" />
            Save this step, then add the calendar ID in the API Keys step to finish connecting Google Calendar.
          </div>
        )}

        <StepFooter onBack={onBack} isSaving={saveBookingConfig.isPending} />
      </form>
    </StepCard>
  );
}
