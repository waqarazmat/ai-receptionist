import { forwardRef, useId, type TextareaHTMLAttributes } from "react";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
  showCharCount?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, helperText, showCharCount = false, id, className = "", value, ...props },
  ref,
) {
  const charCount = typeof value === "string" ? value.length : 0;
  const generatedId = useId();
  const textareaId = id ?? generatedId;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={textareaId} className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={textareaId}
        value={value}
        className={`block w-full rounded-lg border px-3 py-2 text-sm text-slate-900 shadow-sm transition-shadow duration-150 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-offset-slate-900 ${
          error ? "border-rose-400 dark:border-rose-500" : "border-slate-300 dark:border-slate-700"
        } ${className}`}
        {...props}
      />
      <div className="mt-1.5 flex items-center justify-between">
        {error ? (
          <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
        ) : helperText ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">{helperText}</p>
        ) : (
          <span />
        )}
        {showCharCount && <p className="text-xs text-slate-400 dark:text-slate-500">{charCount} characters</p>}
      </div>
    </div>
  );
});
