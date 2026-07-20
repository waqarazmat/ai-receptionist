import { create } from "zustand";

export type StatusFilter = "all" | "active" | "escalated" | "resolved";

interface InboxStore {
  selectedConversationId: string | null;
  statusFilter: StatusFilter;
  searchQuery: string;
  typingByConversation: Record<string, boolean>;
  setSelectedConversation: (id: string | null) => void;
  setFilter: (filter: StatusFilter) => void;
  setSearch: (query: string) => void;
  setTyping: (conversationId: string, isTyping: boolean) => void;
}

export const useInboxStore = create<InboxStore>((set) => ({
  selectedConversationId: null,
  statusFilter: "all",
  searchQuery: "",
  typingByConversation: {},
  setSelectedConversation: (id) => set({ selectedConversationId: id }),
  setFilter: (filter) => set({ statusFilter: filter }),
  setSearch: (query) => set({ searchQuery: query }),
  setTyping: (conversationId, isTyping) =>
    set((state) => ({
      typingByConversation: { ...state.typingByConversation, [conversationId]: isTyping },
    })),
}));
