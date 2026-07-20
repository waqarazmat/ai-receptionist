import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { KeyRound } from "lucide-react";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { useVerifyOtp } from "../../api/auth";
import { useAuthStore } from "../../stores/auth-store";
import { decodeAccessToken } from "../../lib/utils";
import type { UserRole } from "../../types/auth";

export interface OTPVerifyProps {
  email: string;
}

const DASHBOARD_BY_ROLE: Record<UserRole, string> = {
  super_admin: "/admin/dashboard",
  org_staff: "/org/dashboard",
};

export function OTPVerify({ email }: OTPVerifyProps) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const verifyOtp = useVerifyOtp();
  const login = useAuthStore((state) => state.login);
  const navigate = useNavigate();

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setError(null);

    verifyOtp.mutate(
      { email, code },
      {
        onSuccess: (data) => {
          const payload = decodeAccessToken(data.access_token);
          login(
            { accessToken: data.access_token, refreshToken: data.refresh_token },
            { id: payload.sub, email, role: payload.role, org_id: payload.org_id },
          );
          navigate(DASHBOARD_BY_ROLE[payload.role], { replace: true });
        },
        onError: () => {
          setError("Invalid or expired code. Please try again.");
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label="Verification code"
        placeholder="000000"
        value={code}
        onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
        icon={<KeyRound className="h-4 w-4" />}
        error={error ?? undefined}
        inputMode="numeric"
        maxLength={6}
        autoFocus
        required
      />
      <Button type="submit" className="w-full" isLoading={verifyOtp.isPending} disabled={code.length !== 6}>
        Verify
      </Button>
    </form>
  );
}
