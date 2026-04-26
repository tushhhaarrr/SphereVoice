# ADR-004: PostgreSQL RLS for Tenant Isolation

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Backend Engineer, Backend Lead, Full team  
**Technical Story:** SphereVoice is a multi-tenant platform. Employee users manage agents for multiple client tenants. Client users must see only their own data. We need an isolation mechanism that is secure by default and cannot be bypassed by application bugs.

---

## Context

SphereVoice stores tenant-scoped data: agents, calls, provider keys, knowledge bases, phone numbers, webhooks. A security breach where Tenant A sees Tenant B's data is unacceptable — it would destroy client trust.

We evaluated three isolation approaches:

1. **Application-level WHERE clauses** — Every query includes `WHERE tenant_id = ?`
2. **PostgreSQL Row-Level Security (RLS)** — Database enforces isolation via policies
3. **Separate databases per tenant** — Physical isolation

## Decision

**Use PostgreSQL Row-Level Security (RLS)** as the primary isolation mechanism, with application-level `tenant_id` filtering as a secondary defense layer.

### Implementation

**Every tenant-scoped table** includes a `tenant_id UUID NOT NULL` column with a foreign key to `tenants.id`.

**RLS policy pattern:**
```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON <table>
  FOR ALL TO authenticated_users
  USING (
    tenant_id = current_setting('app.current_tenant_id')::UUID
    OR current_setting('app.user_role') = 'admin'
  );
```

**Middleware sets tenant context before every query:**
```python
# FastAPI dependency (runs per-request within the DB transaction)
async def set_tenant_context(db: AsyncSession, user: User):
    await db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": str(user.tenant_id)})
    await db.execute(text("SET LOCAL app.user_role = :role"), {"role": user.role})
```

**Admin bypass:** Users with `role = 'admin'` have `tenant_id = NULL` and can access all tenants via the `OR` clause. This is for Sphere employees who manage multiple clients.

## Rationale

### Why RLS over Alternatives

| Factor | WHERE Clause | RLS | Separate DBs |
|--------|-------------|-----|--------------|
| **Security guarantee** | Relies on dev discipline | DB enforces — app bugs can't bypass | Physical isolation |
| **Forgotten WHERE** | Data leak | Impossible — RLS blocks it | N/A |
| **New query/ORM code** | Must add filter every time | Automatic | N/A |
| **Operational complexity** | Low | Low (one DB) | High (N databases, N connections) |
| **Migration complexity** | Low | Low (one schema) | High (N migrations) |
| **Cross-tenant queries** | Easy (admin) | Admin role bypasses RLS | Requires cross-DB joins |
| **Cost** | 1 DB | 1 DB | N DBs × cost |
| **Performance overhead** | None | ~1-2% per query (negligible) | None per query, but connection pooling is complex |

For a platform with tens of tenants (not thousands), RLS provides the best balance of security and operational simplicity. Separate databases would be justified only at 100+ tenants with strict compliance requirements.

### Defense in Depth

RLS is the **safety net**, not the only defense:
1. **JWT claims** carry `tenant_id` — validated before any logic runs
2. **FastAPI dependency** sets `app.current_tenant_id` from the JWT
3. **SQLAlchemy mixins** add `tenant_id` to all tenant-scoped models
4. **RLS policies** catch anything the application layer misses

If a developer forgets a WHERE clause or introduces a code path that doesn't set tenant context, RLS returns zero rows instead of leaking data.

## Consequences

### Positive
- Data isolation is enforced at the database level — cannot be bypassed by application bugs
- Single database, single schema — simple operations, migrations, backups
- Admin users can query across tenants (for analytics, support, debugging)
- Performance impact is negligible (~1-2% per query)
- Works with SQLAlchemy async sessions without modification

### Negative
- Requires `SET LOCAL app.current_tenant_id` before every request — one missed middleware = broken queries (rows return 0 instead of leaking)
- Schema changes must account for RLS policies (Alembic migrations include policy updates)
- Testing requires setup of RLS context in test fixtures
- Debug/REPL sessions need manual `SET` commands to see data

### Risks
- **Risk:** Middleware fails to set `app.current_tenant_id`, causing all queries to return empty results  
  **Mitigation:** Health check includes a RLS-gated query. Integration tests verify tenant context is set for all route handlers. Sentry alert on unexpected zero-result queries.

## Related ADRs
- [ADR-003: Auth.js v5 + FastAPI JWT Dual-Auth](./ADR-003-dual-auth-strategy.md)
- [ADR-011: Modular Monolith Backend](./ADR-011-modular-monolith.md)
