# SphereVoice Admin View Gap Report

## Scope

This report evaluates SphereVoice as an internal Sphere admin tool for operating client tenants. It focuses on the admin/internal view only: tenant and client onboarding, employee and client user management, cross-tenant visibility, tenant isolation, and admin reporting completeness. External integrations are intentionally excluded.

For the agency-scale frontend isolation strategy that goes beyond this gap report, see [docs/agency-frontend-isolation-plan.md](docs/agency-frontend-isolation-plan.md).

## Executive Summary

SphereVoice already has a meaningful internal operations surface, but it is not yet complete as a true multi-tenant admin platform. The current implementation supports cross-tenant employee access, user invitation and editing, audit-log inspection, analytics, live-call monitoring, provider management, knowledge-base scope controls, admin-only tenant management APIs, and a first-pass internal tenants page. What is still missing is the final operating layer that turns those building blocks into a fully practical internal admin tool: richer tenant onboarding UX, stronger tenant-level workflows, cleanup of demo role semantics, and end-to-end validation of the admin workspace.

The most important technical finding is that tenant isolation is generally well-designed and mostly enforced in PostgreSQL via RLS, but private knowledge-base visibility depends on `app.current_user_id` being set in the request-scoped DB context. That context was not previously set by the shared dependency, which created a correctness gap for private knowledge-base policies.

## Current Completeness By Admin Domain

### Implemented

1. User management exists for admins.
   Evidence: [backend/app/modules/analytics/router.py](backend/app/modules/analytics/router.py), [backend/app/modules/analytics/service.py](backend/app/modules/analytics/service.py), [frontend/src/app/(dashboard)/settings/page.tsx](frontend/src/app/(dashboard)/settings/page.tsx), [frontend/src/modules/analytics/components/users-table.tsx](frontend/src/modules/analytics/components/users-table.tsx)

2. Audit-log inspection exists for admins.
   Evidence: [backend/app/modules/analytics/router.py](backend/app/modules/analytics/router.py), [backend/app/modules/analytics/service.py](backend/app/modules/analytics/service.py), [frontend/src/modules/analytics/components/audit-log-table.tsx](frontend/src/modules/analytics/components/audit-log-table.tsx)

3. Cross-tenant employee analytics exist at the API layer.
   Evidence: [backend/app/modules/analytics/router.py](backend/app/modules/analytics/router.py), [frontend/src/modules/analytics/hooks/use-analytics.ts](frontend/src/modules/analytics/hooks/use-analytics.ts)

4. Live-call monitoring and operational pages exist, but they are not organized as an admin workspace.
   Evidence: [frontend/src/components/layout/sidebar.tsx](frontend/src/components/layout/sidebar.tsx)

5. Role-based backend access exists for admin, employee, and client-user classes.
   Evidence: [backend/app/modules/auth/dependencies.py](backend/app/modules/auth/dependencies.py), [backend/app/modules/auth/models.py](backend/app/modules/auth/models.py)

6. Tenant isolation exists at the schema and policy level.
   Evidence: [backend/alembic/versions/001_initial_schema.py](backend/alembic/versions/001_initial_schema.py), [backend/alembic/versions/002_hnsw_index_and_kb_sharing_rls.py](backend/alembic/versions/002_hnsw_index_and_kb_sharing_rls.py), [backend/tests/test_rls/test_tenant_isolation.py](backend/tests/test_rls/test_tenant_isolation.py)

7. Admin-only tenant management APIs now exist.
   Evidence: [backend/app/modules/analytics/router.py](backend/app/modules/analytics/router.py), [backend/app/modules/analytics/service.py](backend/app/modules/analytics/service.py), [backend/tests/test_analytics/test_tenants_api.py](backend/tests/test_analytics/test_tenants_api.py)

8. A first-class admin tenants page now exists in the frontend.
   Evidence: [frontend/src/app/(dashboard)/tenants/page.tsx](frontend/src/app/(dashboard)/tenants/page.tsx), [frontend/src/modules/analytics/components/tenants-table.tsx](frontend/src/modules/analytics/components/tenants-table.tsx), [frontend/src/components/layout/sidebar.tsx](frontend/src/components/layout/sidebar.tsx)

9. Tenant-aware filtering is now exposed in key admin pages.
   Evidence: [frontend/src/app/(dashboard)/analytics/page.tsx](frontend/src/app/(dashboard)/analytics/page.tsx), [frontend/src/app/(dashboard)/settings/page.tsx](frontend/src/app/(dashboard)/settings/page.tsx), [frontend/src/modules/analytics/components/users-table.tsx](frontend/src/modules/analytics/components/users-table.tsx), [frontend/src/modules/analytics/components/audit-log-table.tsx](frontend/src/modules/analytics/components/audit-log-table.tsx)

### Missing Or Incomplete

1. Tenant onboarding is still basic.
   The UI now supports create and edit flows, but there is still no stepwise onboarding flow, ownership assignment flow, or operational checklist.

2. The role model used in seed/demo data does not match the intended operating model.
   Tenant-local “admin” and “developer” demo users are stored as `client_user`, which is misleading for admin-view validation.

3. Tenant detail is still shallow.
   The tenants page shows summary counts and metadata, but not a full tenant workspace with recent activity, assigned users, or operational health.

4. End-to-end admin validation is still incomplete.
   The new tenant and filtering workflows are implemented, but they still need browser-level verification in a running app.

## How Tenants Are Created Today

Tenants are represented as first-class rows in the `tenants` table via [backend/app/modules/auth/models.py](backend/app/modules/auth/models.py). Tenant creation now happens in four ways:

1. Database migrations establish the table structure.
2. Development seed data creates sample tenants in [backend/seed.py](backend/seed.py).
3. Ad hoc scripts and direct DB writes can insert tenants, as seen in [backend/scripts/benchmark_rag.py](backend/scripts/benchmark_rag.py).
4. Admin-only tenant management endpoints can create and update tenant records via [backend/app/modules/analytics/router.py](backend/app/modules/analytics/router.py).

There is no implemented internal onboarding flow for:

1. Assigning a tenant owner or onboarding checklist.
2. Tracking onboarding state and required setup steps.
3. Viewing deeper tenant-level operational context beyond summary counts.

## How Isolation Works Today

### What Is Strong

1. Tenant-aware tables and foreign keys are present across the core domain.
2. RLS policies enforce tenant scoping in PostgreSQL.
3. Backend RBAC distinguishes admin-only endpoints from employee and client-user flows.
4. Admin users are modeled with `tenant_id = NULL`, allowing cross-tenant operation.

### What Was Missing And Is Now Being Fixed

Knowledge-base sharing policies in [backend/alembic/versions/002_hnsw_index_and_kb_sharing_rls.py](backend/alembic/versions/002_hnsw_index_and_kb_sharing_rls.py) rely on three request-scoped values:

1. `app.current_tenant_id`
2. `app.user_role`
3. `app.current_user_id`

Before this implementation pass, [backend/app/core/dependencies.py](backend/app/core/dependencies.py) set only tenant and role, not current user ID. That meant private knowledge-base policies were incomplete at runtime.

### Remaining Isolation Caveats

1. The main HTTP test fixture in [backend/tests/conftest.py](backend/tests/conftest.py) overrides `set_tenant_context`, so most API tests do not exercise real RLS.
2. UI-level role guards remain convenience only; the real boundary is backend auth plus RLS.

## Admin-View Gaps

### High Priority

1. Tenant management is only partially implemented.
   Backend CRUD and a first frontend tenants page now exist, but the onboarding and tenant-detail workflow is still thin.
2. Seed/demo role semantics are misleading for validation and demos.
3. The admin workspace still lacks a richer tenant detail and operational health view.
4. Browser-level verification is still needed for the new flows.

### Medium Priority

1. Settings is still carrying multiple admin concerns instead of acting as a narrower configuration area.
2. Tenant management is separated from deeper onboarding and account-ownership workflows.

## Recommended Implementation Order

1. Fix isolation correctness first.
   Ensure request-scoped DB context always includes current user ID and add regression coverage around private knowledge-base visibility.

2. Add a real tenant-management admin UI.
   Status: done for the first pass via a dedicated tenants page and sidebar route.

3. Expose tenant selectors across admin reporting.
   Status: done for analytics, audit logs, and user management.

4. Replace raw UUID workflows.
   Status: done for client-user invite flow.

5. Clean up demo and seeded role semantics.
   Align development fixtures with the actual Sphere employee versus client-user model.

6. Add browser-verified tenant admin smoke coverage.
   Validate tenant creation, update, user invite, analytics filtering, and audit filtering in the running UI.

## Completion Assessment

For the admin/internal-tool use case, the platform is partially complete.

1. Core admin building blocks: mostly present.
2. Tenant lifecycle management: materially improved, but still not fully operationally complete.
3. Cross-tenant admin UX: substantially improved, but still missing deeper tenant workflows.
4. Tenant isolation architecture: strong, with one fixed correctness gap around private KB request context.
5. Internal operating model fit for Sphere staff: close to viable for first-pass internal use, but not complete until seed-role cleanup and browser-verified tenant workflows are finished.