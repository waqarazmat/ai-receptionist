import { Fragment, useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { useSaveApiKey, useSaveVoiceConfig, useSaveWhatsappConfig } from "../../../api/setup-wizard";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import type { ApiKeyProvider } from "../../../types/setup-wizard";
import type { StepComponentProps } from "../types";

const WHATSAPP_PHONE_RE = /^\+[1-9]\d{6,14}$/;

interface ProviderConfig {
  key: ApiKeyProvider;
  label: string;
  placeholder: string;
  masked: boolean;
  visible: (setupState: StepComponentProps["setupState"]) => boolean;
}

const PROVIDERS: ProviderConfig[] = [
  { key: "openai", label: "OpenAI", placeholder: "Paste API key", masked: true, visible: () => true },
  { key: "anthropic", label: "Anthropic", placeholder: "Paste API key", masked: true, visible: () => true },
  { key: "cohere", label: "Cohere", placeholder: "Paste API key", masked: true, visible: () => true },
  {
    key: "whatsapp",
    label: "WhatsApp Business Token",
    placeholder: "Paste API key",
    masked: true,
    visible: (s) => Boolean(s.channels?.whatsapp),
  },
  {
    key: "google_calendar",
    label: "Google Calendar ID",
    placeholder: "e.g. your-calendar-id@group.calendar.google.com",
    masked: false,
    visible: (s) => Boolean(s.booking?.calendar_enabled),
  },
  {
    key: "retell",
    label: "Retell API Key",
    placeholder: "Paste API key",
    masked: true,
    visible: (s) => Boolean(s.channels?.voice),
  },
];

function ApiKeyRow({
  orgId,
  provider,
  label,
  placeholder,
  masked,
  isConfigured,
}: {
  orgId: string;
  provider: ApiKeyProvider;
  label: string;
  placeholder: string;
  masked: boolean;
  isConfigured: boolean;
}) {
  const [isEditing, setIsEditing] = useState(!isConfigured);
  const [value, setValue] = useState("");
  const saveApiKey = useSaveApiKey(orgId);

  const handleSave = () => {
    if (!value) return;
    saveApiKey.mutate(
      { provider, api_key: value },
      {
        onSuccess: () => {
          setValue("");
          setIsEditing(false);
        },
      },
    );
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
      <div className="w-48 shrink-0">
        <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{label}</p>
        {isConfigured && !isEditing && (
          <p className="mt-0.5 flex items-center gap-1 text-xs text-emerald-600">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Configured
          </p>
        )}
      </div>
      {isEditing ? (
        <>
          <Input
            type={masked ? "password" : "text"}
            placeholder={placeholder}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="flex-1"
          />
          <Button type="button" size="sm" onClick={handleSave} isLoading={saveApiKey.isPending} disabled={!value}>
            Save
          </Button>
          {isConfigured && (
            <Button type="button" size="sm" variant="ghost" onClick={() => setIsEditing(false)}>
              Cancel
            </Button>
          )}
        </>
      ) : (
        <>
          <Input value={masked ? "•••••••••••••••• (saved)" : "(saved)"} disabled className="flex-1" />
          <Button type="button" size="sm" variant="secondary" onClick={() => setIsEditing(true)}>
            Update
          </Button>
        </>
      )}
    </div>
  );
}

/** For plain (non-secret) config values like a phone number or agent ID —
 * unlike ApiKeyRow, the saved value is shown and editable directly rather
 * than masked behind a "(saved)" placeholder, and it re-syncs from
 * `savedValue` whenever setup state is refetched (e.g. navigating back to
 * this step) so it never shows stale local state. */
function ConfigFieldRow({
  label,
  placeholder,
  helperText,
  savedValue,
  isSaving,
  onSave,
  validate,
}: {
  label: string;
  placeholder: string;
  helperText?: string;
  savedValue: string | null;
  isSaving: boolean;
  onSave: (value: string) => void;
  validate?: (value: string) => string | null;
}) {
  const [value, setValue] = useState(savedValue ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setValue(savedValue ?? "");
  }, [savedValue]);

  const handleSave = () => {
    const validationError = validate?.(value) ?? null;
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    onSave(value);
  };

  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 dark:border-slate-800 p-4">
      <div className="w-48 shrink-0">
        <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{label}</p>
        {savedValue && (
          <p className="mt-0.5 flex items-center gap-1 text-xs text-emerald-600">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Saved
          </p>
        )}
      </div>
      <div className="flex-1">
        <Input
          placeholder={placeholder}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError(null);
          }}
          error={error ?? undefined}
          helperText={error ? undefined : helperText}
        />
      </div>
      <Button
        type="button"
        size="sm"
        onClick={handleSave}
        isLoading={isSaving}
        disabled={!value || value === (savedValue ?? "")}
      >
        Save
      </Button>
    </div>
  );
}

const SUPPORTED_LANGUAGE_OPTIONS = [
  { code: "en", label: "English" },
  { code: "nl", label: "Dutch (Nederlands)" },
  { code: "fr", label: "French (Français)" },
  { code: "de", label: "German (Deutsch)" },
  { code: "es", label: "Spanish (Español)" },
  { code: "it", label: "Italian (Italiano)" },
  { code: "pt", label: "Portuguese (Português)" },
  { code: "ar", label: "Arabic (العربية)" },
  { code: "tr", label: "Turkish (Türkçe)" },
  { code: "ur", label: "Urdu (اردو)" },
  { code: "hi", label: "Hindi (हिन्दी)" },
  { code: "zh", label: "Chinese (中文)" },
  { code: "ru", label: "Russian (Русский)" },
  { code: "pl", label: "Polish (Polski)" },
];

export function ApiKeysStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const configured = new Set(setupState.api_keys_configured);
  const visibleProviders = PROVIDERS.filter((p) => p.visible(setupState));
  const showCalendarHelp = setupState.booking?.calendar_enabled;
  const saveWhatsappConfig = useSaveWhatsappConfig(orgId);
  const saveVoiceConfig = useSaveVoiceConfig(orgId);

  const [selectedLanguages, setSelectedLanguages] = useState<string[]>(
    setupState.voice_supported_languages ?? ["en"],
  );
  const [langSaving, setLangSaving] = useState(false);

  useEffect(() => {
    if (setupState.voice_supported_languages) {
      setSelectedLanguages(setupState.voice_supported_languages);
    }
  }, [setupState.voice_supported_languages]);

  const toggleLanguage = (code: string) => {
    setSelectedLanguages((prev) =>
      prev.includes(code) ? (prev.length > 1 ? prev.filter((c) => c !== code) : prev) : [...prev, code],
    );
  };

  const saveLanguages = (agentId: string) => {
    saveVoiceConfig.mutate({ retell_agent_id: agentId, supported_languages: selectedLanguages });
  };

  const saveLanguagesOnly = () => {
    const agentId = setupState.voice_retell_agent_id ?? "";
    if (!agentId) return;
    setLangSaving(true);
    saveVoiceConfig.mutate(
      { retell_agent_id: agentId, supported_languages: selectedLanguages },
      { onSettled: () => setLangSaving(false) },
    );
  };

  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">API Keys</h3>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Each key is encrypted before it's stored — once saved, the plaintext value is never shown again.
        </p>
      </div>

      {showCalendarHelp && (
        <div className="mb-4 rounded-lg border border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/15 p-4 text-sm text-indigo-900 dark:text-indigo-200">
          <p className="font-medium">Before adding the Calendar ID:</p>
          <p className="mt-1">
            Share the org's Google Calendar with{" "}
            {setupState.google_calendar_service_account_email ? (
              <code className="rounded bg-indigo-100 px-1 py-0.5 text-xs">
                {setupState.google_calendar_service_account_email}
              </code>
            ) : (
              "the platform's service account"
            )}{" "}
            (Calendar settings → Share with specific people → give "Make changes to events" access), then paste that
            calendar's ID below — usually the calendar owner's email address, found under Calendar settings →
            Integrate calendar.
          </p>
        </div>
      )}

      <div className="space-y-3">
        {visibleProviders.map(({ key, label, placeholder, masked }) => (
          <Fragment key={key}>
            <ApiKeyRow
              orgId={orgId}
              provider={key}
              label={label}
              placeholder={placeholder}
              masked={masked}
              isConfigured={configured.has(key)}
            />
            {key === "whatsapp" && (
              <>
                <ConfigFieldRow
                  label="WhatsApp Phone Number"
                  placeholder="+1234567890"
                  helperText="The display number, with country code — e.g. +1234567890."
                  savedValue={setupState.whatsapp_phone_number}
                  isSaving={saveWhatsappConfig.isPending}
                  onSave={(value) => saveWhatsappConfig.mutate({ phone_number: value })}
                  validate={(value) =>
                    WHATSAPP_PHONE_RE.test(value) ? null : "Enter a phone number with country code, e.g. +1234567890."
                  }
                />
                <ConfigFieldRow
                  label="WhatsApp Phone Number ID"
                  placeholder="1234567890123456"
                  helperText="Meta's numeric ID for the number (Meta → WhatsApp → API Setup) — routes inbound webhooks and sends. NOT the display number above."
                  savedValue={setupState.whatsapp_phone_number_id}
                  isSaving={saveWhatsappConfig.isPending}
                  onSave={(value) => saveWhatsappConfig.mutate({ phone_number_id: value })}
                  validate={(value) =>
                    /^\d{5,}$/.test(value.trim()) ? null : "Enter Meta's numeric Phone Number ID (digits only)."
                  }
                />
              </>
            )}
            {key === "retell" && (
              <>
                <ConfigFieldRow
                  label="Retell Agent ID"
                  placeholder="agent_xxxxxxxxxxxxxxxxxxxx"
                  helperText="Found in the Retell dashboard for this agent — separate from the API key above."
                  savedValue={setupState.voice_retell_agent_id}
                  isSaving={saveVoiceConfig.isPending}
                  onSave={saveLanguages}
                  validate={(value) => (value.trim().length > 0 ? null : "Enter the Retell agent ID.")}
                />
                {setupState.channels?.voice && (
                  <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-4">
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100 mb-1">
                      Voice languages
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mb-3">
                      Select every language the caller can choose. When more than one is selected, the AI opens with a "press 1 for English / press 2 for …" menu.
                    </p>
                    <div className="flex flex-wrap gap-3">
                      {SUPPORTED_LANGUAGE_OPTIONS.map(({ code, label }) => (
                        <label key={code} className="flex items-center gap-2 cursor-pointer select-none text-sm">
                          <input
                            type="checkbox"
                            checked={selectedLanguages.includes(code)}
                            onChange={() => toggleLanguage(code)}
                            className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                          />
                          <span className="text-slate-700 dark:text-slate-300">{label}</span>
                        </label>
                      ))}
                    </div>
                    {setupState.voice_retell_agent_id && (
                      <button
                        type="button"
                        onClick={saveLanguagesOnly}
                        disabled={langSaving}
                        className="mt-3 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {langSaving ? "Saving…" : "Save languages"}
                      </button>
                    )}
                  </div>
                )}
              </>
            )}
          </Fragment>
        ))}
      </div>

      <div className="mt-8 flex items-center justify-between border-t border-slate-200 dark:border-slate-800 pt-6">
        {onBack ? (
          <Button type="button" variant="secondary" onClick={onBack}>
            Back
          </Button>
        ) : (
          <span />
        )}
        <Button type="button" onClick={onNext}>
          Continue
        </Button>
      </div>
    </div>
  );
}
