# ADR-003: Auth.js v5 + FastAPI JWT Dual-Auth Strategy

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Frontend Lead, Backend Engineer, Full team  
**Technical Story:** SphereVoice has a Next.js frontend and FastAPI backend. Authentication must work seamlessly across both, support OAuth providers, enforce RBAC, and carry tenant context.

---

## Context

SphereVoice requires:
- Frontend session management with OAuth (Google, Email) support
- Backend API protection with JWT tokens carrying `user_id`, `tenant_id`, and `role`
- Role-based access control (admin, developer, read_only, client)
- Tenant isolation — every API request must be scoped to a tenant

We evaluated three approaches:

1. **Auth.js only** — Handle everything in Next.js, pass session cookies to backend
2. **FastAPI JWT only** — Custom login endpoint, JWT for everything, no Auth.js
3. **Dual-auth** — Auth.js v5 manages frontend sessions + OAuth; FastAPI issues JWTs with tenant/role claims for API calls

## Decision

**Use Auth.js v5 (`next-auth@5`) for frontend session management and FastAPI JWT for backend API protection.**

### Auth Flow

```
1. User clicks "Sign In" → Auth.js handles OAuth/credentials
2. Auth.js creates a session (cookie-based)
3. Frontend calls Auth.js session endpoint to get user info
4. Frontend exchanges Auth.js session for a FastAPI JWT:
   POST /api/v1/auth/token-exchange
   Body: { auth_js_token: "..." }
   Response: { access_token: "...", refresh_token: "..." }
5. JWT contains: { user_id, tenant_id, role, exp }
6. Frontend sends JWT in Authorization header for all /api/v1/* calls
7. FastAPI middleware validates JWT, sets tenant context via RLS
```

### Token Details

| Token | Lifetime | Storage | Purpose |
|-------|----------|---------|---------|
| Auth.js session cookie | Session (browser close) | HTTP-only cookie | Frontend SSR, OAuth state |
| Access token (JWT) | 1 hour | Memory (React state) | API authorization |
| Refresh token | 7 days | HTTP-only cookie | Silent token renewal |

## Rationale

### Why Dual-Auth over Single Strategy

| Factor | Auth.js Only | FastAPI JWT Only | Dual-Auth |
|--------|-------------|-----------------|-----------|
| **OAuth support** | Built-in (Google, GitHub, Email) | Must build from scratch | Auth.js handles OAuth |
| **Server-side rendering** | Native session access | Must forward JWT | Auth.js session for SSR |
| **API protection** | Cookies don't carry tenant claims | Full control over JWT claims | JWT with tenant_id + role |
| **Multi-tenancy** | No tenant claim support | Custom JWT with tenant_id | JWT carries tenant context |
| **RBAC** | Limited to session data | Full role enforcement | Role in JWT claim |
| **Mobile/API clients** | Cookie-based, awkward for APIs | JWT-based, standard | JWT for all API clients |

Key insight: Auth.js excels at frontend OAuth flows but doesn't support custom JWT claims (tenant_id, role) needed for PostgreSQL RLS. FastAPI needs JWT with these claims to set `app.current_tenant_id` in the DB session. The dual approach uses each tool where it's strongest.

### Why Auth.js v5

- Auth.js v5 is the stable version for Next.js App Router
- Built-in adapter pattern for database-backed sessions
- Edge-compatible (runs in Next.js middleware)
- Active community, well-maintained

## Consequences

### Positive
- Auth.js handles the complex OAuth/session management with minimal code
- FastAPI JWT carries all claims needed for tenant isolation and RBAC
- API clients (future mobile, third-party) use standard JWT — no cookie dependency
- Clean separation: Auth.js = "who are you?" / FastAPI JWT = "what can you access?"

### Negative
- Two auth systems to maintain and keep in sync
- Token exchange endpoint adds one extra round-trip after login
- Must handle token refresh gracefully (silent refresh on 401)
- Session invalidation must propagate to both systems

### Risks
- **Risk:** Token desync (Auth.js session valid but JWT expired, or vice versa)  
  **Mitigation:** Frontend interceptor catches 401, triggers silent refresh. If refresh fails, redirect to login. Auth.js session expiry invalidates JWT refresh token.

## Related ADRs
- [ADR-004: PostgreSQL RLS for Tenant Isolation](./ADR-004-postgresql-rls-tenant-isolation.md)
