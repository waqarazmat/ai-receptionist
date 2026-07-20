import { Check } from "lucide-react";
import type { WizardStepKey } from "../../types/setup-wizard";

export interface WizardStepperProps {
  steps: { key: WizardStepKey; label: string }[];
  currentStep: number;
  completedSteps: Set<number>;
  onStepClick: (index: number) => void;
}

export function WizardStepper({ steps, currentStep, completedSteps, onStepClick }: WizardStepperProps) {
  return (
    <nav aria-label="Setup steps">
      {steps.map((step, index) => {
        const isCompleted = completedSteps.has(index);
        const isCurrent = index === currentStep;
        const isLast = index === steps.length - 1;

        return (
          <div key={step.key} className="relative flex gap-3 pb-8 last:pb-0">
            {!isLast && (
              <div
                className={`absolute left-4 top-8 h-full w-px transition-colors duration-200 ${
                  isCompleted ? "bg-emerald-500" : "bg-slate-200 dark:bg-slate-700"
                }`}
              />
            )}
            <button
              type="button"
              onClick={() => onStepClick(index)}
              aria-current={isCurrent}
              className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors duration-200 ${
                isCompleted
                  ? "bg-emerald-500 text-white"
                  : isCurrent
                    ? "bg-indigo-50 dark:bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 ring-2 ring-indigo-600"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200"
              }`}
            >
              {isCompleted ? <Check className="h-4 w-4" /> : index + 1}
            </button>
            <button
              type="button"
              onClick={() => onStepClick(index)}
              className={`pt-1 text-left text-sm font-medium ${
                isCurrent ? "text-indigo-700 dark:text-indigo-300" : isCompleted ? "text-slate-900 dark:text-slate-100" : "text-slate-500 dark:text-slate-400"
              } hover:text-indigo-700`}
            >
              {step.label}
            </button>
          </div>
        );
      })}
    </nav>
  );
}
