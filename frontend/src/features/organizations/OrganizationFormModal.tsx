import { useEffect, useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useCreateOrganization, useUpdateOrganization } from "../../api/organizations";
import type { Organization } from "../../types/organization";

export interface OrganizationFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  organization?: Organization;
}

export function OrganizationFormModal({ isOpen, onClose, organization }: OrganizationFormModalProps) {
  const isEditing = Boolean(organization);
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [timezone, setTimezone] = useState("");

  const createOrg = useCreateOrganization();
  const updateOrg = useUpdateOrganization(organization?.id ?? "");
  const mutation = isEditing ? updateOrg : createOrg;

  useEffect(() => {
    if (isOpen) {
      setName(organization?.name ?? "");
      setIndustry(organization?.industry ?? "");
      setTimezone(organization?.timezone ?? "");
    }
  }, [isOpen, organization]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate({ name, industry, timezone }, { onSuccess: onClose });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={isEditing ? "Edit Organization" : "Add Organization"}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        <Input label="Industry" value={industry} onChange={(e) => setIndustry(e.target.value)} required />
        <Input
          label="Timezone"
          placeholder="America/New_York"
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          required
        />
        {mutation.isError && <p className="text-sm text-red-600 dark:text-red-400">Something went wrong. Please try again.</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={mutation.isPending}>
            {isEditing ? "Save Changes" : "Create Organization"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
