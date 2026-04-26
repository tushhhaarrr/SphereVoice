# SphereVoice — Branch Strategy

## Branch Structure

```
main ──────── production releases (protected, deploy to prod)
  │
  └── staging ── pre-production validation (protected, deploy to staging)
        │
        └── dev ── active development (protected, deploy to dev)
              │
              ├── feat/auth-jwt ──── feature branches (short-lived)
              ├── feat/agent-crud
              ├── fix/rls-policy
              └── chore/deps-update
```

## Rules

### Protected Branches

| Branch | Deploy To | Merge From | Merge Strategy | Required Reviews |
|--------|-----------|------------|----------------|------------------|
| `main` | Production | `staging` only | Squash merge | 2 approvals |
| `staging` | Staging | `dev` only | Squash merge | 1 approval |
| `dev` | Dev | Feature branches | Squash merge | 1 approval |

### Feature Branches

- **Naming:** `{type}/{scope}-{description}`
  - Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `perf`, `test`
  - Scope: module name (e.g., `auth`, `agents`, `pipeline`, `infra`)
  - Example: `feat/auth-jwt-middleware`, `fix/rls-cross-tenant-leak`
- **Branch from:** `dev`
- **Merge into:** `dev`
- **Strategy:** Squash merge (single commit per feature)
- **Lifetime:** ≤ 3 days (break large work into smaller PRs)

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Examples:**
```
feat(auth): add JWT middleware for API routes
fix(rls): prevent cross-tenant data leak in calls query
chore(deps): update fastapi to 0.115.0
docs(pipeline): add CallOrchestrator architecture diagram
test(providers): add encryption round-trip test
```

### Pull Request Process

1. Create feature branch from `dev`
2. Make changes, commit with conventional commits
3. Push and open PR against `dev`
4. CI runs: lint + test + build
5. At least 1 team member approves
6. Squash merge into `dev`
7. Delete the feature branch

### Release Process

1. When `dev` is stable and all phase gates pass:
2. Open PR: `dev` → `staging`
3. CI runs full test suite on staging config
4. 1 approval required, merge
5. Validate on staging for 24h
6. Open PR: `staging` → `main`
7. 2 approvals required, merge
8. Tag release: `v0.X.0`
9. CI deploys to production

### Hotfix Process

1. Branch from `main`: `fix/critical-issue`
2. Fix, test, PR → `main` (2 approvals)
3. Cherry-pick fix to `staging` and `dev`
