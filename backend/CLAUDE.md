# CLAUDE.md — Backend (FastAPI + SQLAlchemy)

> Also read the root `../CLAUDE.md` for global rules, auth model, and security requirements.

## Commands
```bash
# Install dependencies
pip install -r requirements.txt --break-system-packages

# Run dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run Arq worker (background jobs)
arq app.tasks.worker.WorkerSettings

# Create a migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Run tests
pytest tests/ -v
```

## Dependency flow — STRICT
```
api/ (HTTP layer) → services/ (business logic) → models/ + db/ (data layer)
                         ↓
                   ai/ + channels/ + booking/ (domain modules)
                         ↓
                   security/ + utils/ (shared utilities)
```
**Never import upward.** A service never imports from api/. A model never imports from services/. If you feel the need to import upward, you're putting code in the wrong layer.

## Project structure
```
backend/
├── alembic/                    # DB migrations
│   ├── env.py
│   └── versions/
├── app/
│   ├── main.py                 # FastAPI app, router mounting, Socket.IO mount, startup/shutdown
│   ├── config.py               # pydantic-settings: Settings class loading from env vars
│   ├── db/
│   │   ├── engine.py           # async engine + sessionmaker
│   │   ├── base.py             # DeclarativeBase with UUID pk, created_at, updated_at
│   │   └── rls.py              # Middleware: SET app.tenant_id per request
│   ├── models/                 # SQLAlchemy ORM models (one per table)
│   ├── schemas/                # Pydantic request/response schemas
│   ├── api/                    # Route handlers
│   │   ├── deps.py             # FastAPI dependencies (get_db, get_current_user, require_role)
│   │   ├── health.py           # GET /health
│   │   ├── auth/               # POST /api/auth/request-otp, POST /api/auth/verify-otp, POST /api/auth/refresh
│   │   ├── super_admin/        # /api/admin/* — SEPARATE router, SEPARATE middleware
│   │   ├── org_staff/          # /api/org/* — SEPARATE router, RLS enforced
│   │   └── public/             # /api/public/* — webhooks (signature-verified), widget config
│   ├── services/               # Business logic
│   ├── ai/                     # LLM routing, RAG, intent classification, embeddings
│   │   └── prompts/            # System prompt templates
│   ├── channels/               # Channel-specific I/O handlers
│   │   ├── webchat/            # Socket.IO chat handler
│   │   ├── whatsapp/           # Meta Cloud API direct integration
│   │   └── voice/              # Retell custom LLM URL handler
│   ├── booking/                # FSM, slot holds, Google Calendar
│   ├── security/               # encryption, rate_limiter, webhook_verify, rbac
│   ├── realtime/               # Socket.IO server, event handlers, notifications
│   ├── tasks/                  # Arq background workers
│   └── utils/                  # Email sending, logging config, helpers
└── tests/
```

## Database patterns

### Base model (app/db/base.py)
Every model inherits from this. Provides UUID pk + timestamps automatically:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### Tenant-scoped models
Any model holding org-specific data MUST have:
```python
org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
```

Tables WITHOUT org_id (global tables): `users`, `organizations`, `audit_logs`
Tables WITH org_id (tenant-scoped): everything else — `contacts`, `conversations`, `messages`, `knowledge_bases`, `knowledge_chunks`, `appointments`, `escalations`, `channel_configs`, `org_api_keys`

### RLS implementation (app/db/rls.py)
This is the most security-critical file in the backend. Pattern:

1. Alembic migration creates RLS policies on every tenant-scoped table:
```sql
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON conversations
  USING (org_id = current_setting('app.tenant_id')::uuid);
```

2. FastAPI middleware sets the tenant context on each request:
```python
# In the get_db dependency:
async def get_db(current_user: User = Depends(get_current_user)):
    async with async_session() as session:
        if current_user.role == "org_staff":
            await session.execute(text(f"SET app.tenant_id = '{current_user.org_id}'"))
        elif current_user.role == "super_admin":
            # Super admin uses a different connection role that bypasses RLS
            await session.execute(text("SET app.tenant_id = '00000000-0000-0000-0000-000000000000'"))
            # OR: use RESET app.tenant_id to see all rows (requires the DB user to be table owner or have BYPASSRLS)
        yield session
```

3. Even with RLS active, every service-layer query ALSO filters by org_id explicitly:
```python
# CORRECT — defense in depth
stmt = select(Conversation).where(Conversation.org_id == org_id, Conversation.id == conversation_id)

# WRONG — relying only on RLS
stmt = select(Conversation).where(Conversation.id == conversation_id)
```

### pgvector for embeddings (app/models/knowledge_chunk.py)
```python
from pgvector.sqlalchemy import Vector

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    org_id: Mapped[uuid.UUID] = mapped_column(...)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(...)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(384))  # 384 dims for all-MiniLM-L6-v2
    metadata_: Mapped[dict] = mapped_column(JSONB, default={})
```

Create HNSW index in migration:
```sql
CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
```

## API router mounting pattern (app/main.py)
```python
from app.api.auth.router import router as auth_router
from app.api.super_admin.router import router as admin_router
from app.api.org_staff.router import router as org_router
from app.api.public.router import router as public_router
from app.api.health import router as health_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/admin", tags=["super-admin"])
app.include_router(org_router, prefix="/api/org", tags=["org-staff"])
app.include_router(public_router, prefix="/api/public", tags=["public"])
app.include_router(health_router, tags=["health"])
```

**CRITICAL:** `admin_router` and `org_router` are SEPARATE routers with SEPARATE dependencies. The admin router's dependency chain uses `require_super_admin`. The org router's dependency chain uses `require_org_staff`. They do NOT share a router.

## API dependencies (app/api/deps.py)
```python
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Decode JWT, return User object. Raises 401 if invalid."""

async def require_super_admin(user: User = Depends(get_current_user)) -> User:
    """Raises 403 if user.role != 'super_admin'."""

async def require_org_staff(user: User = Depends(get_current_user)) -> User:
    """Raises 403 if user.role != 'org_staff'. Also sets RLS context."""

async def get_db_session(user: User = Depends(get_current_user)) -> AsyncSession:
    """Yields DB session with RLS tenant_id set based on user role."""

async def get_admin_db_session(user: User = Depends(require_super_admin)) -> AsyncSession:
    """Yields DB session with RLS bypassed for super admin queries."""
```

## Security implementations

### Encryption (app/security/encryption.py)
Per-org key derivation — NOT a single Fernet key for all orgs:
```python
import hashlib, base64
from cryptography.fernet import Fernet
from app.config import settings

def derive_org_key(org_id: str) -> bytes:
    """Derive a Fernet key from master key + org_id salt."""
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        settings.MASTER_ENCRYPTION_KEY.encode(),
        org_id.encode(),  # org UUID as salt
        100_000
    )
    return base64.urlsafe_b64encode(dk)

def encrypt_api_key(org_id: str, plaintext: str) -> str:
    key = derive_org_key(org_id)
    return Fernet(key).encrypt(plaintext.encode()).decode()

def decrypt_api_key(org_id: str, ciphertext: str) -> str:
    key = derive_org_key(org_id)
    return Fernet(key).decrypt(ciphertext.encode()).decode()
```

### Rate limiter (app/security/rate_limiter.py)
Redis-based. Two use cases:

1. **OTP rate limiting:**
   - Key: `otp_attempts:{email}:{otp_code}` — max 3, TTL 10 minutes
   - Key: `otp_requests:{email}` — max 5 per hour
   - If limit hit: return same "code sent" message (no enumeration leak), but don't actually send

2. **Per-org message rate limiting:**
   - Key: `msg_count:{org_id}:{hour}` — configurable max per org (default 500/hour)
   - If limit hit: return static fallback message, don't call LLM

### Webhook verification (app/security/webhook_verify.py)
```python
import hmac, hashlib, time

def verify_whatsapp_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

def verify_timestamp(timestamp: str, max_age_seconds: int = 300) -> bool:
    return abs(time.time() - int(timestamp)) <= max_age_seconds
```
**Call both functions before processing ANY webhook. No exceptions. No "skip in dev mode."**

## AI pipeline pattern (app/ai/)

### Flow for every incoming message (any channel):
```
1. input_sanitizer.py    → Check for prompt injection, PII, content violations
2. intent_classifier.py  → Classify: greeting | faq | booking | escalation | off_topic
3. rag_pipeline.py       → If FAQ: hybrid search (pgvector + full-text), get top-k chunks
4. response_generator.py → Generate response using org's LLM via llm_router.py
5. Return response to channel handler
```

### LLM router (app/ai/llm_router.py)
Each org has their own API keys. The router:
1. Decrypts the org's API key for the configured provider
2. Calls the appropriate provider SDK (anthropic, openai, cohere)
3. Returns a unified response format regardless of provider
4. If the primary provider fails, does NOT fall back to another org's keys — returns a graceful error

**Model selection per task (use the cheapest model that works):**
- Intent classification: Claude Haiku / GPT-4o-mini (fast, cheap)
- Input sanitization: Claude Haiku / GPT-4o-mini
- RAG response generation: Claude Sonnet / GPT-4o (customer-facing quality)
- Voice responses: Claude Haiku / GPT-4o-mini (speed matters more than depth for voice)

### RAG hybrid search (app/ai/rag_pipeline.py)
Combine pgvector semantic search with Postgres full-text search:
```python
# 1. Semantic search via pgvector
semantic_results = await session.execute(
    select(KnowledgeChunk)
    .where(KnowledgeChunk.org_id == org_id)
    .order_by(KnowledgeChunk.embedding.cosine_distance(query_embedding))
    .limit(10)
)

# 2. Full-text search via tsvector
fts_results = await session.execute(
    select(KnowledgeChunk)
    .where(
        KnowledgeChunk.org_id == org_id,
        KnowledgeChunk.content.match(query_text)  # uses tsvector
    )
    .limit(10)
)

# 3. Merge via reciprocal rank fusion in Python
merged = reciprocal_rank_fusion(semantic_results, fts_results, k=60)
# 4. Apply confidence threshold — if best score < threshold, escalate instead of answering
```

### Embeddings (app/ai/embeddings.py)
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions, runs on CPU

def embed_text(text: str) -> list[float]:
    return model.encode(text).tolist()

def embed_batch(texts: list[str]) -> list[list[float]]:
    return model.encode(texts).tolist()
```
Load the model ONCE at app startup (in main.py lifespan), not per-request.

## Channel handlers

### Web chat (app/channels/webchat/handler.py)
- Socket.IO events: `connect`, `disconnect`, `send_message`, `typing`
- On `send_message`: run AI pipeline, stream response tokens back via Socket.IO `response_token` events
- On staff takeover: emit `staff_takeover` event to the customer's socket room

### WhatsApp (app/channels/whatsapp/)
- Direct Meta Cloud API integration — NO third-party BSP middleware
- `webhook_handler.py`: receives POST from Meta, verifies signature, enqueues to Arq for async processing
- `message_sender.py`: sends responses via Meta Graph API
- `template_manager.py`: manages pre-approved templates for appointment reminders
- Webhook endpoint returns 200 IMMEDIATELY, before processing. Processing happens in Arq worker.

### Voice (app/channels/voice/retell_handler.py)
- Retell custom LLM URL endpoint: POST /api/public/retell/llm
- Receives: conversation transcript so far
- Returns: AI response text (Retell handles TTS)
- MUST respond within 500ms or caller hears dead air
- Use the FASTEST model tier (Haiku/GPT-4o-mini) for voice, not Sonnet
- Keep RAG retrieval to top-3 chunks max for speed

## Booking FSM (app/booking/fsm.py)
States: `IDLE → COLLECTING_SERVICE → COLLECTING_TIME → COLLECTING_CONTACT_INFO → CONFIRMING → BOOKED`
- Each state has allowed transitions and required data fields
- COLLECTING_CONTACT_INFO asks for name + email (needed for the Calendar attendee and the contact record); if the customer only gives one, it asks for the other specifically. Skipped on a re-entry (e.g. after picking a different time post-CONFIRMING-decline) if both are already in `collected_data`.
- Slot holds in Redis: `SET hold:{org_id}:{slot_iso} {contact_id} EX 300`
- All date/time handling in the booking pipeline (extraction, slot generation, holds, Calendar events) works in the org's timezone (`Organization.timezone`, an IANA name) via `zoneinfo` — see `slot_manager.resolve_org_timezone`. Only converted to UTC at the last moment, right before writing `Appointment.start_time`/`end_time`.
- On BOOKED: create Google Calendar event (with an explicit `timeZone` field and the collected email as attendee), clear Redis hold, save appointment to DB
- On timeout (5 min hold expires): slot automatically releases, conversation gets "slot expired" message

## Background tasks (app/tasks/)
Using Arq (lightweight async Redis-based job queue):
- `embedding_tasks.py`: Re-embed knowledge chunks when created/updated
- `reminder_tasks.py`: Send WhatsApp template messages for upcoming appointments (cron: every 15 min)
- `health_check_tasks.py`: Daily check — test each org's Google Calendar token, WhatsApp webhook, LLM keys. Alert super admin on failure.
- `whatsapp_tasks.py`: Process incoming WhatsApp messages (dequeued from webhook handler)

## Logging
Use `structlog` for structured JSON logging. Every log entry includes:
- `org_id` (if applicable)
- `user_id` (if authenticated)
- `request_id` (unique per HTTP request)
- `channel` (webchat/whatsapp/voice)
- `latency_ms` (for LLM calls and external API calls)

## Error handling pattern
```python
# In services — raise domain exceptions
class OrgNotFoundError(Exception): pass
class SlotUnavailableError(Exception): pass
class LLMProviderError(Exception): pass

# In api/ — catch and return appropriate HTTP responses
@router.get("/org/{org_id}")
async def get_org(org_id: UUID, db: AsyncSession = Depends(get_admin_db_session)):
    try:
        return await org_service.get_org(db, org_id)
    except OrgNotFoundError:
        raise HTTPException(status_code=404, detail="Organization not found")
```

## Testing conventions
- Use `pytest` + `pytest-asyncio` + `httpx` (AsyncClient for FastAPI)
- Test database: separate Postgres instance or use transactions that rollback
- **Security tests are mandatory:** test that org_staff cannot access other org's data, test OTP rate limiting, test webhook signature rejection
- Minimum test coverage for Phase 1: auth flows, RLS isolation, encryption/decryption, rate limiting

## Dependencies (requirements.txt core packages)
```
fastapi
uvicorn[standard]
sqlalchemy[asyncio]>=2.0
asyncpg
alembic
pgvector
pydantic>=2.0
pydantic-settings
python-jose[cryptography]
cryptography
python-socketio
aiohttp
arq
redis[hiredis]
structlog
sentry-sdk[fastapi]
sentence-transformers
anthropic
openai
cohere
httpx
resend
pytest
pytest-asyncio
```
