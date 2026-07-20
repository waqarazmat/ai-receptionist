import { useQuery } from "@tanstack/react-query";
import { apiClient } from "./client";
import type { Contact, ContactDetail } from "../types/contact";

const contactsKey = (search?: string) => ["contacts", search ?? ""] as const;
const contactKey = (id: string) => ["contacts", "detail", id] as const;

export function useContacts(search?: string) {
  return useQuery({
    queryKey: contactsKey(search),
    queryFn: () =>
      apiClient
        .get<{ contacts: Contact[] }>("/api/org/contacts", { params: search ? { search } : undefined })
        .then((r) => r.data.contacts),
  });
}

export function useContact(id: string | null) {
  return useQuery({
    queryKey: contactKey(id ?? ""),
    queryFn: () => apiClient.get<ContactDetail>(`/api/org/contacts/${id}`).then((r) => r.data),
    enabled: Boolean(id),
  });
}
