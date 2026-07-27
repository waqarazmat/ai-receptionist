import { Check } from "lucide-react";
import type { WizardStepKey } from "../../types/setup-wizard";

export interface WizardStepperProps {
  steps: { key: WizardStepKey; label: string }[];
  currentStep: number;
  completedSteps: Set<number>;
  onStepClick: (index: number) => void;
}

export function WizardStepper({ steps, currentStep, completedSteps, onStepClick }: WizardStepperProps) {
  const totalSteps = steps.length;
  const doneCount = completedSteps.size;
  const pct = Math.round((doneCount / totalSteps) * 100);

  return (
    <aside className="flex flex-col gap-6">
      {/* Progress summary */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-700/60 bg-white dark:bg-slate-800/50 p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500">
            Progress
          </span>
          <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">
            {doneCount}/{totalSteps}
          </span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="mt-2 text-[11px] text-slate-400 dark:text-slate-500">
          {pct === 100 ? "All steps complete — ready to activate!" : `${pct}% complete`}
        </p>
      </div>

      {/* Step list */}
      <nav aria-label="Setup steps" className="flex flex-col gap-1">
        {steps.map((step, index) => {
          const isCompleted = completedSteps.has(index);
          const isCurrent = index === currentStep;
          const isLast = index === totalSteps - 1;
          const isClickable = isCompleted || index <= currentStep;

          return (
            <div key={step.key} className="relative">
              {/* Connector line */}
              {!isLast && (
                <div
                  className={`absolute left-7 top-11 w-px h-[calc(100%-12px)] transition-colors duration-300 ${
                    isCompleted
                      ? "bg-indigo-300 dark:bg-indigo-700"
                      : "bg-slate-200 dark:bg-slate-700"
                  }`}
                />
              )}

              <button
                type="button"
                onClick={() => isClickable && onStepClick(index)}
                disabled={!isClickable}
                aria-current={isCurrent ? "step" : undefined}
                className={`
                  group relative w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all duration-200
                  ${isCurrent
                    ? "bg-indigo-50 dark:bg-indigo-500/10 shadow-sm ring-1 ring-indigo-200 dark:ring-indigo-500/30"
                    : isClickable
                      ? "hover:bg-slate-50 dark:hover:bg-slate-800/60 cursor-pointer"
                      : "cursor-default opacity-40"
                  }
                `}
              >
                {/* Circle indicator */}
                <span
                  className={`
                    relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all duration-200
                    ${isCompleted
                      ? "bg-indigo-600 dark:bg-indigo-500 text-white"
                      : isCurrent
                        ? "bg-indigo-600 text-white shadow-md shadow-indigo-200 dark:shadow-indigo-900"
                        : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
                    }
                  `}
                >
                  {isCompleted ? <Check className="h-3.5 w-3.5" strokeWidth={2.5} /> : index + 1}
                </span>

                {/* Label + status */}
                <div className="flex-1 min-w-0">
                  <p
                    className={`text-sm font-medium leading-tight truncate transition-colors duration-200 ${
                      isCurrent
                        ? "text-indigo-700 dark:text-indigo-300"
                        : isCompleted
                          ? "text-slate-700 dark:text-slate-200"
                          : "text-slate-500 dark:text-slate-400"
                    }`}
                  >
                    {step.label}
                  </p>
                  <p className={`text-[11px] mt-0.5 transition-colors duration-200 ${
                    isCompleted
                      ? "text-slate-400 dark:text-slate-500"
                      : isCurrent
                        ? "text-indigo-500 dark:text-indigo-400"
                        : "text-slate-400 dark:text-slate-600"
                  }`}>
                    {isCompleted ? "Done" : isCurrent ? "In progress" : "Pending"}
                  </p>
                </div>

                {/* Active indicator dot */}
                {isCurrent && (
                  <span className="shrink-0 h-1.5 w-1.5 rounded-full bg-indigo-500" />
                )}
              </button>
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
