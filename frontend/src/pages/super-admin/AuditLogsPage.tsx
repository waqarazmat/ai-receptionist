import { useState } from "react";
import { ChevronLeft, ChevronRight, ScrollText } from "lucide-react";
import { useAuditLogs } from "../../api/audit-logs";
import { DataTable, type DataTableColumn } from "../../components/shared/DataTable";
import { EmptyState } from "../../components/shared/EmptyState";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Spinner } from "../../components/ui/Spinner";
import { formatActionLabel, formatDateTime } from "../../lib/utils";
import type { AuditLogEntry } from "../../types/audit-log";

const PAGE_SIZE = 25;

export default function AuditLogsPage() {
  const [action, setAction] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useAuditLogs({
    action: action.trim(),
    start_date: startDate ? new Date(startDate).toISOString() : undefined,
    // Inclusive of the whole end day, not just midnight.
    end_date: endDate ? new Date(`${endDate}T23:59:59.999`).toISOString() : undefined,
    page,
    page_size: PAGE_SIZE,
  });

  function updateFilter(setter: (value: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  const columns: DataTableColumn<AuditLogEntry>[] = [
    { header: "Action", accessor: (row) => formatActionLabel(row.action) },
    { header: "Target", accessor: (row) => row.target_type },
    {
      header: "Details",
      accessor: (row) => (
        <span className="line-clamp-1 text-xs text-slate-500 dark:text-slate-400">
          {Object.keys(row.details).length > 0 ? JSON.stringify(row.details) : "—"}
        </span>
      ),
    },
    { header: "IP Address", accessor: (row) => row.ip_address ?? "—" },
    { header: "When", accessor: (row) => formatDateTime(row.created_at) },
  ];

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div>
      <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Audit Logs</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Every super-admin action, in order.</p>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <Input
          label="Action"
          placeholder="e.g. create_organization"
          value={action}
          onChange={(e) => updateFilter(setAction, e.target.value)}
          className="w-56"
        />
        <Input
          label="From"
          type="date"
          value={startDate}
          onChange={(e) => updateFilter(setStartDate, e.target.value)}
          className="w-40"
        />
        <Input
          label="To"
          type="date"
          value={endDate}
          onChange={(e) => updateFilter(setEndDate, e.target.value)}
          className="w-40"
        />
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Spinner />
          </div>
        ) : isError ? (
          <p className="text-sm text-red-600 dark:text-red-400">Failed to load audit logs.</p>
        ) : !data || data.entries.length === 0 ? (
          <EmptyState
            icon={<ScrollText className="h-10 w-10" />}
            title="No audit log entries"
            description="Nothing matches the current filters."
          />
        ) : (
          <>
            <DataTable columns={columns} data={data.entries} keyExtractor={(row) => row.id} />
            <div className="mt-3 flex items-center justify-between">
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {data.total} entr{data.total === 1 ? "y" : "ies"} · page {page} of {totalPages}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Prev
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
