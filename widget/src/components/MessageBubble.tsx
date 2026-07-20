import { useState } from "preact/hooks";

export interface Message {
  id: string;
  direction: "inbound" | "outbound";
  body: string;
  ts: string;
  sender?: "ai" | "agent" | "visitor" | "staff" | "system";
  optimistic?: boolean;
  html?: string; // pre-rendered markdown for bot messages
  streaming?: boolean; // true while tokens are still arriving
  interactive?: {
    type: "list" | "button";
    body?: { text?: string };
    action?: {
      buttons?: Array<{ reply?: { title?: string } }>;
      sections?: Array<{ rows?: Array<{ id?: string; title?: string; description?: string }> }>;
    };
  };
}

interface Props {
  message: Message;
  onSelect?: (title: string) => void;
}

export function MessageBubble({ message: m, onSelect }: Props) {
  const isUser = m.direction === "outbound";
  const [selected, setSelected] = useState(false);

  if (m.sender === "system") {
    return (
      <div class="system-notice">
        <span>You are now chatting with a staff member</span>
      </div>
    );
  }

  const cls = `bubble ${isUser ? "user" : m.sender === "staff" ? "bot staff" : "bot"}${m.optimistic ? " optimistic" : ""}`;

  const rows = (!selected && m.interactive?.type === "list"
    ? m.interactive.action?.sections?.flatMap((s) => s.rows ?? []) ?? []
    : []
  ).filter((r): r is { id?: string; title: string; description?: string } => Boolean(r.title));

  function handleRowClick(title: string) {
    setSelected(true);
    onSelect?.(title);
  }

  const slotButtons = rows.length > 0 && (
    <div class="suggestions">
      {rows.map((row) => (
        <button
          key={row.id ?? row.title}
          class="suggestion-btn"
          type="button"
          onClick={() => handleRowClick(row.title)}
        >
          {row.title}
        </button>
      ))}
    </div>
  );

  // Streaming bubble: render plain text + blinking cursor, no markdown yet
  if (!isUser && m.streaming) {
    return (
      <div class={cls}>
        {m.body}
        <span class="streaming-cursor" aria-hidden="true" />
      </div>
    );
  }

  if (!isUser && m.html && m.sender !== "staff") {
    return (
      <>
        <div class={cls} dangerouslySetInnerHTML={{ __html: m.html }} />
        {slotButtons}
      </>
    );
  }

  return (
    <>
      <div class={cls}>
        {m.sender === "staff" && <span class="staff-label">Staff</span>}
        {m.body}
      </div>
      {slotButtons}
    </>
  );
}

export function TypingIndicator() {
  return (
    <div class="typing-indicator">
      <div class="typing-dot" />
      <div class="typing-dot" />
      <div class="typing-dot" />
    </div>
  );
}
