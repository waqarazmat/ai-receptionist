import { useEffect, useRef, useState, type FormEvent } from "react";
import { ChevronDown, Eye, Sparkles } from "lucide-react";
import { useSaveSystemPrompts, useSystemPromptPreview } from "../../../api/setup-wizard";
import { Button } from "../../../components/ui/Button";
import { Textarea } from "../../../components/ui/Textarea";
import { StepCard } from "../StepCard";
import { StepFooter } from "../StepFooter";
import {
  INDUSTRY_TEMPLATES,
  fillPlaceholders,
  type IndustryTemplate,
} from "../industry-prompts";
import type { StepComponentProps } from "../types";

export function SystemPromptsStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const prompts = setupState.system_prompts;
  const basicInfo = setupState.basic_info;

  const [greeting, setGreeting] = useState(prompts?.greeting ?? "");
  const [personality, setPersonality] = useState(prompts?.personality ?? "");
  const [escalationRules, setEscalationRules] = useState(prompts?.escalation_rules ?? "");
  const [offTopicResponse, setOffTopicResponse] = useState(prompts?.off_topic_response ?? "");
  const [systemPrompt, setSystemPrompt] = useState(prompts?.system_prompt ?? "");

  const [pickerOpen, setPickerOpen] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  // Read-only preview of the FULL assembled prompt the AI receives. Fetched
  // lazily — only once the admin opens the panel.
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewMode, setPreviewMode] = useState<"chat" | "voice">("chat");
  const preview = useSystemPromptPreview(orgId, previewOpen);

  const saveSystemPrompts = useSaveSystemPrompts(orgId);

  // Close the picker on outside click — same pattern as the shared DropdownMenu
  // component, inlined here so we can render richer items (emoji + label + hint)
  // than the generic component supports.
  useEffect(() => {
    if (!pickerOpen) return;
    function onDown(ev: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(ev.target as Node)) {
        setPickerOpen(false);
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [pickerOpen]);

  const applyTemplate = (template: IndustryTemplate) => {
    // Substitute {{org_name}} etc. from what the admin set on BasicInfoStep.
    // Anything the substituter doesn't have a value for is left in the text
    // as-is so the admin can see and edit the placeholder rather than being
    // silently given an empty gap.
    const filled = fillPlaceholders(template.prompt, {
      org_name: basicInfo?.name,
      industry: basicInfo?.industry,
      phone: basicInfo?.phone,
      email: basicInfo?.email,
      address: basicInfo?.address,
    });
    setSystemPrompt(filled);
    setPickerOpen(false);
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    saveSystemPrompts.mutate(
      {
        greeting,
        personality,
        escalation_rules: escalationRules,
        off_topic_response: offTopicResponse,
        // null (not empty string) so the backend cleanly treats untouched as
        // "no custom prompt" — see receptionist_system.py.
        system_prompt: systemPrompt.trim() ? systemPrompt : null,
      },
      { onSuccess: onNext },
    );
  };

  return (
    <StepCard
      title="System Prompts"
      description="Shape how the AI receptionist talks to customers — its greeting, tone, and boundaries."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Read-only preview of the full prompt the AI actually receives —
            assembled from the fields below + built-in guardrails. */}
        <div className="rounded-lg border border-slate-200 dark:border-slate-700">
          <button
            type="button"
            onClick={() => setPreviewOpen((o) => !o)}
            className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left"
          >
            <span className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
              <Eye className="h-4 w-4" />
              View the full system prompt the AI actually uses
            </span>
            <ChevronDown
              className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${previewOpen ? "rotate-180" : ""}`}
            />
          </button>

          {previewOpen && (
            <div className="border-t border-slate-200 px-4 py-3 dark:border-slate-700">
              <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
                Assembled from the fields below plus built-in safety guardrails and guidelines —
                this is exactly what the model sees on every message. (The knowledge/RAG context is
                added per-message and omitted here.) Read-only; edit the fields below to change it.
              </p>
              <div className="mb-2 inline-flex rounded-md border border-slate-200 p-0.5 dark:border-slate-700">
                {(["chat", "voice"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setPreviewMode(m)}
                    className={`rounded px-3 py-1 text-xs font-medium capitalize transition-colors ${
                      previewMode === m
                        ? "bg-indigo-600 text-white"
                        : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700/60"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
              {preview.isLoading ? (
                <p className="text-sm text-slate-400">Loading…</p>
              ) : preview.isError ? (
                <p className="text-sm text-rose-500">Couldn't load the prompt preview.</p>
              ) : (
                <>
                  <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-xs leading-relaxed text-slate-700 dark:bg-slate-900 dark:text-slate-200">
                    {previewMode === "chat" ? preview.data?.chat : preview.data?.voice}
                  </pre>
                  <p className="mt-1 text-[11px] text-slate-400">
                    {(previewMode === "chat" ? preview.data?.chat_chars : preview.data?.voice_chars) ?? 0} characters
                  </p>
                </>
              )}
            </div>
          )}
        </div>

        <Textarea
          label="Greeting message"
          placeholder="Hi! Welcome to Acme Dental. How can I help you today?"
          value={greeting}
          onChange={(e) => setGreeting(e.target.value)}
          rows={2}
          showCharCount
          required
        />
        <Textarea
          label="AI personality / tone"
          placeholder="Friendly, professional, and reassuring."
          value={personality}
          onChange={(e) => setPersonality(e.target.value)}
          rows={2}
          showCharCount
          required
        />
        <Textarea
          label="Escalation trigger rules"
          placeholder="Escalate to a human if the customer is upset, mentions a medical emergency, or asks to speak to staff."
          value={escalationRules}
          onChange={(e) => setEscalationRules(e.target.value)}
          rows={3}
          showCharCount
          required
        />
        <Textarea
          label="Off-topic handling response"
          placeholder="I can only help with questions about Acme Dental's services and appointments."
          value={offTopicResponse}
          onChange={(e) => setOffTopicResponse(e.target.value)}
          rows={2}
          showCharCount
          required
        />

        <div className="space-y-2">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1">
              <label
                htmlFor="system-prompt"
                className="block text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                Custom system prompt{" "}
                <span className="text-xs font-normal text-slate-400">(optional)</span>
              </label>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Extra guardrails, brand voice, or industry-specific instructions. Appended to
                the assembled prompt the AI sees on every message.
              </p>
            </div>

            {/* Template picker — replaces the earlier single "Load Other" button.
                Shows every industry template as a picker item so admins can seed
                any starting point, not just the industry they picked on BasicInfo. */}
            <div ref={pickerRef} className="relative">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => setPickerOpen((o) => !o)}
                aria-haspopup="listbox"
                aria-expanded={pickerOpen}
              >
                <Sparkles className="h-3.5 w-3.5" />
                Load template
                <ChevronDown className="h-3.5 w-3.5" />
              </Button>

              {pickerOpen && (
                <div
                  role="listbox"
                  className="absolute right-0 z-20 mt-2 w-80 rounded-lg border border-slate-200 bg-white py-1 shadow-lg dark:border-slate-700 dark:bg-slate-800"
                >
                  <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                    Choose a starting point
                  </p>
                  <div className="max-h-72 overflow-y-auto">
                    {INDUSTRY_TEMPLATES.map((template) => (
                      <button
                        key={template.key}
                        type="button"
                        onClick={() => applyTemplate(template)}
                        className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-700/60"
                      >
                        <div className="font-medium">{template.label}</div>
                        <div className="mt-0.5 truncate text-xs text-slate-500 dark:text-slate-400">
                          {template.prompt.split("\n")[0]}
                        </div>
                      </button>
                    ))}
                  </div>
                  <p className="border-t border-slate-100 px-3 pt-2 pb-1.5 text-[11px] text-slate-500 dark:border-slate-700 dark:text-slate-400">
                    Loading a template overwrites the field. Placeholders like{" "}
                    <code className="rounded bg-slate-100 px-1 dark:bg-slate-700">{`{{org_name}}`}</code>{" "}
                    are auto-filled.
                  </p>
                </div>
              )}
            </div>
          </div>

          <Textarea
            id="system-prompt"
            placeholder="Pick a template from the button above, or write your own extra rules, brand-voice guidance, or industry-specific guardrails here."
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={12}
            showCharCount
          />
        </div>

        <StepFooter onBack={onBack} isSaving={saveSystemPrompts.isPending} />
      </form>
    </StepCard>
  );
}
