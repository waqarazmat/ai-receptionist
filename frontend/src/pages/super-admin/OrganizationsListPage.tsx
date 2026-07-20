import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { apiClient } from "../../api/client";
import { useDeleteOrganization, useOrganizations } from "../../api/organizations";
import { Button } from "../../components/ui/Button";
import { DropdownMenu } from "../../components/ui/DropdownMenu";
import { Modal } from "../../components/ui/Modal";
import { Skeleton } from "../../components/ui/Skeleton";
import { DataTable, type DataTableColumn } from "../../components/shared/DataTable";
import { StatusBadge, type SetupStatus } from "../../components/shared/StatusBadge";
import { OrganizationFormModal } from "../../features/organizations/OrganizationFormModal";
import type { Organization } from "../../types/organization";
import { WIZARD_STEP_KEYS, type SetupStateResponse } from "../../types/setup-wizard";

function useSetupStatuses(organizations: Organization[]) {
  const queries = useQueries({
    queries: organizations.map((org) => ({
      queryKey: ["setup-wizard", org.id],
      queryFn: () =>
        apiClient.get<SetupStateResponse>(`/api/admin/organizations/${org.id}/setup`).then((r) => r.data),
      enabled: !org.setup_completed,
      staleTime: 30_000,
    })),
  });

  const statusByOrgId = new Map<string, SetupStatus>();
  organizations.forEach((org, index) => {
    if (org.setup_completed) {
      statusByOrgId.set(org.id, "complete");
      return;
    }
    const progress = queries[index]?.data?.setup_progress;
    const anyStepDone = progress ? WIZARD_STEP_KEYS.some((key) => progress[key]) : false;
    statusByOrgId.set(org.id, anyStepDone ? "in_progress" : "not_started");
  });
  return statusByOrgId;
}

export default function OrganizationsListPage() {
  const navigate = useNavigate();
  const { data: organizations, isLoading } = useOrganizations();
  const deleteOrg = useDeleteOrganization();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingOrg, setEditingOrg] = useState<Organization | null>(null);
  const [deletingOrg, setDeletingOrg] = useState<Organization | null>(null);

  const statusByOrgId = useSetupStatuses(organizations ?? []);

  const columns: DataTableColumn<Organization>[] = [
    {
      header: "Name",
      accessor: (org) => (
        <div>
          <p className="font-medium text-slate-900 dark:text-slate-100">{org.name}</p>
          <p className="text-xs text-slate-400 dark:text-slate-500">{org.slug}</p>
        </div>
      ),
    },
    { header: "Industry", accessor: (org) => org.industry },
    { header: "Messages", accessor: (org) => org.message_count },
    { header: "Escalations", accessor: (org) => org.escalation_count },
    {
      header: "Setup Status",
      accessor: (org) => <StatusBadge status={statusByOrgId.get(org.id) ?? "not_started"} />,
    },
    {
      header: "Actions",
      className: "text-right",
      accessor: (org) => (
        <div className="flex items-center justify-end gap-2 opacity-100 transition-opacity duration-150 md:opacity-0 md:group-hover:opacity-100 md:focus-within:opacity-100">
          <Button size="sm" variant="secondary" onClick={() => navigate(`/admin/organizations/${org.id}/setup`)}>
            {org.setup_completed ? "Configure" : "Setup"}
          </Button>
          {org.setup_completed && (
            <Button size="sm" variant="ghost" onClick={() => navigate(`/admin/organizations/${org.id}/test`)}>
              Test
            </Button>
          )}
          <DropdownMenu
            items={[
              { label: "View Details", onClick: () => navigate(`/admin/organizations/${org.id}`) },
              { label: "Edit", onClick: () => setEditingOrg(org) },
              { label: "Delete", danger: true, onClick: () => setDeletingOrg(org) },
            ]}
          />
        </div>
      ),
    },
  ];

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Organizations</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Manage every client organization on the platform.</p>
        </div>
        <Button onClick={() => setIsCreateOpen(true)}>
          <Plus className="h-4 w-4" />
          Add Organization
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-px overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
          <div className="flex items-center gap-4 bg-slate-50 dark:bg-slate-800/50 px-4 py-3">
            <Skeleton className="h-3 w-40" />
          </div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-4">
              <div className="space-y-2">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-24" />
              </div>
              <Skeleton className="h-6 w-24 rounded-full" />
            </div>
          ))}
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={organizations ?? []}
          keyExtractor={(org) => org.id}
          emptyMessage="No organizations yet. Add your first one to get started."
        />
      )}

      <OrganizationFormModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />
      <OrganizationFormModal
        isOpen={editingOrg !== null}
        onClose={() => setEditingOrg(null)}
        organization={editingOrg ?? undefined}
      />

      <Modal
        isOpen={deletingOrg !== null}
        onClose={() => setDeletingOrg(null)}
        title="Delete Organization"
      >
        <p className="text-sm text-slate-600 dark:text-slate-300">
          Deactivate <strong>{deletingOrg?.name}</strong>? This does not remove any data — it can be
          reactivated later.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setDeletingOrg(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            isLoading={deleteOrg.isPending}
            onClick={() =>
              deletingOrg &&
              deleteOrg.mutate(deletingOrg.id, {
                onSuccess: () => setDeletingOrg(null),
              })
            }
          >
            Delete
          </Button>
        </div>
      </Modal>
    </div>
  );
}
