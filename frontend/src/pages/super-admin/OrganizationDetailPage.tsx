import { useNavigate, useParams } from "react-router-dom";
import { useOrganization } from "../../api/organizations";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Spinner } from "../../components/ui/Spinner";

export default function OrganizationDetailPage() {
  const { orgId = "" } = useParams();
  const navigate = useNavigate();
  const { data: org, isLoading } = useOrganization(orgId);

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (!org) {
    return <p className="text-sm text-red-600 dark:text-red-400">Organization not found.</p>;
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">{org.name}</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{org.slug}</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={org.is_active ? "success" : "neutral"}>
            {org.is_active ? "Active" : "Inactive"}
          </Badge>
          <Button onClick={() => navigate(`/admin/organizations/${org.id}/setup`)}>
            {org.setup_completed ? "Configure" : "Setup"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card title="Overview">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Industry</dt>
              <dd className="text-slate-900 dark:text-slate-100">{org.industry}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Timezone</dt>
              <dd className="text-slate-900 dark:text-slate-100">{org.timezone}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Contact Email</dt>
              <dd className="text-slate-900 dark:text-slate-100">{org.email ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Phone</dt>
              <dd className="text-slate-900 dark:text-slate-100">{org.phone ?? "—"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Address</dt>
              <dd className="text-slate-900 dark:text-slate-100">{org.address ?? "—"}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Activity">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Messages</dt>
              <dd className="text-slate-900 dark:text-slate-100">{org.message_count}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Escalations</dt>
              <dd className="text-slate-900 dark:text-slate-100">{org.escalation_count}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500 dark:text-slate-400">Trial</dt>
              <dd className="text-slate-900 dark:text-slate-100">{org.is_trial ? "Yes" : "No"}</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
