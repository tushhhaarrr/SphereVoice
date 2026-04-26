# ADR-001: Monorepo Structure (Turborepo)

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Full engineering team  
**Technical Story:** SphereVoice needs a repository strategy that supports backend (Python/FastAPI), frontend (Next.js), shared types, and infrastructure code in a coordinated development workflow.

---

## Context

SphereVoice is a full-stack platform with tightly coupled frontend and backend components, shared TypeScript type definitions, Terraform infrastructure code, and CI/CD pipelines. The team of 5 engineers needs to iterate quickly across the stack while maintaining consistency.

We evaluated three repository strategies:

1. **Monorepo with Turborepo** — Single `Sphere/SphereVoice` repository containing all code.
2. **Polyrepo** — Separate repositories for backend, frontend, infra.
3. **Monorepo with Nx** — Single repository with Nx build orchestration.

## Decision

**Use a monorepo managed by Turborepo** with the following workspace structure:

```
Sphere/SphereVoice/
├── backend/          # FastAPI modular monolith (Python 3.11)
├── frontend/         # Next.js 15 (App Router)
├── packages/
│   └── shared-types/ # Shared TypeScript type definitions
├── infra/
│   └── terraform/    # Azure IaC
├── docs/             # PRD, Tech PRD, ADRs, execution plan
├── docker-compose.yml
├── turbo.json        # Turborepo pipeline config
└── pnpm-workspace.yaml
```

**Package management:**
- Frontend + shared-types: `pnpm` (workspace protocol)
- Backend: `pip` + `requirements.txt` (pinned versions)

## Rationale

### Why Monorepo

| Factor | Monorepo | Polyrepo |
|--------|----------|----------|
| **Atomic changes** | One PR = full-stack change | Multiple PRs across repos, coordination overhead |
| **Shared types** | Direct workspace import | Publish package, version sync, npm registry |
| **CI/CD** | Single pipeline, affected-only builds | Separate pipelines, cross-repo triggers |
| **Code review** | Full context in one PR | Reviewers switch repos, lose context |
| **Onboarding** | Clone once, work everywhere | Clone N repos, configure each |
| **Refactoring** | Rename across stack in one commit | Breaking changes propagate slowly |

For a 5-person team building a tightly integrated platform, polyrepo coordination overhead is not justified.

### Why Turborepo over Nx

| Factor | Turborepo | Nx |
|--------|-----------|-----|
| **Complexity** | Minimal config (`turbo.json`) | Heavy config, plugins, generators |
| **Learning curve** | Hours | Days |
| **Cache** | Remote + local, just works | Similar, more configuration |
| **Python support** | Runs any shell command | JS/TS-centric, Python is second-class |
| **Maintenance** | Low — Vercel-backed, stable | Higher — frequent breaking changes |

Turborepo's simplicity fits our small team. We use it for build orchestration and caching, not for code generation or complex dependency graphs.

## Consequences

### Positive
- One `git clone` gives every engineer the full platform
- Frontend type changes propagate instantly to shared-types (no publish cycle)
- Single CI pipeline with Turborepo caching reduces build times
- PRs contain full-stack context for better reviews
- Docker Compose in root orchestrates the entire local dev environment

### Negative
- Repository size grows over time (mitigated by `.gitignore`, sparse checkout if needed)
- CI must handle both Python and Node.js toolchains
- Git history is shared — noisy for engineers working in one area (mitigated by `CODEOWNERS`)

### Risks
- **Risk:** Turborepo doesn't natively understand Python dependency graphs  
  **Mitigation:** Backend tasks in `turbo.json` use explicit `inputs` globs (`backend/**/*.py`) and cache outputs. Python dependency resolution handled by pip, not Turborepo.

## Related ADRs
- [ADR-011: Modular Monolith Backend](./ADR-011-modular-monolith.md)
