import { useState, useEffect, useRef } from "preact/hooks";
import type { WidgetConfig } from "./types.js";
import type { Message } from "./components/MessageBubble.js";
import type { ChatPhase } from "./components/ChatWindow.js";
import { Launcher } from "./components/Launcher.js";
import { ChatWindow } from "./components/ChatWindow.js";
import { loadStoredConversationId, saveConversationId, clearStoredSession } from "./session.js";
import { ChatWebSocket } from "./ws.js";
import type { WsEvent } from "./ws.js";
import { sendMessage, loadHistory, identifyVisitor, updateLocale } from "./api.js";
import { renderMarkdown } from "./markdown.js";

interface AppProps {
  orgId: string;
  apiBase: string;
  initialConfig: WidgetConfig;
}

export function App({ orgId, apiBase, initialConfig }: AppProps) {
  const consentKey = `cw_consent:${orgId}`;

  const [isOpen,          setIsOpen]          = useState(false);
  const [phase,           setPhase]           = useState<ChatPhase>("welcome");
  const [lang,            setLang]            = useState("en");
  const [messages,        setMessages]        = useState<Message[]>([]);
  const [inputValue,      setInputValue]      = useState("");
  const [isTyping,        setIsTyping]        = useState(false);
  const [isSending,       setIsSending]       = useState(false);
  const [consentAccepted, setConsentAccepted] = useState(
    () => typeof localStorage !== "undefined" && localStorage.getItem(consentKey) === "1"
  );

  const wsRef       = useRef<ChatWebSocket | null>(null);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ID of the ephemeral streaming bubble currently being built, null when idle.
  // The bubble uses this fixed sentinel so the final type:"message" can replace it in-place.
  const streamingMsgId = useRef<string | null>(null);

  // ── Session init ────────────────────────────────────────────────────────────
  useEffect(() => {
    const storedConversationId = loadStoredConversationId(orgId);

    // A stored id means we already know the conversation — load its history
    // right away rather than waiting on any connection event (the backend
    // only emits `connected` for a *new* conversation; see webchat/handler.py).
    if (storedConversationId) {
      loadHistory(apiBase, orgId, storedConversationId)
        .then((history) => {
          if (history.length > 0) {
            setMessages(history.map((m) => ({
              id:        m.id,
              direction: m.direction,
              body:      m.body ?? "",
              ts:        String(m.createdAt ?? new Date().toISOString()),
              html:      m.direction === "inbound" ? renderMarkdown(m.body ?? "") : undefined,
            })));
            setPhase("chat");
          }
        })
        .catch(() => {});
    }

    wsRef.current = new ChatWebSocket(
      apiBase,
      orgId,
      storedConversationId,
      handleWsEvent,
      (conversationId) => saveConversationId(orgId, conversationId),
    );

    return () => { wsRef.current?.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId, apiBase]);

  // ── WebSocket event handler ──────────────────────────────────────────────────
  function handleWsEvent(evt: WsEvent) {
    if (evt.type === "typing") {
      setIsTyping(true);
      // Auto-clear after 15s if no message follows
      if (typingTimer.current) clearTimeout(typingTimer.current);
      typingTimer.current = setTimeout(() => setIsTyping(false), 15_000);
      return;
    }

    // ── Streaming token arrives ───────────────────────────────────────────────
    if (evt.type === "message.delta" && evt.body !== undefined) {
      // First delta: clear the typing indicator and create the streaming bubble
      if (typingTimer.current) { clearTimeout(typingTimer.current); typingTimer.current = null; }
      setIsTyping(false);

      if (streamingMsgId.current === null) {
        // First chunk for this turn — create the streaming bubble
        streamingMsgId.current = "__streaming__";
        const bubble: Message = {
          id:        "__streaming__",
          direction: "inbound",
          body:      evt.body,
          ts:        evt.ts ?? new Date().toISOString(),
          sender:    "ai",
          streaming: true,
        };
        setMessages((prev) => [...prev, bubble]);
      } else {
        // Subsequent chunks — append to the existing streaming bubble
        setMessages((prev) =>
          prev.map((m) =>
            m.id === "__streaming__" ? { ...m, body: m.body + evt.body } : m,
          ),
        );
      }
      return;
    }

    // ── Stream aborted — discard partial bubble, clean fallback message follows ─
    if (evt.type === "message.delta.abort") {
      if (streamingMsgId.current !== null) {
        setMessages((prev) => prev.filter((m) => m.id !== "__streaming__"));
        streamingMsgId.current = null;
      }
      return;
    }

    // ── Committed message (final frame, or non-streaming reply) ──────────────
    if (evt.type === "message" && evt.body !== undefined) {
      if (typingTimer.current) { clearTimeout(typingTimer.current); typingTimer.current = null; }
      setIsTyping(false);

      setMessages((prev) => {
        // Dedup check against already-committed messages
        if (evt.messageId && prev.some((m) => m.id === evt.messageId)) return prev;

        // Build the committed message object
        const isStaff = evt.direction === "outbound" && evt.sender === "staff";
        const committedMsg: Message = isStaff
          ? { id: evt.messageId ?? `ws-${Date.now()}`, direction: "inbound", body: evt.body ?? "", ts: evt.ts ?? new Date().toISOString(), sender: "staff", html: evt.body ?? "", interactive: evt.interactive }
          : { id: evt.messageId ?? `ws-${Date.now()}`, direction: "inbound", body: evt.body ?? "", ts: evt.ts ?? new Date().toISOString(), sender: evt.sender ?? "ai", html: renderMarkdown(evt.body ?? ""), interactive: evt.interactive };

        // If a streaming bubble is in progress, replace it in-place (no flicker, no duplicate)
        if (streamingMsgId.current !== null) {
          streamingMsgId.current = null;
          return prev.map((m) => m.id === "__streaming__" ? committedMsg : m);
        }

        // Visitor's own message echoed back — already shown optimistically; skip.
        if (evt.direction === "outbound" && (evt.sender === "visitor" || !evt.sender)) return prev;

        // Staff reply: prepend system notice on first staff message
        if (isStaff) {
          const alreadyHasStaff = prev.some((m) => m.sender === "staff");
          if (!alreadyHasStaff) {
            const notice: Message = { id: `system-staff-${Date.now()}`, direction: "inbound", body: "", ts: evt.ts ?? new Date().toISOString(), sender: "system" };
            return [...prev, notice, committedMsg];
          }
          return [...prev, committedMsg];
        }

        // Plain non-streaming AI / agent / system reply (smalltalk, booking, farewell, takeover notice, etc.)
        return [...prev, committedMsg];
      });
    }
  }

  // ── Send ─────────────────────────────────────────────────────────────────────
  async function handleSend(overrideText?: string) {
    const text = (overrideText ?? inputValue).trim();
    if (!text || isSending || !wsRef.current) return;

    const optId = `opt-${Date.now()}`;
    const opt: Message = {
      id:        optId,
      direction: "outbound",
      body:      text,
      ts:        new Date().toISOString(),
      optimistic: true,
    };
    setMessages((prev) => [...prev, opt]);
    setInputValue("");
    setIsSending(true);
    setIsTyping(true);

    // Fire-and-forget over the socket — no REST call, no idempotency key,
    // no expiring token to refresh (see ws.ts/session.ts). The confirmation
    // that matters to the visitor is the AI/staff response arriving, not an
    // ack for this send itself.
    await sendMessage(wsRef.current, text);
    setMessages((prev) => prev.map((m) => m.id === optId ? { ...m, optimistic: false } : m));
    setIsSending(false);
  }

  function handleLangSelect(l: string) {
    setLang(l);
    void updateLocale(apiBase, orgId, l);
    const needsPreChat = initialConfig.preChatFormEnabled &&
      initialConfig.preChatFields?.some((f) => f.field === "email");
    setPhase(needsPreChat ? "prechat" : "chat");
  }

  async function handlePreChatSubmit(email: string, name?: string) {
    await identifyVisitor(apiBase, orgId, email, name);
    setPhase("chat");
  }

  function handleAcceptConsent() {
    if (typeof localStorage !== "undefined") localStorage.setItem(consentKey, "1");
    setConsentAccepted(true);
  }

  function handleSuggestion(q: string) {
    setInputValue(q);
  }

  // ── Reset ────────────────────────────────────────────────────────────────────
  // Start a brand-new conversation: forget the stored conversation id (so a reload
  // no longer resumes the old chat), drop the on-screen history, and go back to the
  // language/welcome screen. A fresh WebSocket with no conversation id means the
  // backend creates a new conversation on the next message.
  function handleReset() {
    clearStoredSession(orgId);
    wsRef.current?.close();
    if (typingTimer.current) { clearTimeout(typingTimer.current); typingTimer.current = null; }
    streamingMsgId.current = null;
    setMessages([]);
    setIsTyping(false);
    setIsSending(false);
    setInputValue("");
    setPhase("welcome");
    wsRef.current = new ChatWebSocket(
      apiBase,
      orgId,
      null,
      handleWsEvent,
      (conversationId) => saveConversationId(orgId, conversationId),
    );
  }

  return (
    <>
      {isOpen && (
        <ChatWindow
          config={initialConfig}
          phase={phase}
          lang={lang}
          messages={messages}
          isTyping={isTyping}
          inputValue={inputValue}
          isSending={isSending}
          consentAccepted={consentAccepted}
          onLangSelect={handleLangSelect}
          onPreChatSubmit={handlePreChatSubmit}
          onAcceptConsent={handleAcceptConsent}
          onInputChange={setInputValue}
          onSend={handleSend}
          onClose={() => setIsOpen(false)}
          onReset={handleReset}
          onSuggestion={handleSuggestion}
          onSlotSelect={handleSend}
        />
      )}
      <Launcher
        config={initialConfig}
        isOpen={isOpen}
        onClick={() => setIsOpen((v) => !v)}
      />
    </>
  );
}
