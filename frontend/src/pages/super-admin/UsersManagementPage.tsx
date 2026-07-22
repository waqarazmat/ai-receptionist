import { useMemo, useState } from "react";
import { AxiosError } from "axios";
import { Plus } from "lucide-react";
import { useOrganizations } from "../../api/organizations";
import { useUpdateUser, useUsers } from "../../api/users";
import { useAuthStore } from "../../stores/auth-store";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { DropdownMenu } from "../../components/ui/DropdownMenu";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { Skeleton } from "../../components/ui/Skeleton";
import { DataTable, type DataTableColumn } from "../../components/shared/DataTable";
import { SearchInput } from "../../components/shared/SearchInput";
import { InviteUserModal } from "../../features/users/InviteUserModal";
import { formatRelative } from "../../lib/format";
import type { User, UserListFilters, UserRole } from "../../types/user";

const ROLE_OPTIONS: { value: UserRole | ""; label: string }[] = [
  { value: "", label: "All roles" },
  { value: "super_admin", label: "Super Admin" },
  { value: "org_staff", label: "Org Staff" },
];

const STATUS_OPTIONS: { value: "" | "true" | "false"; label: string }[] = [
  { value: "", label: "All statuses" },
  { value: "true", label: "Active" },
  { value: "false", label: "Inactive" },
];

export default function UsersManagementPage() {
  const currentUser = useAuthStore((s) => s.user);

  const [q, setQ] = useState("");
  const [orgId, setOrgId] = useState<string>("");
  const [role, setRole] = useState<"" | UserRole>("");
  const [active, setActive] = useState<"" | "true" | "false">("");

  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [pendingToggle, setPendingToggle] = useState<User | null>(null);
  const [toggleError, setToggleError] = useState<string | null>(null);

  // Debounced/naive: memoize the filter object so referential equality drives
  // the query-key. For MVP without debouncing this refires on every keystroke
  // — fine for the current scale (typically <100 users total).
  const filters = useMemo<UserListFilters>(
    () => ({
      q: q.trim() || undefined,
      org_id: orgId || undefined,
      role: (role || undefined) as UserRole | undefined,
      is_active: active === "" ? undefined : active === "true",
    }),
    [q, orgId, role, active],
  );

  const { data: users, isLoading } = useUsers(filters);
  const { data: organizations } = useOrganizations();

  const updateUser = useUpdateUser(pendingToggle?.id ?? "");

  const orgOptions = useMemo(
    () => [{ value: "", label: "All organizations" }, ...(organizations ?? []).map((o) => ({ value: o.id, label: o.name }))],
    [organizations],
  );

  const columns: DataTableColumn<User>[] = [
    {
      header: "Email",
      accessor: (u) => (
        <div>
          <p className="font-medium text-slate-900 dark:text-slate-100">{u.email}</p>
          {u.id === currentUser?.id && (
            <p className="text-xs text-indigo-500 dark:text-indigo-400">You</p>
          )}
        </div>
      ),
    },
    {
      header: "Organization",
      accessor: (u) => (
        <span className="text-slate-700 dark:text-slate-300">
          {u.org_name ?? <span className="text-slate-400 dark:text-slate-500">—</span>}
        </span>
      ),
    },
    {
      header: "Role",
      accessor: (u) => (
        <Badge variant={u.role === "super_admin" ? "info" : "neutral"}>
          {u.role === "super_admin" ? "Super Admin" : "Org Staff"}
        </Badge>
      ),
    },
    {
      header: "Status",
      accessor: (u) => (
        <Badge variant={u.is_active ? "success" : "danger"}>{u.is_active ? "Active" : "Inactive"}</Badge>
      ),
    },
    { header: "Last Login", accessor: (u) => formatRelative(u.last_login) },
    { header: "Created", accessor: (u) => new Date(u.created_at).toLocaleDateString() },
    {
      header: "Actions",
      className: "text-right",
      accessor: (u) => {
        // Self-actions are hidden entirely: the backend enforces the same
        // rule and would return 400, but hiding the menu item is clearer UX
        // than showing an item that fails on click.
        const isSelf = u.id === currentUser?.id;
        return (
          <div className="flex items-center justify-end gap-2 opacity-100 transition-opacity duration-150 md:opacity-0 md:group-hover:opacity-100 md:focus-within:opacity-100">
            {!isSelf && (
              <DropdownMenu
                items={[
                  {
                    label: u.is_active ? "Deactivate" : "Reactivate",
                    danger: u.is_active,
                    onClick: () => {
                      setToggleError(null);
                      setPendingToggle(u);
                    },
                  },
                ]}
              />
            )}
          </div>
        );
      },
    },
  ];

  const confirmToggle = () => {
    if (!pendingToggle) return;
    updateUser.mutate(
      { is_active: !pendingToggle.is_active },
      {
        onSuccess: () => setPendingToggle(null),
        onError: (err) => {
          if (err instanceof AxiosError) {
            const detail = (err.response?.data as { detail?: string } | undefined)?.detail;
            setToggleError(detail ?? "Something went wrong. Please try again.");
          } else {
            setToggleError("Something went wrong. Please try again.");
          }
        },
      },
    );
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Users</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Manage staff accounts across every organization on the platform.
          </p>
        </div>
        <Button onClick={() => setIsInviteOpen(true)}>
          <Plus className="h-4 w-4" />
          Invite User
        </Button>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-4">
        <SearchInput value={q} onChange={setQ} placeholder="Search by email..." />
        <Select value={orgId} onChange={(e) => setOrgId(e.target.value)} options={orgOptions} />
        <Select
          value={role}
          onChange={(e) => setRole((e.target.value as UserRole) || "")}
          options={ROLE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
        />
        <Select
          value={active}
          onChange={(e) => setActive((e.target.value as "" | "true" | "false") || "")}
          options={STATUS_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
        />
      </div>

      {isLoading ? (
        <div className="space-y-px overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-4 bg-slate-50 px-4 py-3 dark:bg-slate-800/50">
            <Skeleton className="h-3 w-40" />
          </div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center justify-between px-4 py-4">
              <div className="space-y-2">
                <Skeleton className="h-4 w-56" />
                <Skeleton className="h-3 w-32" />
              </div>
              <Skeleton className="h-6 w-24 rounded-full" />
            </div>
          ))}
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={users ?? []}
          keyExtractor={(u) => u.id}
          emptyMessage="No users match these filters."
        />
      )}

      <InviteUserModal isOpen={isInviteOpen} onClose={() => setIsInviteOpen(false)} />

      <Modal
        isOpen={pendingToggle !== null}
        onClose={() => {
          setPendingToggle(null);
          setToggleError(null);
        }}
        title={pendingToggle?.is_active ? "Deactivate User" : "Reactivate User"}
      >
        {pendingToggle && (
          <>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {pendingToggle.is_active ? (
                <>
                  Deactivate <strong>{pendingToggle.email}</strong>? They will no longer be able to log in.
                  This does not delete their data — you can reactivate them later.
                </>
              ) : (
                <>
                  Reactivate <strong>{pendingToggle.email}</strong>? They will be able to log in again immediately.
                </>
              )}
            </p>
            {toggleError && (
              <p className="mt-3 text-sm text-rose-600 dark:text-rose-400">{toggleError}</p>
            )}
            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  setPendingToggle(null);
                  setToggleError(null);
                }}
              >
                Cancel
              </Button>
              <Button
                variant={pendingToggle.is_active ? "danger" : "primary"}
                isLoading={updateUser.isPending}
                onClick={confirmToggle}
              >
                {pendingToggle.is_active ? "Deactivate" : "Reactivate"}
              </Button>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
