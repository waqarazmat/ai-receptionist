import type { Message } from "../../types/message";
import { formatDateTime } from "../../lib/utils";

export interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isStaff = message.role === "staff";
  const isAi = message.role === "ai";

  return (
    <div className={`flex ${isStaff ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-xl px-4 py-2.5 text-sm leading-relaxed shadow-sm ${
          isStaff
            ? "bg-indigo-600 text-white"
            : isAi
              ? "bg-indigo-50 dark:bg-indigo-500/15 text-slate-800 dark:text-slate-100"
              : "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-100"
        }`}
      >
        {isAi && (
          <span className="mb-1.5 inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-600">
            AI
          </span>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
        <p className={`mt-1 text-[11px] tabular-nums ${isStaff ? "text-indigo-200" : "text-slate-400 dark:text-slate-500"}`}>
          {formatDateTime(message.created_at)}
        </p>
      </div>
    </div>
  );
}
