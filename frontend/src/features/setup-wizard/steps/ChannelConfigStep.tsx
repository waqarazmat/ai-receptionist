import { useState, type FormEvent } from "react";
import { MessageSquare, Phone, Smartphone } from "lucide-react";
import { useSaveChannels } from "../../../api/setup-wizard";
import { Switch } from "../../../components/ui/Switch";
import { StepCard } from "../StepCard";
import { StepFooter } from "../StepFooter";
import type { StepComponentProps } from "../types";

const CHANNELS = [
  { key: "webchat" as const, label: "Web Chat", description: "Embeddable chat widget on the org's website", icon: MessageSquare },
  { key: "whatsapp" as const, label: "WhatsApp", description: "Meta Cloud API business messaging", icon: Smartphone },
  { key: "voice" as const, label: "Voice", description: "Phone calls handled via Retell", icon: Phone },
];

export function ChannelConfigStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const channels = setupState.channels;
  const [webchat, setWebchat] = useState(channels?.webchat ?? false);
  const [whatsapp, setWhatsapp] = useState(channels?.whatsapp ?? false);
  const [voice, setVoice] = useState(channels?.voice ?? false);
  const [isTrial, setIsTrial] = useState(channels?.is_trial ?? false);

  const saveChannels = useSaveChannels(orgId);

  const values = { webchat, whatsapp, voice };
  const setters = { webchat: setWebchat, whatsapp: setWhatsapp, voice: setVoice };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    saveChannels.mutate({ webchat, whatsapp, voice, is_trial: isTrial }, { onSuccess: onNext });
  };

  return (
    <StepCard
      title="Channels"
      description="Choose which channels this organization's AI receptionist will handle. You can enable more later."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {CHANNELS.map(({ key, label, description, icon: Icon }) => (
            <div key={key} className="rounded-lg border border-slate-200 dark:border-slate-800 p-4">
              <div className="flex items-center justify-between">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-500/15 text-indigo-600">
                  <Icon className="h-5 w-5" />
                </span>
                <Switch
                  checked={values[key]}
                  onChange={(checked) => setters[key](checked)}
                  label={`Enable ${label}`}
                />
              </div>
              <p className="mt-3 text-sm font-medium text-slate-900 dark:text-slate-100">{label}</p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{description}</p>
            </div>
          ))}
        </div>

        <label className="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-slate-800 p-4 text-sm">
          <input
            type="checkbox"
            checked={isTrial}
            onChange={(e) => setIsTrial(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
          />
          <span>
            <span className="font-medium text-slate-900 dark:text-slate-100">Trial Access</span>
            <span className="ml-1 text-slate-500 dark:text-slate-400">— give this org limited-time access before billing starts</span>
          </span>
        </label>

        <StepFooter onBack={onBack} isSaving={saveChannels.isPending} />
      </form>
    </StepCard>
  );
}
