# ADR-011: Modular Monolith Backend (Domain Modules with Explicit Boundaries)

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Full engineering team  
**Technical Story:** SphereVoice's backend is a FastAPI application with 9 domain areas (auth, agents, providers, calls, pipeline, knowledge_base, analytics, webhooks, phone_numbers). We need an architecture that keeps the codebase organized as it grows while avoiding the operational overhead of microservices for a 5-person team.

---

## Context

We evaluated three backend architectures:

1. **Flat CRUD app** — All routes, models, and services in a handful of large files
2. **Microservices** — Each domain as a separate service with its own deployment
3. **Modular monolith** — Single deployable, internally organized into self-contained domain modules with explicit boundaries

## Decision

**Use a modular monolith architecture**: a single FastAPI application deployed as one container, internally organized into **self-contained domain modules** under `backend/app/modules/`.

### Module Structure

```
backend/app/modules/
├── auth/               # Authentication, JWT, RBAC, tenant context
│   ├── __init__.py     # Public API: login(), verify_token(), get_current_user()
│   ├── router.py       # /api/v1/auth/*
│   ├── models.py       # User, Role SQLAlchemy models
│   ├── schemas.py      # Pydantic request/response models
│   ├── service.py      # Business logic
│   └── dependencies.py # require_role(), FastAPI Depends()
├── agents/             # Agent CRUD, versioning, configuration
├── providers/          # Provider key encryption, CRUD, connection testing
├── calls/              # Call history, lifecycle, outbound calls
├── pipeline/           # Pipecat voice pipeline, orchestrator, factory
├── knowledge_base/     # Document upload, chunking, embedding, vector search
├── phone_numbers/      # Twilio/Plivo integration, number purchase
├── analytics/          # Metrics aggregation, time-series
└── webhooks/           # Registration, delivery, retry, dead letter
```

### Boundary Rules (Enforced in CI)

```
✅ from app.modules.agents import get_agent        # Public API via __init__.py
❌ from app.modules.agents.service import AgentService  # BLOCKED by import-linter
✅ from app.core.database import get_db             # Shared kernel always allowed
✅ Workers import from module public APIs only
```

**Enforcement:** `import-linter` in `pyproject.toml` defines contracts that block cross-module internal imports. CI fails if a violation is introduced.

### Shared Kernel

```
backend/app/core/
├── config.py          # pydantic-settings for configuration
├── database.py        # Async SQLAlchemy engine + session factory
├── security.py        # JWT decode, password hashing
├── encryption.py      # AES-256-GCM for provider keys
├── dependencies.py    # get_db, get_current_user, get_tenant
├── middleware.py       # Tenant context, CORS, request ID
├── exceptions.py      # Structured error responses
└── base_model.py      # TimestampMixin, TenantMixin
```

The shared kernel contains cross-cutting concerns that all modules need. It is NOT a module — it does not have business logic, routes, or its own models.

## Rationale

### Why Modular Monolith over Alternatives

| Factor | Flat CRUD | Microservices | Modular Monolith |
|--------|----------|---------------|------------------|
| **Team size fit** | 1-2 devs | 10+ devs | 3-8 devs |
| **Operational complexity** | Low | Very high (N deploys, N DBs, service mesh) | Low (1 deploy, 1 DB) |
| **Code organization** | Degrades fast | Forced isolation | Explicit boundaries |
| **Refactoring** | Easy (everything in scope) | Hard (cross-service changes) | Easy (in-process calls) |
| **Performance** | Good (in-process) | Network overhead | Good (in-process) |
| **Testing** | Easy | Hard (integration across services) | Easy (in-process + module boundaries) |
| **Debugging** | Easy | Hard (distributed tracing required) | Easy (single process, structured logs) |
| **Migration to microservices** | Big rewrite | Already there | Extract module → standalone service (1 day) |

For 5 engineers building a platform with ~10 domain areas, microservices would add massive operational overhead (separate deployments, inter-service communication, distributed transactions, service mesh) without proportional benefit. A flat CRUD app would work initially but degrade into a tangled mess within months.

### Extraction Path

If a module outgrows the monolith (e.g., `pipeline` needs its own process pool for concurrent call handling):

1. Promote the module's `router.py` to a standalone FastAPI app
2. Replace internal imports with HTTP/gRPC calls
3. Deploy as a separate container
4. Add to Terraform + CI/CD

Estimated effort: **1 day per module.** The modular structure makes this mechanical, not architectural.

### Why import-linter

Without enforcement, module boundaries erode within weeks:
- A developer imports `AgentService` directly instead of using the public API
- Another developer adds a circular dependency between `agents` and `calls`
- Within a month, modules are tightly coupled and extraction becomes a rewrite

`import-linter` makes boundary violations a CI failure — the same way type errors fail the build.

## Consequences

### Positive
- Clear ownership — each module has a defined scope and public API
- In-process calls between modules — no network overhead, no serialization
- Single deployment — simple CI/CD, one Docker image, one health check
- Easy testing — modules can be tested in isolation with mocked dependencies
- Future-proof — extractable to microservices if/when needed (1 day per module)
- `import-linter` prevents boundary erosion automatically

### Negative
- Requires discipline to maintain module boundaries (mitigated by linting)
- All modules share the same database — schema changes can affect multiple modules
- Single process means one module's crash affects all (mitigated by health checks + auto-restart)
- Module public APIs (`__init__.py`) must be maintained as contracts

### Risks
- **Risk:** Module boundary erosion over time (Probability: Medium without enforcement, Low with enforcement)  
  **Mitigation:** `import-linter` enforced in CI. PR reviews check for boundary violations. Module `__init__.py` acts as explicit public API.
- **Risk:** Single module becomes a performance bottleneck  
  **Mitigation:** Extract to separate service (1-day effort). Profile before extracting — most "bottlenecks" are actually specific queries, not module-level issues.

## Related ADRs
- [ADR-001: Monorepo Structure (Turborepo)](./ADR-001-monorepo-turborepo.md)
- [ADR-004: PostgreSQL RLS for Tenant Isolation](./ADR-004-postgresql-rls-tenant-isolation.md)
