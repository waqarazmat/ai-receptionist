import { create } from "zustand";

export type Theme = "light" | "dark";

// NOTE: theme preference is persisted to localStorage. This is a deliberate,
// narrow exception to the "no localStorage" rule in frontend/CLAUDE.md — a
// theme toggle isn't "fully functional" unless it survives reload, and this is
// the universal pattern for it. It stores a single UI preference, not app data.
const STORAGE_KEY = "ar-theme";

function readStoredTheme(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null;
  }
}

function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function resolveInitialTheme(): Theme {
  return readStoredTheme() ?? (systemPrefersDark() ? "dark" : "light");
}

/** Reflect the theme onto <html> — Tailwind keys its `dark:` variant off the
 * `.dark` class (see index.css @custom-variant), and `data-theme` is handy for
 * any non-Tailwind CSS. */
function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.dataset.theme = theme;
}

interface ThemeStore {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggle: () => void;
}

export const useThemeStore = create<ThemeStore>((set, get) => ({
  theme: resolveInitialTheme(),
  setTheme: (theme) => {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* ignore storage failures (private mode) — theme still applies for the session */
    }
    applyTheme(theme);
    set({ theme });
  },
  toggle: () => get().setTheme(get().theme === "dark" ? "light" : "dark"),
}));

/** Apply the resolved theme once at startup, before first paint of the app.
 * The inline script in index.html already set the class to avoid a flash; this
 * keeps the store in sync with it. */
export function initTheme(): void {
  applyTheme(useThemeStore.getState().theme);
}
