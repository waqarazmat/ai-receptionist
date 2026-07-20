import { Button } from "../../components/ui/Button";

export interface StepFooterProps {
  onBack?: () => void;
  isSaving?: boolean;
  nextLabel?: string;
}

export function StepFooter({ onBack, isSaving = false, nextLabel = "Save & Continue" }: StepFooterProps) {
  return (
    <div className="mt-8 flex items-center justify-between border-t border-slate-200 dark:border-slate-800 pt-6">
      {onBack ? (
        <Button type="button" variant="secondary" onClick={onBack}>
          Back
        </Button>
      ) : (
        <span />
      )}
      <Button type="submit" isLoading={isSaving}>
        {nextLabel}
      </Button>
    </div>
  );
}
