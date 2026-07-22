import { useEffect, useState, type FormEvent } from "react";
import { AxiosError } from "axios";
import { UserPlus } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { useInviteTeammate } from "../../api/team";

export interface InviteTeammateModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function InviteTeammateModal({ isOpen, onClose }: InviteTeammateModalProps) {
  const [email, setEmail] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inviteTeammate = useInviteTeammate();

  useEffect(() => {
    if (isOpen) {
      setEmail("");
      setErrorMessage(null);
    }
  }, [isOpen]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    inviteTeammate.mutate(
      { email: email.trim() },
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
    <Modal isOpen={isOpen} onClose={onClose} title="Invite a teammate">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Teammate email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="teammate@yourcompany.com"
          required
          autoFocus
        />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          They&apos;ll be added as an <strong>org staff</strong> member of your organization
          and can log in immediately by requesting a one-time code with this email.
        </p>
        {errorMessage && <p className="text-sm text-rose-600 dark:text-rose-400">{errorMessage}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={inviteTeammate.isPending}>
            <UserPlus className="h-4 w-4" />
            Send invite
          </Button>
        </div>
      </form>
    </Modal>
  );
}
