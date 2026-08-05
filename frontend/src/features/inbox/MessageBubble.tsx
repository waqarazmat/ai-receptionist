import type { Message } from "../../types/message";
import { formatDateTime } from "../../lib/utils";

export interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isAi = message.role === "ai";
  const isStaff = message.role === "staff";
  const isCustomer = message.role === "customer";
  // AI (and any staff replies) sit on the RIGHT; the customer sits on the LEFT.
  const alignRight = isAi || isStaff;

  return (
    <div className={`flex ${alignRight ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-xl px-4 py-2.5 text-sm leading-relaxed shadow-sm ${
          isCustomer
            ? "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-100"
            : isStaff
              ? "bg-teal-600 text-white"
              : "bg-indigo-600 text-white"
        }`}
      >
        {isAi && (
          <span className="mb-1.5 inline-flex items-center rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
            AI
          </span>
        )}
        {isStaff && (
          <span className="mb-1.5 inline-flex items-center rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
            Staff
          </span>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
        <p
          className={`mt-1 text-[11px] tabular-nums ${
            isCustomer ? "text-slate-400 dark:text-slate-500" : "text-white/70"
          }`}
        >
          {formatDateTime(message.created_at)}
        </p>
      </div>
    </div>
  );
}
