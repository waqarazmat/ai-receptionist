import { useEffect, useState, type FormEvent } from "react";
import { AxiosError } from "axios";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import { useInviteUser } from "../../api/users";
import { useOrganizations } from "../../api/organizations";

export interface InviteUserModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function InviteUserModal({ isOpen, onClose }: InviteUserModalProps) {
  const [email, setEmail] = useState("");
  const [orgId, setOrgId] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: organizations } = useOrganizations();
  const inviteUser = useInviteUser();

  useEffect(() => {
    if (isOpen) {
      setEmail("");
      setOrgId("");
      setErrorMessage(null);
    }
  }, [isOpen]);

  const orgOptions = (organizations ?? []).map((org) => ({ value: org.id, label: org.name }));

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setErrorMessage(null);
    inviteUser.mutate(
      { email: email.trim(), org_id: orgId },
      {
        onSuccess: onClose,
        onError: (err) => {
          if (err instanceof AxiosError) {
            const detail = (err.response?.data as { detail?: string } | undefined)?.detail;
            setErrorMessage(detail ?? "Something went wrong. Please try again.");
          } else {
            setErrorMessage("Something went wrong. Please try again.");
          }
        },
      },
    );
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Invite User">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="staff@example.com"
          required
          autoFocus
        />
        <Select
          label="Organization"
          value={orgId}
          onChange={(e) => setOrgId(e.target.value)}
          options={orgOptions}
          placeholder="Select an organization"
          required
        />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          The user will be created as <strong>org_staff</strong>. They can log in immediately by
          requesting an OTP with this email — we don&apos;t send an invite email from here.
        </p>
        {errorMessage && (
          <p className="text-sm text-rose-600 dark:text-rose-400">{errorMessage}</p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={inviteUser.isPending}>
            Invite User
          </Button>
        </div>
      </form>
    </Modal>
  );
}
