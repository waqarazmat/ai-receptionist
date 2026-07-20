import { useEffect, useState } from "react";
import type { Socket } from "socket.io-client";
import { connectStaffSocket, disconnectStaffSocket } from "../lib/socket";

export function useSocket(token: string | null, orgId: string | null): Socket | null {
  const [socket, setSocket] = useState<Socket | null>(null);

  useEffect(() => {
    if (!token || !orgId) {
      setSocket(null);
      return;
    }

    const instance = connectStaffSocket(token, orgId);
    setSocket(instance);

    return () => {
      disconnectStaffSocket();
      setSocket(null);
    };
  }, [token, orgId]);

  return socket;
}
