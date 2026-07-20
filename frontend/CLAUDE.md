# CLAUDE.md — Frontend (React + Vite + TypeScript)

> Also read the root `../CLAUDE.md` for global rules, auth model, and security requirements.

## Commands
```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Build the embeddable chat widget (separate package, lives at repo root, not under frontend/)
cd ../widget && npm install && npm run build

# Type check
npx tsc --noEmit

# Lint
npx eslint src/
```

## Tech stack (locked — do not change)
- **React 18** with functional components and hooks only. No class components.
- **Vite** for bundling. NOT Next.js, NOT CRA.
- **TypeScript** strict mode. No `any` types except when wrapping untyped third-party libs.
- **TanStack Query (React Query v5)** for all server state (API data fetching, caching, mutations).
- **Zustand** for UI-only state (sidebar, wizard step, selected conversation, filters).
- **Tailwind CSS** for styling. No CSS-in-JS, no styled-components, no CSS modules.
- **Socket.IO client** for real-time (live inbox, chat streaming, notifications).
- **React Router v6** for routing.

## Project structure
```
frontend/
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── package.json
├── public/
├── src/
│   ├── main.tsx                 # ReactDOM.createRoot, QueryClientProvider, RouterProvider
│   ├── App.tsx                  # Top-level layout, socket init, auth check
│   ├── routes.tsx               # React Router config — role-based route tree
│   ├── api/                     # TanStack Query hooks + axios client
│   ├── stores/                  # Zustand stores (UI state only)
│   ├── hooks/                   # Custom React hooks
│   ├── components/
│   │   ├── ui/                  # Reusable primitives (Button, Input, Modal, Badge, Table, Spinner)
│   │   ├── layout/              # Sidebar, Header, MainLayout, ProtectedRoute
│   │   ├── auth/                # LoginForm, OTPVerify
│   │   └── shared/              # DataTable, StatsCard, StatusBadge, SearchInput, EmptyState
│   ├── pages/
│   │   ├── auth/                # LoginPage
│   │   ├── super-admin/         # DashboardPage, OrganizationsListPage, SetupWizardPage, etc.
│   │   └── org-staff/           # DashboardPage, InboxPage, EscalationsPage, etc.
│   ├── features/                # Complex multi-component features
│   │   ├── setup-wizard/        # WizardStepper, WizardContext, steps/
│   │   ├── inbox/               # ConversationList, ChatWindow, MessageBubble, TakeoverBanner
│   │   ├── dashboard/           # OrgStatsRow, OverviewCards, RecentActivity
│   │   └── knowledge-base/      # ChunkEditor, ChunkList, BulkImport
│   ├── lib/                     # Socket.IO client, constants, utility functions
│   └── types/                   # TypeScript interfaces matching backend Pydantic schemas
```
The embeddable chat widget is NOT under `frontend/` — it lives at repo root, `../widget/` (own `package.json`, own build). See below.

## State management rules — STRICT

### TanStack Query = ALL server data
Anything that comes from the API goes through TanStack Query. No storing API responses in Zustand or useState.

```typescript
// CORRECT — src/api/organizations.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from './client';

export function useOrganizations() {
  return useQuery({
    queryKey: ['organizations'],
    queryFn: () => apiClient.get('/admin/organizations').then(r => r.data),
  });
}

export function useCreateOrganization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateOrgInput) => apiClient.post('/admin/organizations', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['organizations'] }),
  });
}

// WRONG — never do this
const [orgs, setOrgs] = useState([]);
useEffect(() => { fetch('/api/orgs').then(r => setOrgs(r.data)); }, []);
```

### Zustand = UI-only state
Things like: which sidebar item is selected, what step the wizard is on, whether a modal is open, current filter/search text. NEVER put API data in Zustand.

```typescript
// CORRECT — src/stores/sidebar-store.ts
import { create } from 'zustand';

interface SidebarStore {
  isCollapsed: boolean;
  toggle: () => void;
}

export const useSidebarStore = create<SidebarStore>((set) => ({
  isCollapsed: false,
  toggle: () => set((s) => ({ isCollapsed: !s.isCollapsed })),
}));
```

### What goes where — decision tree
- "Does this data come from the backend?" → TanStack Query
- "Is this purely visual/interaction state?" → Zustand
- "Is this local to one component?" → useState
- "Is this form input?" → useState or react-hook-form (if complex forms)

## API client (src/api/client.ts)
Axios instance with:
1. Base URL from env var (`VITE_API_URL`)
2. Request interceptor: attaches JWT from auth store
3. Response interceptor: on 401, attempt token refresh. If refresh fails, redirect to login.
4. No retry on 403 (forbidden = wrong role, not expired token)

```typescript
import axios from 'axios';
import { useAuthStore } from '../stores/auth-store';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Try refresh token flow
      // If refresh fails: useAuthStore.getState().logout()
    }
    return Promise.reject(error);
  }
);
```

## Routing (src/routes.tsx)
Role-based route tree. After login, JWT is decoded, role determines which routes are accessible:

```
/login                          → LoginPage (public)
/admin/dashboard                → super admin DashboardPage
/admin/organizations            → OrganizationsListPage
/admin/organizations/:id        → OrganizationDetailPage
/admin/organizations/:id/setup  → SetupWizardPage
/admin/audit-logs               → AuditLogsPage
/admin/users                    → UsersManagementPage
/org/dashboard                  → org staff DashboardPage
/org/inbox                      → InboxPage
/org/inbox/:conversationId      → ConversationDetailPage (within InboxPage)
/org/appointments               → AppointmentsPage
/org/knowledge-base             → KnowledgeBasePage
/org/escalations                → EscalationsPage
/org/contacts                   → ContactsPage
/org/settings                   → SettingsPage
```

### ProtectedRoute component (src/components/layout/ProtectedRoute.tsx)
Wraps route groups. Checks:
1. Is there a valid JWT in auth store? If no → redirect to /login
2. Does the JWT's role match the required role for this route group? If no → redirect to the correct dashboard
3. Is the JWT expired? If yes → attempt silent refresh, redirect to /login on failure

```typescript
interface ProtectedRouteProps {
  requiredRole: 'super_admin' | 'org_staff';
  children: React.ReactNode;
}
```

## Socket.IO (src/lib/socket.ts)
Single socket instance, connected after login:

```typescript
import { io, Socket } from 'socket.io-client';

let socket: Socket | null = null;

export function connectSocket(token: string, orgId?: string) {
  socket = io(import.meta.env.VITE_API_URL, {
    auth: { token },
    transports: ['websocket'],
  });
  
  socket.on('connect', () => {
    if (orgId) socket.emit('join_org_room', { org_id: orgId });
  });
  
  return socket;
}

export function getSocket(): Socket | null {
  return socket;
}

export function disconnectSocket() {
  socket?.disconnect();
  socket = null;
}
```

### Socket events the frontend listens for:
- `new_message` — new message in any conversation (update inbox, show notification)
- `response_token` — streaming LLM response token (append to chat window)
- `response_complete` — LLM finished generating (stop loading indicator)
- `escalation_created` — new escalation (show alert, update escalation count)
- `staff_takeover` — staff took over a conversation (update conversation status)
- `typing_indicator` — customer or AI is typing

### useRealtime hook (src/hooks/useRealtime.ts)
Connects Socket.IO events to TanStack Query cache invalidation:
```typescript
// When a new_message event arrives for the current org:
// 1. Invalidate the conversations list query (to update unread counts)
// 2. If the conversation is currently open, append the message to the messages query cache
// 3. Play a notification sound if the tab is not focused
```

## Page patterns

### Super admin — OrganizationsListPage
This is the main page you described. It shows a table where each row is an org with:
- Organization name
- Number of messages (inbound)
- Number of escalations
- Setup status (complete / incomplete / not started)
- **Setup button** → navigates to `/admin/organizations/:id/setup`

Data comes from `useOrganizations()` TanStack Query hook. Each stat (messages, escalations) comes from the same API response — the backend aggregates these counts.

### Super admin — SetupWizardPage
- URL: `/admin/organizations/:orgId/setup`
- 9-step wizard. State managed by `wizard-store.ts` (current step index) + TanStack Query mutations (saving each step).
- Each step is a separate component in `features/setup-wizard/steps/`.
- Steps can be completed in order or jumped to (if previous steps are valid).
- The final step (ReviewAndActivateStep) shows a summary and an **Activate** button.
- On activate: POST to `/api/admin/organizations/:id/activate` → org goes live.

### Org staff — InboxPage
Split-pane layout:
- Left: ConversationList (filterable by status: active, escalated, resolved)
- Right: ChatWindow (selected conversation's messages, real-time updates via Socket.IO)
- TakeoverBanner: appears when AI is handling a conversation, staff can click "Take Over" to switch to human mode
- Messages stream in real-time. Staff replies go through the API, which routes them to the appropriate channel (WhatsApp, web chat).

### Org staff — DashboardPage
Stats cards showing:
- Total inbound messages (today / this week / this month)
- Open escalations count
- Upcoming appointments (next 24 hours)
- Active conversations count
- Recent conversation list (last 10)

All data from a single `useDashboardStats(orgId)` query hook.

## Component conventions

### UI primitives (src/components/ui/)
Build these once, use everywhere. Keep them generic — no business logic:
- `Button` — variants: primary, secondary, danger, ghost. Sizes: sm, md, lg. Loading state.
- `Input` — with label, error message, helper text support.
- `Modal` — dialog overlay. Controlled via `isOpen` prop.
- `Badge` — colored status indicator. Variants: success, warning, danger, info, neutral.
- `Table` — sortable, with optional pagination. Accepts generic row type.
- `Spinner` — loading indicator.
- `Card` — container with optional header, padding.
- `Tabs` — tab navigation within a page.

### Naming conventions
- Components: PascalCase (`ConversationList.tsx`)
- Hooks: camelCase with `use` prefix (`useAuth.ts`)
- Stores: kebab-case with `-store` suffix (`auth-store.ts`)
- API hooks: kebab-case matching resource (`knowledge-base.ts`)
- Types: PascalCase interfaces (`Organization`, `Conversation`, `Message`)
- Pages: PascalCase with `Page` suffix (`DashboardPage.tsx`)

### File size rule
If a component exceeds ~200 lines, split it. Extract sub-components into the same directory or into `features/` if they represent a cohesive feature.

## Types (src/types/)
These mirror the backend's Pydantic response schemas. Keep them in sync.

```typescript
// src/types/organization.ts
export interface Organization {
  id: string;           // UUID string
  name: string;
  slug: string;
  industry: string;
  timezone: string;
  is_active: boolean;
  is_trial: boolean;
  channels_enabled: {
    webchat: boolean;
    whatsapp: boolean;
    voice: boolean;
  };
  setup_completed: boolean;
  message_count: number;
  escalation_count: number;
  created_at: string;   // ISO datetime
}

// src/types/conversation.ts
export interface Conversation {
  id: string;
  org_id: string;
  contact_id: string;
  contact_name: string;
  channel: 'webchat' | 'whatsapp' | 'voice';
  status: 'active' | 'escalated' | 'resolved';
  assigned_to: string | null;  // staff user ID
  last_message_at: string;
  unread_count: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: 'customer' | 'ai' | 'staff';
  content: string;
  channel: 'webchat' | 'whatsapp' | 'voice';
  created_at: string;
}
```

## Widget (../widget/, repo root) — SEPARATE BUILD, NOT under frontend/

The widget is an embeddable chat bubble for client websites. It is NOT part of the main React app, and it is NOT a subdirectory of `frontend/` — it's a standalone package at the repo root (`widget/`), with its own `package.json`/`node_modules`. (An earlier implementation lived at `frontend/widget/`; it was removed 2026-07-09 once the super-admin Test Center was ported onto the root package — see `[[project_widget_rewrite]]` memory if working in this codebase's memory system.)

**Key constraints:**
- Preact, not React — separate `package.json` and `vite.config.ts` (library mode build)
- Output: single JS file, `dist/cw.js`, hosted at `https://genaitech.be/widget/cw.js`
- NO Tailwind (would leak styles onto the host page) — scoped CSS injected into a Shadow DOM instead
- NO TanStack Query, NO Zustand — too heavy. Use raw fetch + useState/hooks.
- Shadow DOM for style isolation from the host page (see `widget/src/index.ts`)
- Connects to backend via Socket.IO (`/chat` namespace) for real-time chat
- Initialized by the host page via a plain `<script>` tag with `data-*` attributes — there is no `AIReceptionist.init(...)` call:
```html
<script src="https://genaitech.be/widget/cw.js" data-org-id="org-uuid-here"></script>
```
`data-api-base` can also be set to override the backend origin (defaults to the production API in the hosted build). Branding (position, colors, header text, greeting) comes from the org's `GET /api/public/webchat/{org_id}/config` response, not from script attributes.

**Widget does NOT handle:**
- Auth (no login — it's a public chat interface for end customers)
- Booking UI (booking happens conversationally through the AI, not through a form)
- Staff features (no takeover UI — that's in the admin panel)

**Widget DOES handle:**
- Chat bubble → opens chat window on click
- Message input + send
- Streaming AI responses (via Socket.IO)
- "Typing" indicator
- "Powered by [YourBrand]" footer
- Conversation continuity — `conversation_id` is persisted to `localStorage` (keyed by org id) so a page reload resumes the same conversation and reloads its history

## Environment variables (via Vite's import.meta.env)
```
VITE_API_URL=http://localhost:8000       # Backend API base URL
VITE_SOCKET_URL=http://localhost:8000    # Socket.IO server URL (same as API in dev)
```

Prefix with `VITE_` or Vite won't expose them to client code.

## Do NOT use
- `localStorage` or `sessionStorage` for anything except the auth refresh token + cached user email (`stores/auth-store.ts`) — that one pair exists so a page refresh/closed tab doesn't log the user out (see `components/auth/AuthProvider.tsx`). The access token itself stays in-memory only (short-lived; re-derived from the refresh token at startup). Don't reach for storage for anything else — Zustand without persist / React state remains the default.
- Next.js, SSR, or server components — this is a client-side SPA.
- CSS modules or styled-components — Tailwind only.
- Redux — use TanStack Query + Zustand as described above.
- `any` type — use `unknown` and narrow, or define proper interfaces.
- Default exports for non-page components — use named exports for better refactoring support. Pages can use default exports for React Router lazy loading.
