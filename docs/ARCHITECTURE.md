# AI Receptionist — File Structure Reference
### 240 files · Monorepo · FastAPI + SQLAlchemy 2.0 + React + Vite

---

## Root Level

```
ai-receptionist/
├── .gitignore           # Python, Node, env files, dist/
├── .env.example         # Template for all env vars (DB, Redis, JWT secret, master encryption key)
├── railway.toml         # Railway monorepo config: points backend/ and frontend/ as separate services
├── README.md
├── backend/
├── frontend/
└── docs/
```

---

## Backend — `backend/`

### Why this layout matters
The backend is split into layers with strict dependency rules. Each layer only imports from layers below it. This matters because when Claude Code generates code, it needs to know WHERE to put things — wrong placement creates circular imports and untestable spaghetti.

**Dependency flow (top → bottom, never upward):**
```
api/ (routes) → services/ (logic) → models/ + db/ (data)
                    ↓
              ai/ + channels/ + booking/ (domain modules)
                    ↓
              security/ + utils/ (shared utilities)
```

### Layer-by-layer explanation

#### `backend/app/db/` — Database connection and tenant isolation
| File | Purpose |
|---|---|
| `engine.py` | Async SQLAlchemy engine + session factory. One connection pool shared across requests. |
| `base.py` | Declarative base class all models inherit from. Adds `id` (UUID), `created_at`, `updated_at` to every table automatically. |
| `rls.py` | **CRITICAL SECURITY FILE.** Middleware that runs `SET app.tenant_id = '{org_id}'` on every DB session before any query executes. This is what makes RLS work — Postgres uses this variable in its row-level security policies to filter data. Super admin requests set a special flag that bypasses RLS via a separate DB role. |

#### `backend/app/models/` — SQLAlchemy ORM models (one per table)
| File | What it maps to |
|---|---|
| `organization.py` | Orgs table: name, slug, working hours, timezone, trial status, active channels, created_by |
| `user.py` | Users table: email, role (super_admin / org_staff), org_id (null for super admin), last_login |
| `contact.py` | End-customer contacts per org: name, phone, email, channel, conversation count |
| `conversation.py` | Conversation sessions: contact_id, org_id, channel, status (active/escalated/resolved), assigned_staff |
| `message.py` | Individual messages: conversation_id, role (ai/customer/staff), content, channel, timestamp |
| `knowledge_base.py` | KB containers per org: name, description, status |
| `knowledge_chunk.py` | Individual chunks: kb_id, content, embedding (pgvector Vector type), metadata |
| `appointment.py` | Bookings: contact_id, org_id, service, datetime, status (held/confirmed/cancelled), google_event_id |
| `escalation.py` | Escalation events: conversation_id, reason, priority, status (pending/picked_up/resolved), assigned_to |
| `channel_config.py` | Per-org channel settings: channel_type, enabled, config JSON (webhook URLs, phone numbers, widget settings) |
| `audit_log.py` | Super admin action log: user_id, action, target_type, target_id, details JSON, ip_address |
| `org_api_keys.py` | **ENCRYPTED.** Per-org API keys: org_id, provider (openai/anthropic/cohere/whatsapp/google), encrypted_key, last_used, status |

#### `backend/app/schemas/` — Pydantic request/response schemas
Mirrors models/ but defines what the API accepts and returns. Keeps internal DB fields (encrypted keys, raw embeddings) out of API responses. Each file has `Create`, `Update`, and `Response` variants.

#### `backend/app/api/` — Route handlers (the HTTP layer)

**Separation principle:** `super_admin/` and `org_staff/` are **separate routers with separate middleware stacks.** This is vulnerability fix #1.4 from the vulnerability doc — they do NOT share a router with an `if role == 'super_admin'` check. Each has its own dependency chain in `deps.py`.

| Directory | Mounted at | Auth required | RLS behavior |
|---|---|---|---|
| `api/auth/` | `/api/auth/` | No (public) | No DB access except user lookup |
| `api/public/` | `/api/public/` | No (webhook signature verification instead) | Org determined from webhook payload |
| `api/super_admin/` | `/api/admin/` | JWT + super_admin role | RLS bypassed via admin DB role |
| `api/org_staff/` | `/api/org/` | JWT + org_staff role | RLS enforced, scoped to JWT's org_id |

| File | Key notes |
|---|---|
| `deps.py` | FastAPI dependencies: `get_db` (yields async session with RLS set), `get_current_user` (JWT decode), `require_super_admin`, `require_org_staff`. These are the security gatekeepers. |
| `health.py` | `/health` — checks DB + Redis connectivity, returns container uptime. Pinged by external monitoring. |

#### `backend/app/services/` — Business logic (the brain)
Routes call services; services call models and domain modules. Routes never contain business logic directly — this makes the code testable without HTTP.

#### `backend/app/ai/` — LLM integration layer
| File | Purpose |
|---|---|
| `llm_router.py` | Given an org_id, decrypts that org's API keys and routes to the correct provider (OpenAI/Anthropic/Cohere). Handles fallback if primary provider fails. |
| `intent_classifier.py` | Classifies incoming message intent: greeting, FAQ, booking_request, escalation_trigger, off_topic. Uses fast/cheap model (Haiku/GPT-4o-mini). |
| `rag_pipeline.py` | Hybrid retrieval: pgvector cosine similarity + Postgres full-text search, merged via reciprocal rank fusion. Returns top-k chunks with confidence scores. |
| `response_generator.py` | Takes classified intent + retrieved chunks + conversation history → generates final response via the org's configured LLM. |
| `input_sanitizer.py` | Checks for prompt injection, PII in customer messages, content policy violations before processing. |
| `embeddings.py` | Local sentence-transformers model (all-MiniLM-L6-v2). Runs on CPU. Used for indexing knowledge base chunks and encoding queries. |
| `prompts/` | System prompts and templates. Separated so they can be customized per org via the setup wizard without touching code. |

#### `backend/app/channels/` — Channel-specific I/O
Each channel has its own subdirectory because the input/output formats are completely different (WebSocket stream vs WhatsApp webhook POST vs Retell custom LLM URL). But they all call the same `services/` and `ai/` layer underneath.

| Channel | Key files |
|---|---|
| `webchat/handler.py` | Socket.IO event handlers for real-time chat. Streams LLM tokens as they generate. |
| `whatsapp/signature_verify.py` | **SECURITY: HMAC-SHA256 verification of Meta webhook signatures. Vulnerability fix #1.5.** |
| `whatsapp/webhook_handler.py` | Parses incoming WhatsApp messages, routes to AI pipeline via Arq background task. |
| `whatsapp/template_manager.py` | Manages pre-approved WhatsApp template messages for reminders/follow-ups. |
| `voice/retell_handler.py` | Custom LLM URL endpoint that Retell calls. Receives transcript, returns AI response. Must be fast (<500ms). |

#### `backend/app/booking/` — Appointment booking FSM
| File | Purpose |
|---|---|
| `fsm.py` | Finite state machine: IDLE → COLLECTING_SERVICE → COLLECTING_TIME → CONFIRMING → BOOKED. Each state has allowed transitions and required data. |
| `slot_manager.py` | Redis-based slot holds: `SET hold:{org}:{slot} {contact} EX 300`. Prevents double-booking during the conversation flow. |
| `google_calendar.py` | OAuth token management + Google Calendar API calls. Handles token refresh, expiry detection, and the health check that alerts you when a token dies. |

#### `backend/app/security/` — Security primitives
| File | Fixes vulnerability |
|---|---|
| `encryption.py` | Per-org Fernet key derivation from master key + org salt. Fixes #1.1. |
| `rate_limiter.py` | Redis-based rate limiting for OTP attempts (3/code, 5/hr/email) AND per-org message caps. Fixes #1.2 and #2.4. |
| `webhook_verify.py` | Shared HMAC verification utils used by WhatsApp + Retell handlers. Fixes #1.5. |
| `rbac.py` | Role enum, permission checks, route-level decorators. Supports #1.3 and #1.4. |

#### `backend/app/realtime/` — Socket.IO server
| File | Purpose |
|---|---|
| `socket_manager.py` | Socket.IO async server setup, mounted on the FastAPI ASGI app. |
| `events.py` | Event handlers: `join_org_room`, `new_message`, `typing_indicator`, `staff_takeover`, `escalation_alert`. |
| `notifications.py` | Push notification logic for escalations and new conversations. |

#### `backend/app/tasks/` — Arq background workers
| File | Purpose |
|---|---|
| `worker.py` | Arq worker config: Redis connection, registered tasks, cron schedules. |
| `embedding_tasks.py` | Async re-embedding when knowledge base chunks are added/updated. |
| `reminder_tasks.py` | Scheduled appointment reminders via WhatsApp template messages. |
| `health_check_tasks.py` | Daily check: Google Calendar tokens valid? WhatsApp webhook reachable? LLM keys working? Alerts super admin on failure. Fixes #2.3. |
| `whatsapp_tasks.py` | Processes incoming WhatsApp messages async (webhook returns 200 immediately, processing happens in background). |

---

## Frontend — `frontend/`

### Architecture decisions baked into this structure

- **TanStack Query** for all server state (API data). Files in `src/api/` are query hooks, not raw fetch calls.
- **Zustand** for UI-only state (sidebar, wizard step, selected conversation). Files in `src/stores/`.
- **Role-based routing** in `src/routes.tsx` — super admin sees `/admin/*` routes, org staff sees `/org/*` routes. `ProtectedRoute.tsx` enforces this.
- **Feature folders** in `src/features/` for complex multi-component features (setup wizard, inbox, dashboard). Simple pages stay in `src/pages/`.

### Key frontend files

| File/Dir | Purpose |
|---|---|
| `src/api/client.ts` | Axios instance with JWT interceptor (auto-attaches token, handles 401 refresh/logout). |
| `src/routes.tsx` | React Router config. Login → role check → redirect to `/admin/dashboard` or `/org/dashboard`. |
| `src/components/layout/ProtectedRoute.tsx` | Wraps routes, checks JWT validity + role. Redirects to login if invalid. |
| `src/stores/auth-store.ts` | Zustand: current user, JWT, role, org_id. Persisted to memory only (not localStorage — not supported in some contexts). |
| `src/stores/inbox-store.ts` | Zustand: selected conversation ID, filter state, unread counts. |
| `src/lib/socket.ts` | Socket.IO client singleton. Auto-joins org room on connect. Reconnects on token refresh. |

### Super admin pages
| Page | What it shows |
|---|---|
| `DashboardPage.tsx` | All-orgs overview: total messages, escalations, active orgs, setup completion rates. |
| `OrganizationsListPage.tsx` | Table of orgs. Each row: name, message count, escalation count, setup status, **Setup button** (links to wizard). |
| `SetupWizardPage.tsx` | 9-step wizard. Receives org_id from URL. Each step is a component in `features/setup-wizard/steps/`. |

### Org staff pages
| Page | What it shows |
|---|---|
| `DashboardPage.tsx` | Org-specific stats: inbound messages today, open escalations, upcoming appointments, recent conversations. |
| `InboxPage.tsx` | Live conversation list + chat window. Real-time via Socket.IO. Staff can take over from AI mid-conversation. |
| `EscalationsPage.tsx` | Escalated conversations awaiting staff response. Priority-sorted. |

### Setup wizard steps (the 9 sections you described)
| Step | What it configures |
|---|---|
| `BasicInfoStep` | Org name, industry, timezone, contact info |
| `WorkingHoursStep` | Per-day open/close times, holidays |
| `ChannelConfigStep` | Toggle WebChat / WhatsApp / Voice on/off. **Trial checkbox** for access control. |
| `ApiKeysStep` | LLM provider keys, WhatsApp Business API token, Google Calendar OAuth. All encrypted before storage. |
| `KnowledgeBaseStep` | Upload/create knowledge base chunks. Bulk import from PDF/text. |
| `BookingConfigStep` | Services list, durations, buffer times, calendar connection. |
| `SystemPromptsStep` | Customize AI personality, greeting, escalation rules, off-topic handling. |
| `StaffAccessStep` | Add org staff emails (these become OTP-authenticated users for this org). |
| `ReviewAndActivateStep` | Summary of all config. Validation checks. **Activate** button goes live. |

---

## Widget — `frontend/widget/`

Separate Vite build that outputs a single JS file. Embedded on client websites via:
```html
<script src="https://cdn.example.com/widget.js"></script>
<script>AIReceptionist.init({ orgId: 'xxx' })</script>
```

Intentionally tiny (~30KB gzipped). No Tailwind (would leak styles). Scoped CSS only. Connects to backend via Socket.IO for real-time chat.

---

## Docs — `docs/`

| File | Purpose |
|---|---|
| `security-checklist.md` | The 12-item checklist from the vulnerability doc. Check each item before going live. |
| `whatsapp-onboarding-guide.md` | Step-by-step for clients to set up their WhatsApp Business account with Meta. You'll send this to every new org. |
| `setup-guide.md` | How to deploy: Railway config, env vars, Postgres setup, Redis setup, first super admin user creation. |
| `api-reference.md` | All endpoints documented. Generated or manual. |
