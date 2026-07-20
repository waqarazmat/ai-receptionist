import { useState, type FormEvent } from "react";
import { useSaveSystemPrompts } from "../../../api/setup-wizard";
import { Textarea } from "../../../components/ui/Textarea";
import { StepCard } from "../StepCard";
import { StepFooter } from "../StepFooter";
import type { StepComponentProps } from "../types";

export function SystemPromptsStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const prompts = setupState.system_prompts;
  const [greeting, setGreeting] = useState(prompts?.greeting ?? "");
  const [personality, setPersonality] = useState(prompts?.personality ?? "");
  const [escalationRules, setEscalationRules] = useState(prompts?.escalation_rules ?? "");
  const [offTopicResponse, setOffTopicResponse] = useState(prompts?.off_topic_response ?? "");

  const saveSystemPrompts = useSaveSystemPrompts(orgId);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    saveSystemPrompts.mutate(
      {
        greeting,
        personality,
        escalation_rules: escalationRules,
        off_topic_response: offTopicResponse,
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

        <StepFooter onBack={onBack} isSaving={saveSystemPrompts.isPending} />
      </form>
    </StepCard>
  );
}
