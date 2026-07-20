import { useMemo, useState } from "react";
import { Users } from "lucide-react";
import { useContacts } from "../../api/contacts";
import { DataTable, type DataTableColumn } from "../../components/shared/DataTable";
import { EmptyState } from "../../components/shared/EmptyState";
import { SearchInput } from "../../components/shared/SearchInput";
import { Spinner } from "../../components/ui/Spinner";
import { ContactDetailModal } from "../../features/contacts/ContactDetailModal";
import { formatDateTime } from "../../lib/utils";
import type { Contact } from "../../types/contact";

export default function ContactsPage() {
  const { data: contacts = [], isLoading } = useContacts();
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const filteredContacts = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return contacts;
    return contacts.filter((contact) =>
      [contact.name, contact.phone, contact.email].some((field) => field?.toLowerCase().includes(query)),
    );
  }, [contacts, search]);

  const columns: DataTableColumn<Contact>[] = [
    { header: "Name", accessor: (row) => row.name },
    { header: "Phone", accessor: (row) => row.phone ?? "—" },
    { header: "Email", accessor: (row) => row.email ?? "—" },
    { header: "Channel", accessor: (row) => <span className="capitalize">{row.channel}</span> },
    { header: "Conversations", accessor: (row) => row.conversation_count },
    {
      header: "Last Contact",
      accessor: (row) => (row.last_contact_at ? formatDateTime(row.last_contact_at) : "—"),
    },
  ];

  return (
    <div>
      <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Contacts</h2>

      <div className="mt-4 max-w-sm">
        <SearchInput value={search} onChange={setSearch} placeholder="Search by name, phone, or email…" />
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        ) : filteredContacts.length === 0 ? (
          <EmptyState
            icon={<Users className="h-10 w-10" />}
            title="No contacts found"
            description={search ? "Try a different search." : "Contacts will appear here once customers reach out."}
          />
        ) : (
          <DataTable
            columns={columns}
            data={filteredContacts}
            keyExtractor={(row) => row.id}
            onRowClick={(row) => setSelectedId(row.id)}
          />
        )}
      </div>

      <ContactDetailModal contactId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
