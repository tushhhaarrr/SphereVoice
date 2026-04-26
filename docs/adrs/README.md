# SphereVoice — Architecture Decision Records

This directory contains all Architecture Decision Records (ADRs) for the SphereVoice.

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](./ADR-001-monorepo-turborepo.md) | Monorepo Structure (Turborepo) | Accepted | 2026-03-04 |
| [ADR-002](./ADR-002-pipecat-fork-strategy.md) | Pipecat Package-First Strategy | Accepted | 2026-03-04 |
| [ADR-003](./ADR-003-dual-auth-strategy.md) | Auth.js v5 + FastAPI JWT Dual-Auth | Accepted | 2026-03-04 |
| [ADR-004](./ADR-004-postgresql-rls-tenant-isolation.md) | PostgreSQL RLS for Tenant Isolation | Accepted | 2026-03-04 |
| [ADR-005](./ADR-005-livekit-pipecat-split.md) | LiveKit for WebRTC/SIP, Pipecat for Pipeline | Accepted | 2026-03-04 |
| [ADR-006](./ADR-006-schema-first-api-design.md) | Schema-First API Design (OpenAPI 3.1) | Accepted | 2026-03-04 |
| [ADR-007](./ADR-007-feature-flags-env-vars.md) | Feature Flags via Environment Variables | Accepted | 2026-03-04 |
| [ADR-008](./ADR-008-terraform-iac.md) | Terraform for IaC, No ARM Templates | Accepted | 2026-03-04 |
| [ADR-011](./ADR-011-modular-monolith.md) | Modular Monolith Backend | Accepted | 2026-03-04 |

## ADR Template

When creating a new ADR, use this structure:

```markdown
# ADR-NNN: Title

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Date:** YYYY-MM-DD
**Deciders:** Names/roles
**Technical Story:** Brief context

## Context
What is the issue? What forces are at play?

## Decision
What did we decide? Include implementation details.

## Rationale
Why this option over alternatives? Include comparison table.

## Consequences
### Positive
### Negative
### Risks

## Related ADRs
```

## Numbering

- ADR-001 to ADR-010: Core architecture decisions (Phase 0B)
- ADR-011+: Domain-specific decisions added as they arise
- Gaps in numbering are intentional (reserved for future decisions)
