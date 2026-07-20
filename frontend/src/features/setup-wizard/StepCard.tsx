import type { ReactNode } from "react";

export interface StepCardProps {
  title: string;
  description: string;
  children: ReactNode;
}

export function StepCard({ title, description, children }: StepCardProps) {
  return (
    <div>
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>
      </div>
      {children}
    </div>
  );
}
