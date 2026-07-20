import { useState, type FormEvent } from "react";
import { Mail } from "lucide-react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { useRequestOtp } from "../../api/auth";

export interface LoginFormProps {
  onOtpRequested: (email: string) => void;
}

export function LoginForm({ onOtpRequested }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const requestOtp = useRequestOtp();

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    // Always move to the OTP step, whether the request succeeded, the email
    // doesn't exist, or it's rate-limited — matching the backend's
    // email-enumeration-prevention response. The success message itself is
    // rendered by LoginPage so it survives this component unmounting.
    requestOtp.mutate(
      { email },
      {
        onSettled: () => onOtpRequested(email),
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        type="email"
        label="Work email"
        placeholder="you@company.com"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        icon={<Mail className="h-4 w-4" />}
        autoFocus
        required
      />
      <Button type="submit" className="w-full" isLoading={requestOtp.isPending} disabled={!email}>
        Send code
      </Button>
    </form>
  );
}
