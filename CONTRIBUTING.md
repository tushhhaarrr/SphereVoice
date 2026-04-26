# Contributing to SphereVoice

## Getting Started

1. Clone the repo and enable git hooks:
   ```bash
   git clone <repo-url>
   cd SphereVoice-mono
   git config core.hooksPath .githooks
   ```

2. Set up local development:
   ```bash
   cp backend/.env.example backend/.env
   # Fill in the values (ask the team lead for dev API keys)

   # Start all services
   ./start.sh
   ```

3. Verify everything works:
   ```bash
   # Backend
   cd backend && ruff check . && mypy app/ && pytest

   # Frontend
   cd frontend && pnpm lint && pnpm type-check && pnpm build
   ```

## Branch Strategy

See [docs/branch-strategy.md](docs/branch-strategy.md) for full details.

**Quick summary:**
- Branch from `dev` → `feat/your-feature`
- Squash-merge back into `dev` via PR
- Never push directly to `dev`, `staging`, or `main`

**Naming:** `{type}/{scope}-{description}`
- `feat/agents-bulk-delete`
- `fix/pipeline-retry-crash`
- `chore/deps-update`

## Definition of Done

See [docs/definition-of-done.md](docs/definition-of-done.md). Every PR must meet this checklist before merge.

## Pull Requests

- Fill out the PR template completely
- CI must pass (lint, type-check, tests, Docker build)
- At least 1 approval required
- Keep PRs small (< 3 days of work)

## Local Dev Commands

| Task | Command |
|------|---------|
| Start everything | `./start.sh` |
| Backend lint | `cd backend && ruff check .` |
| Backend format | `cd backend && ruff format .` |
| Backend tests | `cd backend && pytest` |
| Backend types | `cd backend && mypy app/` |
| Frontend lint | `cd frontend && pnpm lint` |
| Frontend types | `cd frontend && pnpm type-check` |
| Frontend build | `cd frontend && pnpm build` |

## Environments

| Environment | URL | Branch | Auto-deploy |
|-------------|-----|--------|-------------|
| Dev | `console.dev.SphereVoice.Sphere.ai` | `dev` | Yes |
| Production | `console.SphereVoice.Sphere.ai` | `main` | Yes (with approval) |

## Security

- **Never** commit secrets, API keys, or passwords
- Use `.env` files locally (they are gitignored)
- pre-commit hooks will catch private keys automatically
- If you need a dev API key, ask — don't use production keys
