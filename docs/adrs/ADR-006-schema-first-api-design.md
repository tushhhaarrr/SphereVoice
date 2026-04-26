# ADR-006: Schema-First API Design (OpenAPI 3.1)

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Backend Engineer, Frontend Lead, Full team  
**Technical Story:** SphereVoice has a FastAPI backend consumed by a Next.js frontend and potentially future mobile/API clients. We need a strategy for API contract management that keeps frontend and backend in sync.

---

## Context

SphereVoice's frontend and backend are developed in parallel by different engineers. API contract mismatches (e.g., frontend expects `agent_name` but backend sends `name`) cause integration bugs and slow iteration.

We evaluated two approaches:

1. **Code-first** — Write FastAPI routes with Pydantic models, auto-generate OpenAPI spec
2. **Schema-first** — Define OpenAPI 3.1 spec first, then implement against it

## Decision

**Use schema-first API design**: define all API contracts (request/response schemas, status codes, error formats) in the Tech PRD and Pydantic models **before** implementing route handlers. FastAPI auto-generates the OpenAPI spec from Pydantic models, which serves as the living API documentation.

### Workflow

```
1. Tech PRD defines API contract (endpoints, schemas, status codes)
2. Backend: Create Pydantic schemas matching the Tech PRD exactly
3. Backend: Implement route handlers using those schemas
4. FastAPI auto-generates OpenAPI 3.1 spec at /docs
5. Frontend: Code against the Pydantic-defined contract
6. CI: Validate that OpenAPI spec hasn't drifted from baseline (optional)
```

### API Standards

- **Base path:** `/api/v1/`
- **Auth:** JWT Bearer token in `Authorization` header
- **Content type:** `application/json` (multipart for file uploads)
- **Error format:** Consistent across all endpoints:
  ```json
  {
    "error": {
      "code": "VALIDATION_ERROR",
      "message": "Human-readable message",
      "details": [{"field": "name", "message": "Required"}]
    }
  }
  ```
- **Pagination:** Cursor-based for large collections, offset-based for small
- **Filtering:** Query parameters (`?status=active&provider_type=stt`)
- **Versioning:** URL-based (`/api/v1/`, `/api/v2/` when needed)

## Rationale

### Why Schema-First

| Factor | Code-First | Schema-First |
|--------|-----------|-------------|
| **Frontend-backend sync** | Frontend waits for backend to finish | Both teams code against shared contract |
| **Contract changes** | Implicit — PR reviewer must spot them | Explicit — schema change is a deliberate act |
| **Documentation** | Auto-generated, sometimes incomplete | Intentional, complete, reviewed |
| **Parallel development** | Backend blocks frontend | Frontend stubs from schema, backend implements |

### Why Not a Separate OpenAPI YAML

We considered maintaining a standalone `openapi.yaml` spec file, but:
- FastAPI + Pydantic already auto-generates a complete OpenAPI spec
- Maintaining a separate YAML creates a sync problem (two sources of truth)
- Pydantic models ARE the schema definition — they're type-checked Python
- The Tech PRD acts as the human-readable spec; Pydantic models act as the machine-readable spec

## Consequences

### Positive
- API contracts are defined before implementation — fewer integration surprises
- Pydantic models provide runtime validation, serialization, AND documentation
- FastAPI's `/docs` (Swagger UI) and `/redoc` are always up to date
- Frontend engineers can start work using the Tech PRD API contracts
- Type safety throughout — Pydantic validates every request and response

### Negative
- Requires discipline to update Pydantic schemas when the Tech PRD contract changes
- Initial overhead to define schemas before writing handler logic
- No standalone OpenAPI YAML to share with external consumers (use `/openapi.json` endpoint instead)

### Risks
- **Risk:** Schema drift between Tech PRD and implementation  
  **Mitigation:** Code review explicitly checks Pydantic schemas against Tech PRD contracts. Integration tests validate response shapes.

## Related ADRs
- [ADR-011: Modular Monolith Backend](./ADR-011-modular-monolith.md)
