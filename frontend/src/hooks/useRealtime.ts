import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Socket } from "socket.io-client";
import { useInboxStore } from "../stores/inbox-store";
import { useToastStore } from "../stores/toast-store";
import type { MessageRole } from "../types/message";

interface NewMessagePayload {
  conversation_id: string;
  role: MessageRole;
  content: string;
}

interface EscalationCreatedPayload {
  escalation_id: string;
  conversation_id: string;
  reason: string;
  priority: string;
}

interface EscalationPickedUpPayload {
  escalation_id: string;
  conversation_id: string;
}

interface TypingIndicatorPayload {
  conversation_id: string;
  is_typing: boolean;
}

export function useRealtime(socket: Socket | null): void {
  const queryClient = useQueryClient();
  const selectedConversationId = useInboxStore((state) => state.selectedConversationId);
  const setTyping = useInboxStore((state) => state.setTyping);
  const addToast = useToastStore((state) => state.addToast);

  useEffect(() => {
    if (!socket) return;

    function handleNewMessage(payload: NewMessagePayload) {
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
      if (payload.conversation_id === selectedConversationId) {
        queryClient.invalidateQueries({ queryKey: ["conversations", payload.conversation_id, "messages"] });
      }
    }

    function handleEscalationCreated(payload: EscalationCreatedPayload) {
      queryClient.invalidateQueries({ queryKey: ["escalations"] });
      addToast({
        variant: "warning",
        title: "New escalation",
        description: payload.reason,
      });
    }

    function handleEscalationPickedUp(_payload: EscalationPickedUpPayload) {
      queryClient.invalidateQueries({ queryKey: ["escalations"] });
    }

    function handleTypingIndicator(payload: TypingIndicatorPayload) {
      setTyping(payload.conversation_id, payload.is_typing);
    }

    socket.on("new_message", handleNewMessage);
    socket.on("escalation_created", handleEscalationCreated);
    socket.on("escalation_picked_up", handleEscalationPickedUp);
    socket.on("typing_indicator", handleTypingIndicator);

    return () => {
      socket.off("new_message", handleNewMessage);
      socket.off("escalation_created", handleEscalationCreated);
      socket.off("escalation_picked_up", handleEscalationPickedUp);
      socket.off("typing_indicator", handleTypingIndicator);
    };
  }, [socket, queryClient, selectedConversationId, setTyping, addToast]);
}
