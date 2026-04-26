# SphereVoice Agency Frontend Isolation Plan

## Goal

Design SphereVoice as an agency operations console that can safely manage hundreds or thousands of client tenants without accidental cross-client edits, UI confusion, or brittle workflows.

This plan is intentionally focused on frontend isolation and operator safety. Database and backend isolation still matter, but the problem here is different: the UI must make it hard to act on the wrong client, easy to understand scope, and easy to debug when something goes wrong.

## Core Position

For 2 to 5 clients, a global admin UI with filters is acceptable.

For 1000 clients, that model is unsafe.

The frontend should not behave like a flat admin dashboard with tenant filters sprinkled across pages. It should behave like a workspace system:

1. A global agency layer for portfolio search, queue management, alerts, and reporting.
2. A dedicated tenant workspace for all client-specific operations.
3. Strong visual and state isolation between those two layers.

The biggest frontend mistake to avoid is this: letting operators remain in a global view while editing tenant-specific resources.

That is how cross-client errors happen.

## What Is Risky In The Current UX

The current implementation is materially better than before, but it is still optimized for a small number of tenants.

### Current risks

1. Tenant context is mostly filter-based rather than workspace-based.
2. Settings combines multiple admin concerns and encourages editing from a broad cross-tenant surface.
3. Tenant creation exists, but onboarding is not modeled as a controlled flow.
4. A global operator can still move between tenants too easily without a strong scope boundary.
5. Lists are doing too much work. At scale, list pages should route into a tenant workspace, not act as the place where sensitive edits happen.

## Target Frontend Model

### 1. Split the product into two shells

#### Agency shell

This is the Sphere operations layer.

It should include:

1. Tenant directory
2. Onboarding queue
3. Portfolio health dashboard
4. Cross-tenant alerts
5. Work assignment queue
6. Billing or plan review
7. Audit investigation

This shell is where operators search for clients and choose where to go.

It is not where they should perform deep client edits.

#### Tenant workspace shell

This is the isolated client workspace.

It should include:

1. Tenant overview
2. Users
3. Agents
4. Knowledge base
5. Numbers
6. Providers
7. Calls
8. Audit trail
9. Settings

Every page in this shell must be explicitly scoped to one tenant.

Recommended route pattern:

1. `/agency/tenants`
2. `/agency/onboarding`
3. `/agency/portfolio`
4. `/workspace/[tenantId]/overview`
5. `/workspace/[tenantId]/users`
6. `/workspace/[tenantId]/agents`
7. `/workspace/[tenantId]/settings`

This is the single most important frontend isolation change.

## Frontend Isolation Rules

### Rule 1: No tenant editing from global list pages

Global pages can search, review, assign, and route.

Global pages should not allow direct editing of tenant-specific resources like:

1. Users
2. Providers
3. Agents
4. Knowledge-base settings
5. Webhooks

Instead, every primary action should route into the tenant workspace first.

Example:

1. Agency operator searches for `Acme Corporation`.
2. Clicks `Open Workspace`.
3. Lands in `/workspace/[tenantId]/overview`.
4. All edits now happen inside that workspace.

### Rule 2: Sticky tenant identity at the top of every workspace page

Every tenant-scoped screen should have a persistent header showing:

1. Tenant name
2. Tenant status
3. Plan
4. Tenant ID or short slug
5. Owner or assigned CSM/ops lead
6. Environment indicator if relevant

This banner should remain visible while editing.

The operator should never wonder which client they are acting on.

### Rule 3: Tenant switch is a deliberate transition, not a casual filter

At scale, tenant switching must be treated like context switching.

When switching tenant workspaces:

1. Clear tenant-scoped React Query caches.
2. Reset drafts tied to the previous tenant.
3. Abort in-flight requests from the previous tenant.
4. Close edit modals from the previous tenant.
5. Require confirmation if there are unsaved changes.

This prevents stale state and mixed-tenant UI bugs.

### Rule 4: Every mutation must render its tenant scope visibly

Every edit form and destructive action should show a scope block before submit:

1. Tenant
2. Resource type
3. Resource name
4. Environment
5. Last updated by
6. Current version

For destructive actions, add a confirmation step like:

`You are updating provider settings for Acme Corporation.`

This is not decoration. It is an operational safety mechanism.

## Safe Editing Model

### 1. Draft, review, apply

For high-risk changes, do not mutate immediately from inline controls.

Use a three-step flow:

1. Draft change
2. Review change summary
3. Apply change

Best candidates:

1. Provider changes
2. Agent publishing
3. Webhook updates
4. Knowledge-base sharing changes
5. User role changes

### 2. Versioned resources with stale-write protection

Frontend should always submit a version token or updated timestamp with edits.

If another operator changed the same resource:

1. Block the write
2. Show `This record changed while you were editing`
3. Show a diff between current and attempted changes
4. Let the operator reload or merge consciously

This is critical at agency scale because multiple operators will touch the same tenant.

### 3. No inline editing in dense lists for risky fields

Inline list editing is efficient but dangerous for agency operations.

Keep inline actions only for low-risk actions like:

1. View
2. Open workspace
3. Assign owner
4. Activate or deactivate with confirmation

Do not keep inline dropdown editing for sensitive fields at scale.

Instead, open a scoped edit panel or full page inside the tenant workspace.

## Onboarding Model For Hundreds Or Thousands Of Clients

Tenant creation should not be a one-shot modal.

It should become a structured onboarding flow.

### Recommended onboarding stages

1. Company profile
2. Workspace creation
3. Internal owner assignment
4. Client admin invitation
5. Provider setup
6. Phone number or channel assignment
7. Agent template selection
8. Knowledge-base upload
9. QA checklist
10. Go-live approval

### UI shape

Use a dedicated onboarding workspace:

1. `/agency/onboarding`
2. `/agency/onboarding/[tenantId]`

Each tenant should have:

1. Stage status
2. Blocking issues
3. Assigned operator
4. Due date
5. Last activity
6. Escalation notes

### Why this matters

At 1000 tenants, onboarding is not a CRUD problem. It is an operations pipeline problem.

The frontend should reflect that.

## Navigation And Information Architecture For 1000 Clients

### Replace the flat sidebar mental model

The current sidebar is still product-feature-first.

For agency scale, the top-level navigation should be operating-model-first.

Recommended top level:

1. Portfolio
2. Tenants
3. Onboarding
4. Alerts
5. Work Queue
6. Reporting
7. Settings

Inside a tenant workspace, use tenant-specific navigation:

1. Overview
2. Users
3. Agents
4. Knowledge Base
5. Calls
6. Phone Numbers
7. Providers
8. Audit
9. Workspace Settings

This is more scalable than repeating global feature lists for every use case.

### Add portfolio grouping

For 1000 tenants, a flat tenant list is weak.

Support grouping by:

1. Plan
2. Region
3. Industry
4. Assigned ops manager
5. Lifecycle stage
6. Health status

This lets agency operators work portfolios, not just records.

## Frontend State Isolation Requirements

This is the engineering contract the frontend should enforce.

### Route state

1. Tenant workspace pages must derive tenant from route, not optional filter state.
2. Tenant ID must be part of page identity.
3. Direct URL copy/paste must preserve scope safely.

### Query state

1. All query keys must include tenant ID for tenant-scoped resources.
2. Tenant switch must invalidate old tenant cache groups.
3. Global and tenant queries must never share cache keys.

### UI state

1. Modal state must be tenant-scoped.
2. Draft forms must be tenant-scoped.
3. Bulk selections must reset on tenant change.
4. Tabs and local storage keys must include tenant ID.

### Search state

1. Global search searches tenants and routes to workspaces.
2. Workspace search searches only within the active tenant.
3. Search boxes must label scope clearly.

## Error Containment And Operability

You said you do not want downtimes, and if something breaks you want to figure it out quickly.

The frontend should help with that too.

### 1. Error boundaries by workspace section

If users page fails, it should not crash the entire tenant workspace.

Each major panel should fail independently with:

1. Friendly fallback state
2. Request ID
3. Tenant ID
4. Retry button
5. Last successful sync time

### 2. Action traceability in the UI

After each mutation, surface:

1. Request ID
2. Actor
3. Tenant
4. Resource
5. Timestamp

Operators need enough information to report or investigate issues without digging through code.

### 3. Frontend telemetry tags

Every meaningful UI error should include:

1. Tenant ID
2. User ID
3. Route
4. Feature area
5. Action name
6. Correlation ID

Without that, multi-tenant debugging becomes expensive and slow.

## UX Safeguards To Prevent Cross-Client Mistakes

### Required safeguards

1. Workspace header with tenant identity
2. Explicit scope summary on all mutations
3. Unsaved-changes warning on workspace switch
4. Review screen for sensitive mutations
5. No risky inline edits from cross-tenant lists
6. Tenant-scoped drafts and cache reset on switch
7. Clear separation between agency pages and tenant pages

### Recommended safeguards

1. Tenant color chip or avatar in workspace header
2. `Currently working in: Tenant Name` sticky bar
3. Recent-work list for fast return without search confusion
4. Assigned-owner field on each tenant to reduce ownership ambiguity
5. Read-only mode for junior operators on sensitive areas

## Recommended Product Shape

If SphereVoice is truly intended for agency-scale internal use, the frontend should evolve into this structure:

### Agency layer

1. Portfolio dashboard
2. Tenant directory
3. Onboarding pipeline
4. Alert center
5. Work queue
6. Global reporting

### Tenant workspace layer

1. Overview
2. Setup progress
3. Users
4. Agents
5. Knowledge Base
6. Channels and numbers
7. Providers
8. Calls and live operations
9. Audit and change history
10. Workspace settings

## Phased Implementation Plan

### Phase 1: Frontend isolation foundation

1. Introduce agency routes and tenant workspace routes.
2. Move tenant-specific pages under `/workspace/[tenantId]/...`.
3. Add a persistent tenant identity header.
4. Make tenant switch clear cache, drafts, and modal state.
5. Remove risky edit actions from global list pages.

### Phase 2: Safe edit workflows

1. Convert sensitive edits to draft-review-apply flows.
2. Add stale-write protection and version conflict handling.
3. Add unsaved-change confirmation on workspace switch.
4. Show scope summaries on all mutations.

### Phase 3: Agency operating model

1. Build onboarding pipeline pages.
2. Add portfolio grouping and work assignment.
3. Add operational health summaries per tenant.
4. Add tenant ownership and responsibility metadata.

### Phase 4: Operability and scale

1. Add section-level error boundaries.
2. Add request ID and correlation ID surfacing in UI.
3. Improve audit UX for agency investigations.
4. Add browser smoke coverage for workspace switching and onboarding.

## Recommendation

The correct long-term direction is not `more tenant filters`.

The correct direction is `tenant workspaces with explicit context boundaries`.

If you want SphereVoice to work as a serious internal agency platform for 1000 clients, the frontend should be redesigned around these principles:

1. Global agency shell
2. Dedicated tenant workspace shell
3. Safe edit workflows
4. Tenant-scoped state and cache isolation
5. Structured onboarding pipeline
6. Strong traceability and failure containment

That is the frontend model that reduces operator mistakes, improves debugging, and scales operationally.