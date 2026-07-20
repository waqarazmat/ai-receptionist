# CLAUDE.md — AI Receptionist Platform (Root)

## What this project is
A multi-tenant AI receptionist SaaS platform that handles customer conversations for businesses (dental clinics, salons, etc.) across three channels: web chat, WhatsApp, and voice. Each organization gets its own AI receptionist that answers FAQs from a knowledge base, books appointments, and escalates to human staff when needed.

## Monorepo structure
```
ai-receptionist/
├── CLAUDE.md              ← YOU ARE HERE (root — global rules)
├── backend/CLAUDE.md      ← Backend-specific rules (read when working in backend/)
├── frontend/CLAUDE.md     ← Frontend-specific rules (read when working in frontend/)
├── backend/               ← Python FastAPI API server
├── frontend/              ← React admin panel (org staff + super admin dashboards)
├── widget/                ← THE embeddable chat widget — Preact, builds to dist/cw.js,
│                             hosted at https://genaitech.be/widget/cw.js. Standalone
│                             package (own package.json/node_modules), not part of the
│                             frontend/ Vite app. Talks to the same backend as
│                             frontend/ (Socket.IO /chat namespace + GET
│                             /api/public/webchat/{org_id}/{config,conversations/*}).
│                             The super-admin Test Center's live embed preview also
│                             loads this same cw.js (via an iframe). (The earlier
│                             frontend/widget/ implementation was removed 2026-07-09
│                             once Test Center was ported off it; see
│                             [[project_widget_rewrite]] memory.)
└── docs/                  ← Architecture docs, security checklist, onboarding guides
```

**IMPORTANT:** When working on backend code, also read `backend/CLAUDE.md`. When working on frontend code, also read `frontend/CLAUDE.md`. Those files contain layer-specific conventions, patterns, and constraints that override or extend what's written here.

## Tech stack (locked decisions — do not change)
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 async, Alembic, Arq (background jobs)
- **Frontend:** React 18, Vite, TypeScript, TanStack Query (server state), Zustand (UI state), Tailwind CSS
- **Real-time:** Socket.IO (python-socketio on backend, socket.io-client on frontend)
- **Database:** PostgreSQL with pgvector extension (vectors + relational in one DB)
- **Cache/Queue:** Redis (session, rate limiting, slot holds, Arq job queue)
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2) — runs locally on CPU, NOT via an API
- **LLM providers:** Claude (Anthropic), OpenAI, Cohere — routed per-org based on their API keys
- **Hosting:** Railway (backend + Postgres + Redis), Cloudflare Pages (frontend static files)
- **ORM:** SQLAlchemy 2.0 with async support. NOT Prisma, NOT SQLModel, NOT Django ORM.
- **No Docker.** Railway deploys directly from source via buildpacks.

## Multi-tenancy model — CRITICAL
Every piece of data belongs to an organization (tenant). Isolation is enforced at TWO layers:

1. **Postgres Row-Level Security (RLS):** Every table with tenant data has an `org_id` column and an RLS policy that filters on `current_setting('app.tenant_id')`. The application sets this session variable before every query.
2. **Application-layer filtering:** Every query also explicitly includes `WHERE org_id = :org_id` as a defense-in-depth measure. RLS is the safety net, not the primary filter.

**Never create a table that holds tenant data without an `org_id` column.**
**Never write a query against tenant data without filtering by `org_id`.**

## Auth model
- **Authentication:** Email + OTP (one-time password sent via email). No passwords stored anywhere.
- **Session:** JWT tokens. Access token expires in 30 minutes. Refresh token expires in 7 days.
- **Two roles:**
  - `super_admin` — One person (the platform owner). Can see all orgs, configure everything, bypass RLS.
  - `org_staff` — Staff members belonging to a specific org. Can only see their own org's data. RLS enforced.
- **Super admin and org staff use the SAME login flow** (email + OTP) but get routed to different dashboards based on their role in the JWT.

## Security rules — NON-NEGOTIABLE
These come from a formal vulnerability analysis. Every one of these must be implemented. No shortcuts.

1. **OTP rate limiting:** Max 3 verification attempts per OTP code. Max 5 OTP requests per email per hour. After 3 failed attempts, invalidate the code and force a new one.
2. **Email enumeration prevention:** The login endpoint must respond identically whether the email exists or not. Same message, same response time. "If this email is registered, you'll receive a code."
3. **HMAC webhook verification:** Every WhatsApp webhook and Retell webhook must have its signature verified before processing. Implement this from the first commit, not "later." Reject requests older than 5 minutes (replay protection).
4. **Per-org API key encryption:** Use Fernet encryption with per-org derived keys (master key + org-specific salt). The master key is in an environment variable. Never store API keys in plaintext.
5. **Super admin separation:** Super admin API routes live on a SEPARATE FastAPI router with its own middleware stack. Not the same router as org staff with an `if role == 'super_admin'` check. Separate router, separate dependency chain.
6. **UUID-based resource IDs:** All database primary keys are UUIDs, not sequential integers. This mitigates IDOR attacks (guessing the next ID).
7. **Per-org message rate limiting:** Redis counters per org per hour. When the cap is hit, fall back to a static response instead of burning through the org's LLM API key balance.
8. **Graceful degradation:** When any external service fails (LLM API, Google Calendar, WhatsApp), return a helpful fallback message to the customer, not a 500 error. Example: "We're experiencing a brief issue — please call us directly at [number]."
9. **Re-authentication for destructive actions:** Deleting an org, changing API keys, or modifying billing requires a fresh OTP, even if the super admin is already logged in.
10. **Audit logging:** Every super admin action (create org, modify config, change API keys, delete anything) is logged with user_id, action, target, timestamp, and IP address.

## ID conventions
- All primary keys: UUID v4 (`uuid.uuid4()`)
- All IDs in API responses: string representation of UUID
- Never expose sequential integers as identifiers in any API response

## Environment variables (defined in .env, loaded via pydantic-settings)
```
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# Redis
REDIS_URL=redis://host:6379/0

# Auth
JWT_SECRET_KEY=<random 64-char string>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Encryption
MASTER_ENCRYPTION_KEY=<Fernet key — generate via Fernet.generate_key()>

# Email (OTP delivery)
BREVO_API_KEY=<Brevo API key — starts with "xkeysib-">

OTP_FROM_EMAIL=noreply@genaitech.be

# Super admin bootstrap
SUPER_ADMIN_EMAIL=malikaliyan.contact@gmail.com

# App
APP_ENV=development|production
CORS_ORIGINS=["http://localhost:5173"]
```
## Claude Code behavior
Do not ask for confirmation before editing files, running commands, or installing packages. Proceed automatically. Only ask when there is a genuine architectural ambiguity with multiple valid approaches.

## Railway deployment layout
```
Railway Project
├── Service: backend     → source: /backend, start: uvicorn app.main:app
├── Service: postgres    → managed PostgreSQL (enable pgvector extension)
└── Service: redis       → managed Redis (or use Upstash free tier externally)

Cloudflare Pages (separate, not on Railway)
├── Admin panel          → source: /frontend, build: npm run build
└── Widget CDN           → source: /widget, build: npm run build → dist/cw.js,
                            deployed to https://genaitech.be/widget/cw.js. Set
                            VITE_API_BASE to the production API origin at build
                            time (defaults to http://localhost:8000 otherwise).
```

## Git conventions
- Branch: `main` (production), `dev` (development)
- Commit messages: conventional commits (`feat:`, `fix:`, `security:`, `refactor:`)
- Never commit `.env` files. Only `.env.example` with placeholder values.

## Build phases (what to build in what order)
Phase 1: Auth + DB + RLS + super admin CRUD + basic org management (weeks 1-2)
Phase 2: RAG pipeline + web chat + staff inbox (weeks 3-4)
Phase 3: Booking FSM + Google Calendar integration (weeks 5-6)
Phase 4: WhatsApp channel (weeks 7-8)
Phase 5: Voice channel via Retell custom LLM URL (weeks 9-10)
Phase 6: Analytics dashboard + audit logs + polish (weeks 11-12)

**Always build security primitives (encryption, rate limiting, RLS, webhook verification) in Phase 1, not "later."**

## Socket.IO architecture
Two separate AsyncServer instances: `chat_sio` (widget, CORS open, path /socket.io/) and `inbox_sio` (staff panel, CORS restricted, path /socket.io-inbox/). Staff-to-customer emits must use `chat_sio`. Customer-to-staff emits must use `inbox_sio`.