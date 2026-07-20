import { io, type Socket } from "socket.io-client";

let staffSocket: Socket | null = null;
let widgetSocket: Socket | null = null;

export function connectStaffSocket(token: string, orgId: string): Socket {
  staffSocket?.disconnect();

  // /inbox runs on its own Engine.IO mount (see backend socket_manager.py)
  // so it can keep a CORS_ORIGINS-restricted policy separate from the
  // widget's wide-open /chat mount.
  const socket = io(`${import.meta.env.VITE_SOCKET_URL}/inbox`, {
    path: "/socket.io-inbox/",
    auth: { token },
    transports: ["polling", "websocket"],
  });

  socket.on("connect", () => {
    socket.emit("join_org_room", { org_id: orgId });
  });

  staffSocket = socket;
  return socket;
}

export function getStaffSocket(): Socket | null {
  return staffSocket;
}

export function disconnectStaffSocket(): void {
  staffSocket?.disconnect();
  staffSocket = null;
}

export function connectWidgetSocket(orgId: string, sessionToken?: string | null): Socket {
  widgetSocket?.disconnect();

  const socket = io(`${import.meta.env.VITE_SOCKET_URL}/chat`, {
    auth: { org_id: orgId, conversation_id: sessionToken ?? undefined },
    transports: ["polling", "websocket"],
  });

  // See widget/src/socket.ts for why this join round-trip happens after
  // connect rather than during the handshake itself.
  socket.on("connect", () => {
    socket.emit("join");
  });

  widgetSocket = socket;
  return socket;
}

export function getWidgetSocket(): Socket | null {
  return widgetSocket;
}

export function disconnectWidgetSocket(): void {
  widgetSocket?.disconnect();
  widgetSocket = null;
}
