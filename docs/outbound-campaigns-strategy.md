# Outbound Campaigns & CRM Tool-Calling Strategy

> **Status:** Draft  
> **Author:** Architecture  
> **Date:** 2026-03-17  

---

## 1. Executive Summary

Build a **Campaigns** module that lets tenants run bulk outbound voice calls backed by CRM data, with per-row context injection, live in-call tool-calling (WhatsApp, email, SMS, cal.com booking), post-call CRM write-back, and full queuing/concurrency control — all scoped per-tenant and reusable across agents.

### What Already Exists (we build on top of these)

| Capability | Current State |
|---|---|
| Single outbound call | `POST /api/v1/calls` with `dynamic_variables` — fully working |
| CRM integration (Zoho) | OAuth + contact sync + caller enrichment + post-call push |
| Function/tool calling | Webhook-based custom functions + built-in `end_call`/`transfer_call` |
| Dynamic variables | `{{variable}}` substitution in agent prompts from any source |
| Celery + Azure Service Bus | 7 existing workers on ASB (Kombu transport) + Redis result backend |
| Post-call extraction | Schema-driven field extraction → stored in `calls.extracted_data` |
| Tenant isolation (RLS) | All tables tenant-scoped with PostgreSQL row-level security |
| Agent versioning | Published snapshots used at runtime; drafts don't affect live calls |

---

## 2. Architecture Overview

```
┌─────────────── Frontend ───────────────┐
│  Campaign Builder UI                    │
│  ┌──────────┐ ┌────────┐ ┌───────────┐ │
│  │CRM Source │ │Agent   │ │Schedule & │ │
│  │& Filters │ │Picker  │ │Concurrency│ │
│  └────┬─────┘ └───┬────┘ └─────┬─────┘ │
└───────┼────────────┼────────────┼───────┘
        │   POST /api/v1/campaigns        │
        ▼            ▼            ▼
┌──────────────── Backend ───────────────┐
│  Campaigns Module (router/service)      │
│  ┌─────────────────────────────────┐    │
│  │ campaign_runs → campaign_calls  │    │ ← DB models
│  └──────────────┬──────────────────┘    │
│                 │ enqueue                │
│  ┌──────────────▼──────────────────┐    │
│  │   Celery Campaign Worker        │    │
│  │   ┌────────────────────────┐    │    │
│  │   │ Rate Limiter (Redis)   │    │    │
│  │   │ ASB Session Ordering   │    │    │
│  │   └───────────┬────────────┘    │    │
│  │               │ for each row    │    │
│  │   ┌───────────▼────────────┐    │    │
│  │   │ call_outbound_single() │    │    │ ← reuses existing orchestrator
│  │   │ + CRM row → dynamic_   │    │    │
│  │   │   variables injection  │    │    │
│  │   └───────────┬────────────┘    │    │
│  └───────────────┼─────────────────┘    │
│                  │                       │
│  ┌───────────────▼─────────────────┐    │
│  │     VoicePipeline (per call)    │    │
│  │  ┌──────────┐ ┌──────────────┐  │    │
│  │  │Agent     │ │In-Call Tools │  │    │
│  │  │+ CRM row │ │(WhatsApp,    │  │    │
│  │  │context   │ │email, book,  │  │    │
│  │  │injected  │ │CRM write)    │  │    │
│  │  └──────────┘ └──────┬───────┘  │    │
│  └───────────────────────┼──────────┘    │
│                          │ post-call     │
│  ┌───────────────────────▼──────────┐    │
│  │  Post-Call Worker                │    │
│  │  • extraction → extracted_data   │    │
│  │  • CRM write-back (field map)    │    │
│  │  • campaign_call status update   │    │
│  └──────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

---

## 3. Phased Delivery Plan

### Phase 1 — Tenant Integration Framework (Foundation)
**Goal:** Generic integration registry so tenants wire up CRM, calendar, messaging per-tenant — shared by all agents under that tenant.

#### 3.1.1 New DB Table: `tenant_integrations`

```sql
CREATE TABLE tenant_integrations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category      VARCHAR(50) NOT NULL,  -- 'crm', 'calendar', 'messaging', 'email'
  provider      VARCHAR(100) NOT NULL, -- 'zoho_crm', 'hubspot', 'cal_com', 'whatsapp_cloud', 'sendgrid'
  status        VARCHAR(20) NOT NULL DEFAULT 'connected',
  credentials_encrypted TEXT,          -- AES-256-GCM (same as provider_keys)
  config        JSONB NOT NULL DEFAULT '{}',  -- provider-specific: field_mappings, default_from, etc.
  last_synced_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (tenant_id, category, provider)
);
-- RLS: tenant_id = current_setting('app.current_tenant_id')
```

> **Migration path:** Move existing `crm_integrations` to be a specialization of this table, or keep it and add a `tenant_integration_id` FK for unification later. Recommend: keep Zoho as-is for now, add `tenant_integrations` for new providers, and unify in Phase 4.

#### 3.1.2 Integration Categories & Initial Providers

| Category | Providers | Purpose |
|----------|-----------|---------|
| `crm` | Zoho (existing), HubSpot (future) | Read contact data, write-back fields |
| `calendar` | Cal.com, Calendly | Book meetings during/after call |
| `messaging` | WhatsApp Cloud API, Twilio SMS | Send links, docs, confirmations |
| `email` | SendGrid, Postmark, SMTP | Send follow-up emails |
| `custom_webhook` | Any URL | Generic HTTP tool for agents |

#### 3.1.3 Deliverables

- [ ] `tenant_integrations` model + Alembic migration
- [ ] CRUD API: `POST/GET/PUT/DELETE /api/v1/integrations/{category}/{provider}`
- [ ] OAuth flow generalization (extend current Zoho pattern)
- [ ] Frontend: Integration settings page per tenant (cards per category)
- [ ] Encryption reuse from existing `app.core.encryption`

---

### Phase 2 — Campaign Engine (Core)
**Goal:** Create, launch, pause, and monitor bulk outbound call campaigns that pull rows from the CRM.

#### 3.2.1 New DB Tables

**`campaigns`** — Campaign definition (reusable template)

```sql
CREATE TABLE campaigns (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name           VARCHAR(255) NOT NULL,
  description    TEXT,
  agent_id       UUID NOT NULL REFERENCES agents(id),
  status         VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- 'draft' | 'scheduled' | 'running' | 'paused' | 'completed' | 'cancelled'

  -- Source configuration
  source_type    VARCHAR(50) NOT NULL DEFAULT 'crm',  -- 'crm' | 'csv' | 'manual'
  source_config  JSONB NOT NULL DEFAULT '{}',
    -- For CRM: { "integration_id": "...", "module": "Leads", "filter": {"Lead_Status": "Not Contacted"} }
    -- For CSV: { "file_id": "...", "phone_column": "phone", "mapping": {...} }

  -- Variable mapping: CRM field → agent {{variable}}
  variable_mapping JSONB NOT NULL DEFAULT '{}',
    -- { "first_name": "First_Name", "email": "Email", "course_interest": "Custom_Field_1" }

  -- Write-back mapping: agent extracted_data field → CRM field
  writeback_mapping JSONB NOT NULL DEFAULT '{}',
    -- { "qualification_status": "Lead_Status", "preferred_date": "Custom_Date_Field" }

  -- Calling configuration
  from_number        VARCHAR(20),          -- E.164 caller ID
  max_concurrent     INT NOT NULL DEFAULT 5,
  calls_per_minute   INT NOT NULL DEFAULT 10,
  max_retries        INT NOT NULL DEFAULT 2,
  retry_delay_minutes INT NOT NULL DEFAULT 60,

  -- Schedule
  scheduled_at       TIMESTAMPTZ,          -- NULL = manual start
  calling_window     JSONB DEFAULT '{}',   -- { "start": "09:00", "end": "18:00", "timezone": "America/New_York", "days": [1,2,3,4,5] }

  -- Stats (denormalized for fast reads)
  total_contacts     INT NOT NULL DEFAULT 0,
  completed_calls    INT NOT NULL DEFAULT 0,
  successful_calls   INT NOT NULL DEFAULT 0,
  failed_calls       INT NOT NULL DEFAULT 0,

  created_by     UUID REFERENCES users(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- RLS: tenant_id = current_setting('app.current_tenant_id')
-- Indexes: tenant_id, status, agent_id
```

**`campaign_contacts`** — Per-row state machine for each contact in a campaign

```sql
CREATE TABLE campaign_contacts (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id    UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  tenant_id      UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

  -- Contact identity
  phone_number   VARCHAR(30) NOT NULL,  -- E.164
  crm_record_id  VARCHAR(100),          -- Zoho/HubSpot record ID
  crm_module     VARCHAR(50),           -- "Contacts" | "Leads"

  -- Snapshot of CRM data at enqueue time (immutable per attempt)
  contact_data   JSONB NOT NULL DEFAULT '{}',
    -- { "first_name": "John", "email": "john@example.com", "course_interest": "MBA", ... }

  -- State machine
  status         VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 'pending' | 'queued' | 'calling' | 'completed' | 'failed' | 'no_answer' |
    -- 'busy' | 'voicemail' | 'skipped' | 'retry_scheduled' | 'do_not_call'

  -- Link to actual call record
  call_id        UUID REFERENCES calls(id),
  attempt_count  INT NOT NULL DEFAULT 0,
  max_attempts   INT NOT NULL DEFAULT 3,
  next_retry_at  TIMESTAMPTZ,

  -- Write-back results (populated post-call)
  extracted_data JSONB DEFAULT '{}',
  writeback_status VARCHAR(20),  -- 'pending' | 'synced' | 'failed'
  writeback_error  TEXT,

  -- Tool call results during the call
  tool_results   JSONB DEFAULT '[]',
    -- [{"tool": "send_whatsapp", "status": "sent", "at": "..."}, ...]

  priority       INT NOT NULL DEFAULT 0,  -- higher = called first
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- RLS: tenant_id = current_setting('app.current_tenant_id')
-- Indexes: campaign_id+status, phone_number, next_retry_at, crm_record_id
```

#### 3.2.2 Campaign API

```
POST   /api/v1/campaigns                    — Create campaign (draft)
GET    /api/v1/campaigns                    — List campaigns (paginated)
GET    /api/v1/campaigns/{id}               — Campaign detail + stats
PUT    /api/v1/campaigns/{id}               — Update draft campaign
DELETE /api/v1/campaigns/{id}               — Delete (only if draft/completed)

POST   /api/v1/campaigns/{id}/load-contacts — Fetch contacts from CRM source → populate campaign_contacts
POST   /api/v1/campaigns/{id}/start         — Start (enqueue all pending contacts to Celery)
POST   /api/v1/campaigns/{id}/pause         — Pause (stop picking new contacts; in-flight calls finish)
POST   /api/v1/campaigns/{id}/resume        — Resume from paused
POST   /api/v1/campaigns/{id}/cancel        — Cancel (abort remaining)

GET    /api/v1/campaigns/{id}/contacts      — List contacts with status (paginated, filterable)
GET    /api/v1/campaigns/{id}/contacts/{cid}— Single contact detail + call transcript
POST   /api/v1/campaigns/{id}/contacts/{cid}/retry — Manual retry for a failed contact

GET    /api/v1/campaigns/{id}/stats         — Aggregated stats (live)
GET    /api/v1/campaigns/{id}/export        — Export results as CSV
```

#### 3.2.3 Workers (Celery on Azure Service Bus)

All campaign workers run as Celery tasks with Azure Service Bus as the broker (via Kombu's `azureservicebus://` transport). This is the **same transport all 7 existing workers already use** — the campaign workers are just new task modules registered in the same Celery app.

For campaign-specific features that Kombu doesn't expose (scheduled delivery, per-campaign session ordering, dead-letter inspection), the dedicated `CampaignQueue` abstraction in `backend/app/modules/campaigns/queue.py` uses the **azure-servicebus SDK directly**.

**Worker 1: `campaign_orchestrator`** (long-running coordinator)

```python
@celery_app.task(name="campaign.orchestrate", bind=True)
def orchestrate_campaign(self, campaign_id: str):
    """
    Main loop:
    1. Load campaign config
    2. Acquire Redis semaphore (max_concurrent slots — Redis result backend used for counters)
    3. Fetch next batch of 'pending' contacts (ORDER BY priority DESC, created_at ASC)
    4. For each contact: enqueue via CampaignQueue.enqueue() → ASB session queue
    5. Respect calls_per_minute rate limit (Redis token bucket)
    6. Respect calling_window (skip if outside hours; use ASB scheduled_enqueue_time_utc)
    7. Loop until all contacts processed or campaign paused/cancelled
    8. Update campaign.status = 'completed'
    """
```

**Worker 2: `campaign_call_single`** (per-contact call)

```python
@celery_app.task(name="campaign.call_single", bind=True, max_retries=3)
def call_single_contact(self, campaign_id: str, contact_id: str):
    """
    1. Load campaign + contact row
    2. Build dynamic_variables from contact_data + variable_mapping
    3. Call orchestrator.handle_outbound_call(agent_id, to_number, from_number, dynamic_variables)
    4. Monitor call completion (poll or callback)
    5. On completion:
       a. Update campaign_contact.status
       b. Store extracted_data
       c. Trigger CRM write-back task
       d. Update campaign stats
    6. On failure:
       a. If attempts < max_attempts → schedule retry (ASB scheduled enqueue)
       b. Else mark as 'failed' (message goes to ASB dead-letter queue)
    """
```

**Worker 3: `campaign_crm_writeback`** (post-call CRM sync)

```python
@celery_app.task(name="campaign.crm_writeback", bind=True)
def crm_writeback(self, contact_id: str):
    """
    1. Load contact + campaign writeback_mapping
    2. Map extracted_data fields → CRM field names
    3. Call Zoho API: PUT /crm/v6/{module}/{record_id} with mapped fields
    4. Update writeback_status = 'synced' | 'failed'
    5. Log to crm_sync_log
    6. On permanent failure → ASB dead-letter queue for manual review
    """
```

#### 3.2.4 Concurrency & Rate Limiting

```python
# Redis (result backend) used for ephemeral counters:
#   campaign:{id}:semaphore  — counting semaphore (max_concurrent)
#   campaign:{id}:rate       — token bucket (calls_per_minute)
#   campaign:{id}:status     — 'running' | 'paused' | 'cancelled'
#
# Azure Service Bus provides:
#   - Per-campaign FIFO ordering via session_id = campaign_id
#   - Scheduled delivery via scheduled_enqueue_time_utc (for retries)
#   - Dead-letter queue for permanently failed messages
#   - Peek-lock for at-least-once delivery

class CampaignRateLimiter:
    async def acquire_call_slot(self, campaign_id: str) -> bool:
        """Block until a concurrent slot opens AND rate limit allows."""
    
    async def release_call_slot(self, campaign_id: str):
        """Release one concurrent slot."""
    
    async def check_calling_window(self, campaign_id: str, timezone: str) -> bool:
        """Return True if current time is within the calling window."""
```

---

### Phase 3 — In-Call Tool Calling (Agent Actions)
**Goal:** During a live call, the agent can trigger real actions — send WhatsApp, email, book a meeting, update CRM — using tenant-level integrations.

#### 3.3.1 Tool Registry (Tenant-Scoped)

New concept: **Tenant Tool Library** — a set of callable tools available to any agent under that tenant, powered by the tenant's integrations.

```sql
CREATE TABLE tenant_tools (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  integration_id  UUID REFERENCES tenant_integrations(id),  -- NULL for built-in tools
  
  name            VARCHAR(100) NOT NULL,    -- 'send_whatsapp', 'send_email', 'book_meeting'
  display_name    VARCHAR(255) NOT NULL,    -- 'Send WhatsApp Message'
  description     TEXT NOT NULL,            -- LLM-facing description
  category        VARCHAR(50) NOT NULL,     -- 'messaging', 'calendar', 'crm', 'custom'
  
  -- JSON Schema for tool parameters (OpenAI function calling format)
  parameters_schema JSONB NOT NULL,
  
  -- Execution config
  execution_type  VARCHAR(30) NOT NULL DEFAULT 'integration',
    -- 'integration' (use tenant_integration credentials)
    -- 'webhook' (call external URL)
    -- 'built_in' (platform-handled)
  execution_config JSONB NOT NULL DEFAULT '{}',
    -- For webhook: { "url": "...", "method": "POST", "headers": {...} }
    -- For integration: { "action": "send_message", "defaults": {"from": "+1..."} }

  is_active       BOOLEAN NOT NULL DEFAULT true,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  UNIQUE (tenant_id, name)
);
-- RLS: tenant_id = current_setting('app.current_tenant_id')
```

#### 3.3.2 Agent ↔ Tool Binding

Agents pick which tenant tools they can use:

```sql
CREATE TABLE agent_tools (
  agent_id   UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  tool_id    UUID NOT NULL REFERENCES tenant_tools(id) ON DELETE CASCADE,
  config     JSONB DEFAULT '{}',  -- agent-specific overrides (e.g., template text)
  PRIMARY KEY (agent_id, tool_id)
);
```

#### 3.3.3 Built-In Tool Executors

```python
class ToolExecutor:
    """Route tool calls to the correct integration executor."""

    async def execute(self, tool: TenantTool, arguments: dict, call_context: dict) -> dict:
        if tool.execution_type == "integration":
            return await self._execute_integration(tool, arguments, call_context)
        elif tool.execution_type == "webhook":
            return await self._execute_webhook(tool, arguments, call_context)
        elif tool.execution_type == "built_in":
            return await self._execute_builtin(tool, arguments, call_context)

class WhatsAppExecutor:
    """Send WhatsApp messages via Meta Cloud API."""
    async def send_message(self, to: str, template: str, variables: dict) -> dict: ...
    async def send_document(self, to: str, document_url: str, caption: str) -> dict: ...

class EmailExecutor:
    """Send emails via SendGrid/Postmark."""
    async def send_email(self, to: str, subject: str, body_html: str) -> dict: ...

class CalendarExecutor:
    """Book meetings via Cal.com / Calendly API."""
    async def get_available_slots(self, date: str) -> list[dict]: ...
    async def book_slot(self, slot_id: str, name: str, email: str) -> dict: ...

class CrmWriteExecutor:
    """Live CRM field updates during the call (not post-call)."""
    async def update_field(self, record_id: str, module: str, field: str, value: str) -> dict: ...
```

#### 3.3.4 Pipeline Integration

Modify `VoicePipeline._register_function_handlers()` to:

1. Load agent's bound tools from `agent_tools` JOIN `tenant_tools`
2. Generate OpenAI-compatible function definitions from `parameters_schema`
3. Register a handler per tool that calls `ToolExecutor.execute()`
4. Return the executor response to the LLM as the function result

```python
# In VoicePipeline.__init__ or _build_pipeline:
agent_tools = await ToolService.get_agent_tools(db, agent_id, tenant_id)
for tool in agent_tools:
    func_def = tool.to_openai_function()  # name, description, parameters
    handler = self._make_tool_handler(tool)
    llm_service.register_function(func_def["name"], handler)
```

---

### Phase 4 — Campaign UI & Analytics
**Goal:** Full campaign management experience in the frontend.

#### 3.4.1 Frontend Pages

| Page | Route | Purpose |
|------|-------|---------|
| Campaign List | `/workspace/{tenantId}/campaigns` | Table of all campaigns with status chips, stats |
| Campaign Builder | `/workspace/{tenantId}/campaigns/new` | Step wizard: (1) Select Agent → (2) Configure CRM Source → (3) Map Variables → (4) Set Concurrency & Schedule → (5) Review & Launch |
| Campaign Detail | `/workspace/{tenantId}/campaigns/{id}` | Live dashboard: progress bar, call-by-call status, real-time stats, pause/resume controls |
| Contact Detail | `/workspace/{tenantId}/campaigns/{id}/contacts/{cid}` | Individual contact: call recording, transcript, extracted data, CRM sync status |
| Results Export | (action from detail page) | CSV download of all contacts + outcomes |

#### 3.4.2 Campaign Builder Wizard Steps

**Step 1 — Agent Selection**
- Dropdown of tenant's published outbound agents
- Preview: agent prompt, configured tools, extraction fields

**Step 2 — Contact Source**
- Tab: CRM | CSV Upload | Manual Entry
- CRM tab: Select module (Leads/Contacts), apply filters (status, owner, tags)
- Preview: row count + sample rows

**Step 3 — Variable Mapping**
- Left column: Agent's `{{variables}}` (parsed from prompt)
- Right column: CRM fields dropdown
- Auto-map by name similarity
- Test row preview: "Hi {{first_name}}, I'm calling about {{course_interest}}..."

**Step 4 — Write-Back Mapping**
- Left column: Agent's `extraction_fields` (defined on agent)
- Right column: CRM fields to write results into
- Example: `qualification_status` → `Lead_Status`, `preferred_date` → `Custom_Date_1`

**Step 5 — Call Settings**
- From number (dropdown of tenant's active phone numbers)
- Max concurrent calls (slider: 1–50)
- Calls per minute (1–30)
- Retry config (max attempts, retry delay)
- Calling window (time picker + timezone + weekdays)
- Schedule (now / scheduled datetime)

**Step 6 — Tool Configuration**
- Show tools bound to the selected agent
- Configure per-campaign overrides (e.g., WhatsApp template to use)

**Step 7 — Review & Launch**
- Summary card with all settings
- "Start Campaign" / "Schedule Campaign" button

#### 3.4.3 Live Dashboard

```
┌─────────────────────────────────────────────────┐
│  Campaign: "MBA Leads Q1"                       │
│  Agent: Admission Qualifier  │  Status: Running  │
├─────────────────────────────────────────────────┤
│  ████████████░░░░░░░░  234/500 (46.8%)          │
│                                                  │
│  ✅ Completed: 198   ❌ Failed: 12               │
│  📞 In Progress: 5   ⏳ Pending: 266            │
│  🔄 Retry Scheduled: 19                         │
│                                                  │
│  [Pause]  [Cancel]  [Export Results]             │
├─────────────────────────────────────────────────┤
│  Recent Calls (live feed)                        │
│  ┌────────┬───────────┬───────┬────────────────┐ │
│  │Contact │Phone      │Status │Duration │Result│ │
│  ├────────┼───────────┼───────┼────────────────┤ │
│  │John D. │+1415...   │✅     │2:34     │Qual. │ │
│  │Sarah M.│+1650...   │📞     │0:45     │...   │ │
│  │Mike R. │+1510...   │❌     │-        │No ans│ │
│  └────────┴───────────┴───────┴────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

### Phase 5 — Scaling & Hardening
**Goal:** Production-ready for 500+ concurrent calls across tenants.

#### 3.5.1 Horizontal Scaling

```
         ┌────────────────────────────────────────────────────┐
         │  Azure Service Bus                                 │
         │  DEV:  SphereVoice-dev-servicebus      (Basic SKU)         │
         │  PROD: SphereVoice-production-servicebus (Standard SKU)    │
         │  ├── SphereVoice-celery              (general workers)     │
         │  ├── SphereVoice-post-call           (general workers)     │
         │  ├── SphereVoice-crm-sync            (general workers)     │
         │  ├── SphereVoice-webhook-delivery     (general workers)    │
         │  ├── SphereVoice-campaign-calls       (session-enabled*)   │
         │  │   └── dead-letter sub-queue                     │
         │  ├── SphereVoice-campaign-writeback   (with DLQ)           │
         │  └── SphereVoice-crm-webhook-events   (real-time sync)     │
         │                                                    │
         │  * Sessions only in Standard SKU (production)      │
         └────────────────────┬───────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
 ┌────────▼─────┐   ┌────────▼─────┐   ┌────────▼─────┐
 │ Celery       │   │ Celery       │   │ Celery       │
 │ Worker Pod 1 │   │ Worker Pod 2 │   │ Worker Pod N │
 │ (4 threads)  │   │ (4 threads)  │   │ (4 threads)  │
 └──────────────┘   └──────────────┘   └──────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                    ┌─────────▼────────────┐
                    │  Redis               │
                    │  (result backend +   │
                    │   rate limit counters)│
                    └──────────────────────┘
                              │
                    ┌─────────▼────────────┐
                    │  LiveKit SFU         │
                    │  (SIP trunks)        │
                    └──────────────────────┘
```

- **Azure Service Bus** as sole message broker for all Celery workers (via Kombu `azureservicebus://` transport)
- **Two namespaces**: Dev (Basic SKU) and Production (Standard SKU) — same Terraform module, different environment vars
- **Celery worker pool**: Scale horizontally with `--concurrency=N`; competing consumers on ASB queues
- **Redis** (result backend only): Ephemeral rate-limit counters + semaphores; no broker duties
- **Per-campaign FIFO**: ASB sessions (`session_id=campaign_id`) ensure ordering — **production only** (Standard SKU)
- **Platform-wide guard**: Global max (e.g., 200 simultaneous calls) via Redis counter to protect LiveKit/SIP capacity
- **Dead letter queue**: ASB native DLQ per queue; failed messages auto-dead-lettered after max delivery attempts
- **Peek-lock**: At-least-once delivery; messages re-appear if worker crashes before ack

#### 3.5.2 Failure Handling

| Failure Mode | Handling |
|---|---|
| Call not answered | Mark `no_answer`, schedule retry |
| Busy signal | Mark `busy`, retry in `retry_delay_minutes` |
| Voicemail detected | Follow agent's `voicemail_detection` setting (hang up or record) |
| Pipeline crash | Auto-retry (existing voice_pipeline mechanism), then mark `failed` |
| CRM write-back fails | Retry 3x with exponential backoff, then mark `writeback_status=failed` |
| Campaign paused mid-flight | In-flight calls finish normally; no new calls dequeued |
| Worker pod crashes | ASB peek-lock timeout → message re-appears for another worker |

#### 3.5.3 Observability

- **Metrics** (extend existing `app.core.metrics`):
  - `SphereVoice_campaign_calls_total{campaign_id, status}` — counter
  - `SphereVoice_campaign_calls_active{tenant_id}` — gauge
  - `SphereVoice_campaign_call_duration_seconds` — histogram
  - `SphereVoice_campaign_crm_writeback_total{status}` — counter
  - `SphereVoice_campaign_queue_depth{campaign_id}` — gauge

- **Logging**: Structured logs with `campaign_id`, `contact_id`, `call_id` correlation
- **Alerts**: Campaign stall detection (no progress for 10+ min while status=running)

---

## 4. Data Flow — Full Call Lifecycle

```
1. CAMPAIGN CREATION
   User → Create Campaign → Select Agent + CRM Source + Mappings → Save (draft)

2. CONTACT LOADING
   User → "Load Contacts" →
   Campaign Worker → Zoho API (GET /crm/v6/Leads?criteria=...) →
   Snapshot rows into campaign_contacts (contact_data JSONB)

3. CAMPAIGN START
   User → "Start Campaign" →
   campaign.status = 'running' →
   Enqueue: campaign_orchestrator(campaign_id) → ASB queue

4. ORCHESTRATOR LOOP (Celery on ASB)
   For each pending contact (priority order):
     a. Check calling_window → skip if outside hours
     b. Acquire rate limiter token (calls_per_minute, via Redis counter)
     c. Acquire semaphore slot (max_concurrent, via Redis counter)
     d. Enqueue via CampaignQueue → ASB SphereVoice-campaign-calls (with session_id)

5. SINGLE CALL EXECUTION (Celery worker consuming from ASB)
     a. Load contact_data + variable_mapping
     b. Build dynamic_variables: { "first_name": "John", "course_interest": "MBA", ... }
     c. Call orchestrator.handle_outbound_call(agent_id, phone, from_number, dynamic_variables)
     d. VoicePipeline starts → agent speaks with full CRM context

6. IN-CALL TOOL EXECUTION
     Agent (LLM) decides to call a tool →
     e.g., send_whatsapp(to="+14155550101", template="admission_brochure") →
     ToolExecutor → WhatsAppExecutor → Meta Cloud API → ✅ Sent →
     Result returned to LLM: "WhatsApp brochure sent successfully" →
     Agent: "I've just sent the brochure to your WhatsApp."

7. CALL COMPLETION
     Pipeline ends → post_call worker:
     a. Run extraction (e.g., qualification_status="qualified", preferred_date="2026-04-15")
     b. Store in campaign_contacts.extracted_data
     c. Enqueue: campaign_crm_writeback(contact_id)

8. CRM WRITE-BACK
     Worker → Load writeback_mapping:
       extracted "qualification_status" → Zoho field "Lead_Status"
       extracted "preferred_date" → Zoho field "Custom_Date_1"
     → PUT /crm/v6/Leads/{record_id} → ✅ Synced
     → Update writeback_status = 'synced'

9. CAMPAIGN COMPLETION
     Orchestrator detects all contacts processed →
     campaign.status = 'completed' →
     Webhook: { "event": "campaign_completed", "campaign_id": "...", "stats": {...} }
```

---

## 5. Priority & Effort Estimates

| Phase | Scope | Dependencies | Recommended Sprint |
|-------|-------|---|---|
| **Phase 1** | Tenant Integration Framework + Zoho Webhooks | None | Sprint 1 (1 week) |
| **Phase 2** | Campaign Engine (DB + Workers + API) + Azure Service Bus queues | Phase 1 | Sprint 2–3 (2 weeks) |
| **Phase 3** | In-Call Tool Calling + ASAP trigger mode | Phase 1 | Sprint 2–3 (parallel with Phase 2) |
| **Phase 4** | Campaign UI & Analytics + Multi-integration UX | Phase 2 + 3 | Sprint 4–5 (2 weeks) |
| **Phase 5** | Scaling & Hardening + CRM sync unification | Phase 2 | Sprint 5–6 (1–2 weeks) |

**Critical Path:** Phase 1 → Phase 2 → Phase 4 (UI)  
**Parallel Track:** Phase 1 → Phase 3 (tool calling can be developed alongside Phase 2)  
**Key Addition:** Zoho webhook setup goes into Phase 1 (foundation for ASAP mode in Phase 3)

---

## 6. Key Design Decisions

### 6.1 Why snapshot CRM data into `campaign_contacts.contact_data`?

- **Call consistency**: If CRM data changes mid-campaign, in-flight calls aren't affected
- **Audit trail**: You can always see what data the agent had during the call
- **Performance**: No CRM API call per contact at dial-time; data is local
- **Offline resilience**: CRM downtime doesn't block the campaign

### 6.2 Why tenant-level tools instead of agent-level?

- A tenant configures WhatsApp once → all agents under that tenant can use it
- Agents only select which tools they need (via `agent_tools` binding)
- Credentials are managed at tenant level (single place to rotate keys)
- New agents automatically get access to the tenant's tool library

### 6.3 Why Celery + Azure Service Bus instead of direct async?

- **Durability**: ASB peek-lock ensures messages survive worker crashes (redelivery after lock timeout)
- **Horizontal scaling**: Add worker pods without code changes; ASB competing consumers
- **Dead letter queues**: Permanently failed tasks go to ASB DLQ — no custom error handling
- **Session ordering**: Per-campaign FIFO via `session_id=campaign_id` — prevents race conditions
- **Rate limiting**: Redis-based token bucket works across pods (Redis as result backend + counters)
- **Existing infra**: All 7 workers already use ASB via Kombu transport — campaign workers are just new task modules
- **Azure Monitor**: Queue depth, DLQ backlog, delivery latency visible in existing observability stack

### 6.4 Why not a separate dialer service?

The existing `CallOrchestrator.handle_outbound_call()` already handles SIP dial, LiveKit room creation, and pipeline startup. Wrapping it in a Celery task (routed through ASB) gives us queuing+retry+DLQ without duplicating orchestration logic.

### 6.5 Why two layers of ASB? (Kombu + direct SDK)

| Layer | When to use |
|---|---|
| **Celery/Kombu transport** | Standard task dispatch — fire-and-forget with retry. Used by all 7 existing workers and the campaign orchestrator/writeback workers. |
| **Direct ASB SDK** (`CampaignQueue`) | When you need ASB features Kombu doesn't expose: `scheduled_enqueue_time_utc`, `session_id`, DLQ inspection. Used specifically for campaign call scheduling. |

Both hit the same ASB namespace (`SphereVoice-dev-servicebus-ci`). This isn't duplication — it's choosing the right abstraction level per use case.

---

## 7. Example: Education Admission Campaign

**Scenario:** University wants to qualify MBA leads from Zoho CRM.

**Agent Setup:**
- Name: "MBA Admission Qualifier"
- Direction: outbound
- Prompt: "You are calling {{first_name}} about their interest in {{course_interest}}. Ask qualifying questions: budget, timeline, prior education..."
- Extraction fields: `qualification_status`, `budget_range`, `preferred_start_date`, `needs_scholarship`
- Tools enabled: `send_whatsapp` (admission brochure), `book_meeting` (campus tour via Cal.com), `send_email` (application link)

**Campaign Setup:**
- Source: Zoho CRM → Leads → Filter: `Lead_Status = "Not Contacted"` AND `Course_Interest is not null`
- Variable mapping: `first_name → First_Name`, `course_interest → Custom_Field_Course`
- Write-back mapping: `qualification_status → Lead_Status`, `budget_range → Budget_Field`, `preferred_start_date → Start_Date`
- Concurrency: 10 parallel calls
- Window: Mon–Fri 10:00–18:00 IST
- From number: +91-XXXXXXXXXX

**Runtime:**
1. 300 leads loaded from Zoho
2. Campaign starts, 10 calls at a time
3. Agent: "Hi John, I'm calling from XYZ University about your interest in the MBA program..."
4. Agent asks qualifying questions → LLM extracts answers
5. Student interested → Agent calls `send_whatsapp(brochure)` → Student gets PDF on WhatsApp
6. Student wants campus visit → Agent calls `book_meeting(slot)` → Cal.com booking confirmed
7. Call ends → extraction: `qualification_status=qualified, budget=15-20L, start=Aug 2026`
8. CRM write-back: Zoho Lead updated: `Lead_Status=Qualified`, `Budget=15-20L`, `Start_Date=Aug 2026`
9. Dashboard shows 234/300 completed, 85% qualification rate

---

## 8. Files to Create/Modify

### New Backend Files

```
backend/app/modules/campaigns/
  __init__.py
  models.py           — Campaign, CampaignContact models
  schemas.py          — Pydantic request/response schemas
  router.py           — Campaign CRUD + control endpoints
  service.py          — Business logic (create, start, pause, stats)
  rate_limiter.py     — Redis/ASB rate limiter + concurrency semaphore
  
backend/app/modules/tool_registry/
  __init__.py
  models.py           — TenantTool, AgentTool models
  schemas.py          — Tool definition schemas
  router.py           — Tool CRUD API
  service.py          — Tool resolution + execution dispatch
  executors/
    __init__.py
    whatsapp.py       — WhatsApp Cloud API executor
    email.py          — SendGrid/Postmark executor
    calendar.py       — Cal.com/Calendly executor
    crm_write.py      — Live CRM field update executor
    webhook.py        — Generic HTTP webhook executor

backend/app/modules/campaigns/queue.py  — CampaignQueue abstraction (ALREADY EXISTS — Redis or ASB)

backend/app/workers/
  campaign_orchestrator.py  — Main campaign loop worker
  campaign_call.py          — Single call execution worker
  campaign_writeback.py     — CRM write-back worker
  crm_webhook_sync.py       — Real-time Zoho webhook → cache sync + ASAP trigger
```

### Modified Backend Files

```
backend/app/modules/pipeline/voice_pipeline.py
  — Load agent tools from tool_registry
  — Register tool handlers alongside existing function handlers

backend/app/modules/pipeline/orchestrator.py
  — No changes (reuse handle_outbound_call as-is)

backend/app/modules/integrations/models.py
  — Add tenant_integrations table (or extend crm_integrations)

backend/app/modules/integrations/router.py
  — Add POST /crm/zoho/webhook endpoint (real-time notifications)

backend/app/modules/integrations/service.py
  — Register Zoho webhook notifications after OAuth connect
  — Add webhook HMAC verification helpers

backend/app/main.py
  — Register campaign router + tool_registry router

backend/app/workers/celery_app.py
  — Register new task modules (campaign_orchestrator, campaign_call, campaign_writeback, crm_webhook_sync)
  — Add zoho-webhook-renewal-daily beat schedule

backend/app/core/config.py
  — AZURE_SERVICE_BUS_CONNECTION_STRING already exists
  — CELERY_BROKER_BACKEND already supports 'servicebus'
  — No new queue config needed (campaigns use same ASB namespace)
```

### New Frontend Files

```
frontend/src/modules/campaigns/
  components/
    campaign-list.tsx
    campaign-builder/
      step-agent-select.tsx
      step-crm-source.tsx
      step-variable-mapping.tsx
      step-writeback-mapping.tsx
      step-call-settings.tsx
      step-tool-config.tsx
      step-review.tsx
    campaign-detail/
      campaign-dashboard.tsx
      campaign-contacts-table.tsx
      campaign-stats-cards.tsx
      contact-detail-dialog.tsx
  hooks/
    use-campaigns.ts
  types/
    index.ts
  lib/
    campaign-utils.ts

frontend/src/modules/integrations/
  components/
    integration-settings.tsx   — New: unified integration management page
    tool-library.tsx           — New: tenant tool configuration
```

### New Alembic Migrations

```
backend/alembic/versions/
  XXX_add_tenant_integrations.py
  XXX_add_campaigns.py
  XXX_add_tenant_tools.py
  XXX_add_agent_tools.py
```

### Terraform Changes Required

Add campaign queues to `infra/terraform/modules/servicebus/main.tf`:

```hcl
# ── Campaign calls queue (session-enabled in Standard SKU) ─────
resource "azurerm_servicebus_queue" "campaign_calls" {
  name         = "${var.queue_prefix}-campaign-calls"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 5
  lock_duration                        = "PT10M"   # 10 min — calls can take a while
  default_message_ttl                  = "P7D"
  dead_lettering_on_message_expiration = true

  # Sessions for per-campaign FIFO ordering (only works in Standard SKU)
  requires_session = var.sku == "Standard" ? true : false
}

# ── Campaign CRM writeback queue ──────────────────────────
resource "azurerm_servicebus_queue" "campaign_writeback" {
  name         = "${var.queue_prefix}-campaign-writeback"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 10   # More retries for flaky CRM APIs
  lock_duration                        = "PT5M"
  default_message_ttl                  = "P7D"
  dead_lettering_on_message_expiration = true
}

# ── CRM webhook events queue (real-time Zoho notifications) ──
resource "azurerm_servicebus_queue" "crm_webhook_events" {
  name         = "${var.queue_prefix}-crm-webhook-events"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 5
  lock_duration                        = "PT2M"   # Fast processing expected
  default_message_ttl                  = "P1D"    # Webhooks are time-sensitive
  dead_lettering_on_message_expiration = true
}
```

Apply to both environments:
```bash
cd infra/terraform/environments/dev && terraform apply
cd infra/terraform/environments/production && terraform apply
```

---

## 9. Addendum A — Zoho Webhook (Real-Time CRM Sync)

### Current State: Poll-Based Sync

Today the CRM sync is **poll-based** via a Celery beat task:

```
crm-incremental-sync: every 900s (15 minutes)
  → CrmCacheService.incremental_sync()
  → GET /crm/v6/Contacts?modified_since=<last_synced_at>
  → GET /crm/v6/Leads?modified_since=<last_synced_at>
  → Upsert into crm_contacts_cache
```

**Problem:** A new lead in Zoho can take up to 15 minutes before SphereVoice knows about it. For the "ASAP call" use case, this is too slow.

### Solution: Zoho Notification Webhooks

Register a Zoho webhook during OAuth integration so Zoho pushes changes to us in real-time.

#### 9.1 Setup During OAuth Connect

After successful OAuth callback (`handle_zoho_callback`), automatically register a Zoho notification channel:

```python
# In IntegrationService.handle_zoho_callback(), after token exchange:

# Register Zoho webhook notifications
async def _register_zoho_notifications(client: ZohoCrmClient, integration_id: UUID):
    """Subscribe to Zoho CRM change notifications via their Notifications API."""
    webhook_url = f"{settings.BACKEND_URL}/api/v1/integrations/crm/zoho/webhook"
    
    # Subscribe to Contacts and Leads create/update/delete
    await client.post("/crm/v6/actions/watch", json={
        "watch": [
            {
                "channel_id": str(integration_id),  # unique per integration
                "events": ["Contacts.create", "Contacts.edit", "Contacts.delete",
                           "Leads.create", "Leads.edit", "Leads.delete"],
                "channel_expiry": None,  # Zoho auto-renews for 24h; we re-register daily
                "notify_url": webhook_url,
                "token": _sign_webhook_token(integration_id),  # HMAC for verification
            }
        ]
    })
```

#### 9.2 New Webhook Endpoint

```python
@router.post("/crm/zoho/webhook")
async def zoho_webhook_notification(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive real-time change notifications from Zoho CRM.
    
    Zoho sends:
    {
        "module": "Leads",
        "operation": "create",
        "channel_id": "<integration_id>",
        "ids": ["5847395000000398001", "5847395000000398002"],
        "token": "<hmac_token>"
    }
    """
    body = await request.json()
    
    # 1. Verify HMAC token (prevents spoofed webhooks)
    if not _verify_webhook_token(body.get("channel_id"), body.get("token")):
        return Response(status_code=401)
    
    integration_id = UUID(body["channel_id"])
    record_ids = body.get("ids", [])
    module = body.get("module")  # "Contacts" or "Leads"
    operation = body.get("operation")  # "create", "edit", "delete"
    
    # 2. Enqueue cache update (don't block the webhook response)
    crm_webhook_sync.delay(
        integration_id=str(integration_id),
        module=module,
        operation=operation,
        record_ids=record_ids,
    )
    
    # 3. Check if any ASAP campaigns are watching this module
    #    (handled inside the worker — see Addendum C)
    
    return Response(status_code=200)
```

#### 9.3 New Celery Worker: `crm_webhook_sync`

```python
@celery_app.task(name="crm.webhook_sync", bind=True)
def crm_webhook_sync(self, integration_id: str, module: str, operation: str, record_ids: list[str]):
    """Process a Zoho webhook notification — sync specific records into cache.
    
    Runs as a standard Celery task on ASB (via Kombu transport).
    """
    # 1. Fetch full record data from Zoho: GET /crm/v6/{module}?ids={id1,id2,...}
    # 2. Upsert into crm_contacts_cache (same as incremental sync, but targeted)
    # 3. If operation == "delete": mark cache rows as deleted
    # 4. If operation == "create" and ASAP campaign exists:
    #    → Enqueue via CampaignQueue.enqueue() → ASB SphereVoice-campaign-calls queue
```

#### 9.4 Webhook Renewal (Beat Task)

Zoho webhooks expire every 24 hours. Add a daily beat task:

```python
# In celery_app.conf.beat_schedule:
"zoho-webhook-renewal-daily": {
    "task": "crm.renew_zoho_webhooks",
    "schedule": 72000.0,  # Every 20 hours (before 24h expiry)
},
```

#### 9.5 Hybrid Approach

Keep **both** modes:
- **Webhook (primary):** Real-time for <5s latency on new leads
- **Incremental poll (fallback):** Every 15 min as safety net (catches missed webhooks, webhook downtime)

This means you never lose data — the poll fills any gaps.

---

## 10. Addendum B — Azure Service Bus Architecture (Implemented)

### Current Architecture

The project has already migrated **all** Celery workers to Azure Service Bus as the message broker. Redis remains only as the result backend and for ephemeral rate-limit counters.

```
Celery (all workers) → Azure Service Bus (broker, via Kombu azureservicebus:// transport)
Redis → result backend only + ephemeral counters
```

**Configuration (already in place):**

```python
# backend/app/core/config.py
CELERY_BROKER_BACKEND: Literal["redis", "servicebus"] = "redis"  # "servicebus" in cloud envs
AZURE_SERVICE_BUS_CONNECTION_STRING: str = ""  # set in .env for cloud
AZURE_SERVICE_BUS_QUEUE_PREFIX: str = "SphereVoice"   # queues named SphereVoice-<task>

# backend/.env (current)
CELERY_BROKER_BACKEND=servicebus
AZURE_SERVICE_BUS_CONNECTION_STRING=Endpoint=sb://SphereVoice-dev-servicebus-ci.servicebus.windows.net/;...
```

**Celery broker resolution (`celery_app.py`):**
```python
def _resolve_broker_url() -> str:
    if settings.CELERY_BROKER_BACKEND == "servicebus":
        return f"azureservicebus://{settings.AZURE_SERVICE_BUS_CONNECTION_STRING}"
    return settings.CELERY_BROKER_URL  # Redis fallback for local dev
```

### Two Environments — Dev vs Production

| Property | Dev | Production |
|---|---|---|
| **Namespace** | `SphereVoice-dev-servicebus` | `SphereVoice-production-servicebus` |
| **SKU** | Basic | **Standard** |
| **Location** | Central India | Central India |
| **Sessions** | ❌ Not supported | ✅ Supported (per-campaign FIFO) |
| **Dead-letter** | ✅ Supported | ✅ Supported |
| **Topics** | ❌ Not supported | ✅ Supported |
| **Duplicate detection** | ❌ Not supported | ✅ Supported |
| **Public network** | ✅ Enabled | ❌ Private endpoint only |
| **Terraform output** | `cd infra/terraform/environments/dev && terraform output -raw servicebus_connection_string` | Same for `/environments/production` |

**Important:** Campaign session-based ordering (`session_id=campaign_id` for FIFO) **only works in production** because Basic SKU doesn't support sessions. In dev, calls are processed without ordering guarantees — acceptable for testing.

### Queue Topology (Both Environments)

```
┌────────────────────────────────────────────────────────────────────┐
│  Azure Service Bus                                                 │
│  ├── DEV:  SphereVoice-dev-servicebus      (Basic SKU, Central India)     │
│  └── PROD: SphereVoice-production-servicebus (Standard SKU, Central India) │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Existing Queues (Terraform: infra/terraform/modules/servicebus):  │
│  ├── SphereVoice-celery            — default queue (Kombu fallback)        │
│  ├── SphereVoice-post-call         — post-call extraction (5 retries)     │
│  ├── SphereVoice-embeddings        — KB embedding generation (5 retries)  │
│  ├── SphereVoice-webhook-delivery  — webhook dispatch (10 retries)        │
│  ├── SphereVoice-crm-sync          — initial + incremental sync (5 retries)│
│  └── SphereVoice-website-crawl     — KB crawling (3 retries)              │
│                                                                    │
│  Campaign Queues (TO BE ADDED to Terraform — see below):          │
│  ├── SphereVoice-campaign-calls    — session-enabled* (prod only), DLQ    │
│  ├── SphereVoice-campaign-writeback— CRM write-back, DLQ                  │
│  └── SphereVoice-crm-webhook-events— real-time Zoho notifications         │
│                                                                    │
│  * session_id = campaign_id for FIFO ordering per campaign        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Terraform: Add Campaign Queues

Add to `infra/terraform/modules/servicebus/main.tf`:

```hcl
# ── Campaign calls queue (session-enabled in Standard SKU) ─────
resource "azurerm_servicebus_queue" "campaign_calls" {
  name         = "${var.queue_prefix}-campaign-calls"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 5
  lock_duration                        = "PT10M"   # 10 min — calls can take a while
  default_message_ttl                  = "P7D"
  dead_lettering_on_message_expiration = true

  # Sessions for per-campaign FIFO ordering (only works in Standard SKU)
  requires_session = var.sku == "Standard" ? true : false
}

# ── Campaign CRM writeback queue ──────────────────────────
resource "azurerm_servicebus_queue" "campaign_writeback" {
  name         = "${var.queue_prefix}-campaign-writeback"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 10   # More retries for flaky CRM APIs
  lock_duration                        = "PT5M"
  default_message_ttl                  = "P7D"
  dead_lettering_on_message_expiration = true
}

# ── CRM webhook events queue (real-time Zoho notifications) ──
resource "azurerm_servicebus_queue" "crm_webhook_events" {
  name         = "${var.queue_prefix}-crm-webhook-events"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 5
  lock_duration                        = "PT2M"   # Fast processing expected
  default_message_ttl                  = "P1D"    # Webhooks are time-sensitive
  dead_lettering_on_message_expiration = true
}
```

### Two Layers of ASB Usage

| Layer | Purpose | Implementation |
|---|---|---|
| **Celery + Kombu transport** | All standard task dispatch (7 existing workers + new campaign workers) | `celery_app.py` resolves `azureservicebus://` as broker; Kombu handles serialization, routing, acks |
| **Direct ASB SDK** (`CampaignQueue`) | Campaign-specific features Kombu doesn't expose | `backend/app/modules/campaigns/queue.py` — scheduled delivery, session ordering, DLQ inspection |

### CampaignQueue Abstraction (Already Implemented)

```python
# backend/app/modules/campaigns/queue.py

class CampaignQueue(ABC):
    async def enqueue(self, campaign_id, contact_payload, *, scheduled_at=None) -> str: ...
    async def dead_letter_count(self, campaign_id) -> int: ...
    async def close(self) -> None: ...

class RedisCampaignQueue(CampaignQueue):         # Local dev fallback (CELERY_BROKER_BACKEND=redis)
class ServiceBusCampaignQueue(CampaignQueue):    # Cloud — sessions*, DLQ, scheduled delivery

def get_campaign_queue() -> CampaignQueue:
    if settings.CELERY_BROKER_BACKEND == "servicebus":
        return ServiceBusCampaignQueue()
    return RedisCampaignQueue()
```

**Note:** `ServiceBusCampaignQueue` sets `session_id=campaign_id` on messages. This only works in production (Standard SKU). In dev (Basic SKU), session_id is ignored and messages are processed in arbitrary order.

### Why ASB for Everything (Not Just Campaigns)

1. **Single broker**: One Azure resource to monitor, scale, and secure — no Redis broker to maintain in cloud
2. **At-least-once delivery**: ASB peek-lock is more robust than Redis `acks_late` (Redis loses messages on crash)
3. **Dead letter queues**: Every queue gets a DLQ — failed embeddings, webhook deliveries, and CRM syncs are all recoverable
4. **Azure Monitor integration**: Queue depth, delivery latency, and DLQ backlog appear in the existing Azure observability stack
5. **Managed scaling**: ASB Standard tier handles the throughput of all 7 existing workers + campaigns
6. **Local dev unchanged**: `CELERY_BROKER_BACKEND=redis` (default) → developers use Redis locally with zero config

---

## 11. Addendum C — ASAP Queue: Instant Lead-to-Call

### Use Case

A tenant wants: "When a new lead enters my Zoho CRM, call them within 30 seconds."

This is the **speed-to-lead** use case — studies show responding within 5 minutes increases conversion 10x.

### Architecture

```
Zoho CRM                    SphereVoice
┌──────────┐     POST       ┌──────────────────────────┐
│ New Lead  │───webhook────▶│ /crm/zoho/webhook        │
│ Created   │   (<5 sec)    │                          │
└──────────┘                │  1. Verify HMAC          │
                            │  2. Upsert cache         │
                            │  3. Check ASAP triggers  │
                            └──────────┬───────────────┘
                                       │
                       ┌───────────────▼───────────────────┐
                       │ Azure Service Bus (SphereVoice-dev-servicebus-ci) │
                       │ SphereVoice-campaign-calls queue                    │
                       │   session_id = campaign_id (FIFO)           │
                       └───────────────┬───────────────────┘
                                       │ <1 sec
                       ┌───────────────▼───────────────┐
                       │ Campaign Call Worker           │
                       │ 1. Load contact data           │
                       │ 2. Build dynamic_variables     │
                       │ 3. handle_outbound_call()      │
                       │ 4. Agent speaks with context   │
                       └───────────────────────────────┘
                       
Total latency: Zoho webhook (~5s) + queue (<1s) + SIP dial (~3s) = ~9 seconds
```

### Data Model: ASAP Triggers

Add to the `campaigns` table (or a new `campaign_triggers` table):

```sql
-- New fields on campaigns table:
ALTER TABLE campaigns ADD COLUMN trigger_mode VARCHAR(20) NOT NULL DEFAULT 'manual';
  -- 'manual'   — start/pause controlled by user
  -- 'asap'     — auto-trigger from CRM webhook (always-on)
  -- 'scheduled' — one-time future start

ALTER TABLE campaigns ADD COLUMN trigger_config JSONB DEFAULT '{}';
  -- For ASAP mode:
  -- {
  --   "source_module": "Leads",           -- which Zoho module to watch
  --   "filter": { "Lead_Status": "New" }, -- optional: only trigger for matching records
  --   "max_daily_calls": 100,             -- safety limit
  --   "active_hours": { "start": "09:00", "end": "18:00", "timezone": "Asia/Kolkata" },
  --   "queue_outside_hours": true         -- if true, queue for next window; if false, skip
  -- }
```

### ASAP Flow

```python
# In crm_webhook_sync worker (from Addendum A):

async def _check_asap_triggers(db, integration_id, module, new_record_ids):
    """Check if any ASAP campaigns should auto-dial these new records."""
    
    # Find ASAP campaigns for this tenant + module
    campaigns = await db.execute(
        select(Campaign).where(
            Campaign.tenant_id == integration.tenant_id,
            Campaign.trigger_mode == "asap",
            Campaign.status == "running",  # ASAP campaigns stay in 'running' state
            Campaign.source_config["module"].astext == module,
        )
    )
    
    for campaign in campaigns.scalars():
        for record_id in new_record_ids:
            # Load full record from cache
            contact_cache = await CrmCacheService.get_by_zoho_id(db, record_id)
            
            # Apply campaign filter (e.g., Lead_Status == "New")
            if not _matches_filter(contact_cache, campaign.trigger_config.get("filter")):
                continue
            
            # Check daily limit
            if await _daily_limit_reached(campaign):
                continue
            
            # Check calling window
            if not _in_calling_window(campaign.trigger_config):
                if campaign.trigger_config.get("queue_outside_hours"):
                    # Schedule for next window opening
                    next_window = _next_window_start(campaign.trigger_config)
                    await campaign_queue.enqueue_call(
                        campaign_id=str(campaign.id),
                        contact_id=str(contact_cache.id),
                        priority="asap",
                        scheduled_at=next_window,
                    )
                continue
            
            # Create campaign_contact row
            contact = CampaignContact(
                campaign_id=campaign.id,
                tenant_id=campaign.tenant_id,
                phone_number=contact_cache.phone_e164 or contact_cache.mobile_e164,
                crm_record_id=record_id,
                crm_module=module,
                contact_data=contact_cache.raw_data,
                status="queued",
                priority=100,  # High priority
            )
            db.add(contact)
            await db.flush()
            
            # Enqueue to ASAP priority queue
            await campaign_queue.enqueue_call(
                campaign_id=str(campaign.id),
                contact_id=str(contact.id),
                priority="asap",
            )
```

### Campaign Modes Summary

| Mode | Trigger | Use Case |
|---|---|---|
| **Manual (batch)** | User clicks "Start Campaign" | Bulk outreach: "Call 500 leads from Q1 list" |
| **ASAP (real-time)** | CRM webhook notification | Speed-to-lead: "Call every new lead within 30 seconds" |
| **Scheduled** | Cron / one-time datetime | Planned campaigns: "Start calling Monday 9am" |

### Safety Guards for ASAP Mode

1. **Daily call limit** (`max_daily_calls`): Prevent runaway costs
2. **Calling window** (`active_hours`): No 3am calls
3. **Duplicate check**: Don't call the same phone number twice in 24h
4. **Concurrency limit**: Same `max_concurrent` applies (shared with batch campaigns)
5. **Pause/kill switch**: ASAP campaigns can be paused instantly via the UI
6. **DNC check**: Applied before every dial, same as batch

---

## 12. Addendum D — Multiple Integrations Per Tenant

### Updated Constraint

The strategy doc's Phase 1 `tenant_integrations` table had `UNIQUE (tenant_id, category, provider)` — this allows only **one** of each provider per tenant. Update to allow **multiple** integrations per category:

```sql
-- REMOVE: UNIQUE (tenant_id, category, provider)
-- ADD: allow multiple of same type, differentiated by name

CREATE TABLE tenant_integrations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name          VARCHAR(255) NOT NULL,    -- user-given name: "Sales Zoho CRM", "Support Zoho CRM"
  category      VARCHAR(50) NOT NULL,     -- 'crm', 'calendar', 'messaging', 'email'
  provider      VARCHAR(100) NOT NULL,    -- 'zoho_crm', 'hubspot', 'cal_com', etc.
  status        VARCHAR(20) NOT NULL DEFAULT 'connected',
  credentials_encrypted TEXT,
  config        JSONB NOT NULL DEFAULT '{}',
  last_synced_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  UNIQUE (tenant_id, name)  -- names must be unique within a tenant
);
```

### Use Cases for Multiple Integrations

| Scenario | Integrations |
|---|---|
| Sales + Support CRMs | Two Zoho CRM orgs (different credentials) |
| Multi-region | Zoho IN datacenter + Zoho EU datacenter |
| CRM + Calendar + Messaging | Zoho CRM + Cal.com + WhatsApp + SendGrid |
| Multiple WhatsApp business accounts | WhatsApp Business #1 (sales) + #2 (support) |

### Impact on Campaigns

When creating a campaign, the user picks **which integration** to use as the data source:

```
Campaign Builder → Step 2 (Contact Source):
  ┌─────────────────────────────────────────┐
  │ Select CRM Source                        │
  │                                          │
  │  ● Sales Zoho CRM (Zoho - 4,200 leads) │
  │  ○ Support Zoho CRM (Zoho - 890 leads) │
  │  ○ HubSpot Marketing (HubSpot - 12,000)│
  │                                          │
  │ Module: [Leads ▼]                        │
  │ Filter: Lead_Status = "Not Contacted"    │
  └─────────────────────────────────────────┘
```

The `campaigns.source_config` JSONB already has `integration_id` — no schema change needed.

### Migration from Existing `crm_integrations`

The existing `crm_integrations` table has no unique constraint on `(tenant_id, provider)`, so it already supports multiple Zoho connections per tenant. The plan:

1. **Phase 1:** Create `tenant_integrations` for new provider types (calendar, messaging, email)
2. **Phase 1:** Keep `crm_integrations` as-is for Zoho (it works)
3. **Phase 4 (unification):** Add `tenant_integration_id` FK to `crm_integrations` to bridge them
4. **Future:** Migrate all CRM logic to use `tenant_integrations` as the single registry

---

## 13. Addendum E — CRM Sync Architecture Summary

### Three Sync Modes (Layered)

```
Mode 1: INITIAL SYNC (on OAuth connect)
  Trigger: Post-OAuth callback
  Worker:  initial_crm_sync (Celery)
  Flow:    GET /crm/v6/Contacts (all pages) → crm_contacts_cache
           GET /crm/v6/Leads (all pages) → crm_contacts_cache
  Latency: Minutes (depends on record count)
  
Mode 2: INCREMENTAL POLL (every 15 min)
  Trigger: Celery Beat schedule
  Worker:  incremental_crm_sync (Celery)
  Flow:    GET /crm/v6/Contacts?modified_since=<last_synced_at>
           GET /crm/v6/Leads?modified_since=<last_synced_at>
           → Upsert changed records into crm_contacts_cache
  Latency: 0–15 minutes
  Purpose: Safety net / catch missed webhooks

Mode 3: REAL-TIME WEBHOOK (new — from Addendum A)
  Trigger: Zoho notification → POST /crm/zoho/webhook
  Worker:  crm_webhook_sync (Celery or ASB)
  Flow:    Zoho pushes record IDs → worker fetches full records
           → Upsert into crm_contacts_cache
           → Check ASAP campaign triggers
  Latency: <5 seconds
  Purpose: Real-time for speed-to-lead
```

### Data Flow Diagram

```
                    Zoho CRM
                    ┌──────────────────┐
                    │                  │
          ┌────────┤ Contacts / Leads ├────────┐
          │        │                  │        │
          │        └─────────┬────────┘        │
          │                  │                 │
     (initial +          (webhook              │
     incremental)       notification)          │
          │                  │                 │
          ▼                  ▼                 │
   ┌─────────────┐  ┌──────────────┐          │
   │ Celery Beat │  │ POST         │          │
   │ every 15min │  │ /crm/webhook │          │
   └──────┬──────┘  └──────┬───────┘          │
          │                │                   │
          ▼                ▼                   │
   ┌─────────────────────────────┐             │
   │     crm_contacts_cache     │             │
   │  (PostgreSQL, RLS-scoped)  │             │
   │  Indexed: phone_e164,      │             │
   │  mobile_e164, email, name  │             │
   └──────────┬────────────────┘              │
              │                                │
    ┌─────────┼──────────┐                     │
    │         │          │                     │
    ▼         ▼          ▼                     │
 Inbound   Campaign   Frontend                │
 Caller    Contact    Contact                  │
 Enrichment Loading   Browser                  │
    │                                          │
    │      Post-Call Write-Back                 │
    │      ┌─────────────┐                     │
    └─────▶│ Zoho API    │ PUT /crm/v6/...    │
           │ write-back  │─────────────────────┘
           └─────────────┘
```

---

## 14. Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Telephony cost spike (500 simultaneous calls) | High | Platform-wide max concurrent limit; per-tenant billing alerts |
| CRM API rate limits (Zoho: 100 req/min/org) | Medium | Batch CRM reads at load time; write-back queue with backoff |
| Call quality degradation at scale | High | LiveKit SFU scaling; monitor MOS scores; auto-pause if quality drops |
| Stale CRM data during long campaigns | Low | Contact data snapshotted at load; option to refresh before retry |
| Tool execution latency (WhatsApp, email) | Medium | Fire-and-forget with async confirmation; timeout after 10s |
| DNC/compliance violations | Critical | DNC list check before each dial; calling window enforcement; country-specific rules |
| Zoho webhook downtime / missed events | Medium | Incremental poll (15 min) as fallback catches missed webhooks; idempotent upsert |
| Azure Service Bus unavailable | High | All workers affected (ASB is sole broker); ASB has 99.9% SLA; `CELERY_BROKER_BACKEND=redis` as emergency fallback |
| ASAP runaway (webhook storm creates 1000 calls) | High | `max_daily_calls` per ASAP campaign; global platform concurrency guard; rate limiter |
| Multiple CRM integrations credential confusion | Low | Each campaign explicitly references `integration_id`; UI shows integration name |

---

## 15. Compliance Considerations

- **Do Not Call (DNC)**: Check against tenant-managed DNC list before each dial
- **Calling Windows**: Enforce per-timezone restrictions (e.g., TCPA in US: 8am–9pm local)
- **Consent Tracking**: `campaign_contacts.consent_status` field (future Phase 5+)
- **Recording Disclosure**: Agent prompt should include recording notice per local law
- **GDPR**: CRM data snapshots follow same retention policy as call records

---

## 16. Addendum F — Do Not Call (DNC) Management

### Overview

DNC compliance is a **Phase 1 requirement** — every outbound dial must check against a tenant-managed suppression list. Violations can result in significant legal penalties (FTC fines up to $50,000+ per call in the US).

### Data Model

```sql
CREATE TABLE dnc_entries (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  phone_number  VARCHAR(30) NOT NULL,  -- E.164 normalized
  source        VARCHAR(50) NOT NULL DEFAULT 'manual',
    -- 'manual'     — added via UI or API
    -- 'import'     — bulk CSV import
    -- 'opt_out'    — requestd during call (via agent tool)
    -- 'complaint'  — reported complaint
    -- 'bounce'     — number invalid/disconnected
  reason        TEXT,                   -- optional note
  added_by      UUID REFERENCES users(id),
  expires_at    TIMESTAMPTZ,            -- NULL = permanent; some regulations allow expiry
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  UNIQUE (tenant_id, phone_number)
);
-- RLS: tenant_id = current_setting('app.current_tenant_id')
-- Index: phone_number (for fast lookup)
CREATE INDEX idx_dnc_phone ON dnc_entries(phone_number);
CREATE INDEX idx_dnc_tenant_phone ON dnc_entries(tenant_id, phone_number);
```

### API Endpoints

```
GET    /api/v1/dnc                  — List DNC entries (paginated, searchable)
POST   /api/v1/dnc                  — Add single phone number
POST   /api/v1/dnc/import           — Bulk import from CSV
DELETE /api/v1/dnc/{id}             — Remove entry (with audit log)
DELETE /api/v1/dnc/phone/{number}   — Remove by phone number

GET    /api/v1/dnc/check/{number}   — Check if number is on DNC list (internal use)
```

### Import Flow

```python
@router.post("/dnc/import")
async def import_dnc_csv(
    file: UploadFile,
    source: str = "import",
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(require_tenant),
):
    """
    CSV format: phone_number,reason (header optional)
    Max file size: 10MB (~200k numbers)
    
    Returns: { "imported": 15234, "duplicates": 123, "invalid": 45 }
    """
```

### Pre-Dial Check Integration

In `campaign_call_single` worker, **before** calling `handle_outbound_call()`:

```python
async def _check_dnc(db: AsyncSession, tenant_id: UUID, phone_number: str) -> bool:
    """Return True if number is on DNC list (should NOT be called)."""
    normalized = normalize_e164(phone_number)
    result = await db.execute(
        select(DncEntry.id).where(
            DncEntry.tenant_id == tenant_id,
            DncEntry.phone_number == normalized,
            or_(DncEntry.expires_at.is_(None), DncEntry.expires_at > func.now()),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None

# In call_single_contact task:
if await _check_dnc(db, contact.tenant_id, contact.phone_number):
    contact.status = "skipped"
    contact.skip_reason = "dnc"
    await db.commit()
    return  # Do not dial
```

### In-Call Opt-Out Tool

Register a built-in tool `add_to_dnc` that agents can call when customer requests:

```python
# Tool definition
{
    "name": "add_to_dnc",
    "description": "Add the current caller to the Do Not Call list. Use when customer explicitly requests to stop receiving calls.",
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Brief reason for opt-out"
            }
        }
    }
}

# Handler
async def handle_add_to_dnc(arguments: dict, call_context: CallContext):
    await DncService.add(
        db=call_context.db,
        tenant_id=call_context.tenant_id,
        phone_number=call_context.from_number,
        source="opt_out",
        reason=arguments.get("reason", "Customer requested during call"),
    )
    return {"success": True, "message": "Number added to Do Not Call list"}
```

### Files to Create

```
backend/app/modules/dnc/
  __init__.py
  models.py       — DncEntry model
  schemas.py      — Pydantic schemas
  router.py       — CRUD + import endpoints
  service.py      — check_dnc, add, bulk_import
```

### Alembic Migration

```
backend/alembic/versions/
  XXX_add_dnc_entries.py
```

---

## 17. Addendum G — Live Dashboard Real-Time Updates

### Overview

The campaign detail dashboard (Phase 4) displays real-time call progress. Frontend needs live updates without polling.

### Architecture

Use **Server-Sent Events (SSE)** for simplicity and broad browser support. WebSockets are overkill for one-way server→client updates.

```
┌────────────────┐                    ┌──────────────────┐
│    Frontend    │                    │     Backend      │
│   (Dashboard)  │                    │                  │
│                │  GET /campaigns/   │                  │
│                │  {id}/events       │                  │
│                │ ────────────────▶  │  SSE endpoint    │
│                │                    │  (keep-alive)    │
│                │  ◀──────────────── │                  │
│                │  event: call_start │                  │
│                │  data: {...}       │                  │
│                │                    │                  │
│                │  ◀──────────────── │                  │
│                │  event: call_end   │                  │
│                │  data: {...}       │                  │
│                │                    │                  │
│                │  ◀──────────────── │                  │
│                │  event: stats      │                  │
│                │  data: {...}       │                  │
└────────────────┘                    └──────────────────┘
```

### Backend SSE Endpoint

```python
@router.get("/{campaign_id}/events")
async def campaign_events(
    campaign_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    SSE stream for real-time campaign updates.
    
    Events:
      - call_started: { contact_id, phone_number, started_at }
      - call_ended:   { contact_id, status, duration, extracted_data }
      - stats:        { completed, failed, in_progress, pending } (every 5s)
      - campaign_status: { status } (when paused/completed/cancelled)
    """
    # Verify access
    campaign = await CampaignService.get(db, campaign_id)
    if campaign.tenant_id != user.tenant_id:
        raise HTTPException(403)
    
    async def event_generator():
        pubsub = redis.pubsub()
        channel = f"campaign:{campaign_id}:events"
        await pubsub.subscribe(channel)
        
        try:
            # Send initial stats
            stats = await CampaignService.get_stats(db, campaign_id)
            yield f"event: stats\ndata: {json.dumps(stats)}\n\n"
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"{message['data']}\n\n"
                    
                # Periodic stats refresh (every 5 messages or 5 seconds)
                # ...
                
        finally:
            await pubsub.unsubscribe(channel)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

### Publishing Events

In `campaign_call_single` worker:

```python
async def _publish_event(campaign_id: UUID, event_type: str, data: dict):
    """Publish event to Redis pub/sub for SSE distribution."""
    channel = f"campaign:{campaign_id}:events"
    message = f"event: {event_type}\ndata: {json.dumps(data)}"
    await redis.publish(channel, message)

# Usage in worker:
await _publish_event(campaign_id, "call_started", {
    "contact_id": str(contact.id),
    "phone_number": contact.phone_number,
    "started_at": datetime.utcnow().isoformat(),
})

# On completion:
await _publish_event(campaign_id, "call_ended", {
    "contact_id": str(contact.id),
    "status": contact.status,
    "duration": call.duration_seconds,
    "extracted_data": contact.extracted_data,
})
```

### Frontend Hook

```typescript
// frontend/src/modules/campaigns/hooks/use-campaign-events.ts

export function useCampaignEvents(campaignId: string) {
  const [events, setEvents] = useState<CampaignEvent[]>([]);
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [status, setStatus] = useState<CampaignStatus>('running');

  useEffect(() => {
    const eventSource = new EventSource(
      `/api/v1/campaigns/${campaignId}/events`,
      { withCredentials: true }
    );

    eventSource.addEventListener('call_started', (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => [...prev.slice(-99), { type: 'started', ...data }]);
    });

    eventSource.addEventListener('call_ended', (e) => {
      const data = JSON.parse(e.data);
      setEvents((prev) => 
        prev.map((ev) => 
          ev.contact_id === data.contact_id ? { ...ev, ...data, type: 'ended' } : ev
        )
      );
    });

    eventSource.addEventListener('stats', (e) => {
      setStats(JSON.parse(e.data));
    });

    eventSource.addEventListener('campaign_status', (e) => {
      setStatus(JSON.parse(e.data).status);
    });

    return () => eventSource.close();
  }, [campaignId]);

  return { events, stats, status };
}
```

### Fallback: Polling

For environments where SSE doesn't work (some proxies), provide a polling fallback:

```typescript
// Poll every 3 seconds when SSE fails
const { data: stats } = useQuery({
  queryKey: ['campaign-stats', campaignId],
  queryFn: () => fetchCampaignStats(campaignId),
  refetchInterval: sseConnected ? false : 3000,
});
```

---

## 18. Addendum H — Contact Deduplication Strategy

### Overview

Prevent calling the same phone number multiple times across campaigns or within the same campaign.

### Three Levels of Deduplication

| Level | Scope | Rule | Implementation |
|-------|-------|------|----------------|
| **1. Within Campaign** | Same campaign | Phone number appears once | `UNIQUE (campaign_id, phone_number)` on `campaign_contacts` |
| **2. Active Calls** | Platform-wide | Don't dial number currently in a call | Redis set `active_calls:{phone}` with TTL |
| **3. Recent History** | Tenant-wide, 24h | Don't dial same number twice in 24h | Query `calls` table with time window |

### Level 1: Campaign-Level Unique Constraint

```sql
-- Add to campaign_contacts table:
ALTER TABLE campaign_contacts 
  ADD CONSTRAINT uq_campaign_phone UNIQUE (campaign_id, phone_number);
```

When loading contacts from CRM, duplicates are caught at insert:

```python
async def load_contacts(campaign: Campaign, crm_rows: list[dict]):
    for row in crm_rows:
        phone = normalize_e164(row.get("Phone") or row.get("Mobile"))
        if not phone:
            continue
        
        contact = CampaignContact(
            campaign_id=campaign.id,
            tenant_id=campaign.tenant_id,
            phone_number=phone,
            crm_record_id=row["id"],
            contact_data=row,
        )
        try:
            db.add(contact)
            await db.flush()
        except IntegrityError:
            await db.rollback()
            # Duplicate phone in this campaign — skip
            stats["duplicates"] += 1
```

### Level 2: Active Call Guard

```python
# In campaign_call_single worker, before dialing:

async def _is_currently_in_call(redis: Redis, phone_number: str) -> bool:
    """Check if this number is already in an active call (any campaign)."""
    return await redis.exists(f"active_call:{phone_number}")

async def _mark_call_active(redis: Redis, phone_number: str, call_id: str):
    """Mark number as in active call. TTL = max call duration (30 min)."""
    await redis.setex(f"active_call:{phone_number}", 1800, call_id)

async def _mark_call_ended(redis: Redis, phone_number: str):
    """Remove active call marker."""
    await redis.delete(f"active_call:{phone_number}")

# Usage:
if await _is_currently_in_call(redis, contact.phone_number):
    contact.status = "retry_scheduled"
    contact.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
    await db.commit()
    return

await _mark_call_active(redis, contact.phone_number, str(call.id))
try:
    await orchestrator.handle_outbound_call(...)
finally:
    await _mark_call_ended(redis, contact.phone_number)
```

### Level 3: 24-Hour Tenant History

```python
async def _called_recently(
    db: AsyncSession, 
    tenant_id: UUID, 
    phone_number: str, 
    hours: int = 24,
) -> bool:
    """Check if we've called this number in the last N hours."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(Call.id).where(
            Call.tenant_id == tenant_id,
            Call.to_number == phone_number,
            Call.direction == "outbound",
            Call.created_at > cutoff,
            Call.status.in_(["completed", "in_progress"]),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None
```

### Configuration Options

Add to `campaigns` table or `campaigns.config` JSONB:

```python
dedup_config: {
    "skip_if_called_hours": 24,    # 0 = disabled
    "skip_if_active": true,        # default true
    "allow_retry_same_campaign": true,  # for failed attempts
}
```

### ASAP Mode Special Handling

For ASAP campaigns, the dedup window should be configurable per-campaign:

```python
# ASAP trigger config:
{
    "dedup_hours": 48,  # Don't call same lead twice in 48h
    ...
}
```

---

## 19. Addendum I — Agent Version Pinning for Campaigns

### Problem

Agents have draft (mutable) and published (immutable snapshot) states. When a campaign starts:
- Should it use the **current published version** frozen at start time?
- Or should it use **latest published version** for each call (version can change mid-campaign)?

### Decision: Pin at Campaign Start

**Campaigns pin to the published agent version at campaign start time.** This ensures:
1. All calls in a campaign get identical agent behavior
2. Publishing a new agent version doesn't affect running campaigns
3. Campaign results are reproducible

### Implementation

Add to `campaigns` table:

```sql
ALTER TABLE campaigns ADD COLUMN agent_version_id UUID REFERENCES agent_versions(id);
```

When campaign starts:

```python
async def start_campaign(db: AsyncSession, campaign: Campaign):
    # Get current published version
    published = await AgentService.get_published_version(db, campaign.agent_id)
    if not published:
        raise CampaignError("Agent must be published before starting campaign")
    
    campaign.agent_version_id = published.id
    campaign.status = "running"
    await db.commit()
```

When making calls, use the pinned version:

```python
async def call_single_contact(campaign_id: str, contact_id: str):
    campaign = await CampaignService.get(db, campaign_id)
    
    # Use pinned version, not latest
    agent_snapshot = await AgentVersionService.get(db, campaign.agent_version_id)
    
    await orchestrator.handle_outbound_call(
        agent_id=campaign.agent_id,
        agent_version_id=campaign.agent_version_id,  # Pass version ID
        ...
    )
```

Modify `handle_outbound_call()` and `VoicePipeline` to accept optional `agent_version_id`:

```python
async def handle_outbound_call(
    self,
    agent_id: UUID,
    to_number: str,
    from_number: str,
    user_payload: dict,
    dynamic_variables: dict | None = None,
    agent_version_id: UUID | None = None,  # NEW: optional version override
) -> dict:
    if agent_version_id:
        agent_config = await AgentVersionService.get_config(db, agent_version_id)
    else:
        # Use latest published version (existing behavior)
        agent_config = await AgentService.get_published_config(db, agent_id)
```

### UI Indication

In campaign detail view, show which agent version is pinned:

```
Campaign: MBA Leads Q1
Agent: Admission Qualifier (v3 — published 2026-03-15)
        ↳ [View Agent Version]
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Agent unpublished after campaign starts | Campaign continues with pinned version (version snapshot is immutable) |
| Agent deleted | Campaign fails gracefully; contacts marked as `failed` with reason |
| Campaign cloned | New campaign pins to **current** published version, not source campaign's version |
| Pause & Resume | Resume uses same pinned version (no re-pin) |

---

## 20. Addendum J — CSV Upload Flow

### Overview

Campaigns can source contacts from CSV upload instead of CRM. This requires:
1. File upload endpoint
2. Storage (Azure Blob)
3. Parsing and validation
4. Field mapping UI

### Data Flow

```
Frontend                    Backend                         Azure
┌──────────┐  POST          ┌────────────────┐              ┌────────────┐
│  Upload  │ /campaigns/    │  Upload file   │   Upload     │   Blob     │
│  Dialog  │ {id}/upload    │  to temp path  │ ───────────▶ │  Storage   │
│          │ ──────────────▶│                │              │  (temp/)   │
└──────────┘                │  Parse headers │              └────────────┘
                            │  Return preview│
     ◀─────────────────────────────────────────
     {
       "upload_id": "...",
       "headers": ["name", "phone", "email", "company"],
       "preview_rows": [...first 5 rows...],
       "total_rows": 1234
     }
                            
┌──────────┐                ┌────────────────┐
│  Mapping │  POST          │  Validate      │
│  Dialog  │ /confirm       │  mappings      │
│          │ ──────────────▶│                │
│  phone →→│                │  Move to       │
│  "phone" │                │  permanent     │
│          │                │  storage       │
│  name →→ │                │                │
│  "name"  │                │  Enqueue load  │
└──────────┘                │  worker        │
                            └────────────────┘
```

### API Endpoints

```python
@router.post("/{campaign_id}/upload")
async def upload_contacts_csv(
    campaign_id: UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload CSV file and get preview for field mapping.
    
    Max file size: 50MB
    Supported formats: CSV (UTF-8)
    
    Returns:
        upload_id: UUID for confirming upload
        headers: List of column names
        preview_rows: First 5 rows as dicts
        total_rows: Approximate row count
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(400, "Only CSV files supported")
    
    # Upload to temp blob
    blob_path = f"uploads/campaigns/{campaign_id}/temp/{uuid4()}.csv"
    await blob_storage.upload(blob_path, file.file)
    
    # Parse headers and preview
    headers, preview, total = await _parse_csv_preview(blob_path)
    
    upload = CsvUpload(
        id=uuid4(),
        campaign_id=campaign_id,
        blob_path=blob_path,
        headers=headers,
        row_count=total,
        status="pending_mapping",
    )
    db.add(upload)
    await db.commit()
    
    return {
        "upload_id": upload.id,
        "headers": headers,
        "preview_rows": preview,
        "total_rows": total,
    }

@router.post("/{campaign_id}/upload/{upload_id}/confirm")
async def confirm_upload_mapping(
    campaign_id: UUID,
    upload_id: UUID,
    mapping: CsvMappingRequest,  # { "phone_column": "phone", "name_column": "name", ... }
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm field mapping and start loading contacts.
    
    Required mapping:
        phone_column: Column containing phone numbers (E.164 or local format)
    
    Optional mapping:
        name_column, email_column, custom mappings for agent variables
    """
    upload = await db.get(CsvUpload, upload_id)
    if upload.campaign_id != campaign_id:
        raise HTTPException(404)
    
    # Validate phone column exists
    if mapping.phone_column not in upload.headers:
        raise HTTPException(400, f"Column '{mapping.phone_column}' not found")
    
    # Store mapping
    upload.field_mapping = mapping.dict()
    upload.status = "loading"
    await db.commit()
    
    # Enqueue loading worker
    load_csv_contacts.delay(str(upload_id))
    
    return {"status": "loading", "message": "Contacts are being loaded"}
```

### CSV Loading Worker

```python
@celery_app.task(name="campaign.load_csv_contacts", bind=True)
def load_csv_contacts(self, upload_id: str):
    """
    Parse CSV and create campaign_contacts rows.
    
    Handles:
    - Phone number normalization (country detection)
    - Validation (invalid phones skipped)
    - Deduplication (same phone in file)
    - Progress tracking
    """
    upload = await db.get(CsvUpload, UUID(upload_id))
    campaign = await db.get(Campaign, upload.campaign_id)
    mapping = upload.field_mapping
    
    stats = {"loaded": 0, "invalid": 0, "duplicate": 0}
    
    async for row in stream_csv_from_blob(upload.blob_path):
        phone_raw = row.get(mapping["phone_column"])
        phone = normalize_phone(phone_raw, default_country=campaign.default_country)
        
        if not phone:
            stats["invalid"] += 1
            continue
        
        contact_data = {}
        for agent_var, csv_col in mapping.get("variable_mapping", {}).items():
            contact_data[agent_var] = row.get(csv_col)
        
        contact = CampaignContact(
            campaign_id=campaign.id,
            tenant_id=campaign.tenant_id,
            phone_number=phone,
            contact_data=contact_data,
            source="csv",
        )
        
        try:
            db.add(contact)
            await db.flush()
            stats["loaded"] += 1
        except IntegrityError:
            await db.rollback()
            stats["duplicate"] += 1
    
    # Update campaign stats
    campaign.total_contacts = stats["loaded"]
    upload.status = "completed"
    upload.stats = stats
    await db.commit()
    
    # Cleanup temp blob (optional: keep for audit)
    # await blob_storage.delete(upload.blob_path)
```

### Data Model

```sql
CREATE TABLE csv_uploads (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id   UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  blob_path     TEXT NOT NULL,           -- Azure Blob path
  filename      VARCHAR(255) NOT NULL,   -- Original filename
  headers       JSONB NOT NULL,          -- ["name", "phone", "email"]
  field_mapping JSONB,                   -- { "phone_column": "phone", ... }
  row_count     INT,
  stats         JSONB,                   -- { "loaded": 1000, "invalid": 23, "duplicate": 5 }
  status        VARCHAR(20) NOT NULL DEFAULT 'pending_mapping',
    -- 'pending_mapping' | 'loading' | 'completed' | 'failed'
  error         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- RLS: tenant_id = current_setting('app.current_tenant_id')
```

### Frontend Components

```typescript
// frontend/src/modules/campaigns/components/csv-upload/
//   upload-dropzone.tsx    — File drag-and-drop
//   mapping-dialog.tsx     — Column mapping UI
//   upload-progress.tsx    — Progress bar during loading
```

---

## 21. Addendum K — Voicemail Detection (AMD)

### Overview

When an outbound call connects, we need to detect if a human answered or if it went to voicemail. This affects:
- Whether to start the agent conversation
- Whether to leave a voicemail message
- How to categorize the call outcome

### Detection Options

| Method | How It Works | Latency | Accuracy |
|--------|--------------|---------|----------|
| **Twilio AMD** | Twilio's built-in Answering Machine Detection | 3-5s | ~85-90% |
| **Silence Detection** | Measure silence after connect, humans respond faster | 1-2s | ~70-80% |
| **Beep Detection** | Listen for voicemail beep tone | 0.5s after beep | ~95% for machines |
| **Hybrid** | Combine silence + beep detection | Variable | ~90% |

### Recommended: Twilio AMD + Fallback

Use Twilio's `MachineDetection` parameter with `DetectMessageEnd` for async detection:

```python
# In orchestrator.handle_outbound_call():

twiml = f"""
<Response>
    <Dial callerId="{from_number}" 
          action="/api/v1/pipeline/webhooks/dial-complete"
          machineDetection="DetectMessageEnd"
          machineDetectionTimeout="5"
          machineDetectionSilenceTimeout="2000"
          asyncAmd="true"
          asyncAmdStatusCallback="/api/v1/pipeline/webhooks/amd-result"
          asyncAmdStatusCallbackMethod="POST">
        <Number>{to_number}</Number>
    </Dial>
</Response>
"""
```

### AMD Result Webhook

```python
@router.post("/webhooks/amd-result")
async def amd_result_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Twilio AMD async result callback.
    
    AnsweredBy values:
      - human: Human answered
      - machine_start: Machine detected (voicemail started)
      - machine_end_beep: Machine detected (after beep)
      - machine_end_silence: Machine detected (after silence)
      - machine_end_other: Machine detected (other)
      - fax: Fax machine detected
      - unknown: Could not determine
    """
    form = await request.form()
    call_sid = form.get("CallSid")
    answered_by = form.get("AnsweredBy")
    
    call = await CallService.get_by_twilio_sid(db, call_sid)
    if not call:
        return Response(status_code=404)
    
    call.amd_result = answered_by
    
    if answered_by == "human":
        # Continue with agent conversation (already started)
        pass
    elif answered_by.startswith("machine"):
        # Handle voicemail
        await _handle_voicemail_detected(call)
    elif answered_by == "fax":
        # Mark as fax, don't retry
        call.status = "failed"
        call.failure_reason = "fax_detected"
    
    await db.commit()
```

### Agent Configuration

Add to `agents` schema:

```python
class AgentVoicemailConfig(BaseModel):
    detection_enabled: bool = True
    action: Literal["hang_up", "leave_message", "wait"] = "hang_up"
    message_template: str | None = None  # TTS text if action = "leave_message"
    max_message_duration: int = 30       # seconds
```

### Voicemail Handler

```python
async def _handle_voicemail_detected(call: Call):
    """Handle voicemail detection based on agent config."""
    agent = await AgentService.get(db, call.agent_id)
    vm_config = agent.config.get("voicemail", {})
    action = vm_config.get("action", "hang_up")
    
    if action == "hang_up":
        await twilio_client.calls(call.twilio_sid).update(status="completed")
        call.status = "voicemail"
        
    elif action == "leave_message":
        # Generate TTS and play to voicemail
        message = vm_config.get("message_template", "Please call us back.")
        # Substitute dynamic variables
        message = substitute_variables(message, call.dynamic_variables)
        
        # Twilio: <Say> after machine detection
        await twilio_client.calls(call.twilio_sid).update(
            twiml=f'<Response><Say voice="Polly.Amy">{message}</Say></Response>'
        )
        call.status = "voicemail_left"
        
    elif action == "wait":
        # Wait for human to pick up (risky: may play agent to recording)
        call.status = "in_progress"  # Let pipeline continue
```

### Campaign Contact Status Update

```sql
-- Add to campaign_contacts status enum:
-- 'voicemail'      — Voicemail detected, hung up
-- 'voicemail_left' — Voicemail detected, message left
```

---

## 22. Addendum L — Campaign Templates and Cloning

### Use Case

Recurring campaigns (weekly lead qualification, monthly surveys) should be easy to create from templates.

### Implementation

Add `is_template` flag and clone API:

```sql
ALTER TABLE campaigns ADD COLUMN is_template BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE campaigns ADD COLUMN cloned_from_id UUID REFERENCES campaigns(id);
```

### Clone API

```python
@router.post("/{campaign_id}/clone")
async def clone_campaign(
    campaign_id: UUID,
    body: CloneCampaignRequest,  # { "name": "New Campaign Name" }
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Clone a campaign configuration (without contacts).
    
    Clones:
      - Agent reference
      - Source config (CRM filters, variable mappings)
      - Write-back mappings
      - Call settings (concurrency, rate, window)
      - Tool configurations
    
    Does NOT clone:
      - Contacts (campaign_contacts)
      - Stats
      - agent_version_id (pins to NEW published version)
    """
    source = await CampaignService.get(db, campaign_id)
    if source.tenant_id != user.tenant_id:
        raise HTTPException(403)
    
    new_campaign = Campaign(
        tenant_id=source.tenant_id,
        name=body.name or f"{source.name} (Copy)",
        description=source.description,
        agent_id=source.agent_id,
        status="draft",
        
        source_type=source.source_type,
        source_config=source.source_config,
        variable_mapping=source.variable_mapping,
        writeback_mapping=source.writeback_mapping,
        
        from_number=source.from_number,
        max_concurrent=source.max_concurrent,
        calls_per_minute=source.calls_per_minute,
        max_retries=source.max_retries,
        retry_delay_minutes=source.retry_delay_minutes,
        calling_window=source.calling_window,
        
        trigger_mode="manual",  # Reset to manual
        trigger_config={},
        
        cloned_from_id=source.id,
        created_by=user.id,
    )
    
    db.add(new_campaign)
    await db.commit()
    
    # Clone tool configurations (agent_tools with campaign overrides)
    # ... if applicable
    
    return CampaignResponse.from_orm(new_campaign)
```

### Template Library UI

```
┌─────────────────────────────────────────────────┐
│  Campaign Templates                              │
│                                                  │
│  ┌─────────────────┐  ┌─────────────────┐       │
│  │ Lead Qualifier  │  │ Survey Followup │       │
│  │ ★ Template      │  │ ★ Template      │       │
│  │                 │  │                 │       │
│  │ Agent: Qualifier│  │ Agent: Survey   │       │
│  │ Source: Zoho    │  │ Source: CSV     │       │
│  │                 │  │                 │       │
│  │ [Use Template]  │  │ [Use Template]  │       │
│  └─────────────────┘  └─────────────────┘       │
│                                                  │
│  + Create New Template                           │
└─────────────────────────────────────────────────┘
```

### Save as Template

Any campaign can be saved as a template:

```python
@router.post("/{campaign_id}/save-as-template")
async def save_as_template(
    campaign_id: UUID,
    body: SaveAsTemplateRequest,  # { "name": "Lead Qualifier Template" }
    db: AsyncSession = Depends(get_db),
):
    """Mark a campaign as a reusable template."""
    campaign = await CampaignService.get(db, campaign_id)
    
    # Create template copy with is_template=true
    template = Campaign(
        ...same as clone...,
        name=body.name,
        is_template=True,
        status="template",  # Templates don't have normal status
    )
    
    db.add(template)
    await db.commit()
    
    return {"template_id": template.id}
```

---

## 23. Addendum M — API Error Response Schema

### Standard Error Format

All campaign API errors follow a consistent schema:

```python
class CampaignErrorResponse(BaseModel):
    error: str              # Machine-readable error code
    message: str            # Human-readable description
    details: dict | None    # Additional context
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "CAMPAIGN_NOT_FOUND",
                "message": "Campaign with ID '...' not found",
                "details": {"campaign_id": "..."}
            }
        }
```

### Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `CAMPAIGN_NOT_FOUND` | 404 | Campaign ID doesn't exist or not accessible |
| `CAMPAIGN_INVALID_STATE` | 400 | Action not allowed in current state (e.g., starting a running campaign) |
| `CAMPAIGN_NO_CONTACTS` | 400 | Cannot start campaign with 0 contacts loaded |
| `CAMPAIGN_AGENT_NOT_PUBLISHED` | 400 | Agent must be published before starting |
| `CAMPAIGN_FROM_NUMBER_REQUIRED` | 400 | Outbound campaigns require a from_number |
| `CAMPAIGN_FROM_NUMBER_NOT_FOUND` | 400 | Selected from_number not found or not active |
| `CAMPAIGN_SOURCE_ERROR` | 400 | Error loading contacts from source (CRM/CSV) |
| `CAMPAIGN_CRM_DISCONNECTED` | 400 | CRM integration is disconnected |
| `CAMPAIGN_LIMIT_REACHED` | 429 | Tenant campaign limit reached |
| `CONTACT_NOT_FOUND` | 404 | Contact ID doesn't exist |
| `CONTACT_INVALID_STATE` | 400 | Contact action not allowed (e.g., retry on completed) |
| `DNC_INVALID_PHONE` | 400 | Phone number format invalid |
| `DNC_ALREADY_EXISTS` | 409 | Phone already on DNC list |
| `CSV_INVALID_FORMAT` | 400 | CSV parsing error |
| `CSV_TOO_LARGE` | 413 | CSV exceeds max size (50MB) |
| `CSV_MISSING_PHONE_COLUMN` | 400 | Required phone column not mapped |

### Example Responses

**Starting campaign with no contacts:**
```json
HTTP 400 Bad Request
{
    "error": "CAMPAIGN_NO_CONTACTS",
    "message": "Cannot start campaign: no contacts loaded. Load contacts from CRM or upload a CSV first.",
    "details": {
        "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
        "total_contacts": 0
    }
}
```

**Starting campaign with unpublished agent:**
```json
HTTP 400 Bad Request
{
    "error": "CAMPAIGN_AGENT_NOT_PUBLISHED",
    "message": "Agent 'MBA Qualifier' must be published before starting a campaign.",
    "details": {
        "agent_id": "660e8400-e29b-41d4-a716-446655440001",
        "agent_name": "MBA Qualifier",
        "agent_status": "draft"
    }
}
```

**Rate limit reached:**
```json
HTTP 429 Too Many Requests
{
    "error": "CAMPAIGN_LIMIT_REACHED",
    "message": "Maximum concurrent campaigns reached for this tenant. Pause or complete existing campaigns.",
    "details": {
        "limit": 5,
        "active_campaigns": 5
    }
}
```

### Implementation

```python
class CampaignException(HTTPException):
    def __init__(self, error: str, message: str, details: dict | None = None, status_code: int = 400):
        super().__init__(
            status_code=status_code,
            detail={"error": error, "message": message, "details": details}
        )

# Usage:
raise CampaignException(
    error="CAMPAIGN_NO_CONTACTS",
    message="Cannot start campaign: no contacts loaded.",
    details={"campaign_id": str(campaign.id), "total_contacts": 0},
)
```

### OpenAPI Documentation

Add response schemas to router decorators:

```python
@router.post(
    "/{campaign_id}/start",
    responses={
        200: {"model": CampaignResponse},
        400: {"model": CampaignErrorResponse, "description": "Invalid campaign state or configuration"},
        404: {"model": CampaignErrorResponse, "description": "Campaign not found"},
        429: {"model": CampaignErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def start_campaign(...):
    ...
```
