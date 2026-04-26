# SphereVoice API — Execution Plan

**Document:** Phased Execution Plan — Platform API for External Integration Apps  
**Product:** SphereVoice API  
**Company:** Sphere AI  
**Version:** 1.0  
**Date:** March 31, 2026  
**First Consumer:** NanoVoice  
**Author:** SphereVoice Team

---

## 1. What This Is

SphereVoice API is a **service-to-service voice pipeline API** that lets external applications (starting with NanoVoice) run voice AI calls on SphereVoice infrastructure — without touching SphereVoice's tenant, agent, or user systems.

Every consumer registers as an **Integration App** with its own credentials, rate limits, provider whitelist, and usage tracking. The API is designed to serve multiple products off the same pipeline engine.

### How It Differs from SphereVoice's Existing API

| Concern | SphereVoice Internal (`/api/v1/`) | Platform API (`/platform/v1/`) |
|---------|--------------------------|-------------------------------|
| Auth | JWT Bearer (user session) | App ID + App Secret (service-to-service) |
| Agents | Stored in SphereVoice DB | Sent inline per call (not stored) |
| Calls | Stored in `calls` table with full PII | Lightweight `pipeline_runs` row — no PII |
| Transcripts | Stored in `calls.transcript` (JSONB) | Delivered via webhook, cached 24h in Redis, NOT persisted in DB |
| Recordings | Stored in SphereVoice Azure Blob | Uploaded to caller's pre-signed URL, or not stored |
| Billing | No credit system (tenant pays externally) | Per-app usage tracking; consumer handles their own billing |
| Tenant/RLS | Enforced via `SET LOCAL app.current_tenant_id` | No RLS — platform calls don't belong to a SphereVoice tenant |
| Post-call | Extraction → CRM writeback → agent webhook | Webhook to consumer only — no extraction, no CRM |

### Architecture Diagram

```
External Apps                    SphereVoice Backend
─────────────                    ───────────

┌──────────────┐
│  NanoVoice   │──┐
└──────────────┘  │
                  │  POST /platform/v1/calls
┌──────────────┐  │  X-App-Id + X-App-Secret
│  Future App  │──┤
└──────────────┘  │
                  │
┌──────────────┐  │
│  Partner X   │──┘
└──────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Platform Auth (verify_platform_app)                 │
│  → looks up integration_apps table                   │
│  → returns PlatformContext {app_id, tier, limits}    │
├─────────────────────────────────────────────────────┤
│  Rate Limiter (enforce_rate_limit)                   │
│  → Redis sliding window (per-app RPM)                │
│  → Redis counter (per-app concurrent calls)          │
├─────────────────────────────────────────────────────┤
│  Platform Router (/platform/v1/)                     │
│  POST /calls        → start pipeline                 │
│  GET  /calls/{id}   → status + cost                  │
│  GET  /calls/{id}/result → full result (polling)     │
│  POST /calls/{id}/stop → force stop                  │
│  GET  /health       → capacity check                 │
│  GET  /usage        → app usage stats                │
├─────────────────────────────────────────────────────┤
│  CallOrchestrator.handle_platform_call()             │
│  → PipelineRun record (minimal, no PII)              │
│  → LiveKit room (nv_ prefix)                         │
│  → VoicePipeline (same engine as SphereVoice calls)          │
│  → Cost tracking (same PricingService)               │
│  → Webhook delivery on completion                    │
├─────────────────────────────────────────────────────┤
│  Pipeline Engine (UNCHANGED)                         │
│  STT → LLM → TTS → WebRTC                          │
│  VoicePipeline, PipecatProviderFactory,              │
│  CallCostTracker, PricingService — all reused        │
└─────────────────────────────────────────────────────┘
```

---

## 2. Data Isolation Rules

These are non-negotiable. Breaking any rule is a P0 incident.

| Rule | Enforcement |
|------|-------------|
| Platform calls MUST NOT create rows in the `calls` table | `handle_platform_call()` creates `PipelineRun`, never `Call` |
| Platform calls MUST NOT touch RLS/tenant context | No `SET LOCAL app.current_tenant_id` in platform path |
| Transcripts MUST NOT be persisted in SphereVoice Postgres | Delivered via webhook; cached in Redis with 24h TTL |
| Recordings MUST NOT be stored in SphereVoice blob storage | Uploaded to consumer's pre-signed URL if provided; else not recorded |
| Consumer agent configs (system_prompt) MUST NOT be stored | Only a SHA-256 fingerprint (`config_hash`) stored for debugging |
| Platform pipeline errors MUST NOT cascade to SphereVoice tenant calls | Separate Redis counters, separate Prometheus metrics, circuit breaker per app |
| Active call counter MUST always decrement (even on crash) | `try/finally` in stop handler; orphan cleanup on startup |

---

## 3. Phase Breakdown

### Phase 1: Database Models + Migration (Day 1)

**Goal:** Create the `integration_apps`, `pipeline_runs`, and `webhook_dead_letters` tables.

#### Files to Create

**`backend/app/modules/platform/__init__.py`**
```python
"""Platform module — Integration Apps and Platform API."""
```

**`backend/app/modules/platform/models.py`**

```python
"""Platform module — database models.

Tables:
- integration_apps: Registered external applications (NanoVoice, partners, etc.)
- pipeline_runs: Lightweight pipeline execution tracking (no PII)
- webhook_dead_letters: Failed webhook deliveries pending retry
"""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class IntegrationApp(Base):
    """Registered external application that can use the Platform API.

    Each app gets unique credentials (app_id + app_secret), configurable
    rate limits, provider whitelists, and independent usage tracking.
    """

    __tablename__ = "integration_apps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Identity
    app_name = Column(String(100), nullable=False)
    app_slug = Column(String(50), unique=True, nullable=False)

    # Auth credentials
    app_id = Column(String(50), unique=True, nullable=False, index=True)
    app_secret_hash = Column(String(128), nullable=False)
    app_secret_prefix = Column(String(12), nullable=False)

    # Ownership
    owner_type = Column(String(20), nullable=False, server_default="internal")
    owner_email = Column(String(255), nullable=True)

    # Tier & Limits
    tier = Column(String(20), nullable=False, server_default="starter")
    max_concurrent = Column(Integer, nullable=False, server_default="10")
    max_calls_per_minute = Column(Integer, nullable=False, server_default="20")
    max_call_duration_seconds = Column(Integer, nullable=False, server_default="300")
    allowed_providers = Column(
        JSONB, nullable=False,
        server_default='["groq_whisper", "openai", "groq_tts"]',
    )

    # Modes allowed
    allow_outbound = Column(Boolean, nullable=False, server_default="false")

    # Webhook defaults
    default_webhook_url = Column(Text, nullable=True)
    default_webhook_secret = Column(String(128), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, server_default="true")
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Usage counters (updated atomically on each call)
    total_calls = Column(Integer, nullable=False, server_default="0")
    total_duration_seconds = Column(Integer, nullable=False, server_default="0")
    total_cost_usd = Column(Numeric(12, 6), nullable=False, server_default="0")


class PipelineRun(Base):
    """Lightweight pipeline execution record. NO PII.

    Unlike the `calls` table (which stores transcripts, recording URLs,
    CRM data, and is tenant-scoped with RLS), pipeline_runs only tracks:
    - That a pipeline ran
    - How long it took
    - How much it cost
    - Whether it succeeded or failed

    The actual transcript and recording are delivered to the consumer
    via webhook and cached in Redis (24h TTL). Never persisted here.
    """

    __tablename__ = "pipeline_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Reference back to the integration app
    app_id = Column(
        UUID(as_uuid=True), ForeignKey("integration_apps.id"), nullable=False, index=True
    )
    external_id = Column(String(100), nullable=False, index=True)
    source = Column(String(50), nullable=False, server_default="nanovoice")

    # Status
    status = Column(String(20), nullable=False, server_default="connecting")
    # connecting → running → completed
    #                      → failed

    # Config fingerprint (NOT the actual prompt)
    config_hash = Column(String(32), nullable=True)

    # Mode
    mode = Column(String(10), nullable=False, server_default="web")

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Cost (USD)
    stt_cost = Column(Numeric(12, 8), nullable=True)
    llm_cost = Column(Numeric(12, 8), nullable=True)
    tts_cost = Column(Numeric(12, 8), nullable=True)
    telephony_cost = Column(Numeric(12, 8), nullable=True)
    total_cost = Column(Numeric(12, 8), nullable=True)

    # Error tracking
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # LiveKit reference (debugging only)
    livekit_room = Column(String(100), nullable=True)

    # Webhook delivery status
    webhook_delivered = Column(Boolean, nullable=False, server_default="false")

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WebhookDeadLetter(Base):
    """Failed webhook delivery pending retry.

    When the Platform API cannot deliver a call result webhook after
    all retry attempts, the payload is stored here (encrypted at rest).
    
    A background Celery task retries dead letters periodically.
    Entries expire and are purged after 7 days.
    """

    __tablename__ = "webhook_dead_letters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    pipeline_run_id = Column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id"), nullable=False, index=True
    )
    app_id = Column(
        UUID(as_uuid=True), ForeignKey("integration_apps.id"), nullable=False
    )

    event = Column(String(50), nullable=False)
    payload_encrypted = Column(Text, nullable=False)
    target_url = Column(Text, nullable=False)
    attempts = Column(Integer, nullable=False, server_default="0")
    last_error = Column(Text, nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(
        DateTime(timezone=True), nullable=False,
    )
```

#### Alembic Migration

Run:
```bash
cd backend
alembic revision --autogenerate -m "add_platform_api_tables"
```

Verify the generated migration creates all 3 tables and indexes.

#### Seed NanoVoice App

Add to a new seed script or extend `backend/seed.py`:

```python
# After migration, seed the NanoVoice integration app
import hashlib, secrets

app_secret = f"nv_sec_{secrets.token_urlsafe(32)}"
print(f"NANOVOICE APP SECRET (save this): {app_secret}")

app = IntegrationApp(
    app_name="NanoVoice",
    app_slug="nanovoice",
    app_id=f"nv_app_{secrets.token_urlsafe(8)}",
    app_secret_hash=hashlib.sha256(app_secret.encode()).hexdigest(),
    app_secret_prefix=app_secret[:12],
    owner_type="internal",
    owner_email="girish@Sphere.ai",
    tier="enterprise",
    max_concurrent=50,
    max_calls_per_minute=30,
    max_call_duration_seconds=600,
    allowed_providers=["groq_whisper", "openai", "groq_tts", "soniox", "elevenlabs", "cartesia"],
    allow_outbound=False,
)
```

#### Verification

- [ ] Migration runs cleanly: `alembic upgrade head`
- [ ] Tables exist: `\dt integration_apps`, `\dt pipeline_runs`, `\dt webhook_dead_letters`
- [ ] NanoVoice app seeded and queryable
- [ ] Existing SphereVoice tables untouched

---

### Phase 2: Platform Auth + Rate Limiting (Day 2)

**Goal:** Build the auth dependency and rate limiter that protect every platform endpoint.

#### Files to Create

**`backend/app/core/platform_auth.py`**

```python
"""Platform API authentication — per-app credentials.

Authentication flow:
1. Consumer sends X-App-Id and X-App-Secret headers
2. We hash the secret and look up the integration_apps table
3. Constant-time comparison prevents timing attacks
4. Returns PlatformContext with app config, limits, and permissions

This is completely separate from SphereVoice's JWT auth (core/dependencies.py).
No JWT, no user session, no RLS.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from dataclasses import dataclass
from uuid import UUID

import structlog
from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.modules.platform.models import IntegrationApp

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PlatformContext:
    """Immutable context for the current platform API request.

    Injected via Depends(verify_platform_app) into every platform endpoint.
    Contains everything the endpoint needs to enforce limits and track usage.
    """

    app_uuid: UUID
    app_id: str
    app_name: str
    app_slug: str
    tier: str
    max_concurrent: int
    max_calls_per_minute: int
    max_call_duration_seconds: int
    allowed_providers: list[str]
    allow_outbound: bool
    default_webhook_url: str | None
    default_webhook_secret: str | None


async def verify_platform_app(request: Request) -> PlatformContext:
    """Authenticate an integration app via X-App-Id + X-App-Secret.

    Raises:
        401: Missing or invalid credentials
        403: App is deactivated
    """
    app_id_header = request.headers.get("X-App-Id", "")
    app_secret_header = request.headers.get("X-App-Secret", "")

    if not app_id_header or not app_secret_header:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_credentials",
                "message": "X-App-Id and X-App-Secret headers are required",
            },
        )

    # Hash the provided secret for comparison
    secret_hash = hashlib.sha256(app_secret_header.encode()).hexdigest()

    async with async_session_factory() as db:
        result = await db.execute(
            select(IntegrationApp).where(IntegrationApp.app_id == app_id_header)
        )
        app = result.scalar_one_or_none()

    if app is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_app_id", "message": "App not found"},
        )

    if not app.is_active:
        raise HTTPException(
            status_code=403,
            detail={"error": "app_deactivated", "message": "Integration app is deactivated"},
        )

    # Constant-time comparison to prevent timing-based secret guessing
    if not hmac.compare_digest(secret_hash, app.app_secret_hash):
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_secret", "message": "App secret is incorrect"},
        )

    # Fire-and-forget: update last_used_at (non-blocking)
    asyncio.create_task(_touch_last_used(app.id))

    return PlatformContext(
        app_uuid=app.id,
        app_id=app.app_id,
        app_name=app.app_name,
        app_slug=app.app_slug,
        tier=app.tier,
        max_concurrent=app.max_concurrent,
        max_calls_per_minute=app.max_calls_per_minute,
        max_call_duration_seconds=app.max_call_duration_seconds,
        allowed_providers=app.allowed_providers or [],
        allow_outbound=app.allow_outbound,
        default_webhook_url=app.default_webhook_url,
        default_webhook_secret=app.default_webhook_secret,
    )


async def _touch_last_used(app_uuid: UUID) -> None:
    """Update last_used_at timestamp — best-effort, non-blocking."""
    try:
        from datetime import datetime, UTC

        async with async_session_factory() as db:
            await db.execute(
                update(IntegrationApp)
                .where(IntegrationApp.id == app_uuid)
                .values(last_used_at=datetime.now(UTC))
            )
            await db.commit()
    except Exception:
        pass  # Non-critical — don't fail requests over timestamp updates
```

**`backend/app/core/platform_rate_limit.py`**

```python
"""Platform API rate limiting — per-app, Redis-backed.

Two independent limits enforced:
1. Requests per minute (sliding window) — prevents burst abuse
2. Concurrent active calls (counter) — prevents resource exhaustion

Both use Redis atomic operations for correctness under concurrency.
"""

from __future__ import annotations

import time

import structlog
from fastapi import Depends, HTTPException, Request

from app.core.platform_auth import PlatformContext, verify_platform_app

logger = structlog.get_logger(__name__)


async def enforce_rate_limit(
    request: Request,
    ctx: PlatformContext = Depends(verify_platform_app),
) -> PlatformContext:
    """Enforce per-app rate limit and concurrency limit.

    Layered on top of verify_platform_app — auth runs first,
    then limits are checked. Returns the same PlatformContext.
    """
    from app.core.database import get_redis

    redis = await get_redis()
    now = int(time.time())

    # ── 1. Per-minute rate limit (sliding window) ──
    minute_bucket = now // 60
    rpm_key = f"platform:rpm:{ctx.app_id}:{minute_bucket}"

    count = await redis.incr(rpm_key)
    if count == 1:
        await redis.expire(rpm_key, 120)  # 2 min TTL (covers current + next window)

    if count > ctx.max_calls_per_minute:
        retry_after = 60 - (now % 60)
        logger.warning(
            "platform_rate_limit_exceeded",
            app_id=ctx.app_id,
            rpm=count,
            limit=ctx.max_calls_per_minute,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Max {ctx.max_calls_per_minute} requests/minute for your app tier",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # ── 2. Concurrent active calls ──
    active_key = f"platform:active:{ctx.app_id}"
    active = int(await redis.get(active_key) or 0)

    if active >= ctx.max_concurrent:
        logger.warning(
            "platform_concurrency_limit_exceeded",
            app_id=ctx.app_id,
            active=active,
            limit=ctx.max_concurrent,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "concurrency_limit_exceeded",
                "message": f"Max {ctx.max_concurrent} concurrent calls for your app tier",
                "active_calls": active,
            },
        )

    return ctx
```

#### Verification

- [ ] Import `verify_platform_app` and `enforce_rate_limit` — no circular imports
- [ ] Valid credentials → returns `PlatformContext`
- [ ] Wrong secret → 401
- [ ] Missing headers → 401
- [ ] Deactivated app → 403
- [ ] Rate limit Redis keys increment correctly
- [ ] Concurrency check reads from Redis

---

### Phase 3: Platform Router + Schemas (Day 2–3)

**Goal:** Build all 6 platform endpoints (no orchestrator logic yet — just routing + validation).

#### Files to Create

**`backend/app/modules/platform/schemas.py`**

```python
"""Platform API — request/response schemas.

All schemas are self-contained. They do NOT import from
SphereVoice's existing agent/call schemas to avoid coupling.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Call Request ────────────────────────────────────

class PlatformCallRequest(BaseModel):
    """Start a voice pipeline call.

    The consumer sends the full agent config inline — SphereVoice does not
    store or persist agent definitions for platform calls.
    """

    # Consumer's reference
    external_id: str = Field(
        ...,
        max_length=100,
        description="Your unique reference for this call (for idempotency and tracking)",
    )

    # Call mode
    mode: str = Field("web", pattern="^(web|outbound)$")

    # Agent config (inline — not stored)
    system_prompt: str = Field(
        ...,
        max_length=50000,
        description="The LLM system prompt for this call",
    )
    first_message: str | None = Field(
        None,
        max_length=2000,
        description="Optional greeting the agent says when the call connects",
    )
    voice: str = Field("alloy", max_length=100)
    llm_model: str = Field("gpt-4o-mini", max_length=100)
    stt_provider: str = Field("groq_whisper", max_length=50)
    tts_provider: str = Field("openai", max_length=50)
    tools: list[dict] = Field(
        default_factory=list,
        max_length=10,
        description="OpenAI function-calling tool definitions (max 10)",
    )
    max_duration_seconds: int | None = Field(
        None,
        ge=10,
        le=600,
        description="Max call duration. Defaults to your app tier's limit.",
    )

    # Optional context injection
    context_documents: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Up to 5 text strings injected as RAG context",
    )

    # Dynamic variables for prompt template injection
    dynamic_variables: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value pairs for {{variable}} replacement in system_prompt",
    )

    # Delivery
    webhook_url: str | None = Field(
        None,
        description="Where to POST call events. Falls back to app default.",
    )
    webhook_secret: str | None = Field(
        None,
        min_length=16,
        description="HMAC-SHA256 signing key for webhook payloads. Falls back to app default.",
    )
    recording_upload_url: str | None = Field(
        None,
        description="Pre-signed PUT URL. SphereVoice uploads the recording here. If omitted, no recording is saved.",
    )

    # Outbound only
    to_number: str | None = Field(
        None,
        max_length=20,
        description="Outbound phone number (E.164 format). Required for mode=outbound.",
    )
    from_number: str | None = Field(
        None,
        max_length=20,
        description="Caller ID phone number. Required for mode=outbound.",
    )


# ── Call Response ───────────────────────────────────

class PlatformCallResponse(BaseModel):
    """Response after starting a platform call."""

    call_id: str
    external_id: str
    status: str  # connecting

    # Web mode — consumer uses these to join the LiveKit room
    livekit_url: str | None = None
    livekit_token: str | None = None
    room_name: str | None = None


# ── Call Status ─────────────────────────────────────

class CostBreakdown(BaseModel):
    stt_usd: float
    llm_usd: float
    tts_usd: float
    telephony_usd: float
    total_usd: float


class ErrorDetail(BaseModel):
    code: str
    message: str


class PlatformCallStatus(BaseModel):
    """Pipeline run status. Does NOT include transcript."""

    call_id: str
    external_id: str
    status: str  # connecting | running | completed | failed
    duration_seconds: int | None = None
    cost: CostBreakdown | None = None
    error: ErrorDetail | None = None


# ── Call Result (Polling Fallback) ──────────────────

class PlatformCallResult(BaseModel):
    """Full call result including transcript. Available for 24h via Redis cache."""

    call_id: str
    external_id: str
    app_id: str
    status: str
    duration_seconds: int | None = None
    transcript: list[dict] = []  # [{speaker, text, timestamp}]
    cost: CostBreakdown | None = None
    disconnection_reason: str | None = None
    error: ErrorDetail | None = None


# ── Health ──────────────────────────────────────────

class AppCapacity(BaseModel):
    active_calls: int
    max_concurrent: int
    available: int


class PlatformHealth(BaseModel):
    healthy: bool
    your_app: AppCapacity
    platform: dict  # {"livekit": "ok", "redis": "ok"}


# ── Usage ───────────────────────────────────────────

class PlatformUsage(BaseModel):
    app_name: str
    total_calls: int
    total_duration_seconds: int
    total_cost_usd: float
    active_calls_now: int
    limits: dict
```

**`backend/app/modules/platform/router.py`**

```python
"""Platform API — router with all endpoints.

All endpoints require integration app authentication via
X-App-Id + X-App-Secret headers.

Endpoints:
  POST /platform/v1/calls           — Start a pipeline call
  GET  /platform/v1/calls/{id}      — Get status + cost (no transcript)
  GET  /platform/v1/calls/{id}/result — Full result including transcript (polling fallback)
  POST /platform/v1/calls/{id}/stop — Force-stop a running call
  GET  /platform/v1/health          — App capacity + platform health
  GET  /platform/v1/usage           — App usage stats
"""

from __future__ import annotations

import json
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.database import async_session_factory, get_redis
from app.core.platform_auth import PlatformContext, verify_platform_app
from app.core.platform_rate_limit import enforce_rate_limit
from app.modules.platform.models import PipelineRun
from app.modules.platform.schemas import (
    CostBreakdown,
    ErrorDetail,
    PlatformCallRequest,
    PlatformCallResponse,
    PlatformCallResult,
    PlatformCallStatus,
    PlatformHealth,
    PlatformUsage,
    AppCapacity,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/platform/v1", tags=["Platform API"])


# ── POST /calls — Start a pipeline call ─────────────

@router.post("/calls", response_model=PlatformCallResponse)
async def start_platform_call(
    body: PlatformCallRequest,
    ctx: PlatformContext = Depends(enforce_rate_limit),
):
    """Start a voice pipeline call.

    Send the full agent config inline. SphereVoice runs the pipeline, delivers
    the transcript and cost via webhook when the call ends.

    **Idempotency:** If you send the same `external_id` within 5 minutes,
    the cached response is returned without starting a new call.
    """
    # ── Validate provider access ──
    for provider in [body.stt_provider, body.tts_provider]:
        if provider not in ctx.allowed_providers:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "provider_not_allowed",
                    "message": f"Provider '{provider}' is not allowed for your app tier",
                    "allowed_providers": ctx.allowed_providers,
                },
            )

    # ── Validate outbound mode ──
    if body.mode == "outbound" and not ctx.allow_outbound:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "outbound_not_allowed",
                "message": "Outbound calls are not enabled for your app",
            },
        )

    if body.mode == "outbound" and (not body.to_number or not body.from_number):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "missing_outbound_fields",
                "message": "to_number and from_number are required for outbound calls",
            },
        )

    # ── Enforce duration cap from app tier ──
    max_duration = min(
        body.max_duration_seconds or ctx.max_call_duration_seconds,
        ctx.max_call_duration_seconds,
    )

    # ── Resolve webhook URL (request → app default → reject) ──
    webhook_url = body.webhook_url or ctx.default_webhook_url
    webhook_secret = body.webhook_secret or ctx.default_webhook_secret

    if not webhook_url:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "webhook_required",
                "message": "Provide webhook_url in request or set a default webhook for your app",
            },
        )

    if not webhook_secret:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "webhook_secret_required",
                "message": "Provide webhook_secret in request or set a default for your app",
            },
        )

    # ── Idempotency check ──
    redis = await get_redis()
    idempotency_key = f"platform:idem:{ctx.app_id}:{body.external_id}"
    cached = await redis.get(idempotency_key)
    if cached:
        logger.info("platform_call_idempotent_hit", app_id=ctx.app_id, external_id=body.external_id)
        return PlatformCallResponse(**json.loads(cached))

    # ── Delegate to orchestrator ──
    from app.modules.pipeline.orchestrator import CallOrchestrator

    async with async_session_factory() as db:
        orchestrator = CallOrchestrator(db)
        result = await orchestrator.handle_platform_call(
            ctx=ctx,
            request=body,
            max_duration=max_duration,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )

    # ── Cache for idempotency (5 min) ──
    await redis.setex(idempotency_key, 300, result.model_dump_json())

    return result


# ── GET /calls/{id} — Status + cost (no transcript) ──

@router.get("/calls/{call_id}", response_model=PlatformCallStatus)
async def get_platform_call_status(
    call_id: UUID,
    ctx: PlatformContext = Depends(verify_platform_app),
):
    """Get pipeline run status and cost breakdown.

    Does NOT include the transcript. Use `GET /calls/{id}/result`
    or receive the webhook for transcript data.
    """
    async with async_session_factory() as db:
        result = await db.execute(
            select(PipelineRun)
            .where(PipelineRun.id == call_id)
            .where(PipelineRun.app_id == ctx.app_uuid)
        )
        run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(404, detail={"error": "not_found", "message": "Pipeline run not found"})

    cost = None
    if run.total_cost is not None:
        cost = CostBreakdown(
            stt_usd=float(run.stt_cost or 0),
            llm_usd=float(run.llm_cost or 0),
            tts_usd=float(run.tts_cost or 0),
            telephony_usd=float(run.telephony_cost or 0),
            total_usd=float(run.total_cost),
        )

    error = None
    if run.error_code:
        error = ErrorDetail(code=run.error_code, message=run.error_message or "")

    return PlatformCallStatus(
        call_id=str(run.id),
        external_id=run.external_id,
        status=run.status,
        duration_seconds=run.duration_seconds,
        cost=cost,
        error=error,
    )


# ── GET /calls/{id}/result — Full result (polling fallback) ──

@router.get("/calls/{call_id}/result", response_model=PlatformCallResult)
async def get_platform_call_result(
    call_id: UUID,
    ctx: PlatformContext = Depends(verify_platform_app),
):
    """Get full call result including transcript.

    This is a **polling fallback** for when your webhook receiver
    was down. Results are cached in Redis for 24 hours after the
    call ends. After that, they are gone — SphereVoice does not persist
    platform call transcripts.
    """
    redis = await get_redis()
    cached = await redis.get(f"platform:result:{call_id}")

    if not cached:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "result_not_found",
                "message": "Result not found. It may have expired (24h TTL) or the call is still running.",
            },
        )

    result = json.loads(cached)

    # Verify this result belongs to this app (prevent cross-app data access)
    if result.get("app_id") != ctx.app_id:
        raise HTTPException(
            status_code=404,
            detail={"error": "result_not_found", "message": "Result not found for your app"},
        )

    return PlatformCallResult(**result)


# ── POST /calls/{id}/stop — Force stop ──

@router.post("/calls/{call_id}/stop", status_code=202)
async def stop_platform_call(
    call_id: UUID,
    ctx: PlatformContext = Depends(verify_platform_app),
):
    """Force-stop a running pipeline call.

    The call will be finalized and the webhook delivered as if
    the call ended naturally.
    """
    # Verify ownership
    async with async_session_factory() as db:
        result = await db.execute(
            select(PipelineRun)
            .where(PipelineRun.id == call_id)
            .where(PipelineRun.app_id == ctx.app_uuid)
        )
        run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(404, detail={"error": "not_found"})

    if run.status in ("completed", "failed"):
        return {"status": run.status, "message": "Call already ended"}

    from app.modules.pipeline.orchestrator import CallOrchestrator

    async with async_session_factory() as db:
        orchestrator = CallOrchestrator(db)
        await orchestrator.handle_platform_call_end(call_id)

    return {"status": "stopping", "message": "Call stop initiated"}


# ── GET /health — Capacity check ──

@router.get("/health", response_model=PlatformHealth)
async def platform_health(
    ctx: PlatformContext = Depends(verify_platform_app),
):
    """Check your app's capacity and SphereVoice health.

    Use this before starting calls to verify capacity is available.
    """
    redis = await get_redis()
    active = int(await redis.get(f"platform:active:{ctx.app_id}") or 0)

    # LiveKit health check (best-effort)
    livekit_ok = "ok"
    try:
        from app.core.config import get_settings
        from livekit.api import LiveKitAPI

        settings = get_settings()
        api = LiveKitAPI(
            url=settings.LIVEKIT_URL,
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        await api.room.list_rooms()
    except Exception:
        livekit_ok = "degraded"

    return PlatformHealth(
        healthy=livekit_ok == "ok",
        your_app=AppCapacity(
            active_calls=active,
            max_concurrent=ctx.max_concurrent,
            available=max(0, ctx.max_concurrent - active),
        ),
        platform={"livekit": livekit_ok},
    )


# ── GET /usage — App usage stats ──

@router.get("/usage", response_model=PlatformUsage)
async def platform_usage(
    ctx: PlatformContext = Depends(verify_platform_app),
):
    """Get your app's aggregate usage stats."""
    redis = await get_redis()
    active = int(await redis.get(f"platform:active:{ctx.app_id}") or 0)

    async with async_session_factory() as db:
        from app.modules.platform.models import IntegrationApp

        result = await db.execute(
            select(IntegrationApp).where(IntegrationApp.id == ctx.app_uuid)
        )
        app = result.scalar_one()

    return PlatformUsage(
        app_name=app.app_name,
        total_calls=app.total_calls,
        total_duration_seconds=app.total_duration_seconds,
        total_cost_usd=float(app.total_cost_usd),
        active_calls_now=active,
        limits={
            "max_concurrent": ctx.max_concurrent,
            "max_calls_per_minute": ctx.max_calls_per_minute,
            "max_call_duration_seconds": ctx.max_call_duration_seconds,
        },
    )
```

#### Register Router in main.py

Add to `backend/app/main.py` after existing router registrations:

```python
from app.modules.platform.router import router as platform_router

# After the existing app.include_router(pricing_router, prefix=API_V1) line:
app.include_router(platform_router)  # Own prefix: /platform/v1/
```

#### Verification

- [ ] `POST /platform/v1/calls` returns 401 without headers
- [ ] `POST /platform/v1/calls` returns 401 with wrong secret
- [ ] `POST /platform/v1/calls` accepts valid app credentials and returns validation errors for missing fields
- [ ] `GET /platform/v1/health` returns capacity info
- [ ] Idempotency: same external_id within 5 min returns cached response
- [ ] Provider whitelist: disallowed provider → 403
- [ ] Outbound mode: disabled → 403
- [ ] All existing SphereVoice endpoints unaffected

---

### Phase 4: Orchestrator — `handle_platform_call()` (Day 3–5)

**Goal:** Add the core method that runs a pipeline for platform calls. This is the most complex and critical phase.

#### File to Edit: `backend/app/modules/pipeline/orchestrator.py`

Add TWO new methods to `CallOrchestrator`:

1. `handle_platform_call()` — starts the pipeline
2. `_make_platform_stop_handler()` — handles call completion (static method)

**Reference pattern:** Follow `handle_test_call()` (line 406) but with these critical differences:

| handle_test_call() | handle_platform_call() |
|--------------------|----------------------|
| Loads Agent from DB | Receives config inline via PlatformCallRequest |
| Creates a `Call` record | Creates a `PipelineRun` record |
| Sets RLS tenant context | No RLS, no tenant |
| Uses `_make_pipeline_stop_handler` | Uses `_make_platform_stop_handler` |
| Stop handler writes to `calls` table | Stop handler writes to `pipeline_runs` table |
| Stop handler triggers post_call extraction | Stop handler sends webhook only |
| Recording stored in SphereVoice blob | Recording uploaded to caller's pre-signed URL |
| Transcript stored in `calls.transcript` | Transcript sent via webhook, cached in Redis |

```python
# Add to CallOrchestrator class — new method

async def handle_platform_call(
    self,
    ctx: PlatformContext,
    request: PlatformCallRequest,
    max_duration: int,
    webhook_url: str,
    webhook_secret: str,
) -> PlatformCallResponse:
    """Run a voice pipeline for an external integration app.

    This method is the platform equivalent of handle_test_call().
    Key differences:
    - No SphereVoice Agent lookup — config comes inline in the request
    - No SphereVoice Call record — creates PipelineRun (minimal, no PII)
    - No RLS tenant context — platform calls don't belong to a SphereVoice tenant
    - Transcript/recording delivered via webhook, not stored in SphereVoice
    - Capacity-gated via per-app Redis counters
    """
    import hashlib
    from types import SimpleNamespace
    from app.core.database import get_redis
    from app.modules.platform.models import PipelineRun

    redis = await get_redis()

    # 1. Increment active call counter (Redis atomic)
    active_key = f"platform:active:{ctx.app_id}"
    await redis.incr(active_key)

    try:
        # 2. Create PipelineRun record (NOT a Call record)
        run = PipelineRun(
            app_id=ctx.app_uuid,
            external_id=request.external_id,
            source=ctx.app_slug,
            status="connecting",
            mode=request.mode,
            started_at=datetime.now(UTC),
            config_hash=hashlib.sha256(
                request.system_prompt[:500].encode()
            ).hexdigest()[:16],
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        # 3. Create LiveKit room
        room_name = f"pf_{run.id.hex[:12]}"
        await self._create_livekit_room(room_name)
        run.livekit_room = room_name
        await self.db.commit()

        # 4. Build a virtual agent (SimpleNamespace, no DB model)
        # VoicePipeline reads attributes from this object.
        # Must match the attrs VoicePipeline accesses on agent.
        agent_ns = SimpleNamespace(
            id=run.id,
            name=f"platform_{request.external_id}",
            system_prompt=request.system_prompt,
            first_message=request.first_message,
            voice_id=request.voice,
            llm_model=request.llm_model,
            language="en",
            interruption_threshold=0.5,
            max_call_duration=max_duration,
            silence_timeout=30,
            max_silence_warnings=2,
            knowledge_bases=[],
            tools=[],
            stt_provider_id=None,
            llm_provider_id=None,
            tts_provider_id=None,
            flow_config=None,
            tenant_id=None,
            stt_config=None,
            agent_tool_configs=[],
        )

        # 5. Resolve providers using platform-level env vars
        # (skips per-agent and per-tenant DB lookups)
        stt_service = await PipecatProviderFactory.get_stt(agent_ns, self.db)
        llm_service = await PipecatProviderFactory.get_llm(agent_ns, self.db)
        tts_service = await PipecatProviderFactory.get_tts(agent_ns, self.db)

        # 6. Cost tracker (reuses existing CallCostTracker)
        provider_info = await PipecatProviderFactory.resolve_provider_info(agent_ns, self.db)
        cost_tracker = CallCostTracker(
            call_id=str(run.id),
            stt_provider=provider_info.get("stt", {}).get("provider"),
            stt_model=provider_info.get("stt", {}).get("model"),
            llm_provider=provider_info.get("llm", {}).get("provider"),
            llm_model=provider_info.get("llm", {}).get("model"),
            tts_provider=provider_info.get("tts", {}).get("provider"),
            tts_model=provider_info.get("tts", {}).get("model"),
            telephony_provider="livekit",  # web = no telephony cost
        )

        # 7. Generate agent token
        agent_token = self._create_agent_token(room_name)

        # 8. Build pipeline
        pipeline = VoicePipeline(
            call_id=run.id,
            agent=agent_ns,
            livekit_url=settings.LIVEKIT_URL,
            livekit_token=agent_token,
            room_name=room_name,
            stt_service=stt_service,
            stt_fallback=None,
            llm_service=llm_service,
            tts_service=tts_service,
            dynamic_variables=request.dynamic_variables or {},
            cost_tracker=cost_tracker,
            on_error=self._make_pipeline_error_handler(
                run.id, tenant_id=None, direction="inbound",
            ),
            on_stop=CallOrchestrator._make_platform_stop_handler(
                run_id=run.id,
                app_id=ctx.app_id,
                app_uuid=ctx.app_uuid,
                external_id=request.external_id,
                webhook_url=webhook_url,
                webhook_secret=webhook_secret,
                recording_upload_url=request.recording_upload_url,
                cost_tracker=cost_tracker,
            ),
            auto_greet_on_first_join=bool(request.first_message),
            dry_run=True,  # Skip CRM enrichment
        )

        # 9. Store in active pipelines registry
        _active_pipelines[f"pf_{run.id}"] = pipeline

        # 10. Start pipeline (async, non-blocking)
        await pipeline.start()

        # 11. Generate caller token for the browser (web mode)
        caller_token = self._create_caller_token(
            room_name, f"platform_caller_{request.external_id}"
        )

        return PlatformCallResponse(
            call_id=str(run.id),
            external_id=request.external_id,
            status="connecting",
            livekit_url=settings.LIVEKIT_URL,
            livekit_token=caller_token,
            room_name=room_name,
        )

    except Exception:
        # Decrement on failure so counter stays accurate
        await redis.decr(active_key)
        logger.exception(
            "platform_call_start_failed",
            app_id=ctx.app_id,
            external_id=request.external_id,
        )
        raise


@staticmethod
def _make_platform_stop_handler(
    run_id: UUID,
    app_id: str,
    app_uuid: UUID,
    external_id: str,
    webhook_url: str,
    webhook_secret: str,
    recording_upload_url: str | None,
    cost_tracker: CallCostTracker,
):
    """Build the on_stop callback for platform pipeline runs.

    Unlike _make_pipeline_stop_handler (which writes to the calls table,
    triggers post-call extraction, and enqueues CRM writeback), this:

    1. Updates pipeline_runs (minimal, no PII)
    2. Caches full result in Redis (24h TTL) — polling fallback
    3. Delivers transcript + cost via webhook
    4. Decrements the active call counter (ALWAYS, even on error)
    5. Does NOT trigger extraction, CRM, or agent webhooks
    """

    async def _handle_platform_stop(reason: str) -> None:
        from app.core.database import get_redis
        from app.modules.platform.models import PipelineRun, IntegrationApp
        from app.modules.platform.webhook_dispatcher import dispatch_platform_webhook
        from app.modules.pricing.service import PricingService

        redis = await get_redis()
        active_key = f"platform:active:{app_id}"

        try:
            # 1. Get transcript from pipeline
            pipeline = _active_pipelines.pop(f"pf_{run_id}", None)
            transcript: list[dict] = []
            if pipeline:
                transcript = pipeline.get_transcript()

            # 2. Calculate duration + costs
            async with async_session_factory() as db:
                run = await db.get(PipelineRun, run_id)
                if not run or run.status == "completed":
                    return  # Already finalized

                ended_at = datetime.now(UTC)
                duration = int((ended_at - run.started_at).total_seconds()) if run.started_at else 0

                # Cost calculation
                stt_cost = llm_cost = tts_cost = telephony_cost = total_cost = None
                usage_metrics_dict = None

                if cost_tracker and duration > 0:
                    cost_tracker.set_telephony_seconds(0)  # web = free
                    cost_tracker.estimate_from_transcript(transcript, float(duration))
                    usage_metrics_dict = cost_tracker.to_dict()

                    try:
                        usage = cost_tracker.get_usage_metrics()
                        breakdown = await PricingService.calculate_costs(db, usage)
                        stt_cost = breakdown.stt_cost
                        llm_cost = breakdown.llm_cost
                        tts_cost = breakdown.tts_cost
                        telephony_cost = breakdown.telephony_cost
                        total_cost = breakdown.total_cost
                    except Exception:
                        logger.warning("platform_cost_calculation_failed", run_id=str(run_id), exc_info=True)

                # 3. Update PipelineRun record (minimal)
                run.status = "completed"
                run.ended_at = ended_at
                run.duration_seconds = duration
                run.stt_cost = stt_cost
                run.llm_cost = llm_cost
                run.tts_cost = tts_cost
                run.telephony_cost = telephony_cost
                run.total_cost = total_cost
                await db.commit()

                # 4. Update app-level usage counters (atomic)
                from sqlalchemy import update as sql_update

                await db.execute(
                    sql_update(IntegrationApp)
                    .where(IntegrationApp.id == app_uuid)
                    .values(
                        total_calls=IntegrationApp.total_calls + 1,
                        total_duration_seconds=IntegrationApp.total_duration_seconds + duration,
                        total_cost_usd=IntegrationApp.total_cost_usd + (total_cost or 0),
                    )
                )
                await db.commit()

            # 5. Build result payload
            cost_dict = None
            if total_cost is not None:
                cost_dict = {
                    "stt_usd": float(stt_cost or 0),
                    "llm_usd": float(llm_cost or 0),
                    "tts_usd": float(tts_cost or 0),
                    "telephony_usd": float(telephony_cost or 0),
                    "total_usd": float(total_cost),
                }

            result_payload = {
                "call_id": str(run_id),
                "external_id": external_id,
                "app_id": app_id,
                "status": "completed",
                "duration_seconds": duration,
                "transcript": transcript,
                "cost": cost_dict,
                "disconnection_reason": reason,
                "error": None,
            }

            # 6. Cache in Redis (24h TTL) — polling fallback
            import json as json_mod

            await redis.setex(
                f"platform:result:{run_id}",
                86400,
                json_mod.dumps(result_payload, default=str),
            )

            # 7. Deliver webhook (with retry + dead letter)
            await dispatch_platform_webhook(
                url=webhook_url,
                secret=webhook_secret,
                event="call.ended",
                payload=result_payload,
                pipeline_run_id=run_id,
                app_uuid=app_uuid,
            )

        except Exception:
            logger.exception("platform_stop_handler_error", run_id=str(run_id))

            # Mark PipelineRun as failed
            try:
                async with async_session_factory() as db:
                    run = await db.get(PipelineRun, run_id)
                    if run and run.status not in ("completed", "failed"):
                        run.status = "failed"
                        run.error_code = "stop_handler_crash"
                        run.error_message = "Internal error during call finalization"
                        await db.commit()
            except Exception:
                pass

        finally:
            # ALWAYS decrement active counter — even on error
            try:
                await redis.decr(active_key)
                # Prevent negative drift from double-decrements
                current = int(await redis.get(active_key) or 0)
                if current < 0:
                    await redis.set(active_key, 0)
            except Exception:
                pass

    return _handle_platform_stop


async def handle_platform_call_end(self, pipeline_run_id: UUID) -> None:
    """Force-stop a platform pipeline run.

    Called from the /calls/{id}/stop endpoint.
    Delegates to the existing pipeline stop mechanism.
    """
    pipeline_key = f"pf_{pipeline_run_id}"
    pipeline = _active_pipelines.get(pipeline_key)

    if pipeline:
        await pipeline.stop("manual_stop")
    else:
        # Pipeline not in memory — might already be stopped or on another worker
        logger.warning(
            "platform_call_end_pipeline_not_found",
            run_id=str(pipeline_run_id),
        )
```

#### Key Implementation Notes

1. **The virtual agent (`SimpleNamespace`)** must expose all the attributes that `VoicePipeline.__init__` and the provider factory read from the agent object. Check `voice_pipeline.py` line 134-215 and `factory.py` `resolve_provider_info()` for exact attribute access patterns. If `VoicePipeline` accesses an attribute you didn't add to the namespace, it will crash at runtime.

2. **The `_make_platform_stop_handler` is a static method closure** (same pattern as `_make_pipeline_stop_handler` on line 709). It captures all needed values at creation time because by the time it executes, the original request context is gone.

3. **`_active_pipelines` is a global dict** in `orchestrator.py`. Platform pipelines use the `pf_` prefix to avoid key collision with SphereVoice call pipelines (which use string call_id) and test call pipelines.

4. **Error handling in the start method:** If anything fails after `redis.incr(active_key)`, we MUST decrement in the except block. The stop handler's `finally` block also decrements, so the normal flow is: increment on start, decrement on stop. The except block handles the case where start itself fails before the pipeline runs.

#### Verification

- [ ] Platform call starts: LiveKit room created, pipeline running, caller token returned
- [ ] Call ends naturally (silence timeout): stop handler fires, webhook delivered, Redis result cached
- [ ] Manual stop via API: pipeline stops, same finalization as natural end
- [ ] Active call counter: increments on start, decrements on end/error
- [ ] Cost calculation: matches test call costs for same duration
- [ ] Pipeline run record: status transitions correctly (connecting → completed / failed)
- [ ] No `calls` table rows created for platform calls
- [ ] No RLS context set during platform calls
- [ ] Existing SphereVoice calls (inbound, outbound, test) are completely unaffected

---

### Phase 5: Webhook Dispatcher (Day 4–5)

**Goal:** Reliable webhook delivery with retry, HMAC signing, and dead letter storage.

#### File to Create: `backend/app/modules/platform/webhook_dispatcher.py`

```python
"""Platform API — reliable webhook delivery.

Delivery guarantees:
1. Retry up to 5 times with exponential backoff (1s, 5s, 30s, 2min, 10min)
2. HMAC-SHA256 signature on every payload (X-Webhook-Signature header)
3. Idempotency key on every delivery (X-Webhook-Id header)
4. Dead letter storage for deliveries that exhaust all retries
5. 4xx responses from consumer → no retry (client error)
6. 5xx responses or timeouts → retry

Separate from SphereVoice's existing webhook_delivery.py which handles
agent webhooks for SphereVoice tenant calls. Different model, different
retry logic, different storage.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, UTC
from uuid import UUID, uuid4

import httpx
import structlog

from app.core.database import async_session_factory

logger = structlog.get_logger(__name__)

# Retry delays in seconds: 1s, 5s, 30s, 2min, 10min
RETRY_DELAYS = [1, 5, 30, 120, 600]


async def dispatch_platform_webhook(
    url: str,
    secret: str,
    event: str,
    payload: dict,
    pipeline_run_id: UUID,
    app_uuid: UUID,
) -> bool:
    """Deliver a webhook with retry and dead-letter fallback.

    Args:
        url: Target webhook URL
        secret: HMAC signing key
        event: Event type (e.g., "call.ended", "call.failed")
        payload: JSON-serializable dict
        pipeline_run_id: For dead letter tracking
        app_uuid: Integration app UUID

    Returns:
        True if eventually delivered, False if dead-lettered.
    """
    body = json.dumps(payload, default=str, separators=(",", ":"))
    signature = hmac.new(
        secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()

    webhook_id = str(uuid4())

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"sha256={signature}",
        "X-Webhook-Event": event,
        "X-Webhook-Id": webhook_id,
        "X-Webhook-Timestamp": datetime.now(UTC).isoformat(),
        "User-Agent": "SphereVoice-Platform-Webhook/1.0",
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(len(RETRY_DELAYS)):
            try:
                resp = await client.post(
                    url,
                    content=body,
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code < 300:
                    # Success
                    logger.info(
                        "platform_webhook_delivered",
                        pipeline_run_id=str(pipeline_run_id),
                        event=event,
                        attempt=attempt,
                        status=resp.status_code,
                    )
                    # Mark as delivered
                    await _mark_webhook_delivered(pipeline_run_id)
                    return True

                if resp.status_code < 500:
                    # 4xx client error — don't retry, consumer's problem
                    logger.warning(
                        "platform_webhook_client_error",
                        pipeline_run_id=str(pipeline_run_id),
                        status=resp.status_code,
                        body=resp.text[:200],
                    )
                    await _mark_webhook_delivered(pipeline_run_id)
                    return True  # Don't dead-letter client errors

                # 5xx server error — retry
                logger.warning(
                    "platform_webhook_server_error",
                    attempt=attempt,
                    status=resp.status_code,
                )

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning(
                    "platform_webhook_network_error",
                    attempt=attempt,
                    error=str(e),
                )

            # Wait before retry (skip wait on last attempt)
            if attempt < len(RETRY_DELAYS) - 1:
                await asyncio.sleep(RETRY_DELAYS[attempt])

    # All retries exhausted — dead letter
    logger.error(
        "platform_webhook_dead_lettered",
        pipeline_run_id=str(pipeline_run_id),
        event=event,
        url=url,
    )

    await _store_dead_letter(
        pipeline_run_id=pipeline_run_id,
        app_uuid=app_uuid,
        event=event,
        payload=body,
        target_url=url,
    )

    return False


async def _mark_webhook_delivered(pipeline_run_id: UUID) -> None:
    """Update pipeline_run to indicate webhook was delivered."""
    try:
        from app.modules.platform.models import PipelineRun

        async with async_session_factory() as db:
            run = await db.get(PipelineRun, pipeline_run_id)
            if run:
                run.webhook_delivered = True
                await db.commit()
    except Exception:
        pass  # Best-effort


async def _store_dead_letter(
    pipeline_run_id: UUID,
    app_uuid: UUID,
    event: str,
    payload: str,
    target_url: str,
) -> None:
    """Store a failed webhook delivery for later retry."""
    try:
        from app.modules.platform.models import WebhookDeadLetter

        async with async_session_factory() as db:
            db.add(WebhookDeadLetter(
                pipeline_run_id=pipeline_run_id,
                app_id=app_uuid,
                event=event,
                payload_encrypted=payload,  # TODO: encrypt with AES-256-GCM
                target_url=target_url,
                attempts=len(RETRY_DELAYS),
                last_error="max retries exceeded",
                last_attempt_at=datetime.now(UTC),
                expires_at=datetime.now(UTC) + timedelta(days=7),
            ))
            await db.commit()
    except Exception:
        logger.exception("dead_letter_store_failed", pipeline_run_id=str(pipeline_run_id))
```

#### Verification

- [ ] Successful webhook delivery: returns True, logs delivery
- [ ] Consumer returns 500: retries 5 times with correct delays
- [ ] Consumer returns 400: no retry, returns True
- [ ] Consumer unreachable: retries then dead letters
- [ ] Dead letter row created with correct data
- [ ] Webhook signature verifiable by consumer using `hmac.new(secret, body, sha256)`
- [ ] X-Webhook-Id is unique per delivery (idempotency key for consumer)

---

### Phase 6: Prometheus Metrics + Startup Cleanup (Day 5–6)

**Goal:** Add observability for platform calls and handle orphaned pipeline runs on restart.

#### File to Edit: `backend/app/core/metrics.py`

Add these counters/gauges alongside existing SphereVoice metrics:

```python
# ── Platform API Metrics ──

PLATFORM_CALLS_TOTAL = Counter(
    "SphereVoice_platform_calls_total",
    "Total platform API calls started",
    ["app_id", "mode", "status"],
)

PLATFORM_CALL_DURATION = Histogram(
    "SphereVoice_platform_call_duration_seconds",
    "Platform call duration in seconds",
    ["app_id"],
    buckets=[10, 30, 60, 120, 300, 600],
)

PLATFORM_ACTIVE_CALLS = Gauge(
    "SphereVoice_platform_active_calls",
    "Currently active platform pipeline calls",
    ["app_id"],
)

PLATFORM_WEBHOOK_DELIVERY = Counter(
    "SphereVoice_platform_webhook_deliveries_total",
    "Platform webhook delivery attempts",
    ["app_id", "event", "status"],  # status: delivered|dead_lettered
)

PLATFORM_ERRORS = Counter(
    "SphereVoice_platform_errors_total",
    "Platform API errors",
    ["app_id", "error_code"],
)
```

#### File to Edit: `backend/app/main.py`

Add orphaned platform run cleanup to the lifespan:

```python
async def _cleanup_orphaned_platform_runs() -> None:
    """Finalize platform pipeline_runs stuck from a previous crash.

    On restart, any platform calls that were 'connecting' or 'running'
    are now dead (pipeline was in memory). Mark them as failed and
    reset the active call Redis counters.
    """
    from app.modules.platform.models import PipelineRun
    from sqlalchemy import update

    cutoff = datetime.now(UTC) - timedelta(hours=1)
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                update(PipelineRun)
                .where(
                    PipelineRun.status.in_(["connecting", "running"]),
                    PipelineRun.started_at < cutoff,
                )
                .values(
                    status="failed",
                    ended_at=datetime.now(UTC),
                    error_code="orphaned_run_cleanup",
                    error_message="Pipeline was running when server restarted",
                )
                .returning(PipelineRun.id)
            )
            orphaned = [str(r[0]) for r in result.all()]
            await db.commit()
            if orphaned:
                logger.warning("orphaned_platform_runs_cleaned", count=len(orphaned))

        # Reset all active counters (they drift after restarts)
        redis = await get_redis()
        keys = await redis.keys("platform:active:*")
        for key in keys:
            await redis.set(key, 0)

    except Exception:
        logger.exception("orphaned_platform_run_cleanup_failed")
```

Add to the lifespan function:
```python
# In lifespan(), after _cleanup_orphaned_calls():
await _cleanup_orphaned_platform_runs()
```

#### Verification

- [ ] Metrics endpoint (`/metrics`) shows new platform counters
- [ ] After a call completes: `SphereVoice_platform_calls_total` incremented
- [ ] After restart: orphaned `pipeline_runs` marked as failed
- [ ] After restart: Redis active counters reset to 0

---

### Phase 7: Integration Testing (Day 6–7)

**Goal:** End-to-end tests that verify the full platform call lifecycle.

#### File to Create: `backend/tests/test_platform/test_platform_api.py`

Tests to implement:

```python
"""Platform API integration tests.

Test the full lifecycle:
1. Auth (valid/invalid credentials)
2. Start call (validation, idempotency, provider whitelist)
3. Call completes (stop handler, webhook, cost, Redis cache)
4. Polling fallback (GET /calls/{id}/result)
5. Rate limiting (RPM + concurrency)
6. Data isolation (no calls table rows, no RLS)
"""

class TestPlatformAuth:
    async def test_missing_headers_returns_401(self): ...
    async def test_invalid_secret_returns_401(self): ...
    async def test_deactivated_app_returns_403(self): ...
    async def test_valid_credentials_return_context(self): ...

class TestPlatformCallStart:
    async def test_start_web_call_returns_livekit_credentials(self): ...
    async def test_disallowed_provider_returns_403(self): ...
    async def test_outbound_disabled_returns_403(self): ...
    async def test_missing_webhook_returns_422(self): ...
    async def test_duration_capped_to_app_tier(self): ...
    async def test_idempotency_returns_cached_response(self): ...
    async def test_pipeline_run_created_not_call(self): ...

class TestPlatformCallEnd:
    async def test_stop_handler_updates_pipeline_run(self): ...
    async def test_stop_handler_caches_result_in_redis(self): ...
    async def test_stop_handler_delivers_webhook(self): ...
    async def test_stop_handler_decrements_active_counter(self): ...
    async def test_stop_handler_decrements_on_error(self): ...
    async def test_no_call_table_rows_created(self): ...

class TestPlatformPolling:
    async def test_get_result_returns_cached_transcript(self): ...
    async def test_get_result_rejects_cross_app_access(self): ...
    async def test_expired_result_returns_404(self): ...

class TestPlatformRateLimiting:
    async def test_rpm_limit_returns_429(self): ...
    async def test_concurrency_limit_returns_429(self): ...

class TestPlatformWebhook:
    async def test_webhook_delivered_with_correct_signature(self): ...
    async def test_webhook_retries_on_5xx(self): ...
    async def test_webhook_no_retry_on_4xx(self): ...
    async def test_webhook_dead_letter_on_exhaustion(self): ...

class TestDataIsolation:
    async def test_no_rls_context_set(self): ...
    async def test_no_calls_table_writes(self): ...
    async def test_transcript_not_in_postgres(self): ...
```

#### Verification

- [ ] All tests pass
- [ ] No flaky tests (use deterministic mocks for LiveKit, Redis)
- [ ] Coverage: auth, routing, orchestrator, webhook dispatcher

---

## 4. Complete File Manifest

### Files to CREATE (9 files)

| # | File | Purpose |
|---|------|---------|
| 1 | `backend/app/modules/platform/__init__.py` | Module init |
| 2 | `backend/app/modules/platform/models.py` | IntegrationApp, PipelineRun, WebhookDeadLetter |
| 3 | `backend/app/modules/platform/schemas.py` | Request/response Pydantic models |
| 4 | `backend/app/modules/platform/router.py` | 6 platform endpoints |
| 5 | `backend/app/modules/platform/webhook_dispatcher.py` | Reliable delivery + dead letter |
| 6 | `backend/app/core/platform_auth.py` | App ID + Secret verification → PlatformContext |
| 7 | `backend/app/core/platform_rate_limit.py` | Per-app RPM + concurrency limiting |
| 8 | `backend/alembic/versions/xxxx_add_platform_tables.py` | Migration (auto-generated) |
| 9 | `backend/tests/test_platform/test_platform_api.py` | Integration tests |

### Files to EDIT (4 files)

| # | File | Change |
|---|------|--------|
| 1 | `backend/app/main.py` | Register platform router + orphaned run cleanup |
| 2 | `backend/app/modules/pipeline/orchestrator.py` | Add `handle_platform_call()`, `_make_platform_stop_handler()`, `handle_platform_call_end()` |
| 3 | `backend/app/core/metrics.py` | Add platform Prometheus counters |
| 4 | `backend/seed.py` | Add NanoVoice app seeding |

### Files NOT touched (everything else)

The existing SphereVoice system is untouched:
- `core/dependencies.py` (JWT auth) — no changes
- `core/security.py` (token creation) — no changes
- `modules/calls/` — no changes
- `modules/agents/` — no changes
- `modules/auth/` — no changes
- `modules/pipeline/voice_pipeline.py` — no changes
- `modules/pipeline/factory.py` — no changes (SimpleNamespace satisfies the same attribute interface)
- `modules/pipeline/services/` — no changes
- `modules/webhooks/` — no changes (platform has its own webhook system)
- All frontend files — no changes

---

## 5. Execution Timeline

| Day | Phase | Deliverable |
|-----|-------|-------------|
| 1 | Phase 1: DB models + migration | Tables created, NanoVoice seeded |
| 2 | Phase 2: Auth + rate limiting | `verify_platform_app` + `enforce_rate_limit` working |
| 2–3 | Phase 3: Router + schemas | All 6 endpoints responding (auth + validation only) |
| 3–5 | Phase 4: Orchestrator logic | `handle_platform_call()` — full call lifecycle |
| 4–5 | Phase 5: Webhook dispatcher | Reliable delivery with retry + dead letter |
| 5–6 | Phase 6: Metrics + cleanup | Prometheus counters + startup orphan cleanup |
| 6–7 | Phase 7: Integration tests | Full lifecycle tested, ready for NanoVoice |

**Total: 7 working days.**

---

## 6. Post-Build: NanoVoice Integration Checklist

Once the Platform API is live, NanoVoice needs to:

1. **Store app credentials** — `X-App-Id` and `X-App-Secret` in NanoVoice env
2. **Implement webhook receiver** — `POST /hooks/SphereVoice/call-ended` endpoint
3. **Verify webhook signature** — `hmac.new(secret, body, sha256)` matches `X-Webhook-Signature`
4. **Handle idempotency** — check `X-Webhook-Id` to deduplicate
5. **Implement polling fallback** — cron job hitting `GET /platform/v1/calls/{id}/result` for stale calls
6. **Build circuit breaker** — if SphereVoice returns 5xx/429 repeatedly, stop sending calls temporarily
7. **Pre-signed upload URL** — generate Azure Blob SAS URLs for `recording_upload_url`

---

## 7. Future Enhancements (Not in Scope Now)

| Enhancement | When to Build |
|-------------|--------------|
| Admin UI in SphereVoice dashboard (manage apps, view usage) | After NanoVoice validates demand |
| Webhook event streaming (call.transcript.chunk, call.tool_called) | When real-time events are needed |
| Outbound call support via platform API | When NanoVoice needs telephony |
| Per-app API key rotation (generate new secret, grace period) | Before onboarding external partners |
| Dead letter retry Celery beat task | After first dead letter incident |
| Platform API OpenAPI docs page (`/platform/docs`) | Before public launch |
| Per-app provider key override (BYOK) | When partners want their own OpenAI keys |
| Billing integration (Stripe/Razorpay) | When NanoVoice monetizes |

---

## 8. Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| SimpleNamespace missing an attribute VoicePipeline reads | Pipeline crash on first call | Test with actual pipeline run in dev; grep all `agent.` accesses in voice_pipeline.py |
| Redis counter drift (increment without decrement on crash) | Active count grows forever, blocking new calls | Startup cleanup resets all counters; `finally` block in stop handler |
| Webhook consumer permanently down | Dead letters pile up | 7-day expiry + future Celery beat retry task |
| LiveKit room not cleaned up after platform call | Orphaned rooms consume resources | LiveKit's `empty_timeout=300` auto-cleans; startup cleanup deletes rooms |
| Platform call exhausts LLM rate limits affecting SphereVoice tenant calls | SphereVoice production degradation | Platform calls use platform-level provider keys; use separate OpenAI org/project if needed |
| `config_hash` collision (different prompts, same hash prefix) | Minor: debug info is less useful | Acceptable risk — hash is for debugging, not identity |
