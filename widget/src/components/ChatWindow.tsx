import { useRef, useEffect, useState } from "preact/hooks";
import type { WidgetConfig } from "../types.js";
import type { Message } from "./MessageBubble.js";
import { MessageBubble, TypingIndicator } from "./MessageBubble.js";

export type ChatPhase = "welcome" | "prechat" | "chat";

interface Props {
  config: WidgetConfig;
  phase: ChatPhase;
  lang: string;
  messages: Message[];
  isTyping: boolean;
  inputValue: string;
  isSending: boolean;
  consentAccepted: boolean;
  onLangSelect: (lang: string) => void;
  onPreChatSubmit: (email: string, name?: string) => Promise<void>;
  onAcceptConsent: () => void;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onClose: () => void;
  onSuggestion: (q: string) => void;
  onSlotSelect: (title: string) => void;
}

const LANGS = [
  { code: "nl", label: "NL" },
  { code: "en", label: "EN" },
  { code: "fr", label: "FR" },
];

export function ChatWindow({
  config, phase, lang, messages, isTyping,
  inputValue, isSending, consentAccepted,
  onLangSelect, onPreChatSubmit, onAcceptConsent, onInputChange, onSend, onClose, onSuggestion,
  onSlotSelect,
}: Props) {
  const posClass = config.position === "bottom-left" ? "pos-left" : "pos-right";
  const endRef = useRef<HTMLDivElement>(null);
  const [preChatEmail, setPreChatEmail]   = useState("");
  const [preChatName,  setPreChatName]    = useState("");
  const [preChatError, setPreChatError]   = useState("");
  const [preChatBusy,  setPreChatBusy]    = useState(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isTyping]);

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim() && !isSending) onSend();
    }
  }

  const greeting =
    config.greetingByLang[lang] ??
    config.greetingByLang["nl"] ??
    Object.values(config.greetingByLang)[0] ??
    "Welkom! Hoe kan ik u helpen? 👋";

  const suggestedQuestions = config.suggestedQuestions ?? [];

  return (
    <div class={`chat-window ${posClass}${phase !== "welcome" || messages.length > 0 ? " open" : " open"}`}>
      {/* Header */}
      <div class="header">
        <div class="header-avatar">
          {config.avatarUrl ? (
            <img src={config.avatarUrl} alt={config.headerTitle} />
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"
                 fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          )}
        </div>
        <div class="header-info">
          <span class="header-title">{config.headerTitle}</span>
          <div class="header-status">
            <span class="status-dot" />
            <span>Online</span>
          </div>
        </div>
        <button class="close-btn" onClick={onClose} type="button" aria-label="Close">&#215;</button>
      </div>

      {/* Pre-chat form */}
      {phase === "prechat" && (
        <div class="welcome">
          <div class="welcome-icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                 stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <h2 class="welcome-title">Before we start</h2>
          <p class="welcome-sub">Leave your email so we can follow up if needed.</p>
          <div class="prechat-form">
            <input
              class="prechat-input"
              type="text"
              placeholder="Your name (optional)"
              value={preChatName}
              onInput={(e) => setPreChatName((e.target as HTMLInputElement).value)}
            />
            <input
              class="prechat-input"
              type="email"
              placeholder="Your email address *"
              value={preChatEmail}
              onInput={(e) => { setPreChatEmail((e.target as HTMLInputElement).value); setPreChatError(""); }}
            />
            {preChatError && <p class="prechat-error">{preChatError}</p>}
            <button
              class="prechat-submit"
              type="button"
              disabled={preChatBusy}
              onClick={async () => {
                const email = preChatEmail.trim();
                if (!email || !email.includes("@")) {
                  setPreChatError("Please enter a valid email address.");
                  return;
                }
                setPreChatBusy(true);
                await onPreChatSubmit(email, preChatName.trim() || undefined);
                setPreChatBusy(false);
              }}
            >
              {preChatBusy ? "…" : "Start chat →"}
            </button>
            <button
              class="prechat-skip"
              type="button"
              onClick={() => onPreChatSubmit("", undefined)}
            >
              Skip
            </button>
          </div>
        </div>
      )}

      {/* Welcome screen */}
      {phase === "welcome" && (
        <div class="welcome">
          <div class="welcome-icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                 stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <h2 class="welcome-title">{greeting}</h2>
          <p class="welcome-sub">
            {config.responseTimeText ?? "Choose your language to get started."}
          </p>
          <div class="lang-picker">
            {LANGS.map((l) => (
              <button
                key={l.code}
                class={`lang-btn${lang === l.code ? " selected" : ""}`}
                type="button"
                onClick={() => onLangSelect(l.code)}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat body */}
      <div class={`chat-body${phase === "chat" ? " active" : ""}`}>
        <div class="messages">
          {/* Suggested questions before first user message */}
          {messages.length === 0 && suggestedQuestions.length > 0 && (
            <div class="suggestions">
              {suggestedQuestions.map((q) => (
                <button
                  key={q}
                  class="suggestion-btn"
                  type="button"
                  onClick={() => onSuggestion(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          {messages.map((m) => <MessageBubble key={m.id} message={m} onSelect={onSlotSelect} />)}
          {isTyping && <TypingIndicator />}
          <div ref={endRef} />
        </div>

        <div class="controls">
          <textarea
            class="textarea"
            rows={1}
            placeholder="Type a message…"
            value={inputValue}
            onInput={(e) => {
              const t = e.target as HTMLTextAreaElement;
              onInputChange(t.value);
              // Auto-resize
              t.style.height = "auto";
              t.style.height = Math.min(t.scrollHeight, 120) + "px";
            }}
            onKeyDown={handleKeyDown}
            disabled={isSending}
          />
          <button
            class="send-btn"
            type="button"
            onClick={onSend}
            disabled={!inputValue.trim() || isSending}
            aria-label="Send"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                 stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>

        {!consentAccepted && (
          <div class="consent-banner">
            <span>We store your chat to help with follow-ups.</span>
            <button class="consent-accept" type="button" onClick={onAcceptConsent}>OK</button>
          </div>
        )}

        {config.poweredByVisible && (
          <div class="footer">
            <a href="https://genaitech.be" target="_blank" rel="noopener noreferrer">
              Powered by GenAITech
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
