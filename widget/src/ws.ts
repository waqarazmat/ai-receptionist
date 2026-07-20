import { io, type Socket } from "socket.io-client";

export interface WsEvent {
  v: number;
  type: "message" | "message.delta" | "message.delta.abort" | "typing" | "status" | "connected" | "ready" | "pong";
  conversationId?: string;
  messageId?: string;
  body?: string;
  interactive?: {
    type: "list" | "button";
    body?: { text?: string };
    action?: {
      buttons?: Array<{ reply?: { title?: string } }>;
      sections?: Array<{ rows?: Array<{ id?: string; title?: string; description?: string }> }>;
    };
  };
  direction?: "inbound" | "outbound";
  sender?: "ai" | "agent" | "visitor" | "staff" | "system";
  lang?: string;
  ts?: string;
  replayed?: boolean;
  status?: string;
  streaming?: boolean;
}

type EventHandler = (evt: WsEvent) => void;

/**
 * Adapts the real backend's Socket.IO `/chat` namespace (see
 * app/channels/webchat/handler.py + app/realtime/socket_manager.py) to the
 * WsEvent shape the rest of this widget (app.tsx, MessageBubble) already
 * understands, so nothing above this module needs to know the backend
 * speaks Socket.IO rather than the raw-WebSocket protocol this widget was
 * originally built against. `response_token` events are accumulated and
 * replayed as a single synthetic `message` event on `response_complete`,
 * since the real backend never sends a separate "final committed message"
 * frame the way the original protocol did — the client already has the
 * full text from the deltas.
 */
export class ChatWebSocket {
  private socket: Socket;
  private closed = false;
  private conversationId: string | null;
  private streamingBuffer = "";

  constructor(
    apiBase: string,
    private readonly orgId: string,
    conversationId: string | null,
    private readonly onEvent: EventHandler,
    private readonly onOpen?: (conversationId: string) => void,
  ) {
    this.conversationId = conversationId;

    this.socket = io(`${apiBase}/chat`, {
      // Callback-style function form (not a plain object) so a reconnect
      // re-reads this.conversationId — important once the first `connected`
      // event has resolved a real id, so a reconnect resumes the same
      // conversation instead of starting a new one. socket.io-client calls
      // this with a callback rather than reading a return value — a plain
      // `() => ({...})` silently sends no auth payload at all.
      auth: (cb: (data: object) => void) =>
        cb({ org_id: this.orgId, conversation_id: this.conversationId ?? undefined }),
      transports: ["websocket", "polling"],
    });

    this.socket.on("connect", () => {
      this.socket.emit("join");
    });

    this.socket.on("connected", (data: { conversation_id: string }) => {
      this.conversationId = data.conversation_id;
      this.onOpen?.(data.conversation_id);
    });

    this.socket.on("response_token", (data: { token: string }) => {
      this.streamingBuffer += data.token;
      this.onEvent({ v: 1, type: "message.delta", body: data.token });
    });

    this.socket.on("response_complete", () => {
      const body = this.streamingBuffer;
      this.streamingBuffer = "";
      this.onEvent({
        v: 1,
        type: "message",
        direction: "inbound",
        sender: "ai",
        body,
        messageId: `ai-${Date.now()}`,
        ts: new Date().toISOString(),
      });
    });

    this.socket.on("staff_message", (data: { content: string }) => {
      this.onEvent({
        v: 1,
        type: "message",
        direction: "outbound",
        sender: "staff",
        body: data.content,
        messageId: `staff-${Date.now()}`,
        ts: new Date().toISOString(),
      });
    });

    this.socket.on("takeover_event", () => {
      this.onEvent({
        v: 1,
        type: "message",
        direction: "inbound",
        sender: "system",
        body: "",
        messageId: `takeover-${Date.now()}`,
        ts: new Date().toISOString(),
      });
    });
  }

  /** Sends a customer message. The only inbound event this widget's UI
   * actually triggers — everything else (ping/hello/replay) was specific
   * to the original raw-WebSocket protocol and has no equivalent needed
   * here, since socket.io-client already handles reconnection + liveness. */
  send(data: { message?: string }): void {
    if (this.closed) return;
    const message = data["message"];
    if (typeof message === "string" && message.length > 0) {
      this.socket.emit("send_message", { message });
    }
  }

  close(): void {
    this.closed = true;
    this.socket.disconnect();
  }
}
