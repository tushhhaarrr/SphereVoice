# SphereVoice API — Execution Plan

**Document:** Phased Execution Plan — Platform API for External Integration Apps  
**Product:** SphereVoice API  
**Company:** Sphere AI  
**Version:** 2.0  
**Date:** March 31, 2026  
**First Consumer:** NanoVoice  
**Author:** SphereVoice Team

---

## 1. What This Is and Why

SphereVoice API is a service-to-service voice pipeline API that lets external applications run voice AI calls on SphereVoice infrastructure without touching SphereVoice's tenant, agent, or user systems. The first consumer is NanoVoice, but the architecture supports any number of future products and partner integrations using the same surface.

Every consumer registers as an **Integration App** — a first-class entity in the SphereVoice database with its own credentials, configurable rate limits, provider whitelist, and independent usage tracking. This is not a hacky internal endpoint. It is a versioned, production-grade API contract that external products depend on for their entire business.

### How It Differs from SphereVoice's Existing API

The existing SphereVoice API (`/api/v1/`) is built for logged-in dashboard users. It uses JWT sessions, loads agents from the database, stores call records with full PII (transcripts, recordings, CRM data), and enforces tenant isolation via PostgreSQL Row-Level Security. The Platform API (`/platform/v1/`) does none of that. It authenticates via app-level credentials (not user sessions), receives agent configuration inline with each call request (nothing stored), tracks pipeline executions in a lightweight table with no PII, and delivers transcripts via webhook rather than persisting them. There is no RLS, no tenant context, no post-call extraction, no CRM writeback. The two systems share the pipeline engine (VoicePipeline, provider factory, cost tracker) but nothing else.

### Architecture Overview

External apps authenticate with `X-App-Id` and `X-App-Secret` headers. Every request passes through a platform auth layer (separate from JWT auth) and a per-app rate limiter (Redis-backed). The router validates the request, resolves webhook URLs, and delegates to a new `handle_platform_call()` method on the existing `CallOrchestrator`. This method creates a `PipelineRun` record (not a `Call` record), builds a LiveKit room, constructs a `VoicePipeline` using the inline agent config, and starts the pipeline. When the call ends, a dedicated stop handler calculates costs, caches the full result in Redis (24-hour TTL), delivers it via webhook with retry and dead-letter fallback, and decrements the active call counter. The existing pipeline engine, provider factory, and cost calculation service are reused unchanged.

---

## 2. Data Isolation Rules

These rules are non-negotiable. Breaking any one of them is a P0 incident.

Platform calls must never create rows in the `calls` table. The `handle_platform_call()` method creates `PipelineRun` records only. Platform calls must never set RLS tenant context — there is no `SET LOCAL app.current_tenant_id` in the platform path. Transcripts must never be persisted in SphereVoice's PostgreSQL database. They are delivered to the consumer via webhook and cached in Redis with a 24-hour TTL for polling fallback. After 24 hours, the data is gone from SphereVoice's systems entirely. Recordings must not be stored permanently in SphereVoice's Azure Blob Storage. If the consumer requests recording, LiveKit Egress writes to a temporary Azure Blob (`recordings/platform/{run_id}.mp3`) which is re-uploaded to the consumer's pre-signed URL and then deleted. If no recording is requested, no audio is saved anywhere. The consumer's agent configuration (system prompt, tools, etc.) must not be stored in any SphereVoice table. Only a SHA-256 fingerprint of the first 500 characters is stored in `pipeline_runs.config_hash` for debugging. Platform pipeline errors must not cascade to SphereVoice tenant calls. Separate Redis counters, separate Prometheus metrics, and a per-app circuit breaker ensure isolation. Platform pipelines must not interfere with the call duration watchdog — they are stored in a separate dict or the watchdog explicitly skips `pf_` prefixed keys. Platform stop handlers must not publish to `EventBroadcaster`, must not enqueue `process_call.delay()`, and must not create `call_events` rows. The active call counter must always decrement when a call ends, even if the stop handler itself crashes. This is enforced via a `try/finally` block.

---

## 3. Phased Execution

### Phase 1 — Database Models and Migration

**Duration:** Day 1

**What to do.** Create a new `platform` module under `backend/app/modules/platform/` with an `__init__.py` and a `models.py`. Define three tables: `integration_apps`, `pipeline_runs`, and `webhook_dead_letters`. Generate an Alembic migration and run it.

**The `integration_apps` table** stores one row per registered external application. It holds the app's identity (name, slug, unique `app_id`), authentication (SHA-256 hash of the app secret, a display prefix), ownership metadata (internal vs partner, contact email), tier and limits (max concurrent calls, max calls per minute, max call duration, list of allowed STT/LLM/TTS providers, whether outbound is enabled), default webhook configuration, status flags, and aggregate usage counters (total calls, total duration, total cost in USD). The `app_id` column must be indexed for fast lookup during auth. The `app_secret_hash` is a SHA-256 hash — the raw secret is never stored.

**The `pipeline_runs` table** is a lightweight execution tracker. It stores the pipeline run's UUID, a foreign key to `integration_apps`, the consumer's `external_id` (their reference for this call), source name, status (connecting/running/completed/failed), a mode field (web or outbound), start and end timestamps, duration in seconds, per-category cost fields (stt, llm, tts, telephony, total — all `Numeric(12,8)`), error code and message fields, the LiveKit room name for debugging, a `webhook_delivered` boolean, and a `config_hash` string (SHA-256 fingerprint of the prompt, for debugging). This table explicitly does NOT contain: the system prompt, the transcript, the recording URL, any phone numbers, any user identity, or any other PII. It is a pipeline execution log, not a call record.

**The `webhook_dead_letters` table** stores failed webhook deliveries for later retry. It holds the pipeline run reference, the app reference, the event type, the payload (stored as plaintext JSON for V1 since NanoVoice is an internal consumer — the column is named `payload_encrypted` to signal that encryption must be retrofitted before any external partner onboarding), the target URL, attempt count, last error, and an expiry timestamp (7 days from creation, after which the row is purged).

**After creating the migration,** seed a NanoVoice integration app record. Generate a cryptographically random app secret, hash it, and store the hash. Print the raw secret exactly once for the operator to save. Set NanoVoice to the enterprise tier with 50 max concurrent calls, 30 calls/minute, 600-second max duration, and a broad provider whitelist. Outbound should be disabled initially.

**What NOT to do.** Do not modify any existing tables. Do not add columns to the `calls` table, the `tenants` table, or any other existing model. Do not add tenant_id to pipeline_runs — platform calls don't belong to a tenant. Do not create a foreign key from `pipeline_runs` to `calls` — they are completely separate domains.

**Verify by:** Running `alembic upgrade head` cleanly, confirming all three tables exist, querying the seeded NanoVoice app, and running the existing test suite to confirm nothing is broken.

---

### Phase 2 — Platform Authentication and Rate Limiting

**Duration:** Day 2

**What to do.** Create two new files in `backend/app/core/`: `platform_auth.py` and `platform_rate_limit.py`. These are FastAPI dependencies that will be injected into every platform endpoint.

**The auth dependency (`verify_platform_app`)** reads `X-App-Id` and `X-App-Secret` from request headers. If either is missing, return 401 immediately. Hash the provided secret with SHA-256 and look up the `integration_apps` table by `app_id`. If no row is found, return 401. If the app is deactivated, return 403. Compare the computed hash against the stored hash using `hmac.compare_digest` (constant-time comparison to prevent timing attacks). On success, return a frozen dataclass called `PlatformContext` containing the app's UUID, app_id string, name, slug, tier, all limit values, allowed providers list, outbound permission flag, and default webhook URL/secret. Also fire-and-forget an async task to update `last_used_at` on the app row — this must not block the request.

**The rate limiter (`enforce_rate_limit`)** depends on `verify_platform_app` (so auth always runs first) and checks two Redis-backed limits. First, a per-minute sliding window: increment a Redis key `platform:rpm:{app_id}:{minute_bucket}` and reject with 429 if it exceeds `max_calls_per_minute`. Set a 2-minute TTL on first increment to auto-expire. Second, a concurrent call count: read `platform:active:{app_id}` and reject with 429 if it meets or exceeds `max_concurrent`. The 429 responses must include a `Retry-After` header and a structured JSON body with the error code, message, and relevant limits.

**What NOT to do.** Do not modify `core/dependencies.py` or `core/security.py`. The existing JWT auth system is untouched. Do not use the same `HTTPBearer` scheme — platform auth uses custom headers, not Bearer tokens. Do not store rate limit state in PostgreSQL — Redis is the only acceptable backend for this. Do not implement IP-based rate limiting — all limits are per-app.

**Consider:** The `PlatformContext` dataclass should be frozen (immutable) to prevent accidental mutation during request processing. The auth lookup runs on every request, so it should be fast — the `app_id` column must be indexed (done in Phase 1). If you ever add caching for the app lookup, use a very short TTL (30 seconds max) so that deactivation takes effect quickly.

**Verify by:** Writing unit tests for the auth dependency with valid credentials, invalid secret, missing headers, and deactivated app. Confirm rate limit Redis keys are created and expire correctly.

---

### Phase 3 — Platform Router and Schemas

**Duration:** Day 2–3

**What to do.** Create `schemas.py` and `router.py` in the platform module. Define all request/response schemas as Pydantic models. Build all six endpoints with validation and auth wired in, but without orchestrator logic yet (the actual call start comes in Phase 4).

**The schemas** must be self-contained. Do not import from SphereVoice's existing agent or call schemas to avoid coupling. The main request schema (`PlatformCallRequest`) accepts:

- `external_id` (consumer's reference, max 100 chars)
- `mode` (web or outbound)
- `system_prompt` (max 50,000 chars)
- `first_message` (optional greeting text the agent speaks immediately)
- `language` (BCP-47 code like `en-US`, `hi-IN`, `ta-IN`, `multilingual` — defaults to `en-US`. This is critical: the factory uses it to resolve STT language codes, select TTS models (Sarvam for Hindi, Smallest for multilingual), and append language instructions to the system prompt. Without this field, all platform calls would be forced English-only.)
- `voice` (voice_id for TTS — e.g., an ElevenLabs voice ID)
- `llm_model` (e.g., `gpt-4o-mini`, `gpt-4o`)
- `llm_temperature` (optional, float 0.0–2.0, default 0.7)
- `llm_max_tokens` (optional, int, default 300 — controls max response length per turn)
- `stt_provider` (e.g., `deepgram`, `groq_whisper`, `soniox`)
- `stt_model` (optional, e.g., `nova-2`, `whisper-large-v3-turbo` — provider-specific model name. If omitted, the factory's default for the chosen provider is used. Passed through to `config.settings.transcription.sttModel`.)
- `tts_provider` (e.g., `elevenlabs`, `openai_tts`, `cartesia`)
- `tts_model` (optional, e.g., `eleven_turbo_v2_5`, `tts-1` — provider-specific model override. Passed through to `config.settings.voiceLanguage.ttsModel`.)
- `responsiveness` (optional, float 0.0–1.0, default 0.5 — controls how aggressively the agent can be interrupted mid-speech. Maps to `config.settings.speech.responsiveness`.)
- `end_on_silence_seconds` (optional, int, default 30 — hang up after this many seconds of silence)
- `tools` (list of OpenAI function-calling dicts, max 10)
- `max_duration_seconds` (optional, capped to app tier)
- `context_documents` (up to 5 RAG context strings)
- `dynamic_variables` (key-value pairs for prompt template injection)
- `webhook_url` and `webhook_secret` (fall back to app defaults)
- `recording_upload_url` (optional pre-signed Azure Blob PUT URL — see Recording section in Phase 4)
- outbound-specific `to_number`/`from_number`

**The six endpoints are:**

1. `POST /platform/v1/calls` — Start a pipeline call. Depends on `enforce_rate_limit`. Validates provider whitelist (reject with 403 if consumer requests a provider their tier doesn't allow). Validates outbound permission. Enforces duration cap (min of request value and app tier limit). Resolves webhook URL from request or app default (reject 422 if neither exists). Checks idempotency: same `external_id` from same app within 5 minutes returns the cached response from Redis without starting a new call. This prevents the number one production issue — a consumer retry spawning duplicate pipelines.

2. `GET /platform/v1/calls/{id}` — Get status and cost breakdown. Reads from `pipeline_runs` table. Verifies the run belongs to the requesting app (prevents cross-app data access). Does NOT return the transcript — that's only available via webhook or the polling endpoint.

3. `GET /platform/v1/calls/{id}/result` — Polling fallback. Returns the full result including transcript from Redis cache. Available for 24 hours after call completion. Verifies app ownership. Returns 404 if expired or not found.

4. `POST /platform/v1/calls/{id}/stop` — Force-stop a running call. Verifies ownership, delegates to orchestrator. Returns 202 Accepted.

5. `GET /platform/v1/health` — Returns the app's current capacity (active calls vs max), available headroom, and LiveKit connectivity status. Useful for consumers to check before sending calls. **The LiveKit connectivity check must be cached** — a synchronous LiveKit API call adds 200-500ms latency. Cache the LiveKit status in Redis with a 30-second TTL (`platform:livekit_health`). The health endpoint reads from cache and returns stale-but-fast results. A background task (or the first cache miss) refreshes it.

6. `GET /platform/v1/usage` — Returns the app's aggregate usage stats: total calls, total duration, total cost, and current active call count.

**CORS configuration.** If NanoVoice's browser-side JavaScript ever needs to call platform endpoints directly (e.g., polling `GET /platform/v1/calls/{id}/result` while the user waits), CORS headers are needed. For v1, all platform API calls are expected to go through NanoVoice's backend (server-to-server), so CORS is NOT configured on `/platform/` endpoints. This is a deliberate security decision — browser-side access would expose the `X-App-Secret` in client JavaScript. If a future consumer needs browser-side access, implement a separate token-exchange endpoint that returns a short-lived, scoped JWT for specific operations (not the app secret). Do NOT add `Access-Control-Allow-Origin: *` to platform endpoints.

**Register the router** in `main.py` with `app.include_router(platform_router)` — note that the router defines its own `/platform/v1/` prefix, so do NOT add the `API_V1` prefix here. Place it after the existing router registrations.

**What NOT to do.** Do not use the same prefix as SphereVoice's internal API (`/api/v1/`). Do not share Pydantic schemas with existing modules. Do not expose the transcript in the status endpoint — it goes through webhooks only. Do not allow calls without a webhook URL and secret — the consumer MUST receive the result somehow.

**Consider:** The idempotency cache key includes both the `app_id` and the `external_id`, so different apps can use the same external_id without collision. The 5-minute TTL is short enough that a consumer can retry after a genuine failure but long enough to catch accidental double-submits. When an idempotency hit occurs and the first call is still running, return the original `pipeline_run_id` with status `"running"` — do NOT return a completed result (it doesn't exist yet). The consumer checks the call status via `GET /platform/v1/calls/{id}` to know when it finishes. When the first call has already completed and the cached result exists in Redis, return the cached result directly. The idempotency cache stores the `pipeline_run_id` as the value, not the full response — the response is reconstructed from the `pipeline_runs` table or Redis result cache depending on status.

**Verify by:** Hitting each endpoint with valid auth and confirming proper validation responses. Test provider whitelist rejection, outbound mode rejection, missing webhook rejection, and idempotency cache hit.

---

### Phase 4 — Orchestrator: `handle_platform_call()`

**Duration:** Day 3–5

This is the most complex and critical phase. It adds the actual voice pipeline lifecycle for platform calls.

**What to do.** Add three new methods to the existing `CallOrchestrator` class in `orchestrator.py`:

1. **`handle_platform_call()`** — the main entry point, called by the router
2. **`_make_platform_stop_handler()`** — a static method that builds the on-stop callback
3. **`handle_platform_call_end()`** — for force-stopping from the API

**The `handle_platform_call()` method** follows the same structural pattern as the existing `handle_test_call()` (line 406 in orchestrator.py) but diverges in critical ways. The method receives the `PlatformContext`, the `PlatformCallRequest`, the resolved max duration, and the resolved webhook URL and secret. It proceeds as follows:

First, increment the app's active call counter in Redis. This must happen early so that the concurrency limit is respected even during slow pipeline construction. If anything fails after this point, the counter must be decremented in an exception handler.

Second, create a `PipelineRun` record in the database. Not a `Call` record — never a `Call` record. The run stores the app_id, external_id, status "connecting", the current timestamp, the config hash, and the mode.

Third, create a LiveKit room with a `pf_` prefix on the name (e.g., `pf_abc123def456`). This prefix prevents key collisions with SphereVoice's existing rooms which use `call_`, `test_`, and `SphereVoice-outbound-` prefixes.

Fourth, build a virtual agent object. This is the most fragile and critical step. The existing `VoicePipeline` accesses the agent object via `getattr(self.agent, attr, default)` — so any `SimpleNamespace` that provides the right attributes will work. But the agent also has a deeply nested `config` dict that the pipeline reads via `config.get("settings", {}).get(...)`. This means `config` must be a real Python dict with the correct nested structure, not a SimpleNamespace.

**Resolving the consumer's provider choice into provider_key UUIDs.** The consumer specifies providers by name string (e.g., `stt_provider="soniox"`, `tts_provider="cartesia"`). The factory resolves providers by `provider_key.id` UUID when the agent has a non-null `stt_provider_id` / `tts_provider_id`. To honor the consumer's choice, look up the provider_key row before building the SimpleNamespace: `SELECT id FROM provider_keys WHERE provider_name = :name AND provider_category = :cat AND is_active = True ORDER BY is_default DESC LIMIT 1`. Set the returned UUID as `stt_provider_id` / `tts_provider_id` on the virtual agent. If no matching row exists, return 422 with `validation_invalid_provider` and include the requested provider name in the error details. If the consumer omits the field, leave the ID as `None` — the factory will fall through to the global default. For `llm_provider_id`, leave it as `None` — the LLM provider is determined by the `llm_model` string (e.g., `gpt-4o-mini` → OpenAI, `llama-3.3-70b` → Groq), not by a provider_key row. The provider whitelist validation (Phase 3) must still run BEFORE this lookup to catch disallowed providers early with a 403.

**Complete attribute list for the virtual agent SimpleNamespace** (verified by auditing every `getattr(self.agent, ...)` in `voice_pipeline.py` and `factory.py`):

| Attribute | Source from PlatformCallRequest | Default if omitted |
|-----------|--------------------------------|-------------------|
| `id` | Generate a UUID (same as pipeline_run_id is fine) | Required |
| `name` | `f"platform_{app_context.slug}"` | `""` |
| `type` | Always `"single_prompt"` | `"single_prompt"` |
| `tenant_id` | Always `None` — platform calls have no tenant | `None` |
| `language` | `request.language` | `"en-US"` |
| `voice_id` | `request.voice` | `None` (factory default) |
| `llm_model` | `request.llm_model` | `None` (factory default) |
| `llm_max_tokens` | `request.llm_max_tokens` | `300` |
| `llm_temperature` | `request.llm_temperature` | `0.7` |
| `stt_provider_id` | Resolved from `request.stt_provider` — look up the `provider_keys` row by name+category, use its UUID. `None` if consumer omits (factory uses global default). | `None` |
| `llm_provider_id` | Always `None` — LLM provider is determined by `llm_model` string, not a provider_key row | `None` |
| `tts_provider_id` | Resolved from `request.tts_provider` — same lookup as STT. `None` if consumer omits. | `None` |
| `max_call_duration_seconds` | `resolved_max_duration` | `600` |
| `ring_duration_seconds` | `0` — no ring for web calls | `0` |
| `end_on_silence_seconds` | `request.end_on_silence_seconds` | `30` |

**The `config` dict** must follow this exact nested structure. The pipeline reads it via `config.get(key)` and `config.get("settings", {}).get(sub, {}).get(leaf)`:

```
config = {
    "prompt": request.system_prompt,       # The system prompt template
    "system_prompt": request.system_prompt, # Some paths read this key instead
    "welcome_message": request.first_message or "",
    "variables": [],                        # No template variables for platform calls
                                           # (dynamic_variables are pre-resolved into the prompt)
    "functions": request.tools or [],       # OpenAI function-calling dicts
    "max_call_duration_seconds": resolved_max_duration,
    "end_on_silence_seconds": request.end_on_silence_seconds or 30,
    "ring_duration_seconds": 0,
    "settings": {
        "speech": {
            "responsiveness": request.responsiveness or 0.5,
            "latencyTuning": {
                "minIdleTimeToAffordEndpointing": None,
                "noInputTimeout": None,
            },
        },
        "transcription": {
            "sttModel": request.stt_model or "",       # e.g., "nova-2"
            "optimizeFor": "",
            "boostedKeywords": [],
            "vocabularySpecialization": None,
            "denoisingMode": None,
        },
        "voiceLanguage": {
            "ttsModel": request.tts_model or "",       # e.g., "eleven_turbo_v2_5"
            "voiceVolume": None,
        },
        "backgroundSound": None,
        "webhooks": {
            "enabled": False,  # Platform uses its own webhook system
            "timeoutMs": None,
            "retryCount": None,
        },
    },
}
```

**Dynamic variables must be resolved before building the config.** The `PlatformCallRequest.dynamic_variables` dict (e.g., `{"customer_name": "Priya", "deal_value": "$5,000"}`) must be applied to `system_prompt` via string replacement BEFORE setting `config["prompt"]`. Replace every `{{key}}` pattern in the prompt with the corresponding value. Reject any variable value that itself contains `{{` (template injection — see Security section). After resolution, `config["variables"]` stays empty because there are no unresolved placeholders left.

**IMPORTANT: Pass `dynamic_variables=None` to the VoicePipeline constructor.** The pipeline has two independent variable systems: (1) `config["variables"]` resolved via `resolve_variables()` in `_build_system_prompt()` using `{{placeholder}}` template syntax, and (2) the `dynamic_variables` constructor parameter, which `_append_caller_context()` injects as a "CALLER INFORMATION" block appended to the prompt. If you pre-resolve variables into the prompt AND also pass them as `dynamic_variables`, the pipeline will double-inject them — the prompt already contains "Priya" where `{{customer_name}}` was, and then the pipeline appends "CALLER INFORMATION: Customer Name: Priya" at the end. Pass `dynamic_variables=None` (or empty dict) to avoid this. The `dynamic_variables` parameter is designed for SphereVoice's CRM enrichment path (where the orchestrator injects caller data from Zoho/HubSpot), not for platform calls where all variables are pre-resolved.

**Wiring the `CostTrackingObserver`.** The existing pipeline uses a `CostTrackingObserver` (a Pipecat `FrameProcessor` subclass) that intercepts `MetricsFrame` events during the call to feed real-time LLM token counts and TTS character counts to the `CallCostTracker`. Without this observer, cost tracking falls back to `estimate_from_transcript()` which guesses tokens as chars/4 — significantly less accurate. Wire the observer into platform pipelines the same way `handle_test_call()` does. The observer is constructed with a reference to the `CallCostTracker` instance and added to the pipeline's processor chain.

Fifth, resolve STT, LLM, and TTS services using the existing `PipecatProviderFactory`. The factory's `get_stt()`, `get_llm()`, and `get_tts()` methods accept the agent object and a database session. They resolve the provider key by checking: (1) agent-level override (null for platform → skip), (2) **global default provider_keys in the database** (`is_default=True`, no tenant filter applied when `tenant_id` is None), then (3) env var fallback (only if no DB default exists and `_provider_env_fallback_enabled()` returns True). Since the virtual agent has all provider IDs set to None and tenant_id set to None, the factory will use whichever shared `provider_keys` rows are marked as `is_default=True` in the database. In the typical SphereVoice deployment, these are the org-level shared provider keys created by the seed script. Make sure these global default provider_keys have valid API credentials for all providers in the platform whitelist. Env vars like `OPENAI_API_KEY` are only reached if no matching DB row exists.

Sixth, create a `CallCostTracker`. Call `PipecatProviderFactory.resolve_provider_info(stt_service, llm_service, tts_service)` — this is a `@staticmethod` on `PipecatProviderFactory`, NOT on `CallCostTracker`. It returns a dict with `stt`, `llm`, `tts` keys each containing `provider` and `model` strings. Pass these to the `CallCostTracker` constructor with `telephony_provider="livekit"` (platform web calls use LiveKit directly with zero telephony cost, same as test calls).

Seventh, generate the agent's LiveKit access token and build the `VoicePipeline`. Pass the platform-specific stop handler (built by `_make_platform_stop_handler`) as the `on_stop` callback. Pass the existing `_make_pipeline_error_handler` as `on_error` (error handling is the same). Set `dry_run=True` so that any tool execution during the call (tenant tools or custom webhook tools) is flagged as a dry run, preventing side-effects like CRM writes. CRM enrichment is already skipped for platform calls because the virtual agent has `tenant_id=None` — the orchestrator's CRM lookup path is gated by tenant_id and will not fire.

**Wiring `context_documents` to `kb_context`.** The request schema accepts `context_documents` (up to 5 RAG context strings). Join them into a single string separated by `"\n---\n"` (e.g., `"\n---\n".join(request.context_documents)`) and pass the result as the `kb_context` parameter to VoicePipeline. The pipeline appends this text to the system prompt, giving the LLM reference material. Do NOT call `_build_rag_processor()` — platform agents have no knowledge_base records in the database. Pass `kb_processor=None`.

Eighth, store the pipeline in the global `_active_pipelines` dict with a `pf_` prefix key. Start the pipeline. Do NOT call `start_recording()` — platform web calls do not use LiveKit Egress recording to Azure Blob (see Recording section below). Generate a caller token and return the response with LiveKit credentials.

**Caller token identity.** The existing `_create_caller_token(room_name, user_id)` uses `f"caller_{user_id}"` as the LiveKit identity. Platform calls have no `user_id`. Use `f"caller_{external_id}"` as the identity — this is the consumer's reference and is unique per call. If `external_id` is missing or too long, generate a random UUID.

**Caller token TTL.** The existing `_create_caller_token` does not set an expiry. Platform caller tokens MUST have a TTL. Call `.with_ttl(timedelta(seconds=max_duration_seconds + 60))` on the `AccessToken` builder (this is new behavior specific to platform calls). This prevents a consumer from holding onto a token after the call ends and attempting to rejoin the room.

**Recording for platform calls.** The existing recording system uses LiveKit Egress → Azure Blob Storage. LiveKit Egress requires an S3-compatible or GCS destination configured at the LiveKit server level — it cannot stream to an arbitrary pre-signed PUT URL. Therefore, platform call recording works as follows: if the consumer provides a `recording_upload_url`, SphereVoice starts a LiveKit Egress recording to a temporary Azure Blob path (`recordings/platform/{run_id}.mp3`). When the call ends, the stop handler downloads the MP3 from Azure Blob and re-uploads it to the consumer's pre-signed URL via an HTTP PUT, then deletes the temporary Azure Blob. If the re-upload fails, the temporary blob is kept for 24 hours (matching the result cache TTL) and the consumer can retry via polling. If no `recording_upload_url` is provided, no recording is created at all. This two-step approach is necessary because LiveKit Egress cannot target arbitrary URLs.

**The `_make_platform_stop_handler()` static method** builds a closure that runs when the pipeline stops (silence timeout, max duration, manual stop, etc.). This is where the critical differences from SphereVoice's existing stop handler live. Every difference is listed here because missing one causes data leakage or cross-contamination.

It pops the pipeline from `_active_pipelines` (using the `pf_` prefixed key) and extracts the transcript. It calculates duration and costs using the same `PricingService.calculate_costs()` that SphereVoice uses. It updates the `PipelineRun` row (not a `Call` row) with status "completed", timing, and cost fields. It atomically increments the app's usage counters (total_calls, total_duration, total_cost) on the `IntegrationApp` row. If recording was started (consumer provided `recording_upload_url`), it calls `stop_recording(run_id)` to finalize the LiveKit Egress, then spawns a background task to download from Azure Blob and re-upload to the consumer's URL. If no recording was started, skip this entirely. It builds a result payload containing the call_id, external_id, app_id, status, duration, transcript, cost breakdown, and disconnection reason. It caches this payload in Redis with a 24-hour TTL under the key `platform:result:{run_id}`. It dispatches the webhook as a **fire-and-forget background task** using `asyncio.create_task()` — the webhook dispatcher runs independently after the stop handler returns (see Phase 5 fix below). And in a `finally` block — always, regardless of whether any of the above crashed — it decrements the active call counter and clamps it to zero to prevent negative drift.

**What the platform stop handler must NOT do (that the existing SphereVoice stop handler does):**

- Must NOT call `process_call.delay()` — that's SphereVoice's Celery task for post-call extraction, CRM writeback, and tenant webhook delivery. Platform calls have none of that.
- Must NOT publish to `EventBroadcaster` — that powers the SphereVoice frontend's real-time call list updates. No SphereVoice frontend user is watching platform calls.
- Must NOT call `stop_recording(call_id)` using the Call model's `call_id` — platform recording uses `run_id` as the key in `_active_recorders`, not a Call UUID.
- Must NOT create a `call_ended` event in the `call_events` table — platform calls have no `Call` record to reference.
- Must NOT update any Prometheus metrics that use `tenant_id` as a label with a None value — use the platform-specific metrics (Phase 6) labeled by `app_id` instead.

**The `handle_platform_call_end()` method** looks up the pipeline in `_active_pipelines` by `pf_{run_id}` key and calls `pipeline.stop("manual_stop")`. The existing VoicePipeline stop mechanism will then trigger the platform stop handler.

**What NOT to do.** Do not create a `Call` record anywhere in this flow. Do not set RLS context. Do not call `deliver_agent_webhook()` (that's SphereVoice's tenant webhook system). Do not enqueue `process_call.delay()` (that's SphereVoice's post-call extraction/CRM pipeline). Do not publish to `EventBroadcaster` (that's SphereVoice's frontend real-time update system — platform calls have no frontend). Do not call `start_recording()` with SphereVoice's default Azure Blob egress path — if recording is needed, use the platform-specific temp path `recordings/platform/{run_id}.mp3`. Do not modify the existing `_make_pipeline_stop_handler()` — the platform has its own. Do not modify `VoicePipeline` itself — the virtual agent namespace and config dict must satisfy its existing interface. Do not pass `tenant_id` to any Prometheus metric labels — use dedicated platform metrics labeled by `app_id`.

**Consider:** The `SimpleNamespace` virtual agent is the single biggest risk in this phase. One missing attribute means a runtime `AttributeError` that kills the call. Before writing the implementation, exhaustively audit every place `voice_pipeline.py`, `factory.py`, `variable_resolver.py`, and `flow_engine.py` access agent attributes. Build the namespace with all of them. When in doubt, add the attribute with a safe default (None, empty string, empty list). Also consider that the error handler (`_make_pipeline_error_handler`) references `tenant_id` for Prometheus labels — pass None for platform calls and ensure the metric label handler tolerates None or "unknown".

**Consider: Tool execution — two paths exist in the pipeline.** The consumer can pass up to 10 tool definitions as OpenAI function-calling dicts. These are placed in `config["functions"]` and registered via `_make_custom_function_handler()`. That handler checks each tool dict for a `webhook_url` field. If present, **the pipeline makes a real HTTP call** to that URL during the live call (via httpx, 10-second timeout) and feeds the response back to the LLM. If no `webhook_url` is present, the handler returns a generic `{"status": "completed"}` — the LLM believes it executed but nothing actually happened.

**For platform V1, strip `webhook_url` from all consumer-supplied tool dicts before building the config.** This prevents two problems: (a) **SSRF** — a malicious consumer could set `webhook_url` to an internal IP/cloud metadata endpoint and SphereVoice would make the request from its own network, and (b) **unexpected execution** — consumers unfamiliar with the webhook_url field might accidentally trigger real HTTP calls. With webhook_url stripped, tool calls become LLM-only structured output: the LLM "calls" the function, the pipeline returns a fake success, and the full tool call + arguments appear in the transcript delivered via webhook. The consumer handles tool calls on their end after the call.

Separately, the pipeline also has a `_register_tenant_tool_handlers()` path that loads tools from the `TenantTool` database table and executes them via `ToolExecutor` (Google Sheets, Calendar, CRM writes). This path is gated by `if _agent_id and _tenant_id` — since the platform virtual agent has `tenant_id=None`, this code path is **safely skipped** for platform calls, no extra guarding needed.

If a future version needs real-time tool execution for platform consumers, it must: validate the webhook_url with the same SSRF checks applied to `recording_upload_url` and `webhook_url` (private IP rejection, HTTPS enforcement), enforce a per-call tool execution count limit, and never use the existing `ToolExecutor` which has service-account access to Google Sheets, calendars, and CRM.

**Consider: LiveKit token scoping.** The caller token generated for platform calls must have minimal permissions: join the room, subscribe to the agent's audio, publish audio (so the user can speak to the agent). It must NOT have admin permissions (kick participants, delete room, start recordings). The token's `room` claim must be locked to the specific `pf_` room for this call — a consumer cannot reuse a token to join a different room. Set the token expiry to `max_duration_seconds + 60` (the call duration cap plus a small buffer) so tokens auto-expire even if the call ends abnormally.

**Consider:** The active call counter increment-then-try pattern means that if the pipeline construction fails (bad provider, LiveKit down, etc.), you MUST decrement in the except block. But the stop handler also decrements. So a successful start followed by a normal stop results in exactly one decrement (from the stop handler). A failed start results in exactly one decrement (from the except block). There is no double-decrement in the normal case. However, if the server crashes between increment and pipeline start, the counter will be off by 1 — this is handled by the startup cleanup in Phase 6.

**Verify by:** Starting an actual web call through the platform API in the development environment. Join the LiveKit room from a browser. Speak to the agent. End the call. Confirm: pipeline_runs row has status=completed with correct cost, Redis has the cached result, webhook was delivered (use a RequestBin or similar), no calls table rows were created, active counter is back to 0.

---

### Phase 5 — Webhook Dispatcher

**Duration:** Day 4–5

**What to do.** Create `webhook_dispatcher.py` in the platform module. This is a standalone async function that delivers webhooks with guaranteed delivery semantics: retry, signing, idempotency keys, and dead-letter fallback.

The dispatcher takes the target URL, the HMAC signing secret, the event type, the JSON payload, the pipeline run ID, and the app's UUID. It serializes the payload to a compact JSON string and computes an HMAC-SHA256 signature using the consumer's webhook secret. Every delivery attempt includes these headers: `Content-Type: application/json`, `X-Webhook-Signature: sha256={hex_digest}` (so the consumer can verify authenticity), `X-Webhook-Event` (the event type, e.g., "call.ended"), `X-Webhook-Id` (a unique UUID for idempotency — the consumer can deduplicate by this), `X-Webhook-Timestamp` (ISO 8601, for replay attack detection), and `User-Agent: SphereVoice-Platform-Webhook/1.0`.

The retry strategy uses five attempts with exponential backoff: 1 second, 5 seconds, 30 seconds, 2 minutes, 10 minutes. On each attempt, if the consumer returns a 2xx status, the delivery is considered successful and the `pipeline_runs.webhook_delivered` flag is set to true. If the consumer returns a 4xx status, no retry is attempted — this is a client-side error (bad endpoint, auth rejection, etc.) and retrying won't help. If the consumer returns a 5xx status or the connection times out, the next retry fires after the backoff delay.

If all five attempts are exhausted, the payload is stored in the `webhook_dead_letters` table with the pipeline run reference, the encrypted payload, the target URL, the attempt count, and an expiration timestamp 7 days in the future. A future Celery beat task (not in scope for this plan) will retry dead letters periodically.

**What NOT to do.** Do not reuse SphereVoice's existing `webhook_delivery.py` or `WebhookDelivery` model. That system is designed for SphereVoice agent webhooks with tenant context, call_id references, and different retry semantics. The platform webhook dispatcher is a separate system. Do not log the full payload (it contains transcripts, which are PII). Log the pipeline_run_id, event type, attempt number, and HTTP status only.

**CRITICAL: The webhook dispatcher must never block the stop handler.** The retry schedule totals up to ~13 minutes (1s + 5s + 30s + 2m + 10m). If the consumer is down, the stop handler would hold a database session open for 13 minutes — this is unacceptable. The stop handler calls `asyncio.create_task(dispatch_platform_webhook(...))` and returns immediately. The dispatch function runs independently in the background. All database work in the stop handler (updating pipeline_run, incrementing counters, caching to Redis) completes BEFORE the webhook is dispatched. The dispatch function opens its own database session only for the dead-letter write if all retries fail. This means: if the server crashes during webhook delivery, the pipeline_run row is already correct (status=completed, costs saved) — only the webhook delivery is lost, and the consumer can poll for results.

**Consider:** The consumer must be able to verify the webhook signature. Document the verification algorithm clearly: compute `hmac.new(webhook_secret.encode(), raw_body_bytes, sha256).hexdigest()` and compare to the signature after stripping the `sha256=` prefix. The body must be the exact byte sequence that was signed — no re-serialization. This is why the dispatcher signs the serialized string and sends that exact string as the body.

**Consider:** The dead letter payload contains the transcript (PII). The `payload_encrypted` column name is intentionally forward-looking. For the V1 launch (where the only consumer is NanoVoice, which is also you), store the payload as plaintext JSON in this column — the column name signals intent, not current implementation. Before onboarding any external partner, retrofit AES-256-GCM encryption using the same `EncryptionService` that SphereVoice uses for CRM OAuth tokens. This is a hard requirement in the operational readiness checklist for partner onboarding, not for the NanoVoice launch.

**Verify by:** Unit testing delivery to a mock server that returns 200 (immediate success), 500-then-200 (retry succeeds), and 500-always (dead letter created). Verify the HMAC signature is correct by recomputing it on the consumer side.

---

### Phase 6 — Prometheus Metrics and Startup Cleanup

**Duration:** Day 5–6

**What to do.** Add platform-specific Prometheus metrics to `core/metrics.py`: a counter for total platform calls started (labeled by app_id, mode, and status), a histogram for call duration (labeled by app_id, with buckets at 10, 30, 60, 120, 300, 600 seconds), a gauge for currently active calls (labeled by app_id), a counter for webhook deliveries (labeled by app_id, event, and delivery status), and a counter for platform errors (labeled by app_id and error code). Instrument the orchestrator's platform methods and the webhook dispatcher to emit these metrics.

Add a startup cleanup function to `main.py` called `_cleanup_orphaned_platform_runs()`. This runs during the lifespan startup, after the existing `_cleanup_orphaned_calls()`. It finds all `pipeline_runs` rows with status "connecting" or "running" that have a `started_at` older than 1 hour, marks them as failed with error code "orphaned_run_cleanup", and resets all `platform:active:*` Redis keys to zero. This handles the case where the server crash left active call counters in an inconsistent state — the only safe thing to do on restart is reset them all to zero, since no pipelines from the previous process are still running.

**What NOT to do.** Do not add platform metrics to the existing SphereVoice metric labels. They must be separate counters/histograms so that platform traffic never pollutes SphereVoice tenant dashboards. Do not skip the Redis counter reset on startup — counter drift is the silent killer that eventually blocks all new platform calls.

**Separate platform pipelines from the tenant watchdog.** The existing `_call_duration_watchdog()` function (line ~85 in orchestrator.py) iterates ALL entries in `_active_pipelines` and accesses `pipeline._stopped`, `pipeline._started_at`, and `pipeline._max_call_duration_seconds` — all VoicePipeline attributes. It does NOT call `CallService` or look up Call records, so platform pipelines stored with `pf_` keys would not crash the loop today. However, mixing platform and tenant pipelines in the same dict makes operational debugging harder and creates a regression risk if the watchdog is later modified to access Call fields. For defense-in-depth, separate them. Two options:

Option A (preferred): Store platform pipelines in a **separate dict** — `_active_platform_pipelines: dict[str, VoicePipeline] = {}` — so the existing watchdog never sees them. Add a separate platform watchdog that checks platform pipeline duration against the app's `max_duration` limit and force-stops overdue pipelines. The `handle_platform_call_end()` method and the `get_active_pipeline()` utility functions must check both dicts.

Option B: Keep using the single `_active_pipelines` dict with `pf_` prefix keys, but modify the existing watchdog to **skip keys starting with `pf_`**. This is simpler but requires editing the watchdog code (which the plan otherwise says not to touch). If you go this route, the skip must be a simple `if call_id.startswith("pf_"): continue` at the top of the loop — do not add any platform logic to the watchdog beyond this guard.

Choose Option A if you want zero risk to existing tenant call monitoring. Choose Option B if you want fewer code changes.

**Consider:** If you run multiple backend instances behind a load balancer, the orphan cleanup will run on each instance at startup. This is fine because the SQL update is idempotent and the Redis reset is a simple SET. But be aware that if one instance is healthy and another restarts, the Redis counter reset will zero out the healthy instance's active calls too. This is an acceptable tradeoff for now — the counter will self-correct as active calls finish. For production multi-instance deployments, consider using a Redis-based distributed lock around the cleanup.

**Verify by:** Checking the `/metrics` endpoint for new platform counters. Force-killing the backend mid-call, restarting, and confirming orphaned runs are marked failed and Redis counters are zero.

---

### Phase 7 — Integration Tests

**Duration:** Day 6–7

**What to do.** Create a test file at `backend/tests/test_platform/test_platform_api.py` covering the full lifecycle.

**Auth tests:** Missing headers return 401. Invalid secret returns 401. Deactivated app returns 403. Valid credentials return PlatformContext with correct fields.

**Call start tests:** A valid web call request returns LiveKit credentials and a pipeline_run_id. Requesting a disallowed provider returns 403. Requesting outbound mode when disabled returns 403. Missing webhook URL returns 422. Duration is capped to the app tier's maximum. Same external_id within 5 minutes returns the cached response (idempotency). A pipeline_runs row is created — no calls table rows.

**Call end tests:** The stop handler updates pipeline_runs to completed with correct duration and cost. The result is cached in Redis under the correct key. The webhook is dispatched. The active call counter is decremented. The counter is decremented even if the stop handler encounters an error.

**Polling tests:** The result endpoint returns the cached transcript for the correct app. A different app trying to access the same result gets 404 (cross-app isolation). An expired result returns 404.

**Rate limit tests:** Exceeding calls per minute returns 429 with Retry-After header. Exceeding concurrent call limit returns 429.

**Webhook tests:** A successful delivery includes a verifiable HMAC signature. A 5xx consumer response triggers retries. A 4xx consumer response does not trigger retries. Exhausted retries create a dead letter row.

**Data isolation tests:** After a complete call lifecycle, assert zero rows in the calls table for the platform call. Assert no RLS context was set during the request. Assert the transcript is not in any PostgreSQL table (only in Redis and the webhook payload).

**What NOT to do.** Do not test the VoicePipeline internals — that's already tested by SphereVoice's existing test suite. The platform tests only cover the platform-specific path: auth, routing, PipelineRun lifecycle, webhook delivery, and data isolation. Do not use real LiveKit or real providers in tests — mock them. Do not make tests dependent on specific cost values — assert that costs are non-null and positive, not that they equal a specific number.

**Verify by:** All tests pass. Existing SphereVoice test suite still passes. No flaky tests.

---

## 4. Complete File Manifest

**Files to CREATE (10 files):**

1. `backend/app/modules/platform/__init__.py` — Module init.
2. `backend/app/modules/platform/models.py` — IntegrationApp, PipelineRun, WebhookDeadLetter ORM models.
3. `backend/app/modules/platform/schemas.py` — All Pydantic request/response models for the 6 endpoints.
4. `backend/app/modules/platform/router.py` — The 6 platform endpoints with auth, validation, and orchestrator delegation.
5. `backend/app/modules/platform/webhook_dispatcher.py` — Reliable webhook delivery with retry, signing, and dead letter.
6. `backend/app/core/platform_auth.py` — App authentication dependency returning PlatformContext.
7. `backend/app/core/platform_rate_limit.py` — Per-app RPM and concurrency rate limiting.
8. `backend/alembic/versions/xxxx_add_platform_tables.py` — Auto-generated Alembic migration for the 3 new tables.
9. `backend/tests/test_platform/test_platform_api.py` — Integration test suite.
10. `docs/platform-api-guide.md` — Consumer-facing API documentation with examples and webhook verification guides.

**Files to EDIT (5 files):**

1. `backend/app/main.py` — Register the platform router, add `PLATFORM_ENABLED` kill switch check (per-request dependency), and add orphaned platform run cleanup to the startup lifespan.
2. `backend/app/modules/pipeline/orchestrator.py` — Add `handle_platform_call()`, `_make_platform_stop_handler()`, `handle_platform_call_end()`, and either (a) add `_active_platform_pipelines` dict + platform watchdog, or (b) add `pf_` prefix skip guard to the existing watchdog loop.
3. `backend/app/core/metrics.py` — Add platform-specific Prometheus counters and histograms.
4. `backend/app/core/config.py` — Add all `PLATFORM_*` environment variable definitions to the `Settings` class.
5. `backend/seed.py` — Add NanoVoice integration app seeding.

**Files NOT touched:** Everything else. The existing SphereVoice auth system, Call model, Agent model, VoicePipeline, provider factory, recording service, post-call extraction, CRM writeback, webhook delivery, and the entire frontend are untouched.

---

## 5. Timeline

| Day | Phase | What Ships |
|-----|-------|-----------|
| 1 | Phase 1 | Three new tables in production, NanoVoice app seeded, config env vars defined |
| 2 | Phase 2 + start Phase 3 | Auth and rate limiting working, router skeleton responding, error envelope enforced |
| 3 | Finish Phase 3 + start Phase 4 | All 6 endpoints wired with validation, consumer docs started alongside schemas |
| 4 | Phase 4 continued | `handle_platform_call()` working — can start a real web call |
| 5 | Finish Phase 4 + Phase 5 | Stop handler finalizes calls, webhook delivery with HMAC signing working |
| 6 | Phase 6 | Metrics on Grafana, orphan cleanup on startup, structured logging in place |
| 7 | Phase 7 | Tests passing, security hardening verified |
| 8 | Operational readiness | Load test in staging, checklist verified, documentation complete |
| 9 | Rollout | Flag flipped in production, e2e verified with NanoVoice test call, monitoring confirmed |

Total: **9 working days** (7 for build, 2 for hardening and rollout).

---

## 6. What NanoVoice Needs to Do After This

Once the Platform API is live, the NanoVoice team (which is also you) needs to build their side of the integration:

Store the `X-App-Id` and `X-App-Secret` credentials in NanoVoice's environment. Implement a webhook receiver endpoint that accepts `POST` with JSON body, verifies the `X-Webhook-Signature` header using HMAC-SHA256, and deduplicates by `X-Webhook-Id`. Build a polling fallback — a cron job that checks `GET /platform/v1/calls/{id}/result` for any NanoVoice calls that are older than 10 minutes without a webhook callback. Implement a circuit breaker around SphereVoice API calls — if SphereVoice returns 5xx or 429 more than 5 times in a row, stop sending new calls for 30 seconds. For recordings, generate Azure Blob SAS (Shared Access Signature) PUT URLs scoped to a container in NanoVoice's own storage account and send them as `recording_upload_url` in the call request — SphereVoice will upload the recording there after the call ends.

---

## 7. Risks

**SimpleNamespace attribute mismatch** — The virtual agent object must expose every attribute that VoicePipeline, the provider factory, flow engine, and variable resolver access. A single missing attribute causes a runtime crash on the first call. Mitigation: exhaustively grep all agent attribute access patterns before implementation, and test with a real pipeline run in dev. The most dangerous surface is the `config` dict — it is a deeply nested dict (not a SimpleNamespace) that the pipeline reads via `config.get("settings", {}).get("speech", {}).get("responsiveness")` and many similar paths. The complete config structure is documented in Phase 4 above. Also, the `type` attribute MUST be `"single_prompt"` — if it's missing or wrong, the pipeline may try to load a conversation flow engine which expects structured flow nodes.

**Call duration watchdog — operational separation** — The existing `_call_duration_watchdog()` iterates ALL entries in `_active_pipelines` but only accesses VoicePipeline attributes (`_stopped`, `_started_at`, `_max_call_duration_seconds`) — it does NOT query Call records or call CallService, so platform pipelines won't crash it today. However, mixing pipeline types in the same dict creates a regression risk if the watchdog is later modified to access Call-specific fields, and makes operational debugging harder. Mitigation: either store platform pipelines in a separate `_active_platform_pipelines` dict (Option A) or add a `pf_` prefix guard to the watchdog loop (Option B). See Phase 6 for details.

**Redis counter drift** — If the server crashes between incrementing the active counter and starting the pipeline (or between the pipeline stopping and decrementing), the counter drifts. Over time, this can block new calls. Mitigation: startup cleanup resets all counters; the stop handler's finally block clamps to zero; and the health endpoint reports the current counter so NanoVoice can see if something looks wrong.

**Webhook consumer permanently unavailable** — If NanoVoice's webhook endpoint is down for days, dead letters accumulate with transcript data. Mitigation: 7-day expiry auto-purges old dead letters; the polling fallback (`GET /calls/{id}/result`) gives NanoVoice a second chance to retrieve results within 24 hours.

**LiveKit room leak** — If the platform creates a room but the pipeline never starts (crash between room creation and pipeline.start), the room sits orphaned. Mitigation: LiveKit's `empty_timeout=300` setting auto-cleans rooms that have been empty for 5 minutes. No action needed from SphereVoice.

**Platform calls competing for LLM rate limits with SphereVoice tenant calls** — Both platform and tenant calls use the same OpenAI API key. A burst of platform calls could exhaust the rate limit and degrade tenant calls. Mitigation: for now, the per-app concurrency limit (50 for NanoVoice) caps the blast radius. For production scale, consider using a separate OpenAI organization or project key for platform calls.

**Recording re-upload failure** — The two-step recording process (LiveKit Egress → Azure Blob → consumer's pre-signed URL) has more failure points than direct upload. If the re-upload to the consumer fails, the temporary Azure Blob is kept for 24 hours. Mitigation: the webhook payload includes a `recording_status` field (`"uploaded"`, `"upload_failed"`, `"not_requested"`) so the consumer knows whether to expect a recording. A future retry mechanism can re-attempt failed uploads from the temp blob.

---

## 8. API Versioning and Contract Stability

The API lives at `/platform/v1/`. The `v1` is part of the URL path, not a header. This is deliberate — URL-based versioning is the only strategy that works reliably when your consumers are automation tools (Zapier, Make.com) that don't let users set custom headers easily.

**Version promise.** Once v1 is live and NanoVoice is using it, the following are backwards-compatible changes that do NOT require a version bump: adding new optional fields to request schemas, adding new fields to response schemas, adding new endpoints under `/platform/v1/`, adding new webhook event types, loosening validation (e.g., increasing max_duration cap), and adding new enum values to output fields. The following are breaking changes that DO require v2: removing or renaming any existing field, changing the type of an existing field, removing an endpoint, tightening validation in a way that rejects previously-valid requests, changing the authentication mechanism, and changing the webhook signature algorithm.

**Deprecation protocol.** If v2 is ever needed, v1 continues to work for 90 days after v2 launches. During that 90 days, every v1 response includes a `Deprecation: true` header and a `Sunset: {date}` header per RFC 8594. NanoVoice (and any other consumer) gets email notification at 90, 60, 30, and 7 days before sunset.

**What NOT to do.** Do not use header-based versioning (`Accept: application/vnd.SphereVoice.v1+json`). Do not use query parameter versioning (`?version=1`). Do not version individual endpoints independently — the entire surface moves together. Do not introduce breaking changes in v1 under any circumstance, even if they seem "minor." From the consumer's perspective, every change that makes their existing integration stop working is a production incident, no matter how easy the fix is.

---

## 9. Error Handling and Error Code Standards

Every Platform API error response follows a single envelope format. No exceptions, no variations, no special cases.

The envelope has four fields: `error_code` (a machine-readable string like `rate_limit_exceeded`, `invalid_provider`, `app_deactivated`), `message` (a human-readable English sentence, suitable for logging by the consumer), `details` (an optional dict with additional context, such as `{"allowed_providers": ["openai", "groq"], "requested": "anthropic"}`), and `request_id` (a UUID assigned to every platform request for tracing).

**Error code taxonomy.** Authentication errors use the `auth_` prefix: `auth_missing_credentials`, `auth_invalid_secret`, `auth_app_deactivated`. Rate limit errors use `rate_limit_`: `rate_limit_rpm_exceeded`, `rate_limit_concurrency_exceeded`. Validation errors use `validation_`: `validation_missing_field`, `validation_invalid_provider`, `validation_outbound_disabled`, `validation_duration_exceeded`, `validation_no_webhook`. Pipeline errors use `pipeline_`: `pipeline_start_failed`, `pipeline_provider_error`, `pipeline_timeout`, `pipeline_livekit_unavailable`. Internal errors use `internal_`: `internal_server_error`, `internal_database_error`.

**HTTP status mapping.** 401 for all auth failures. 403 for valid auth but insufficient permission (deactivated app, disallowed provider, outbound not enabled). 404 for resource not found (run_id doesn't exist or belongs to another app). 409 for conflict (trying to stop an already-completed call). 422 for validation failures (missing webhook, bad field values). 429 for rate limits (always include `Retry-After` header). 500 for internal errors (never expose stack traces, never expose database errors, always return the error envelope with a generic message and the request_id for correlation).

**The request_id.** Every inbound platform request is assigned a UUID4 by the auth middleware. This ID is added to the response headers as `X-Request-Id`, included in every error response body, passed as a field to all log entries for this request, and used as the OTEL trace context correlation ID. When a consumer reports an issue, the first thing support asks for is the request_id. If they don't have it, you look it up by their external_id and approximate timestamp.

**What NOT to do.** Do not return bare HTTP status codes without the error envelope. Do not return HTML error pages (FastAPI's default 404 handler returns HTML). Override the exception handlers for the platform router to always return JSON. Do not leak internal details in error messages — "database connection pool exhausted" becomes "internal_server_error: unable to process your request at this time." Do not use numeric error codes — strings are self-documenting and don't need a lookup table.

---

## 10. Security Hardening

Beyond the basic auth and HMAC webhook signing described in earlier phases, the following security measures are required for production.

**App secret generation and storage.** Secrets are generated using `secrets.token_urlsafe(48)` — 64 characters of URL-safe base64 giving 384 bits of entropy. The secret is displayed exactly once when the app is created. Only the SHA-256 hash is stored in `integration_apps.app_secret_hash`. There is no "show secret again" feature. If lost, the operator generates a new secret, which invalidates the old one immediately.

**Request payload validation.** The `system_prompt` field is the highest-risk input — it controls what the LLM does. Enforce a maximum length of 50,000 characters. Reject any prompt containing `<script>`, `javascript:`, or other common injection patterns in any context_documents. Sanitize dynamic_variables values — they are injected into the prompt via string replacement, so a variable value containing `{{` could cause template injection. Strip or reject any variable value containing double curly braces.

**Transport security.** All platform endpoints must be HTTPS-only. In the production NGINX/Traefik configuration, the `/platform/` path must have HSTS headers and reject plain HTTP. Webhook delivery must only target HTTPS URLs. Reject any `webhook_url` that starts with `http://` — this prevents transcript data from being sent in plaintext. The only exception is `http://localhost` for local development.

**Rate limiting abuse patterns.** The per-minute and per-concurrent limits prevent basic abuse, but also watch for: an app rapidly cycling call starts and stops to waste pipeline resources (add a cooldown — same external_id can't start a new call within 5 seconds of the previous one ending), an app sending calls with extremely long prompts to waste LLM tokens (the 50K char limit caps this), and an app sending calls that immediately fail to inflate the call counter (the counter decrements on failure, but log and alert if failure rate exceeds 50%).

**Webhook URL and recording URL validation.** Before accepting a `webhook_url` or `recording_upload_url`, validate that it uses HTTPS (except localhost), that it doesn't resolve to a private IP range (10.x, 172.16-31.x, 192.168.x, 127.x, ::1, 169.254.x — this prevents SSRF, including cloud metadata endpoint attacks), and that it doesn't point to SphereVoice's own domain (prevent request loop). Perform this validation at call-creation time, not at delivery time, so the consumer gets clear feedback. The `recording_upload_url` is especially sensitive because SphereVoice performs an HTTP PUT to it with the MP3 file body — a malicious URL could exfiltrate data or probe internal services. Apply the same SSRF validation function to both URLs.

**Secrets in logs.** Ensure that `X-App-Secret` is never logged. Add it to the list of scrubbed headers in the logging middleware. The `app_secret_hash` should never appear in API responses. The webhook signing secret should never appear in error messages.

**What NOT to do.** Do not implement IP allowlisting per app in v1 — it adds management complexity that isn't needed yet. Do not implement mTLS between SphereVoice and the consumer — standard HTTPS with HMAC webhook signing is sufficient. Do not add CAPTCHA or human verification — this is a machine-to-machine API. Do not implement OAuth 2.0 client credentials flow in v1 — the custom header scheme is simpler, more predictable for automation tools, and sufficient for the current trust model where every consumer is a known entity.

---

## 11. Observability, Tracing, and Logging

Prometheus metrics (Phase 6) give you dashboards. This section covers the rest of the observability stack: structured logging, distributed tracing, and alerting.

**Structured logging.** Every log entry in the platform path must include these fields as structured key-value pairs (not interpolated into the message string): `request_id`, `app_id`, `app_name`, `pipeline_run_id` (when available), `external_id` (when available), `event` (a dot-separated event name like `platform.call.started`, `platform.call.completed`, `platform.webhook.delivered`). Use Python's `structlog` or the existing SphereVoice logger's `extra` dict — do not use f-strings to embed these values in the message. Structured fields are filterable in Grafana Loki; interpolated strings are not.

**Key log events to emit.** `platform.auth.success` and `platform.auth.failure` on every request (with failure reason). `platform.call.started` when the pipeline starts (include provider triple: stt, llm, tts). `platform.call.completed` when the stop handler finishes (include duration, cost, transcript word count — NOT the transcript itself). `platform.call.failed` when the pipeline crashes (include error code, not the full stack trace — that goes to Sentry). `platform.webhook.attempt` on each delivery attempt (include attempt number, target URL domain only — not full path which might contain secrets, and HTTP status). `platform.webhook.delivered` or `platform.webhook.dead_lettered` on final outcome. `platform.rate_limit.hit` when a request is rejected (include which limit was hit and current values). `platform.cleanup.orphaned` when startup cleanup marks a run as failed.

**Distributed tracing.** The existing SphereVoice backend uses OpenTelemetry. Platform calls must participate in the same trace infrastructure. The auth middleware must create a new OTEL span `platform.request` with attributes for app_id, request_id, and endpoint. The orchestrator's `handle_platform_call()` must create a child span `platform.pipeline.lifecycle`. The webhook dispatcher must create a child span `platform.webhook.delivery` with attempt count and target URL. This ensures that a single trace shows the full journey: request received → auth checked → pipeline started → pipeline stopped → costs calculated → webhook delivered.

**Alerting rules.** Define these in the Grafana alerting configuration (or Terraform if you manage alerts as code). Critical alerts (page): platform error rate exceeds 10% over 5 minutes, active call counter for any app exceeds 90% of its limit for more than 2 minutes, webhook dead letter rate exceeds 20% over 1 hour. Warning alerts (Slack): any single app's failure rate exceeds 30% over 15 minutes, orphaned run cleanup marks more than 5 runs on startup, 429 rate limit responses exceed 50 per minute for any single app.

**What NOT to do.** Do not log transcripts, phone numbers, system prompts, or webhook secrets. Do not send platform trace data to a separate OTEL collector — use the same one, but add a `service.namespace=platform` resource attribute so you can filter. Do not create a separate Grafana dashboard initially — add a "Platform API" row to the existing SphereVoice overview dashboard with the key metrics (calls/minute, active calls, error rate, webhook success rate).

---

## 12. Configuration Management

All platform-specific configuration must be driven by environment variables and per-app database rows, not hardcoded in application code.

**Environment variables (set in SphereVoice's `.env` or deployment secrets):**

`PLATFORM_ENABLED` (boolean, default false) — master kill switch. When false, all `/platform/` endpoints return 503 with a maintenance message. This lets you disable the entire platform API without redeploying. **Implementation note:** this must be checked on every request (as a FastAPI dependency or middleware), NOT at router registration time. If you check it at import time, changing the env var requires a process restart. Checking per-request means you can flip the flag in the env and it takes effect immediately (the `Settings` object is cached via `@lru_cache`, so either use a Redis-backed flag instead, or clear the settings cache on SIGHUP, or accept that a restart is needed — the last option is simplest and fine for v1). `PLATFORM_DEFAULT_MAX_CONCURRENT` (int, default 50) — used as the default when creating new integration apps. `PLATFORM_DEFAULT_RPM` (int, default 30) — default calls per minute for new apps. `PLATFORM_DEFAULT_MAX_DURATION` (int, default 600) — default max call duration in seconds. `PLATFORM_WEBHOOK_TIMEOUT` (int, default 10) — seconds to wait for a consumer's webhook endpoint to respond before marking the attempt as failed. `PLATFORM_RESULT_CACHE_TTL` (int, default 86400) — seconds to keep the call result in Redis for polling. `PLATFORM_DEAD_LETTER_EXPIRY_DAYS` (int, default 7) — days before dead letter rows are auto-purged. `PLATFORM_IDEMPOTENCY_WINDOW` (int, default 300) — seconds for the idempotency cache on external_id.

**Per-app configuration (stored in `integration_apps` table):** All the tier-specific limits (max concurrent, RPM, max duration, allowed providers, outbound enabled), webhook URL and secret, contact email, and app status. These are managed via seed script initially, and later via an admin API.

**Provider resolution for platform calls.** Platform calls do NOT use tenant provider keys. The pipeline factory resolves providers by checking: (1) agent-level provider_id (null → skip), (2) global default `provider_keys` rows in the database (`is_default=True`, no tenant filter), then (3) env var fallback. In the typical SphereVoice deployment, step 2 finds the shared provider_keys created by the seed script — these are the org-level keys platform calls will use. Make sure the global default provider_keys have valid API credentials for all providers in the platform whitelist. The env vars (`OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`, `GROQ_API_KEY`) are only reached as a last-resort fallback if no matching DB row exists, but they should still be set as a safety net.

**What NOT to do.** Do not hardcode the 50-concurrent or 30-RPM limits anywhere. Do not hardcode the webhook retry schedule — make it configurable (or at minimum, extract it to a constant at the top of the dispatcher file). Do not read tenant-specific settings for platform calls — the tenant context is None and must stay None.

---

## 13. Graceful Degradation and Circuit Breaking

The platform API must degrade gracefully when dependencies fail, rather than returning 500s.

**LiveKit unavailable.** If LiveKit is down or unreachable when a platform call starts, return a 503 with error code `pipeline_livekit_unavailable` and a `Retry-After: 30` header. Do not return 500 — the consumer should know this is a temporary infrastructure issue and can retry. Check LiveKit connectivity in the health endpoint so NanoVoice can pre-flight before sending calls.

**LLM/STT/TTS provider down.** If the provider returns a 5xx during pipeline construction (not during the call itself — that's handled by VoicePipeline's retry mechanism), catch the error, decrement the active call counter, mark the pipeline_run as failed with error code `pipeline_provider_error`, and return 502 with a clear message identifying which provider failed. Do not expose the provider's raw error message — it may contain API keys or internal details.

**Redis unavailable.** If Redis is down, rate limiting and idempotency checks fail. The platform should continue to work without rate limiting rather than rejecting all calls. Log a critical alert and proceed without rate checks. The per-app concurrency limit in the database (checked during auth) provides a coarse safety net. The active call counter in Redis is a best-effort optimization on top of the database row.

**Webhook consumer permanently down.** After 5 failed delivery attempts, the dead letter is created and the stop handler completes normally. The pipeline run is still marked as completed with correct costs. The consumer can poll for results within 24 hours. The dead letter is purged after 7 days. At no point does a webhook failure affect the pipeline execution or cost calculation.

**PostgreSQL unavailable.** If the database is down, the platform cannot authenticate (app lookup fails) and cannot create pipeline_run records. Return 503 on all endpoints. There is no meaningful degradation mode without the database.

**What NOT to do.** Do not implement a cross-cutting circuit breaker that disables the entire platform API when one dependency is unhealthy. Each dependency has its own failure mode and its own degradation path. Do not retry at the platform router level — retries happen inside the specific subsystem (pipeline retries inside VoicePipeline, webhook retries inside the dispatcher). Do not queue calls when at capacity — return 429 immediately and let the consumer decide when to retry.

---

## 14. Deployment and Rollout Strategy

The platform API ships as part of the existing SphereVoice backend deployment. There is no separate service, no separate container, and no separate database. This keeps operational complexity low.

**Feature flag rollout.** The `PLATFORM_ENABLED=false` env var ensures the platform endpoints are disabled by default. The rollout sequence is: deploy the code to production with the flag off, run the Alembic migration to create the three tables, seed the NanoVoice integration app, flip the flag to true, have NanoVoice send a single test call, verify end-to-end (pipeline run created, stopped correctly, webhook delivered, costs calculated, no calls table rows), then open up for real traffic.

**Database migration safety.** The three new tables (`integration_apps`, `pipeline_runs`, `webhook_dead_letters`) are additive — no existing tables are modified. The migration is zero-risk: it adds tables, adds indexes, and seeds one row. There is no downtime needed. Run `alembic upgrade head` as part of the normal deployment pipeline.

**Rollback plan.** If the platform API causes issues after launch, flip `PLATFORM_ENABLED=false`. This immediately returns 503 on all platform endpoints while leaving the rest of SphereVoice unaffected. Any in-flight platform calls will complete (the pipeline is already running and doesn't check the flag), but no new ones will start. If the database migration itself causes issues (extremely unlikely since it only adds tables), run `alembic downgrade -1` to drop the three tables. This is safe because no existing code references them.

**Load testing before launch.** Before flipping the flag to true in production, run a load test in staging: 50 concurrent web calls through the platform API, sustained for 5 minutes. Monitor: LiveKit room creation rate, LLM token throughput, Redis memory for call results, PostgreSQL connection pool usage, and webhook delivery latency. The goal is to verify that 50 platform calls don't degrade SphereVoice's existing tenant call performance. If they do, reduce NanoVoice's concurrent limit.

**DNS and routing.** The platform API is served on the same domain and port as the SphereVoice API. NGINX/Traefik routing is by path prefix: `/platform/` goes to the same upstream as `/api/`. No new DNS records needed. No new TLS certificates needed. No new load balancer rules needed.

**What NOT to do.** Do not deploy the platform API as a separate microservice. The pipeline reuse is the entire point — a separate service would need to duplicate the pipeline engine, provider factory, cost tracker, and LiveKit integration. Do not use a separate database for platform tables — the joins (e.g., between pipeline_runs and integration_apps) need to be in the same database, and the admin queries need to see both SphereVoice and platform data. Do not create a separate Docker image — the existing backend Dockerfile picks up the new module automatically.

---

## 15. Credits, Usage Tracking, and Billing Readiness

NanoVoice gives users $10 trial credits. The Platform API must track usage precisely enough to support this, even though actual billing integration (Stripe/Razorpay) is out of scope for now.

**Per-call cost tracking.** Every `pipeline_run` row stores `stt_cost`, `llm_cost`, `tts_cost`, `telephony_cost`, and `total_cost` at `Numeric(12,8)` precision. These are calculated by the same `PricingService.calculate_costs()` that SphereVoice uses. The cost is always in USD — currency conversion is NanoVoice's responsibility.

**Per-app aggregate counters.** The `integration_apps` table has `total_calls`, `total_duration_seconds`, and `total_cost_usd` columns. These are incremented atomically in the stop handler using `UPDATE integration_apps SET total_cost_usd = total_cost_usd + :cost WHERE id = :app_id`. The atomic increment prevents race conditions when multiple calls end simultaneously.

**NanoVoice credit enforcement.** NanoVoice is responsible for checking whether the user has sufficient credits before sending a call to SphereVoice. SphereVoice does not enforce credits — it only reports costs. NanoVoice's pre-call flow: check user's remaining credits → if credits < estimated minimum call cost (e.g., $0.05 for 1 minute), reject → otherwise, send the call to SphereVoice → when the webhook delivers the completed result with the actual cost, deduct from the user's credit balance. The reason SphereVoice doesn't enforce credits is isolation: SphereVoice doesn't know about NanoVoice users, their credit balances, or their billing plans. SphereVoice only knows about integration apps.

**Usage reporting.** The `GET /platform/v1/usage` endpoint returns the app's aggregate stats. NanoVoice can poll this for dashboard display. But for per-user billing, NanoVoice correlates costs by `external_id` — which NanoVoice sets to something like `nv_user_{user_id}_{call_id}` so it can attribute costs to individual users.

**Cost estimation endpoint (not in v1, but design for it).** NanoVoice will eventually want a `POST /platform/v1/estimate` endpoint that takes a call duration estimate and provider triple and returns the estimated cost before starting the call. This lets them show "this call will cost approximately $0.12" to users. Design the pricing service and tier limits so this endpoint is easy to add later — the data is already there, just the route is missing.

**What NOT to do.** Do not implement user-level billing in the platform API. Do not add a "credits" or "balance" column to `integration_apps` — that's NanoVoice's concern. Do not enforce cost limits in the platform API — NanoVoice enforces limits and calls `POST /platform/v1/calls/{id}/stop` if a call runs too long. Do not implement usage-based throttling (e.g., "disable app after $100 in charges") — that's a future feature.

---

## 16. Documentation for Consumers

Before NanoVoice goes live, the Platform API needs clear documentation. Not a Swagger page — actual written documentation that a developer can follow without trial and error.

**What the documentation must cover:**

1. **Authentication.** How to set the `X-App-Id` and `X-App-Secret` headers. What errors look like when auth fails. That the secret is SHA-256 compared so there's no partial-match risk.

2. **Starting a web call.** The exact POST body schema with every field explained. Which fields are required vs optional. What happens when optional fields are omitted (defaults). What the response looks like. How to use the returned LiveKit credentials to connect a browser (or a custom client) to the call.

3. **Starting an outbound call (future).** Marked as "coming soon" with a description of what will be possible.

4. **Receiving webhooks.** The exact payload schema for each event type. How to verify the HMAC signature (step-by-step, with code examples in Python, Node.js, and Go). The retry behavior (5 attempts, exponential backoff). Dead letter semantics. The idempotency ID header for deduplication.

5. **Polling for results.** How to use `GET /platform/v1/calls/{id}/result` as a fallback. The 24-hour TTL. What 404 means (expired or doesn't exist or wrong app).

6. **Error handling.** The error envelope format. The complete list of error codes with causes and recommended consumer actions. Which errors are retryable (5xx, 429) and which are not (4xx).

7. **Rate limits.** How to check current capacity (health endpoint). What 429 responses look like. The `Retry-After` header convention.

8. **Usage and costs.** How to query aggregate usage. How per-call costs are calculated. What `usage_metrics` contains in the webhook payload.

9. **LiveKit client integration.** For web calls, how to use the LiveKit JS SDK or React SDK to connect a browser to the call. What events to listen for. How to display the agent connection state. This is critical because NanoVoice's entire user experience depends on it.

10. **Code examples.** Complete Python and Node.js examples for: starting a call, connecting to it, receiving the webhook, and verifying the signature. Not snippets — complete, runnable scripts.

**Format.** The documentation lives in `docs/platform-api-guide.md` in the SphereVoice repo initially. When the Platform API goes public, it moves to a hosted docs site. The OpenAPI spec (auto-generated by FastAPI) is a supplement, not a replacement — Swagger UIs are terrible for understanding workflows.

**What NOT to do.** Do not auto-generate the documentation from docstrings. Docstrings describe what a function does; API documentation describes how a consumer accomplishes a task. They are fundamentally different. Do not put the documentation in a separate repo — it must version-lock with the API code. Do not write the documentation after shipping — write it during Phase 3 when you're building the schemas, so the documentation and the schemas are consistent from day one.

---

## 17. Operational Readiness Checklist

Before the `PLATFORM_ENABLED` flag is flipped to true in production, every item on this list must be verified.

**Infrastructure readiness.** The three database tables exist and have the correct indexes. The NanoVoice integration app is seeded with the correct tier limits. Redis has sufficient memory headroom for the expected active call counters and result cache (estimate: 50 concurrent × 100KB result payload = 5MB peak Redis usage for NanoVoice alone). LiveKit can handle the additional concurrent rooms (verify with LiveKit's admin API or dashboard).

**Monitoring readiness.** Platform Prometheus metrics are emitting data (verify on `/metrics`). The Grafana dashboard row is rendering. Alert rules are configured and tested (trigger a test alert, verify it reaches the Slack channel). Structured log fields are appearing in Grafana Loki (run a test query for `event="platform.call.started"`).

**Security readiness.** The NanoVoice app secret has been transmitted to the NanoVoice environment via a secure channel (not Slack, not email — use a secrets manager or face-to-face). The webhook URL has been validated as HTTPS. SSRF checks are in place and tested. The `X-App-Secret` header is confirmed absent from access logs (check NGINX log format and application log output).

**Functional readiness.** A complete end-to-end call has been executed in production with the flag temporarily on: call started, agent spoke, user spoke, call ended, costs calculated, webhook delivered with correct transcript and signature, no rows in calls table, pipeline_run row has correct status and costs.

**Rollback readiness.** The operator knows how to flip `PLATFORM_ENABLED=false` and has tested it. The operator knows how to run `alembic downgrade -1` if the nuclear option is needed. The operator has access to the Redis CLI to manually reset platform counters if needed.

**Documentation readiness.** The consumer (NanoVoice) has received the API documentation, has implemented the webhook receiver, and has tested webhook signature verification against a known payload.

---

## 18. Future Enhancements (Not in Scope)

These are explicitly out of scope. Do not build them now.

An admin UI in the SphereVoice dashboard for managing integration apps, viewing usage charts, and retrying dead letters — build this only after NanoVoice validates demand. Real-time webhook event streaming (transcript chunks, tool calls during the call) — build when a consumer needs live updates, not after-the-fact webhooks. Outbound call support via the platform API — requires telephony provider allocation per app and is a separate design. Per-app API key rotation with a grace period — needed before onboarding external partners who might leak their credentials. A Celery beat task for retrying dead letters — build after the first dead letter incident proves the need. Encrypted-at-rest dead letter payloads — must be done before any partner onboarding. A public documentation page for the platform API at `/platform/docs` — auto-generate from OpenAPI spec before public launch. Per-app bring-your-own-key (BYOK) for providers — when partners want to use their own OpenAI keys instead of yours. Billing integration with Stripe or Razorpay — when NanoVoice starts charging its users and needs automated top-ups. Real-time usage webhooks — send a webhook when an app reaches 80% or 100% of some cost threshold. Multi-region routing — direct platform calls to the nearest LiveKit region based on caller geography. SLA tiers — different uptime guarantees and priority queuing for enterprise-tier apps vs sandbox-tier. Audit log API — let consumers query their own auth and error logs for compliance.
