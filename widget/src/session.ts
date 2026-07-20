const STORAGE_KEY = (orgId: string) => `_cw_conversation_${orgId}`;

/** The real backend has no separate "session" concept — a conversation_id
 * (created by the server on first Socket.IO connect, see webchat/handler.py)
 * IS the session. Persisting just that id is enough to resume: reconnecting
 * with the same conversation_id in the Socket.IO auth payload rejoins the
 * same conversation and its room. */
export function loadStoredConversationId(orgId: string): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY(orgId));
  } catch {
    return null;
  }
}

export function saveConversationId(orgId: string, conversationId: string): void {
  try {
    localStorage.setItem(STORAGE_KEY(orgId), conversationId);
  } catch {
    /* storage full or unavailable */
  }
}

export function clearStoredSession(orgId: string): void {
  try {
    localStorage.removeItem(STORAGE_KEY(orgId));
  } catch {
    /* ignore */
  }
}
