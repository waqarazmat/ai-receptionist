import { useState, type FormEvent } from "react";
import { CheckCircle2, Plus, X } from "lucide-react";
import { useSaveStaffAccess } from "../../../api/setup-wizard";
import { Button } from "../../../components/ui/Button";
import { Input } from "../../../components/ui/Input";
import { StepCard } from "../StepCard";
import { StepFooter } from "../StepFooter";
import type { StepComponentProps } from "../types";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function StaffAccessStep({ orgId, setupState, onBack, onNext }: StepComponentProps) {
  const existingEmails = setupState.staff_emails;
  const [emails, setEmails] = useState<string[]>(existingEmails);
  const [newEmail, setNewEmail] = useState("");
  const [error, setError] = useState<string | null>(null);

  const saveStaffAccess = useSaveStaffAccess(orgId);

  const addEmail = () => {
    const trimmed = newEmail.trim();
    if (!EMAIL_PATTERN.test(trimmed)) {
      setError("Enter a valid email address.");
      return;
    }
    if (emails.includes(trimmed)) {
      setError("That email has already been added.");
      return;
    }
    setEmails((prev) => [...prev, trimmed]);
    setNewEmail("");
    setError(null);
  };

  const removeEmail = (email: string) => setEmails((prev) => prev.filter((e) => e !== email));

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    saveStaffAccess.mutate({ emails }, { onSuccess: onNext });
  };

  return (
    <StepCard
      title="Staff Access"
      description="Add the staff emails that should have org_staff access to this organization's dashboard."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex items-center gap-2">
          <Input
            type="email"
            placeholder="staff@example.com"
            value={newEmail}
            onChange={(e) => {
              setNewEmail(e.target.value);
              setError(null);
            }}
            error={error ?? undefined}
            className="flex-1"
          />
          <Button type="button" variant="secondary" onClick={addEmail}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
        </div>

        {emails.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">No staff added yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800 rounded-lg border border-slate-200 dark:border-slate-800">
            {emails.map((email) => (
              <li key={email} className="flex items-center justify-between px-4 py-2.5">
                <span className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
                  {email}
                  {existingEmails.includes(email) && (
                    <span className="flex items-center gap-1 text-xs text-emerald-600">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Account active
                    </span>
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => removeEmail(email)}
                  className="text-slate-400 dark:text-slate-500 hover:text-red-600"
                  aria-label={`Remove ${email}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <StepFooter onBack={onBack} isSaving={saveStaffAccess.isPending} />
      </form>
    </StepCard>
  );
}
