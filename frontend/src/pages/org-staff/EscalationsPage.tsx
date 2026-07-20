import { useNavigate } from "react-router-dom";
import { useEscalations, usePickUpEscalation } from "../../api/escalations";
import { DataTable, type DataTableColumn } from "../../components/shared/DataTable";
import { EscalationPriorityBadge } from "../../components/shared/StatusBadge";
import { Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Spinner";
import { formatRelativeTime } from "../../lib/utils";
import type { Escalation } from "../../types/escalation";

function PickUpButton({ escalation, onPickedUp }: { escalation: Escalation; onPickedUp: (conversationId: string) => void }) {
  const pickUp = usePickUpEscalation(escalation.id);

  if (escalation.status !== "pending") {
    return <span className="text-xs text-slate-400 dark:text-slate-500">Picked up</span>;
  }

  return (
    <Button
      size="sm"
      variant="secondary"
      isLoading={pickUp.isPending}
      onClick={(e) => {
        e.stopPropagation();
        pickUp.mutate(undefined, { onSuccess: () => onPickedUp(escalation.conversation_id) });
      }}
    >
      Pick Up
    </Button>
  );
}

export default function EscalationsPage() {
  const { data: escalations, isLoading, isError } = useEscalations();
  const navigate = useNavigate();

  function openInInbox(escalation: Escalation) {
    navigate(`/org/inbox?conversation=${escalation.conversation_id}`);
  }

  const columns: DataTableColumn<Escalation>[] = [
    { header: "Conversation", accessor: (row) => row.contact_name },
    { header: "Reason", accessor: (row) => <span className="line-clamp-1">{row.reason}</span> },
    { header: "Priority", accessor: (row) => <EscalationPriorityBadge priority={row.priority} /> },
    { header: "Escalated", accessor: (row) => formatRelativeTime(row.created_at) },
    {
      header: "",
      accessor: (row) => (
        <PickUpButton escalation={row} onPickedUp={(conversationId) => navigate(`/org/inbox?conversation=${conversationId}`)} />
      ),
      className: "text-right",
    },
  ];

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (isError) {
    return <p className="text-sm text-red-600 dark:text-red-400">Failed to load escalations.</p>;
  }

  return (
    <div>
      <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Escalations</h2>
      <div className="mt-6">
        <DataTable
          columns={columns}
          data={escalations ?? []}
          keyExtractor={(row) => row.id}
          onRowClick={openInInbox}
          emptyMessage="No pending escalations."
        />
      </div>
    </div>
  );
}
