import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Rocket } from "lucide-react";
import { useActivateOrg } from "../../../api/setup-wizard";
import { Button } from "../../../components/ui/Button";
import { Card } from "../../../components/ui/Card";
import { Modal } from "../../../components/ui/Modal";
import { WIZARD_STEP_KEYS, WIZARD_STEPS } from "../../../types/setup-wizard";
import type { StepComponentProps } from "../types";

export function ReviewAndActivateStep({ orgId, setupState, onBack }: StepComponentProps) {
  const navigate = useNavigate();
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const activateOrg = useActivateOrg(orgId);

  const missingSteps = WIZARD_STEP_KEYS.filter((key) => !setupState.setup_progress[key]);
  const stepLabel = (key: string) => WIZARD_STEPS.find((s) => s.key === key)?.label ?? key;

  const { basic_info, working_hours, channels, api_keys_configured, knowledge_base, booking, system_prompts, staff_emails } =
    setupState;

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Review & Activate</h3>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Double-check everything below, then activate the organization to go live.
        </p>
      </div>

      {missingSteps.length > 0 && (
        <div className="mb-6 flex items-start gap-3 rounded-lg border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
          <div className="text-sm text-amber-800 dark:text-amber-200">
            <p className="font-medium">Setup isn't complete yet</p>
            <p className="mt-1">
              Finish these steps before activating: {missingSteps.map(stepLabel).join(", ")}.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card title="Basic Info">
          {basic_info ? (
            <div className="space-y-1 text-sm text-slate-600 dark:text-slate-300">
              <p className="font-medium text-slate-900 dark:text-slate-100">{basic_info.name}</p>
              <p>{basic_info.industry}</p>
              <p>{basic_info.timezone}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-500">Not set</p>
          )}
        </Card>

        <Card title="Working Hours">
          {working_hours && Object.keys(working_hours.hours).length > 0 ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">
              Open {Object.keys(working_hours.hours).length} day(s) a week
              {working_hours.holidays.length > 0 && `, ${working_hours.holidays.length} holiday(s)`}
            </p>
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-500">Not set</p>
          )}
        </Card>

        <Card title="Channels">
          {channels ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {[channels.webchat && "Web Chat", channels.whatsapp && "WhatsApp", channels.voice && "Voice"]
                .filter(Boolean)
                .join(", ") || "None enabled"}
              {channels.is_trial && " · Trial"}
            </p>
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-500">Not set</p>
          )}
        </Card>

        <Card title="API Keys">
          {api_keys_configured.length > 0 ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">{api_keys_configured.join(", ")}</p>
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-500">None configured</p>
          )}
        </Card>

        <Card title="Knowledge Base">
          {knowledge_base ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {knowledge_base.name} · {knowledge_base.chunks.length} chunk(s)
            </p>
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-500">Not set</p>
          )}
        </Card>

        <Card title="Booking">
          {booking ? (
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {booking.services.length} service(s) · Calendar {booking.calendar_enabled ? "on" : "off"}
            </p>
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-500">Not set</p>
          )}
        </Card>

        <Card title="System Prompts">
          {system_prompts ? (
            <p className="line-clamp-2 text-sm text-slate-600 dark:text-slate-300">{system_prompts.greeting}</p>
          ) : (
            <p className="text-sm text-slate-400 dark:text-slate-500">Not set</p>
          )}
        </Card>

        <Card title="Staff Access">
          <p className="text-sm text-slate-600 dark:text-slate-300">{staff_emails.length} staff member(s)</p>
        </Card>
      </div>

      <div className="mt-8 flex items-center justify-between border-t border-slate-200 dark:border-slate-800 pt-6">
        {onBack ? (
          <Button type="button" variant="secondary" onClick={onBack}>
            Back
          </Button>
        ) : (
          <span />
        )}
        <Button type="button" size="lg" disabled={missingSteps.length > 0} onClick={() => setIsConfirmOpen(true)}>
          <Rocket className="h-4 w-4" />
          Activate Organization
        </Button>
      </div>

      <Modal isOpen={isConfirmOpen} onClose={() => setIsConfirmOpen(false)} title="Activate Organization">
        <p className="text-sm text-slate-600 dark:text-slate-300">
          This will make <strong>{basic_info?.name}</strong> live. Its AI receptionist will start handling
          real customer conversations across the enabled channels.
        </p>
        {activateOrg.isError && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">Activation failed. Please check all steps are complete.</p>
        )}
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setIsConfirmOpen(false)}>
            Cancel
          </Button>
          <Button
            isLoading={activateOrg.isPending}
            onClick={() =>
              activateOrg.mutate(undefined, {
                onSuccess: () => navigate("/admin/organizations"),
              })
            }
          >
            Confirm & Activate
          </Button>
        </div>
      </Modal>
    </div>
  );
}
