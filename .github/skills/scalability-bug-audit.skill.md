---
name: scalability-bug-audit
description: "Deep audit skill that finds scalability bottlenecks and latent bugs early in FastAPI + Next.js codebases. Scans database patterns, async pitfalls, N+1 queries, connection leaks, race conditions, memory leaks, and common production failure modes before they hit staging."
argument-hint: "Audit the agents module" or "Full scalability sweep"
---

# Scalability & Early Bug Detection Audit

You are a **senior reliability engineer** performing a deep audit of a FastAPI (Python) + Next.js (TypeScript) codebase. Your goal: find scalability bottlenecks and latent bugs **before they reach production**.

---

## When to Use This Skill

- Before merging a large feature branch
- After adding a new module or major endpoint
- Periodic health check on the entire codebase
- When investigating degraded performance or intermittent failures
- Pre-launch scalability review

---

## Step 1 — Scope the Audit

Determine what to audit based on the user's input:

| Input | Scope |
|---|---|
| Module name (e.g., "agents") | `backend/app/modules/<name>/` + related tests |
| "Full sweep" / "entire backend" | All modules + core + workers |
| "Frontend" | `frontend/src/modules/` + API layer |
| Specific file | That file + its callers/callees |
| No input | Ask: "Which module or area? Or should I do a full sweep?" |

---

## Step 2 — FastAPI / Python Backend Audit

Run through **every** checklist item. Report findings with severity (🔴 Critical, 🟠 High, 🟡 Medium, 🔵 Low) and the exact file + line.

### 2.1 — Database & SQLAlchemy

- [ ] **N+1 queries**: Look for loops that execute queries inside them. Check `selectinload()` / `joinedload()` usage on relationships.
- [ ] **Missing indexes**: Find `filter()` / `where()` clauses on columns without indexes, especially `tenant_id`, foreign keys, and columns used in `ORDER BY`.
- [ ] **Connection pool exhaustion**: Check `pool_size` and `max_overflow` vs expected concurrent connections. Look for sessions not being properly closed (missing `async with` or bare `await session.execute()` without cleanup).
- [ ] **Long-held transactions**: Find endpoints that hold a DB session open while doing external I/O (HTTP calls, file uploads, queue publishes). The session should be committed/closed before external calls.
- [ ] **Missing `await`**: Search for coroutine calls missing `await` — SQLAlchemy async is especially prone to this (silently returns a coroutine object instead of data).
- [ ] **Bulk operations**: Find loops doing individual `INSERT`/`UPDATE` that should use `bulk_insert_mappings()` or `insert().values([...])`.
- [ ] **Eager loading overkill**: Check for `joinedload()` on relationships that load huge collections when only a count or existence check is needed.
- [ ] **RLS bypass risk**: Verify every tenant-scoped query runs through the RLS-aware session. Look for raw `text()` queries or direct engine access that skip RLS `SET` context.
- [ ] **Migration safety**: Check Alembic migrations for `ALTER TABLE` on large tables without `CONCURRENTLY`, missing `NOT NULL` with defaults, or data migrations mixed with schema changes.

### 2.2 — Async & Concurrency

- [ ] **Sync in async**: Find blocking calls in async endpoints — `time.sleep()`, synchronous `requests`, `open()` file I/O, CPU-heavy computation without `run_in_executor()`.
- [ ] **Missing `await`**: Grep for common patterns: `session.execute(`, `session.commit(`, `session.refresh(`, `httpx.AsyncClient` calls — ensure all are awaited.
- [ ] **Event loop blocking**: Look for `asyncio.run()` called inside an already-running loop. Check for sync Redis clients where async (`redis.asyncio`) should be used.
- [ ] **Race conditions**: Find shared mutable state accessed from multiple async tasks without locks. Check singletons modified at runtime, global dicts/lists, class-level mutables.
- [ ] **Task cancellation safety**: Check `asyncio.Task` usage — are tasks properly awaited or cancelled on shutdown? Look for fire-and-forget `asyncio.create_task()` without error handling.
- [ ] **Concurrency limits**: Verify external API calls (LLM, STT, TTS) have semaphores or connection limits to prevent stampede under load.

### 2.3 — API Design & Validation

- [ ] **Unbounded list endpoints**: Find `GET` endpoints returning all rows without pagination (`limit`/`offset` or cursor). These will OOM at scale.
- [ ] **Missing response models**: Endpoints without `response_model` may leak internal fields (passwords, tokens, internal IDs).
- [ ] **Large payload ingestion**: Check `POST`/`PUT` endpoints for missing `Content-Length` limits or file upload size caps.
- [ ] **Slow serialization**: Find endpoints returning deeply nested models that could use `defer()` or select specific columns.
- [ ] **Missing rate limiting**: Public or auth endpoints without rate limiting (login, signup, webhook receivers).
- [ ] **Error response leaking internals**: Check exception handlers — do 500 errors expose stack traces or DB schema details?

### 2.4 — Celery / Background Tasks

- [ ] **Task idempotency**: Are tasks safe to retry? Look for tasks that create records without deduplication keys.
- [ ] **Missing `acks_late`**: Tasks doing external work should use `acks_late=True` so they re-run if the worker crashes.
- [ ] **Unbounded task queues**: Check for tasks that spawn more tasks in a loop without backpressure.
- [ ] **DB sessions in tasks**: Celery tasks should create their own sessions — never share FastAPI request sessions.
- [ ] **Result backend bloat**: If `result_backend` is configured, check that results have a TTL to avoid Redis/DB bloat.

### 2.5 — Memory & Resource Leaks

- [ ] **Unclosed clients**: Find `httpx.AsyncClient()`, `aiohttp.ClientSession()`, Redis connections, or WebSocket connections that aren't used as context managers.
- [ ] **Growing caches**: Check `@lru_cache` or in-memory dicts that grow without bounds. Verify `maxsize` is set.
- [ ] **File handle leaks**: Find file operations not using `async with aiofiles.open(...)` or `with open(...)`.
- [ ] **Streaming responses**: Large file downloads or audio streams should use `StreamingResponse` — not load entire content into memory.

### 2.6 — Security (Scalability-Adjacent)

- [ ] **JWT validation on every request**: Verify middleware validates JWT signature, expiration, and tenant claims — not just presence.
- [ ] **Query injection via `text()`**: Find raw SQL queries with f-string or `.format()` interpolation instead of parameterized queries.
- [ ] **SSRF via user-provided URLs**: Check webhook URLs, callback URLs, or any user-supplied URL that the server fetches. Validate against internal network ranges.
- [ ] **Tenant isolation gaps**: Search for queries that filter by `tenant_id` from user input instead of the JWT-derived tenant context.

---

## Step 3 — Next.js / TypeScript Frontend Audit

### 3.1 — Data Fetching & State

- [ ] **Missing error boundaries**: Pages/components that fetch data without `<ErrorBoundary>` or TanStack Query error handling.
- [ ] **Stale cache keys**: TanStack Query keys that don't include all dependencies (tenant, filters, pagination params).
- [ ] **Waterfall requests**: Sequential `useQuery()` calls that could be parallelized with `useQueries()`.
- [ ] **Overfetching**: API calls returning full entities when only a few fields are needed (no field selection or dedicated endpoints).
- [ ] **Missing `Suspense` boundaries**: Server components doing heavy data fetching without streaming/suspense.
- [ ] **Unbounded lists in client state**: Zustand stores or React state holding large arrays that grow without cleanup.

### 3.2 — Rendering & Performance

- [ ] **Missing `key` props**: Lists rendered without stable, unique keys (using array index on dynamic lists).
- [ ] **Re-render storms**: Components subscribing to entire Zustand store instead of selectors. Large context providers causing cascade re-renders.
- [ ] **Heavy client bundles**: Large libraries imported without dynamic `import()` or `next/dynamic`.
- [ ] **Images without optimization**: `<img>` tags instead of `next/image`. Missing `width`/`height` causing layout shift.
- [ ] **Missing `React.memo` / `useMemo`**: Expensive computations or component renders in hot paths without memoization.

### 3.3 — API Layer

- [ ] **No request deduplication**: Multiple components triggering the same API call without shared query keys.
- [ ] **Missing abort controllers**: Long-running requests (search, analytics) without `AbortController` on unmount.
- [ ] **Hardcoded API URLs**: API base URL not sourced from env vars, breaking across environments.
- [ ] **Auth token handling**: Token refresh race conditions — multiple concurrent 401s triggering multiple refresh attempts.

---

## Step 4 — Cross-Cutting Concerns

- [ ] **Logging gaps**: Critical operations (payments, tenant CRUD, auth events) without structured log entries.
- [ ] **Missing health checks**: Background workers, WebSocket handlers, or scheduled tasks without health/readiness probes.
- [ ] **No circuit breakers**: External service calls (LLM, STT, TTS, telephony) without timeout + retry + fallback patterns.
- [ ] **Telemetry blind spots**: Key transactions without OpenTelemetry spans (DB queries, external API calls, queue operations).
- [ ] **Docker resource limits**: Missing memory/CPU limits in `docker-compose.yml` or Kubernetes manifests.
- [ ] **Environment parity**: Config values that differ between dev and production without clear documentation.

---

## Step 5 — Generate Report

Produce a structured report with:

```markdown
# Scalability & Bug Audit Report — [Scope]

**Date:** [date]
**Auditor:** GitHub Copilot
**Scope:** [what was audited]

## Summary
- 🔴 Critical: [N] findings
- 🟠 High: [N] findings  
- 🟡 Medium: [N] findings
- 🔵 Low: [N] findings

## Critical Findings
### [Finding Title]
- **Severity:** 🔴 Critical
- **File:** `path/to/file.py` L42-L58
- **Issue:** [Concise description of the bug or bottleneck]
- **Impact:** [What breaks at scale or under what conditions]
- **Fix:** [Specific code change or pattern to apply]
- **Effort:** [S/M/L]

[Repeat for all findings, grouped by severity]

## Recommendations
1. [Prioritized action items]
2. ...

## Clean Areas
[List areas that passed all checks — this builds confidence]
```

---

## Step 6 — Quick Wins

After the report, identify the **top 3 quick wins** — fixes that are:
1. High impact on reliability or scalability
2. Low effort (< 30 min each)
3. Low risk of regression

Offer to implement them immediately.

---

## SphereVoice-Specific Checks

These apply to this codebase's unique architecture.

### Voice Pipeline (Pipecat / LiveKit)

- [ ] **Pipeline frame leak**: Check that Pipecat pipeline frames are consumed and not accumulating in queues. Look for unbounded `asyncio.Queue` between processors.
- [ ] **Transport cleanup on disconnect**: Verify `LiveKitTransport` is properly cleaned up when a call ends (participant leaves, timeout, error). Leaked transports hold WebRTC connections open.
- [ ] **Provider factory caching**: Does `PipecatProviderFactory` cache service instances per-call or globally? Global caching of stateful services (STT/TTS with open connections) causes cross-call contamination.
- [ ] **VAD sensitivity under load**: `SileroVADAnalyzer` runs inference on every audio frame — verify it's not blocking the pipeline's event loop. Should run in a thread/process pool if latency degrades under many concurrent calls.
- [ ] **Concurrent call limits**: Is there a semaphore or counter limiting how many simultaneous Pipecat pipelines can run? Without this, a spike in inbound calls can OOM the server.
- [ ] **Graceful call draining on deploy**: During rolling deployments, active calls must drain before the pod is killed. Check for SIGTERM handling that waits for active pipelines to finish.

### Multi-Tenancy / RLS

- [ ] **RLS context in background tasks**: Celery tasks and background `asyncio.Task` instances must set `tenant_id` in the DB session before queries. If they inherit the wrong context or none, data leaks across tenants.
- [ ] **Tenant context in WebSocket handlers**: WebSocket connections persist — verify tenant context is validated on connect AND on every message, not just at handshake.
- [ ] **Cross-tenant cache pollution**: Redis cache keys must include `tenant_id`. A cache key like `agent:{agent_id}` without tenant scoping can serve data to the wrong tenant if agent IDs overlap.

---

## Common FastAPI Scalability Anti-Patterns (Reference)

| Anti-Pattern | Why It Fails at Scale | Detection |
|---|---|---|
| Sync ORM in async endpoint | Blocks event loop, kills throughput | `grep -r "Session()" --include="*.py"` in async funcs |
| `SELECT *` without pagination | OOM on large tables | Endpoints returning `list[Model]` without `limit` param |
| Single DB session for request + background | Session closed before task runs | Tasks referencing request-scoped `db` |
| `@lru_cache` on DB-backed config | Stale data, growing memory | `@lru_cache` without `maxsize` or TTL |
| Fire-and-forget `create_task()` | Unhandled exceptions, task GC'd | `create_task` without `await` or callback |
| Global mutable state | Race conditions under concurrency | Module-level `dict`/`list` modified at runtime |
| Missing connection timeouts | Hung connections exhaust pool | `httpx`/`aiohttp` without `timeout=` |

---

## Example Prompts

- "Run a full scalability audit on the backend"
- "Audit the calls module for N+1 queries and connection leaks"
- "Check the frontend for re-render storms and overfetching"
- "Find all missing `await` in the pipeline module"
- "Pre-launch reliability audit — full sweep, backend + frontend"
