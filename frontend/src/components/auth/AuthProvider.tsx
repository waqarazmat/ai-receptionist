import { useEffect, useState, type ReactNode } from "react";
import axios from "axios";
import { Spinner } from "../ui/Spinner";
import { useAuthStore, getStoredRefreshToken, getStoredUserEmail } from "../../stores/auth-store";
import { decodeAccessToken } from "../../lib/utils";
import type { AccessTokenResponse } from "../../types/auth";

export interface AuthProviderProps {
  children: ReactNode;
}

// Runs once at app startup, before any route renders: if a refresh token
// survived from a previous session (localStorage), silently exchange it for
// a fresh access token so a hard reload doesn't bounce the user to /login.
// Gating the whole route tree behind `checked` avoids ProtectedRoute
// flashing a redirect to /login for a split second while this is in flight
// (isAuthenticated starts false on every fresh page load).
//
// Uses a raw axios call rather than apiClient, same reasoning as
// api/client.ts's own refreshAccessToken: apiClient's response interceptor
// would try to refresh-on-401 too, and at this point the store has no
// refresh token yet to feed it — recursive and unnecessary either way.
export function AuthProvider({ children }: AuthProviderProps) {
  const [checked, setChecked] = useState(false);
  const login = useAuthStore((state) => state.login);
  const logout = useAuthStore((state) => state.logout);

  useEffect(() => {
    const refreshToken = getStoredRefreshToken();
    const email = getStoredUserEmail();

    if (!refreshToken) {
      setChecked(true);
      return;
    }
    if (!email) {
      // Shouldn't happen — login() always writes both keys together — but if
      // storage is somehow half-written, there's no way to rebuild a valid
      // User, so treat it as corrupt state and clear it.
      logout();
      setChecked(true);
      return;
    }

    axios
      .post<AccessTokenResponse>(`${import.meta.env.VITE_API_URL}/api/auth/refresh`, {
        refresh_token: refreshToken,
      })
      .then((response) => {
        const payload = decodeAccessToken(response.data.access_token);
        login(
          { accessToken: response.data.access_token, refreshToken },
          { id: payload.sub, email, role: payload.role, org_id: payload.org_id },
        );
      })
      .catch(() => {
        // Expired or invalid — clear the dead refresh token so this doesn't
        // retry forever on every future load.
        logout();
      })
      .finally(() => setChecked(true));
    // Intentionally empty deps — a one-time startup check, not something
    // that should re-run when the store changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!checked) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Spinner size="lg" />
      </div>
    );
  }

  return <>{children}</>;
}
