import { create } from "zustand";
import type { User } from "../types/auth";

interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

interface AuthStore {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login: (tokens: AuthTokens, user: User) => void;
  logout: () => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
}

// Deliberate, narrow exception to this project's default "no localStorage"
// rule (frontend/CLAUDE.md): the refresh token is long-lived (7 days) and
// must survive a hard reload or closed tab, or every refresh logs the user
// out. The access token itself stays in-memory only (short-lived, 30 min —
// losing it on reload is fine, since AuthProvider silently exchanges the
// stored refresh token for a fresh one at startup).
const REFRESH_TOKEN_KEY = "refresh_token";
// The access token JWT carries only sub/role/org_id (see backend
// app/api/auth/jwt.py's create_access_token), not email — so email needs
// its own persisted slot to reconstruct a full `User` on startup without an
// extra round-trip.
const USER_EMAIL_KEY = "user_email";

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getStoredUserEmail(): string | null {
  return localStorage.getItem(USER_EMAIL_KEY);
}

function persistSession(refreshToken: string, email: string): void {
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  localStorage.setItem(USER_EMAIL_KEY, email);
}

function clearPersistedSession(): void {
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_EMAIL_KEY);
}

export const useAuthStore = create<AuthStore>((set) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  isAuthenticated: false,
  login: (tokens, user) => {
    persistSession(tokens.refreshToken, user.email);
    set({
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      user,
      isAuthenticated: true,
    });
  },
  logout: () => {
    clearPersistedSession();
    set({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    });
  },
  setTokens: (accessToken, refreshToken) => {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    set({ accessToken, refreshToken });
  },
}));
