import type { WidgetConfig } from "./types.js";
import { API_BASE } from "./types.js";
import type { ChatWebSocket } from "./ws.js";

export async function fetchConfig(orgId: string, apiBase = API_BASE): Promise<WidgetConfig> {
  const res = await fetch(`${apiBase}/api/public/webchat/${orgId}/config`);
  if (!res.ok) throw new Error(`Config fetch failed: ${res.status}`);
  return res.json() as Promise<WidgetConfig>;
}

/** Sending is a Socket.IO emit (see ws.ts), not a REST call — the real
 * backend has no REST message endpoint. Kept as an async function (rather
 * than inlining `ws.send(...)` at the one call site in app.tsx) so that
 * call site doesn't need to change beyond its arguments. */
export async function sendMessage(ws: ChatWebSocket, body: string): Promise<void> {
  ws.send({ message: body });
}

/** No backend concept of per-conversation locale (see app/channels/webchat/
 * handler.py — no locale field anywhere) — no-op so the language picker UI
 * still works (it still switches which `greetingByLang` entry displays),
 * it just doesn't sync anywhere server-side. */
export async function updateLocale(_apiBase: string, _orgId: string, _lang: string): Promise<void> {
  return;
}

/** No backend concept of visitor identification (email capture) either —
 * see WidgetConfigResponse.preChatFormEnabled, always false, so the
 * pre-chat form this would back is never actually shown. Kept as a no-op
 * rather than removed so app.tsx's call site needs no changes if that
 * changes later. */
export async function identifyVisitor(_apiBase: string, _orgId: string, _email: string, _name?: string): Promise<void> {
  return;
}

export interface HistoryMessage {
  id: string;
  direction: "inbound" | "outbound";
  body: string | null;
  createdAt: unknown;
  status: string | null;
}

export async function loadHistory(apiBase: string, orgId: string, conversationId: string): Promise<HistoryMessage[]> {
  const res = await fetch(`${apiBase}/api/public/webchat/${orgId}/conversations/${conversationId}/messages`);
  if (!res.ok) return [];
  const data = (await res.json()) as { messages?: HistoryMessage[] };
  return data.messages ?? [];
}
