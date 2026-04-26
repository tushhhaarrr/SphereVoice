# SphereVoice — Execution Plan

**Document:** Phased Execution Plan  
**Product:** SphereVoice - Internal Voice AI Agent Platform  
**Company:** Sphere AI  
**Version:** 3.0  
**Date:** March 4, 2026  
**Timeline:** 24 Weeks (6 Months) + 1 Week Pre-Flight  
**Team Size:** 5 Engineers (2 Frontend, 2 Backend, 1 Infra/DevOps)  
**Phase Cadence:** Every phase ≤ 2 weeks. No exceptions.

---

## Guiding Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| 1 | **Ship incrementally, validate continuously** | Every phase ends with a working, demo-able deliverable |
| 2 | **Observability before features** | Logging, tracing, and metrics go in *before* business logic |
| 3 | **Security is not a phase — it is a constant** | Auth, encryption, RLS, and audit logging built into every sprint |
| 4 | **Test at the boundary, not the implementation** | Integration tests on API contracts. Unit tests for pure logic only |
| 5 | **Pin everything, trust nothing** | Every dependency, Docker image, and CI action pinned to exact version |
| 6 | **Design for portability** | Standard protocols (PostgreSQL, Redis, S3 API, Docker). Zero lock-in |
| 7 | **Fail fast, recover gracefully** | Circuit breakers, fallbacks, graceful degradation everywhere |
| 8 | **No idle engineers** | Every phase has meaningful work for all 5 roles |
| 9 | **Modular monolith, not microservices** | Domain modules with explicit boundaries in a single deployable. Extractable later if needed. |

---

## Architecture: Monorepo + Modular Monolith

### Why Monorepo (Turborepo)

Single `Sphere/SphereVoice` repo contains frontend, backend, shared types, and infrastructure. Turborepo handles build orchestration and caching. One PR = one review across the full stack.

### Why Modular Monolith (Backend)

The backend is a **single FastAPI application** deployed as one container, but internally organized into **self-contained domain modules**. This is NOT a flat CRUD app — each module owns its models, schemas, routes, and service logic.

**Key rules:**
1. **Each module is a directory** under `backend/app/modules/` with its own `models.py`, `schemas.py`, `router.py`, `service.py`
2. **Modules communicate via public APIs** — import only from `module/__init__.py`, never reach into another module's internals
3. **Shared kernel** (`backend/app/core/`) contains cross-cutting concerns: DB session, auth middleware, config, encryption, base models
4. **Workers** (`backend/app/workers/`) are cross-module Celery tasks — they import from module public APIs
5. **Enforced by tooling** — `import-linter` (Python) blocks cross-module internal imports in CI

**Domain modules:**
| Module | Responsibility |
|--------|---------------|
| `auth` | JWT issuance, RBAC, tenant context, session management |
| `agents` | Agent CRUD, versioning, configuration, templates |
| `providers` | Provider key encryption, CRUD, connection testing |
| `calls` | Call history, call lifecycle, outbound calls |
| `pipeline` | Pipecat voice pipeline, `CallOrchestrator`, `PipecatProviderFactory`, STT/LLM/TTS services |
| `knowledge_base` | Document upload, chunking, embedding, vector search, RAG |
| `analytics` | Metrics aggregation, time-series, dashboard data |
| `webhooks` | Webhook registration, delivery, retry, dead letter |
| `phone_numbers` | Twilio/Plivo integration, number purchase, routing |

**Extraction path:** If any module hits scaling limits (e.g., `pipeline` needs its own process pool), extract it to a separate service by:
1. Promote the module's `router.py` to a standalone FastAPI app
2. Replace internal imports with HTTP/gRPC calls
3. Deploy as a separate container

This is a 1-day operation per module — not a rewrite.

### Frontend Module Structure

The frontend mirrors the backend's modular approach:
| Module | Responsibility |
|--------|---------------|
| `auth` | Login, session, role guards, auth context |
| `agents` | Agent list, builder, flow canvas, prompt editor, settings |
| `calls` | Call history, call detail, transcript viewer, audio player |
| `providers` | Provider management UI, connection test |
| `knowledge-base` | KB upload, document list, attachment config |
| `analytics` | Metric cards, time-series charts, client dashboard |
| `settings` | User management, webhooks, audit log |
| `live` | Live monitoring dashboard, real-time transcript |

Each module directory contains: `components/`, `hooks/`, `types/`, and a barrel `index.ts`. Shared UI primitives (shadcn/ui wrappers) live in `src/components/ui/`.

### Directory Structure

```
Sphere/SphereVoice/                              # Monorepo root (Turborepo)
├── docs/
│   ├── prd.md                             # WHAT — features, UX, business value
│   ├── tech-prd.md                        # HOW — architecture, schemas, APIs
│   ├── execution-plan.md                  # WHEN — phased delivery plan
│   └── retell-audit.md                    # Competitive reference
│
├── backend/                               # FastAPI modular monolith (Python 3.11)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                        # FastAPI app — registers module routers
│   │   ├── core/                          # ── Shared kernel ──
│   │   │   ├── config.py                  # Settings via pydantic-settings
│   │   │   ├── database.py                # Async SQLAlchemy engine + session
│   │   │   ├── security.py                # JWT decode, password hashing
│   │   │   ├── encryption.py              # AES-256-GCM for provider keys
│   │   │   ├── dependencies.py            # get_db, get_current_user, get_tenant
│   │   │   ├── middleware.py              # Tenant context, CORS, request ID
│   │   │   ├── exceptions.py              # HTTPException subclasses
│   │   │   └── base_model.py              # TimestampMixin, TenantMixin
│   │   │
│   │   ├── modules/                       # ── Domain modules ──
│   │   │   ├── auth/
│   │   │   │   ├── __init__.py            # Public API: login(), verify_token()
│   │   │   │   ├── router.py              # /api/v1/auth/*
│   │   │   │   ├── models.py              # User, Role SQLAlchemy models
│   │   │   │   ├── schemas.py             # LoginRequest, TokenResponse, etc.
│   │   │   │   ├── service.py             # Auth business logic
│   │   │   │   └── dependencies.py        # require_role(), get_current_user()
│   │   │   │
│   │   │   ├── agents/
│   │   │   │   ├── __init__.py            # Public API
│   │   │   │   ├── router.py              # /api/v1/agents/*
│   │   │   │   ├── models.py              # Agent, AgentVersion
│   │   │   │   ├── schemas.py
│   │   │   │   └── service.py
│   │   │   │
│   │   │   ├── providers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py              # /api/v1/providers/*
│   │   │   │   ├── models.py              # ProviderKey
│   │   │   │   ├── schemas.py
│   │   │   │   └── service.py             # Encrypt/decrypt, test connection
│   │   │   │
│   │   │   ├── calls/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py              # /api/v1/calls/*
│   │   │   │   ├── models.py              # Call, CallTranscript
│   │   │   │   ├── schemas.py
│   │   │   │   └── service.py
│   │   │   │
│   │   │   ├── pipeline/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py              # Internal webhook endpoints
│   │   │   │   ├── models.py              # CallEvent
│   │   │   │   ├── orchestrator.py        # CallOrchestrator
│   │   │   │   ├── factory.py             # PipecatProviderFactory
│   │   │   │   ├── flow_engine.py         # Flow execution (Flex/Rigid)
│   │   │   │   └── services/              # Provider service wrappers
│   │   │   │       ├── stt.py
│   │   │   │       ├── llm.py
│   │   │   │       └── tts.py
│   │   │   │
│   │   │   ├── knowledge_base/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py              # /api/v1/knowledge-bases/*
│   │   │   │   ├── models.py              # KnowledgeBase, KBDocument, KBEmbedding
│   │   │   │   ├── schemas.py
│   │   │   │   ├── service.py             # Upload, chunk, embed, search
│   │   │   │   └── retriever.py           # RAG retrieval for live calls
│   │   │   │
│   │   │   ├── phone_numbers/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py              # /api/v1/phone-numbers/*
│   │   │   │   ├── models.py              # PhoneNumber
│   │   │   │   ├── schemas.py
│   │   │   │   └── service.py             # Twilio/Plivo integration
│   │   │   │
│   │   │   ├── analytics/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py              # /api/v1/analytics/*
│   │   │   │   ├── models.py              # MetricAggregate
│   │   │   │   ├── schemas.py
│   │   │   │   └── service.py             # Aggregation queries
│   │   │   │
│   │   │   └── webhooks/
│   │   │       ├── __init__.py
│   │   │       ├── router.py              # /api/v1/webhooks/*
│   │   │       ├── models.py              # Webhook, WebhookDelivery
│   │   │       ├── schemas.py
│   │   │       └── service.py             # Dispatch, retry, dead letter
│   │   │
│   │   └── workers/                       # ── Celery tasks (cross-module) ──
│   │       ├── __init__.py
│   │       ├── celery_app.py              # Celery config + beat schedule
│   │       ├── post_call.py               # Imports from calls + pipeline modules
│   │       ├── embeddings.py              # Imports from knowledge_base module
│   │       ├── webhook_delivery.py        # Imports from webhooks module
│   │       └── retention.py               # Imports from calls module
│   │
│   ├── alembic/                           # Database migrations
│   │   ├── alembic.ini
│   │   └── versions/
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_auth/
│   │   ├── test_agents/
│   │   ├── test_calls/
│   │   ├── test_pipeline/
│   │   ├── test_providers/
│   │   ├── test_knowledge_base/
│   │   └── test_rls/                      # Cross-tenant isolation tests
│   ├── requirements.txt
│   ├── pyproject.toml                     # import-linter rules
│   └── Dockerfile
│
├── frontend/                              # Next.js 15 modular frontend
│   ├── src/
│   │   ├── app/                           # App Router (thin route layer)
│   │   │   ├── layout.tsx
│   │   │   ├── (dashboard)/
│   │   │   │   ├── agents/page.tsx        # → imports from modules/agents
│   │   │   │   ├── calls/page.tsx         # → imports from modules/calls
│   │   │   │   ├── providers/page.tsx     # → imports from modules/providers
│   │   │   │   ├── live/page.tsx          # → imports from modules/live
│   │   │   │   ├── analytics/page.tsx     # → imports from modules/analytics
│   │   │   │   ├── knowledge-base/page.tsx
│   │   │   │   └── settings/page.tsx
│   │   │   └── api/auth/[...nextauth]/
│   │   │
│   │   ├── modules/                       # ── Domain modules ──
│   │   │   ├── auth/
│   │   │   │   ├── components/            # LoginForm, RoleGuard
│   │   │   │   ├── hooks/                 # useAuth, useSession
│   │   │   │   ├── types/
│   │   │   │   └── index.ts               # Public API barrel
│   │   │   ├── agents/
│   │   │   │   ├── components/            # AgentList, AgentBuilder, FlowCanvas, PromptEditor
│   │   │   │   ├── hooks/                 # useAgents, useAgentBuilder
│   │   │   │   ├── types/
│   │   │   │   └── index.ts
│   │   │   ├── calls/
│   │   │   │   ├── components/            # CallHistory, CallDetail, TranscriptViewer
│   │   │   │   ├── hooks/
│   │   │   │   ├── types/
│   │   │   │   └── index.ts
│   │   │   ├── providers/
│   │   │   ├── knowledge-base/
│   │   │   ├── analytics/
│   │   │   ├── live/
│   │   │   └── settings/
│   │   │
│   │   ├── components/                    # ── Shared UI (shadcn/ui wrappers) ──
│   │   │   ├── ui/                        # Button, Input, Dialog, Table, Badge
│   │   │   └── layout/                    # Sidebar, Breadcrumbs, AppShell
│   │   │
│   │   ├── lib/                           # Shared utilities
│   │   │   ├── api-client.ts              # Axios/fetch wrapper with JWT
│   │   │   ├── auth.ts                    # Auth.js v5 config
│   │   │   └── utils.ts
│   │   │
│   │   └── types/                         # Global TypeScript types
│   │
│   ├── package.json
│   └── Dockerfile
│
├── packages/
│   └── shared-types/                      # Shared TS types (used by frontend + tooling)
│       ├── src/
│       └── package.json
│
├── infra/
│   └── terraform/
│       ├── environments/{dev,staging,production}/
│       └── modules/{database,redis,storage,container_apps,vm,monitoring}/
│
├── docker-compose.yml                     # Local dev (PostgreSQL, Redis, backend, frontend, Celery)
├── turbo.json                             # Turborepo pipeline config
├── pnpm-workspace.yaml                    # pnpm workspace: frontend + packages/*
└── .github/
    ├── workflows/                         # CI/CD
    └── agents/                            # SphereVoice-techlead agent
```

---

## Team Structure & Ownership

| Role | Abbr | Ownership |
|------|------|-----------|
| **Backend Lead** (BL) | 1 | Voice pipeline (Pipecat), API layer, provider abstraction, call orchestration |
| **Backend Engineer** (BE) | 1 | Database, auth, knowledge base, background jobs, webhooks |
| **Frontend Lead** (FL) | 1 | Agent builder (flow + prompt), application shell, state management |
| **Frontend Engineer** (FE) | 1 | Call history, live monitoring, analytics, client portal |
| **Infra/DevOps** (IN) | 1 | Terraform, CI/CD, Docker, monitoring stack, security hardening |

**Shared:** Code review (every PR ≥1 approval), on-call rotation (post-Phase 9), RFC process for cross-cutting changes.

---

## Phase Overview

| Phase | Name | Weeks | Duration | Tasks | Load Balance |
|-------|------|-------|----------|-------|--------------|
| **0A** | Repo & Dev Environment | Week 0 (Mon–Wed) | 3 days | 7 | IN heavy, all assist |
| **0B** | ADRs & Risk Planning | Week 0 (Thu–Fri) | 2 days | 5 | All equal |
| **1** | Infra, Observability & Frontend Scaffold | Weeks 1–2 | 2 weeks | 14 | IN + FL/FE parallel |
| **2** | Database Schema & Tenant Isolation | Weeks 3–4 | 2 weeks | 9 | BE heavy, FL continues scaffold |
| **3** | Auth, Providers & App Shell | Weeks 5–6 | 2 weeks | 14 | All busy — first full-stack phase |
| **4** | LiveKit + Pipecat + STT | Weeks 7–8 | 2 weeks | 14 | BL/BE pipeline, FL/FE build agent UIs |
| **5** | Full Voice Pipeline | Weeks 9–10 | 2 weeks | 13 | BL/BE complete pipeline, FL/FE build settings + test call |
| **6** | Single Prompt Agent | Weeks 11–12 | 2 weeks | 9 | FL/FE heavy, BL/BE integrate |
| **7** | Flow Builder & Versioning | Weeks 13–14 | 2 weeks | 10 | FL/FE canvas, BL engine |
| **8** | Phone Numbers & Call History | Weeks 15–16 | 2 weeks | 10 | Balanced |
| **9** | Live Monitoring & Post-Call | Weeks 17–18 | 2 weeks | 10 | Balanced |
| **10** | Knowledge Base & RAG | Weeks 19–20 | 2 weeks | 10 | BE heavy, FE builds UI |
| **11** | Analytics, Templates & User Mgmt | Weeks 21–22 | 2 weeks | 11 | Balanced |
| **12** | Hardening, Testing & Launch | Weeks 23–24 | 2 weeks | 14 | All hands — launch sprint |

**13 phases. All ≤ 2 weeks. Average ~5 tasks per person per 2-week phase. No idle engineers.**

---

## Phase 0A: Repo & Dev Environment (Week 0 — Mon–Wed)

**Goal:** Every engineer has a working local environment by Wednesday.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 0A.1 | Create `Sphere/SphereVoice` monorepo (modular monolith) | IN | Turborepo config. **Backend:** `backend/app/modules/{auth,agents,calls,providers,knowledge_base,analytics,webhooks,pipeline}` each with own `router.py`, `models.py`, `schemas.py`, `service.py`. Shared kernel in `backend/app/core/`. **Frontend:** `frontend/src/modules/{auth,agents,calls,providers,knowledge-base,analytics,settings}` each with own `components/`, `hooks/`, `types/`. Shared UI in `frontend/src/components/`. **Packages:** `packages/shared-types/`. **Infra:** `infra/terraform/`. |
| 0A.2 | Pin upstream `pipecat-ai` package and document local extension strategy | BL | `backend/requirements.txt` pins Pipecat version; SphereVoice custom processors/services live in repo code |
| 0A.3 | `.nvmrc` → `20.18`, `.python-version` → `3.11.11` | IN | All engineers verified |
| 0A.4 | `docker-compose.yml` for local dev | IN | `docker compose up` → PostgreSQL 15, Redis 7.2, backend, frontend — all healthy |
| 0A.5 | Pre-commit hooks | IN | `black`, `ruff`, `eslint`, `prettier`, `commitlint` |
| 0A.6 | Branch strategy documented | IN | `main` → `staging` → `dev`. Feature branches off `dev`. Squash merges. |
| 0A.7 | Module boundary linting + dependency rules | IN | `import-linter` (Python) rules: modules cannot import from other modules' internals — only from `__init__.py` public API. Frontend: ESLint `no-restricted-imports` enforces same pattern. |

---

## Phase 0B: ADRs & Risk Planning (Week 0 — Thu–Fri)

**Goal:** Every non-obvious architectural decision documented. Key risks have mitigation plans.

### Architecture Decision Records

| ADR | Decision |
|-----|----------|
| ADR-001 | Monorepo structure (Turborepo) |
| ADR-002 | Pipecat package-first strategy |
| ADR-003 | Auth.js v5 + FastAPI JWT dual-auth |
| ADR-004 | PostgreSQL RLS for tenant isolation |
| ADR-005 | LiveKit for WebRTC/SIP, Pipecat for pipeline |
| ADR-006 | Schema-first API design (OpenAPI 3.1 spec) |
| ADR-007 | Feature flags via environment variables |
| ADR-008 | Terraform for IaC, no ARM templates |
| ADR-011 | Modular monolith backend (domain modules with explicit boundaries) |

### Risk Register

| Risk | Prob. | Impact | Mitigation | Owner |
|------|-------|--------|------------|-------|
| Pipecat package upgrade regressions | Med | High | Exact version pin, staged upgrade validation, pipeline regression tests | BL |
| Latency >500ms P99 | Low | Critical | Fast stack default (Flux + Groq + Cartesia) | BL |
| Azure credits exhausted early | Med | Med | Weekly credit alert, portable Terraform | IN |
| LiveKit SIP complexity | Med | High | Spike in Phase 0, fallback to Twilio Media Streams | BL |
| Team member departure | Low | High | Pair programming, documented ADRs | All |

### Definition of Done (Global)

1. Code merged to `dev` with ≥1 approval
2. Integration tests pass in CI
3. No new Sentry errors in staging for 24h
4. OpenAPI spec updated (if API changed)
5. Relevant metrics/traces emitting
6. README/runbook updated (if infra changed)

---

## Phase 1: Infra, Observability & Frontend Scaffold (Weeks 1–2)

**Goal:** Cloud infra running, observability operational, frontend project bootstrapped with design system.

**Exit Criteria:** Terraform provisions all resources. Traces in Grafana. Next.js 15 app renders with shadcn/ui components.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 1.1 | Azure subscription + resource group (`SphereVoice-Sphere`, Central India) via Terraform | IN | `terraform apply` targets existing `SphereVoice-Sphere` resource group |
| 1.2 | PostgreSQL 15 Flexible Server + pgvector | IN | `psql` connects, `CREATE EXTENSION vector` succeeds |
| 1.3 | Redis 7.2 (Azure Cache) | IN | `redis-cli ping` → `PONG` |
| 1.4 | Azure Blob Storage (S3 API) | IN | Upload/download via `boto3` S3-compatible endpoint |
| 1.5 | Azure Container Registry (ACR) | IN | `docker push` succeeds |
| 1.6 | Azure Key Vault for encryption master key | IN | Key Vault provisioned, master key stored |
| 1.7 | GitHub Actions CI pipeline | IN | PR → lint + test + build. `main` → deploy. |
| 1.8 | Sentry + `sentry-sdk 2.14.0` | IN | Error in Sentry within 30s |
| 1.9 | OpenTelemetry collector + Grafana + Prometheus | IN | Traces in Tempo, metrics in Prometheus |
| 1.10 | Structured logging (JSON) → Azure Monitor | BE | `{"level":"info","tenant_id":"...","trace_id":"..."}` |
| 1.11 | Health check endpoints (`/health`, `/ready`) | BE | Docker HEALTHCHECK passes |
| 1.12 | Next.js 15 project + Tailwind 3.4.1 + shadcn/ui init | FL | `npm run dev` renders empty shell |
| 1.13 | Design tokens, theme provider, dark/light mode | FL | Toggle works, tokens consistent |
| 1.14 | Shared component library scaffold (Button, Input, Dialog, Table, Badge) | FE | 5 components render with Storybook/stories |

**Resource utilization:**
- IN: weeks 1–2 fully loaded (9 infra tasks)
- BL: assists IN with Docker/Pipecat config, reviews ADR spikes
- BE: logging + health endpoints + starts reviewing schema design
- FL: bootstraps Next.js app, design system, theme
- FE: component library, Storybook setup

### Phase 1 Gate

- [ ] All cloud resources provisioned and accessible
- [ ] CI pipeline green on `dev`
- [ ] Sentry + Grafana + structured logs operational
- [ ] Next.js app renders with shadcn components + dark mode

---

## Phase 2: Database Schema & Tenant Isolation (Weeks 3–4)

**Goal:** All tables deployed, RLS proven, seed data available. Frontend layout and routing wired.

**Exit Criteria:** Cross-tenant query returns zero rows. Frontend has full route structure with placeholder pages.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 2.1 | Alembic setup + initial migration | BE | `alembic upgrade head` creates all tables |
| 2.2 | Core tables: `tenants`, `users`, `provider_keys` | BE | Correct columns, indexes, constraints |
| 2.3 | Agent tables: `agents`, `agent_versions`, `knowledge_bases` | BE | FK relationships correct |
| 2.4 | Call tables: `calls`, `call_transcripts` | BE | Partitioning strategy documented |
| 2.5 | Infra tables: `phone_numbers`, `webhooks`, `audit_logs` | BE | Audit trigger fires on INSERT/UPDATE/DELETE |
| 2.6 | Row-Level Security (RLS) policies | BE | Wrong `tenant_id` → zero rows |
| 2.7 | RLS integration test suite | BE | CI: 2 tenants, cross-tenant returns empty |
| 2.8 | Seed script (2 tenants, 3 users each) | BE | `python seed.py` < 5s |
| 2.9 | App shell: sidebar navigation, breadcrumbs, route structure | FL | All routes render placeholder pages, responsive layout |

**Resource utilization:**
- BE: fully loaded (8 schema + RLS tasks)
- IN: supports BE on Terraform DB config, runs security reviews on RLS
- FL: builds app shell, routing, sidebar, breadcrumbs — real layout work
- FE: continues component library (Table, Form components), starts call history page wireframe
- BL: starts LiveKit spike (research + docs), reviews schema for voice pipeline needs

### Phase 2 Gate

- [ ] 100% RLS tests passing
- [ ] Audit trigger fires on all CUD operations
- [ ] App shell navigable with all routes (even if pages are placeholders)

---

## Phase 3: Auth, Providers & App Shell (Weeks 5–6)

**Goal:** First full-stack feature. Auth works end-to-end. Providers can be added, tested, and managed. App shell is role-aware.

**Exit Criteria:** Employee logs in, adds Deepgram key, clicks "Test", sees green checkmark. Client user redirected away from admin pages.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 3.1 | Auth.js v5 setup in Next.js 15 | FL | `/api/auth/signin` renders, Google/Email providers |
| 3.2 | FastAPI JWT issuance (`/api/v1/auth/login`) | BE | Valid creds → JWT with `user_id`, `tenant_id`, `role` |
| 3.3 | JWT middleware for `/api/v1/*` routes | BE | Missing/expired token → 401 |
| 3.4 | RBAC decorator: `@require_role(...)` | BE | Read-only user on write endpoint → 403 |
| 3.5 | Tenant context middleware (sets `app.current_tenant_id`) | BE | Every DB query auto-scoped by tenant |
| 3.6 | Auth.js ↔ FastAPI token exchange | FL + BE | Login → Auth.js session → JWT → API calls work E2E |
| 3.7 | Role-based UI guards | FL | Client at `/agents` → redirect to `/dashboard` |
| 3.8 | Provider key encryption (AES-256-GCM) | BE | Encrypt → store → decrypt round-trip. Never plaintext. |
| 3.9 | Provider CRUD API (`/api/v1/providers`) | BE | CRUD with tenant scoping, keys encrypted |
| 3.10 | Provider connection test endpoint | BE | `POST /providers/{id}/test` → success/failure |
| 3.11 | Provider management UI | FE | List, add, edit, test, delete. Green checkmark. |
| 3.12 | Agent CRUD API (`/api/v1/agents`) | BL | Create/read/update/delete with tenant scoping |
| 3.13 | Agent list UI (TanStack Table) | FE | Sortable, filterable table of agents |
| 3.14 | Audit log: all auth + CRUD events | BE | `audit_logs` entries for login, provider changes |

**Resource utilization:**
- BE: auth middleware + provider encryption + CRUD (6 tasks) — full load
- BL: agent CRUD API + reviews auth for pipeline needs
- FL: Auth.js + token exchange + role guards (3 tasks)
- FE: provider UI + agent list UI (2 tasks)
- IN: reviews security, assists with Key Vault integration

### Phase 3 Gate

- [ ] Auth works E2E (login → JWT → tenant-scoped API call)
- [ ] Provider key encrypted, tested, stored
- [ ] Agent CRUD operational
- [ ] Role-based UI guards working
- [ ] Load test: 100 concurrent API requests <200ms P95

---

## Phase 4: LiveKit + Pipecat + STT (Weeks 7–8)

**Goal:** Audio flows from phone → LiveKit → Pipecat → STT. Frontend engineers build agent builder UI foundations in parallel.

**Exit Criteria:** Inbound call transcribes in real-time. Prompt editor and agent settings UI scaffolded.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 4.1 | Deploy LiveKit Server on Azure VM | IN | Dashboard accessible, API key configured |
| 4.2 | SIP gateway configuration | IN | SIP trunk registered, Twilio domain → LiveKit |
| 4.3 | Twilio SIP → LiveKit integration test | BL | Inbound call creates room with audio track |
| 4.4 | Install pinned upstream Pipecat package with extras | BL | `import pipecat` succeeds using the version pinned in `backend/requirements.txt` |
| 4.5 | LiveKitTransport integration test | BL | Transport joins room, receives + sends audio frames |
| 4.6 | CI: dependency upgrade smoke-check | IN | Pipecat version pin change triggers pipeline smoke tests before merge |
| 4.7 | CallOrchestrator skeleton | BL | Webhook → logs metadata → creates `calls` record |
| 4.8 | `PipecatProviderFactory` — STT factory | BL | Agent config → correct STT service instance |
| 4.9 | DeepgramSTTService (Flux + Nova-3) | BE | Streaming transcription, Flux default |
| 4.10 | SileroVADAnalyzer setup + tuning | BE | VAD detects speech within 10ms |
| 4.11 | STT fallback via ServiceSwitcher | BE | Deepgram timeout → auto-switch to AssemblyAI |
| 4.12 | Prompt editor (Monaco Editor) | FL | Syntax highlighting, `{{variable}}` autocomplete |
| 4.13 | Agent settings UI (voice, LLM, speech, call) | FL | All prd.md §3.4 settings configurable |
| 4.14 | Call history page scaffold + table skeleton | FE | TanStack Table wired to mock data, columns configurable |

**Resource utilization:**
- BL: 5 tasks — LiveKit + Pipecat + STT factory (the hard stuff)
- BE: 3 tasks — Deepgram, VAD, fallback
- IN: 3 tasks — LiveKit deploy + SIP + CI
- FL: 2 tasks — prompt editor + agent settings (parallel with pipeline)
- FE: 1 task — call history scaffold (ahead of Phase 8 data)

### Phase 4 Gate

- [ ] Inbound call → LiveKit room → Pipecat receives audio
- [ ] Real-time streaming transcription
- [ ] STT fallback activates on provider failure
- [ ] Prompt editor and settings UI render with mock data

---

## Phase 5: Full Voice Pipeline (Weeks 9–10)

**Goal:** Complete STT → LLM → TTS pipeline. First real AI conversation. Frontend builds test call UI.

**Exit Criteria:** Phone call with AI conversation works. P50 <300ms. Test call button wired (even if not yet connected).

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 5.1 | `PipecatProviderFactory` — LLM factory | BL | Agent config → Groq/OpenAI/Anthropic service |
| 5.2 | LLMContextAggregatorPair (turn management) | BE | Proper turn-taking, no overlap |
| 5.3 | System prompt injection from agent config | BE | Prompt from DB injected into LLM context |
| 5.4 | Function calling via Pipecat FunctionSchema | BE | LLM calls `transfer_call`, `end_call` |
| 5.5 | `PipecatProviderFactory` — TTS factory | BL | CartesiaTTS / ElevenLabsTTS based on config |
| 5.6 | Full Pipeline assembly (Transport → STT → LLM → TTS) | BL | Pipeline runs end-to-end |
| 5.7 | PipelineRunner + PipelineTask + OTel metrics | BL | Traces emitted per call |
| 5.8 | End-to-end inbound call test | BL + IN | Phone call → AI responds. Conversation works. |
| 5.9 | Latency measurement + tuning | BL | P50 <300ms, P99 <500ms over 50+ test calls |
| 5.10 | Call recording → Azure Blob | BE | Recording stored, retrievable by call ID |
| 5.11 | Circuit breaker for provider failures | BE | 3 failures → circuit opens → fallback → alert |
| 5.12 | Agent test call UI (WebRTC via LiveKit) | FL | "Test Call" button → connects to LiveKit room |
| 5.13 | Live monitoring page wireframe + WebSocket skeleton | FE | Page structure ready, WS client connects |

**Resource utilization:**
- BL: 6 tasks — LLM, TTS, pipeline assembly, latency tuning (critical path)
- BE: 4 tasks — turn mgmt, function calling, recording, circuit breaker
- IN: assists with LiveKit load test, supports E2E call testing
- FL: test call UI — the bridge between pipeline and frontend
- FE: live monitoring wireframe — ahead of Phase 9

### Phase 5 Gate

- [ ] End-to-end call: inbound → Pipecat → AI conversation → hang-up
- [ ] P50 <300ms, P99 <500ms (50+ test calls)
- [ ] Fallback activates within 2s on provider failure
- [ ] Recording retrievable from Azure Blob
- [ ] Full call trace visible in Grafana
- [ ] 10 concurrent calls, all complete successfully

---

## Phase 6: Single Prompt Agent (Weeks 11–12)

**Goal:** Create a single-prompt agent, configure it, test with a live call from the browser.

**Exit Criteria:** Employee creates agent → writes prompt → configures voice/LLM → clicks "Test Call" → has conversation in browser → sees transcript.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 6.1 | Dynamic variables system (backend + frontend) | FL + BE | Define variables with defaults, inject at call time |
| 6.2 | Welcome message configuration | FL | Toggle: "Agent speaks first" vs "Agent waits" |
| 6.3 | Function calling UI | FL | Define name, description, params, endpoint |
| 6.4 | Agent test panel: browser → LiveKit → pipeline | FL + BL | "Test Call" → WebRTC → conversation → transcript |
| 6.5 | Test call transcript display (real-time) | FE | Speaker labels, timestamps, auto-scroll |
| 6.6 | Post-call extraction config UI | FE | Define fields (summary, success, sentiment, custom) |
| 6.7 | Webhook configuration UI | FE | Set URL, events, retry. Test button. |
| 6.8 | Agent config → PipecatProviderFactory integration | BL | All UI settings correctly load into pipeline |
| 6.9 | Graceful call termination (hang-up, timeout, error) | BL | All exit paths clean up resources |

**Resource utilization:**
- FL: 4 tasks — variables, welcome msg, functions, test panel (lead role this phase)
- FE: 3 tasks — transcript display, extraction config, webhook config
- BL: 2 tasks — factory integration, graceful termination
- BE: assists FL with backend for variables + extraction schema
- IN: E2E test automation setup, staging environment refresh

### Phase 6 Gate

- [ ] Create agent → configure → test call → works E2E
- [ ] Agent config loads correctly in PipecatProviderFactory
- [ ] Test call works with <3s setup time
- [ ] Graceful cleanup on all termination paths

---

## Phase 7: Flow Builder & Versioning (Weeks 13–14)

**Goal:** Visual conversation flow builder with 8 node types, execution engine, version control.

**Exit Criteria:** 5-node dental booking flow → test call → AI follows flow → publish v1 → roll back after editing v2.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 7.1 | React Flow canvas + custom theme | FL | Canvas renders, zoom/pan, grid snapping |
| 7.2 | 8 node types (Conversation, Function, Logic Split, Transfer, Press Digit, Extract Variable, SMS, Ending) | FL + FE | All draggable, configurable, visually distinct |
| 7.3 | Node configuration panels (slide-out per type) | FE | Click node → edit → save → node updates |
| 7.4 | Edge connections + validation | FL | No orphans, start required, ending reachable |
| 7.5 | Flow execution engine (backend) | BL | Traverses flow JSON during Pipecat call |
| 7.6 | Flex vs Rigid execution modes | BL | Flex: AI jumps. Rigid: sequential. |
| 7.7 | Flow → Pipeline integration | BL | Pipecat reads flow JSON, executes nodes |
| 7.8 | Agent versioning (draft → published → archived) | BE + FL | Save version, publish, rollback |
| 7.9 | Version history sidebar | FE | Version list with timestamps, diffs |
| 7.10 | Publish confirmation + optional smoke test | FL | Confirmation dialog. Optional test call. |

**Resource utilization:**
- FL: 4 tasks — canvas, validation, versioning, publish (lead role)
- FE: 3 tasks — node types, config panels, version sidebar
- BL: 3 tasks — execution engine, modes, integration (critical)
- BE: assists with versioning backend, API endpoints
- IN: performance profiling on flow rendering, CI for flow validation tests

### Phase 7 Gate

- [ ] 5-node flow works with live call (AI follows nodes)
- [ ] Validation catches orphan nodes, missing start/ending
- [ ] Publish v1 → edit → publish v2 → rollback to v1

---

## Phase 8: Phone Numbers & Call History (Weeks 15–16)

**Goal:** Buy phone numbers, route inbound calls, complete call history with search/filter/export.

**Exit Criteria:** Purchase number → assign to agent → inbound call → call in history with transcript + recording + filtering.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 8.1 | Phone number search API (Twilio) | BE | Search by country, area code, pattern |
| 8.2 | Purchase + assign to agent | BE | Buy → DB → Twilio webhook → SphereVoice |
| 8.3 | Inbound call routing (number → agent) | BL | Webhook → find agent → create Pipecat pipeline |
| 8.4 | Phone number management UI | FE | Search, purchase, assign, status indicators |
| 8.5 | Outbound call API (single + dynamic vars) | BL | `POST /calls/outbound` → Pipecat initiates |
| 8.6 | Call history API (list, filter, detail) | BE | Filter by tenant, agent, date, status, sentiment |
| 8.7 | Advanced filtering + saved presets | BE + FE | Compose filters, save presets |
| 8.8 | Call history table (TanStack Table) | FE | Custom columns, sort, paginate. 10K+ rows. |
| 8.9 | Call detail: transcript + audio player | FE | Synchronized player with transcript highlighting |
| 8.10 | Export calls (CSV, JSON) | BE + FE | Async export for large datasets |

**Resource utilization:**
- BE: 4 tasks — phone APIs, call history API, filtering, export
- BL: 2 tasks — inbound routing, outbound calls
- FE: 4 tasks — phone UI, filtering UI, table, detail view
- FL: assists with table component patterns, reviews UX
- IN: staging phone number provisioning, load testing history queries

### Phase 8 Gate

- [ ] Buy number → assign agent → inbound call handled E2E
- [ ] Call in history within 5s with transcript + recording
- [ ] Filter 10K+ calls by multiple criteria <500ms
- [ ] Client sees only their tenant's calls

---

## Phase 9: Live Monitoring & Post-Call Processing (Weeks 17–18)

**Goal:** Real-time active call dashboard. Background extraction, webhooks, retention.

**Exit Criteria:** Employee sees live transcript. Post-call extraction runs. Webhook fires within 10s.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 9.1 | WebSocket server for real-time events | BE | Events: `call_started`, `call_ended`, `transcript_chunk` |
| 9.2 | Active calls dashboard | FE | List live calls, duration counter, auto-updates |
| 9.3 | Live transcription stream | FE | Click call → transcript updates real-time |
| 9.4 | Real-time latency display per call | FE | P50 latency shown. Red if >500ms. |
| 9.5 | Manual call termination | FE + BL | "End Call" → pipeline terminated → room closed |
| 9.6 | Celery worker: post-call data extraction | BE | After call → extract summary, success, sentiment |
| 9.7 | Recording transcoding + permanent storage | BE | Raw → MP3 → Azure Blob → 90-day URL |
| 9.8 | Webhook delivery (retry + dead letter) | BE | POST → retry 3x → dead letter on failure |
| 9.9 | Webhook delivery log UI | FE | View attempts, status codes, replay |
| 9.10 | Data retention auto-cleanup | BE | Configurable per tenant. Nightly Celery beat. |

**Resource utilization:**
- BE: 5 tasks — WebSocket, Celery, recording, webhooks, retention
- BL: 1 task — manual termination integration
- FE: 4 tasks — dashboard, transcript, latency, webhook log
- FL: reviews UX, assists with WebSocket client patterns
- IN: Celery worker scaling config, monitoring queue depth

### Phase 9 Gate

- [ ] Live monitoring shows real-time transcript
- [ ] Post-call extraction populates structured data
- [ ] Webhook fires within 10s, retries on failure
- [ ] 50 concurrent calls complete, all in history

---

## Phase 10: Knowledge Base & RAG (Weeks 19–20)

**Goal:** Upload docs, embeddings, vector search, and inject chunks during live calls.

**Exit Criteria:** Agent answers KB question correctly during live call. RAG adds <50ms.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 10.1 | File upload API (PDF, DOCX, TXT — 100MB) | BE | Upload → Azure Blob → document ID |
| 10.2 | Text extraction (PyMuPDF, python-docx) | BE | All 3 formats → clean text |
| 10.3 | Chunking (512 tokens, 50 overlap) | BE | Document → chunks with metadata |
| 10.4 | Embedding generation (OpenAI `text-embedding-3-small`) | BE | Chunk → 1536-dim vector → pgvector |
| 10.5 | Similarity search API | BE | Query → top-k by cosine similarity |
| 10.6 | Knowledge base CRUD UI | FE | Drag-and-drop upload, progress, doc list |
| 10.7 | KB attachment config (agent → KB link) | BE + FL | Attach KBs, configure top-k, threshold |
| 10.8 | RAG retrieval during Pipecat call | BL | Question → embed → search → inject into LLM |
| 10.9 | RAG latency benchmark (<50ms) | BL | HNSW index. Confirmed <50ms for 100K chunks. |
| 10.10 | Sharing scope: private, tenant-wide, global | BE | Visibility by scope. RLS enforced. |

**Resource utilization:**
- BE: 6 tasks — upload, extraction, chunking, embedding, search, sharing
- BL: 2 tasks — RAG integration + latency benchmark (critical path)
- FE: 1 task — KB CRUD UI
- FL: 1 task — attachment config UI
- IN: pgvector HNSW index tuning, benchmarking

### Phase 10 Gate

- [ ] Agent answers KB question correctly during live call
- [ ] RAG adds <50ms latency
- [ ] Upload 10MB PDF → embedded in <60s
- [ ] Sharing scopes enforced by RLS

---

## Phase 11: Analytics, Templates & User Management (Weeks 21–22)

**Goal:** Metrics dashboard, agent templates, and user administration.

**Exit Criteria:** Dashboard loads in <2s. Templates create working agents. Admins can invite/manage users.

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 11.1 | Metrics aggregation (Celery periodic task) | BE | Pre-compute daily/weekly/monthly aggregates |
| 11.2 | Analytics API: metric cards + time series | BE | Calls, duration, latency, concurrency, success rate |
| 11.3 | Metric cards UI (Recharts) | FE | 7 cards with trend indicators (↑/↓) |
| 11.4 | Time-series charts + filter panel | FE | Line charts, zoom, date range, tenant/agent filter |
| 11.5 | Client read-only dashboard | FE | Their tenant only. No config/cost data. |
| 11.6 | Export: charts as PNG/SVG, data as CSV | FE | Download per chart/table |
| 11.7 | 8 pre-built agent templates | BL + FL | Gallery, preview, "Use Template" → agent created |
| 11.8 | Save agent as custom template | FL | Save → set scope → appears in gallery |
| 11.9 | User invite system (email + magic link) | BE | Admin invites → email → account with role |
| 11.10 | User management UI (list, edit role, deactivate) | FE | Admin changes roles, deactivates users |
| 11.11 | Audit log viewer | FE | Filterable table: who, what, when, from where |

**Resource utilization:**
- BE: 3 tasks — aggregation, analytics API, user invites
- BL: 1 task — templates (agent config generation)
- FE: 5 tasks — charts, filters, client dashboard, export, user mgmt, audit viewer
- FL: 2 tasks — template gallery + custom template save
- IN: query performance profiling on analytics, caching strategy

### Phase 11 Gate

- [ ] Dashboard loads in <2s with 30 days of data
- [ ] Client sees only their tenant's analytics
- [ ] Templates create working agents
- [ ] Admin can invite, edit roles, deactivate users

---

## Phase 12: Hardening, Testing & Launch (Weeks 23–24)

**Goal:** Security hardened, load tested, chaos tested, documented, and 3 clients onboarded. This is the launch sprint — all hands.

**Exit Criteria:** Pen test passed. 100 concurrent calls at P50 <300ms. Runbooks tested. 3 clients live.

### Week 23: Security + Performance

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 12.1 | Pen testing (OWASP Top 10) | IN + All | No critical/high findings |
| 12.2 | Dependency scan (`pip audit` + `npm audit`) | IN | Zero critical CVEs |
| 12.3 | Rate limiting on all API endpoints | BE | 100/min per user, 1000/min per tenant. 429 + Retry-After. |
| 12.4 | Azure Front Door + WAF | IN | DDoS protection, OWASP rules |
| 12.5 | Secret scanning (Gitleaks) + CSP/HSTS headers | IN | PR blocked on secrets. A+ security headers. |
| 12.6 | DB index audit + query optimization | BE | `EXPLAIN ANALYZE` for all critical paths |
| 12.7 | Load test: 100 concurrent calls (Locust) | BL + IN | All complete. P50 <300ms. P99 <500ms. Zero errors. |
| 12.8 | Load test: 1000 concurrent API requests | BE + IN | P95 <200ms. Zero 5xx. |

### Week 24: Testing, Docs & Launch

| # | Task | Owner | Acceptance Criteria |
|---|------|-------|---------------------|
| 12.9 | E2E tests — critical paths (Playwright) | FL | Login → create agent → test call → view history. In CI. |
| 12.10 | Chaos test: kill backend during calls | IN | Active calls survive. New calls route healthy. |
| 12.11 | API documentation (auto-generated OpenAPI) | BE | Every endpoint at `/docs` with examples |
| 12.12 | User guide + deployment runbooks | FL + IN | "First agent in 5 min" tutorial. Runbooks tested by non-author. |
| 12.13 | Production deployment + DNS + TLS | IN | `terraform apply` on prod. HTTPS. |
| 12.14 | Onboard 3 clients | All | Tenants, agents, phone numbers live. 10 observed calls each. |

**Resource utilization:**
- Week 23: IN (pen test, WAF, scanning), BE (rate limiting, DB tuning, load test), BL (call load test)
- Week 24: FL (E2E tests, user guide), FE (assists E2E + onboarding), IN (chaos, prod deploy), All (onboarding)

### Phase 12 Gate (Launch Checklist)

- [ ] **Security:** Pen test passed, zero critical CVEs, WAF + rate limiting active
- [ ] **Performance:** 100 concurrent calls P50 <300ms, P99 <500ms
- [ ] **Reliability:** Chaos test — instance death → zero dropped calls
- [ ] **Observability:** Grafana dashboards, alerts configured, runbooks tested
- [ ] **Documentation:** API docs, user guide, runbooks complete
- [ ] **Clients:** 3 live clients making real calls
- [ ] **Data integrity:** Cross-tenant isolation verified with 3 live clients
- [ ] **Backup:** DB backup + restore tested

---

## Cross-Cutting Concerns (Every Phase)

### Continuous Security

| Activity | Cadence | Tool |
|----------|---------|------|
| Dependency vulnerability scan | Every CI run | `pip audit` + `npm audit` |
| Secret scanning | Every PR | Gitleaks |
| RLS regression tests | Every CI run | Custom test suite |
| JWT validation | Every API request | Middleware |

### Continuous Observability

| Activity | Cadence | Tool |
|----------|---------|------|
| Structured log review | Daily | Azure Monitor / Grafana |
| Latency trend monitoring | Daily | Grafana dashboard |
| Error rate monitoring | Real-time | Sentry + Prometheus |
| Trace sampling | Every request (10% prod) | OpenTelemetry + Tempo |
| Credit usage | Weekly | Azure Cost Management |

### Continuous Testing

| Activity | Cadence | Tool |
|----------|---------|------|
| Unit + integration tests | Every CI run | pytest + vitest |
| E2E (critical paths) | Nightly | Playwright |
| Load tests | Weekly (Phase 5+) | Locust |
| Chaos tests | Bi-weekly (Phase 9+) | Chaos Toolkit |

---

## Milestone Summary

| Milestone | Phase | Week | Deliverable |
|-----------|-------|------|-------------|
| **M0** | 0A–0B | 0 | Repo + ADRs + risk register |
| **M1** | 1 | 2 | Cloud infra + observability + frontend scaffold |
| **M2** | 2 | 4 | Database + RLS + app shell |
| **M3** | 3 | 6 | Auth + providers + first full-stack feature |
| **M4** | 4 | 8 | Audio pipeline (LiveKit + Pipecat + STT) |
| **M5** | 5 | 10 | **First voice call** — full pipeline working |
| **M6** | 6 | 12 | Single prompt agent + test calls from browser |
| **M7** | 7 | 14 | Flow builder + versioning |
| **M8** | 8 | 16 | Phone numbers + call history |
| **M9** | 9 | 18 | Live monitoring + post-call processing |
| **M10** | 10 | 20 | Knowledge base + RAG in live calls |
| **M11** | 11 | 22 | Analytics + templates + user management |
| **M12** | 12 | 24 | **Launch** — 3 clients live |

---

## Scaling Plan (Post-Launch)

| Threshold | Action | Cost |
|-----------|--------|------|
| 100 concurrent calls | Single backend + LiveKit | ~$350/mo (credits) |
| 500 concurrent calls | 3 backend replicas, LiveKit cluster | ~$800/mo |
| 1000 concurrent calls | Read replica, Redis cluster, Celery workers | ~$1,500/mo |
| 2000+ concurrent calls | Multi-region (US-East + Mumbai), CDN | ~$3,000/mo |

---

## Cost Projections

| Period | Monthly Cost | Notes |
|--------|-------------|-------|
| Weeks 1–10 (Dev) | ~$50/mo | Dev only. Azure credits. |
| Weeks 11–18 (Staging) | ~$150/mo | Staging + dev. Credits. |
| Weeks 19–24 (Prod prep) | ~$250/mo | Prod + staging + dev. Credits. |
| Post-Launch | ~$250–350/mo | Azure pay-as-you-go |
| Post-Credits | ~$150/mo | Supabase + Railway migration |

---

## Decision Log

| Date | Decision | ADR | Rationale |
|------|----------|-----|-----------|
| 2026-03-04 | `tenant_id` (not `organization_id`) | ADR-009 | Industry-standard multi-tenancy term |
| 2026-03-04 | Next.js 15.1.6 + Auth.js v5 | ADR-003.1 | Native App Router support, Edge-compatible |
| 2026-03-04 | Pin all deps to exact versions | ADR-010 | Reproducible builds, no breaking changes |
| 2026-03-04 | Modular monolith (domain modules) | ADR-011 | Clean boundaries per domain, extractable to services later, `import-linter` enforced |
| | | | |

---

**End of Document**

This plan maps to [prd.md](./prd.md) (WHAT) and [tech-prd.md](./tech-prd.md) (HOW). Update all three together.
