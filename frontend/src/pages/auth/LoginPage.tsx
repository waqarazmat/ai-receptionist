import { useState } from "react";
import { LoginForm } from "../../components/auth/LoginForm";
import { OTPVerify } from "../../components/auth/OTPVerify";

export default function LoginPage() {
  const [email, setEmail] = useState<string | null>(null);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-800/50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">AI Receptionist</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Sign in to your dashboard</p>
        </div>
        <div className="rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-8 shadow-sm">
          {email ? (
            <div className="space-y-4">
              <p className="text-sm text-emerald-600">
                If this email is registered, you&apos;ll receive a code.
              </p>
              <OTPVerify email={email} />
            </div>
          ) : (
            <LoginForm onOtpRequested={setEmail} />
          )}
        </div>
      </div>
    </div>
  );
}
