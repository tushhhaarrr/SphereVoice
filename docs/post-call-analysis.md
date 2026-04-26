# Post-Call Analysis & CRM Writeback — Feature Plan

> **Status:** Draft  
> **Date:** 2026-03-19  
> **Scope:** Backend (extraction engine, CRM writeback), Frontend (template picker, writeback mapping), Integrations (Zoho CRM, future CRMs)

---

## 1. Overview

Every completed SphereVoice call produces a structured **post-call data output** — a JSON document of insights extracted from the transcript via LLM. This data serves three purposes:

1. **In-Platform Analytics** — Displayed in call detail modals, aggregated in dashboards, filterable across calls
2. **CRM Writeback** — Automatically pushed back to the source CRM (Zoho today; extensible to HubSpot, Salesforce) so customer records stay enriched
3. **Campaign Reporting** — Drives campaign-level success/failure metrics and per-contact outcome tracking

### Current State

| Component | Status | Location |
|---|---|---|
| Inline extraction engine | ✅ Working | `backend/app/modules/pipeline/extraction.py` |
| Celery worker extraction | ✅ Working | `backend/app/workers/post_call.py` |
| 3 standard fields (`call_summary`, `call_successful`, `user_sentiment`) | ✅ Hardcoded toggles | `agent.config.settings.postCallExtraction` |
| 4 Celery fields (`call_summary`, `call_successful`, `user_sentiment`, `key_topics`) | ✅ Hardcoded | `backend/app/workers/post_call.py` |
| Custom `extraction_fields` per agent | ✅ Working | `agents.extraction_fields` (JSONB array) |
| `calls.extracted_data` storage | ✅ Working, GIN-indexed | `backend/app/modules/calls/models.py` |
| Recording upload to Azure Blob | ✅ Working | `backend/app/workers/post_call.py` |
| Webhook delivery (`call_ended`, `extraction_complete`) | ✅ Working | `backend/app/workers/post_call.py` |
| CRM push for all calls (call log + note + field update) | ✅ Working for Zoho | `backend/app/modules/integrations/crm_data.py` |
| Campaign writeback mapping UI | ✅ Working | `frontend/.../step-writeback-mapping.tsx` |
| Campaign CRM writeback worker | ✅ Working via Celery | `backend/app/modules/campaigns/workers.py` |
| Published agent snapshots | ✅ Extraction uses published config | `backend/app/modules/pipeline/orchestrator.py` |

### Dual Extraction Paths (Important)

The codebase currently has **two separate extraction code paths** that must be understood:

| Path | Trigger | File | LLM Client | Fields |
|---|---|---|---|---|
| **Inline extraction** | Orchestrator `handle_call_ended()` — runs in the FastAPI process | `backend/app/modules/pipeline/extraction.py` | `httpx` → OpenAI-compatible API (agent's LLM provider) | Agent's `extraction_fields` + 3 standard toggles |
| **Celery worker extraction** | `process_call` task — runs in Celery worker after call ends | `backend/app/workers/post_call.py` | Azure OpenAI SDK → OpenAI SDK → basic fallback | Fixed 4 fields (`call_summary`, `user_sentiment`, `call_successful`, `key_topics`) |

**Current issue:** Both paths may run on the same call, with the Celery worker overwriting the inline result. The plan consolidates these into a single unified path (§6).

### Post-Call Processing Pipeline (Celery `process_call`)

After every call ends, the orchestrator enqueues a Celery task that runs four steps sequentially:

```
process_call(call_id)
  │
  ├── 1. _extract_post_call_data()    → LLM extraction (summary, sentiment, success)
  │      Azure OpenAI → OpenAI → basic fallback (word count)
  │
  ├── 2. _upload_recording()          → Fetch raw recording → upload to Azure Blob Storage
  │      recordings/{tenant_id}/{call_id}.mp3
  │
  ├── 3. _dispatch_webhooks()         → Fire "call_ended" and "extraction_complete" events
  │      Payload includes extracted_data for extraction_complete
  │
  └── 4. _push_to_crm()              → CrmDataService.push_call_to_crm()
         Call log + note + field update + contact auto-create
```

**Key facts:**
- Task has `max_retries=3` with Celery auto-retry
- Metrics tracked: `WORKER_TASKS_TOTAL`, `WORKER_TASK_DURATION_SECONDS`
- CRM push is **non-fatal** — failures don't block the rest of the pipeline
- CRM push already runs for **all calls** (including inbound), not just campaigns

### What's Missing

- No **predefined template library** — users must type field names and descriptions from scratch
- Standard fields are limited to 3 toggles (inline) or 4 hardcoded fields (Celery); no structured default output schema
- No **schema versioning** — can't distinguish data produced by different extraction configurations
- **Duplicate extraction** — two independent code paths that can overwrite each other
- No **writeback configuration on the agent** itself (only at campaign level or tenant-global)
- CRM field mapping is tenant-global only — not per-agent
- `key_topics` field extracted by Celery worker but not available in inline extraction or templates
- No **extraction_complete webhook** includes extracted data from the inline path (only Celery path)

---

## 2. Post-Call Data Schema

### 2.1 Default Fields (Always Extracted)

These fields are extracted for **every call** with zero configuration. They form the baseline analytics dataset.

| Field Key | Type | Description | Rationale |
|---|---|---|---|
| `call_summary` | string | 2-3 sentence summary of the call | Universal — powers call list view |
| `call_successful` | boolean | Whether the call's main objective was achieved | Core KPI — pass/fail |
| `success_score` | number | Rate call success on a scale of 1-10 | Granular ranking for analytics |
| `success_description` | string | Qualitative assessment of call performance | Explains the score for review |
| `customer_sentiment` | string | Overall emotional tone: `positive`, `neutral`, `negative` | Already exists — key signal |
| `customer_frustrated` | boolean | Whether the customer expressed frustration | Escalation trigger |
| `script_followed` | boolean | Whether the agent followed the prescribed prompt/script | Quality baseline |
| `key_topics` | array | List of key topics discussed during the call | Already extracted by Celery worker |

**Meta fields** (system-populated, not LLM-extracted):

| Field Key | Type | Description |
|---|---|---|
| `_extraction_version` | string | Schema version (e.g., `"1.0"`) — for analytics query compatibility |
| `_extracted_at` | string | ISO 8601 timestamp of extraction |
| `_model_used` | string | LLM model that performed extraction (e.g., `"gpt-4o-mini"`) |

### 2.2 Template Library (Opt-in per Agent)

Templates are **predefined groups of extraction fields** organized by category. When an agent enables a category, all its fields are added to the extraction prompt.

#### Appointment

| Field Key | Type | Description |
|---|---|---|
| `appointment_booked` | boolean | Tracks if a customer booked an appointment |
| `appointment_cancelled` | boolean | Track when appointments are cancelled by the customer |
| `appointment_rescheduled` | boolean | Track when appointments are moved to a different time |
| `booking_status` | string | Current status of the booking attempt (`confirmed`, `pending`, `cancelled`, `no_show`) |
| `appointment_date` | string | Scheduled appointment date (ISO 8601 date) |
| `appointment_time` | string | Scheduled appointment time |
| `booking_details` | object | Complete booking information in structured format |

#### Sales

| Field Key | Type | Description |
|---|---|---|
| `sale_completed` | boolean | Track when a sale is successfully closed |
| `lead_qualified` | boolean | Whether the prospect meets qualification criteria |
| `revenue_amount` | number | Dollar amount of revenue generated from the call |
| `upsell_opportunity` | boolean | Whether additional sales opportunities were discovered |
| `lead_status` | string | Current qualification status: `hot`, `warm`, `cold`, `disqualified` |
| `product_interest_level` | string | Level of interest shown: `high`, `medium`, `low`, `none` |
| `discount_requested` | boolean | Whether customer requested pricing discounts |
| `products_discussed` | array | List of products or services discussed during the call |

#### Support

| Field Key | Type | Description |
|---|---|---|
| `issue_resolved` | boolean | Whether the customer's issue was resolved during the call |
| `issue_severity` | string | Priority level: `critical`, `high`, `medium`, `low` |
| `support_ticket_created` | boolean | Whether a follow-up support ticket was created |
| `time_to_resolution` | number | Minutes taken to resolve the customer issue |
| `issue_type` | string | Category of the support issue (free text) |
| `escalation_required` | boolean | Whether the issue needs escalation to higher support tier |
| `troubleshooting_steps` | integer | Number of troubleshooting steps attempted |

#### Customer Experience

| Field Key | Type | Description |
|---|---|---|
| `csat_score` | number | Numerical rating of customer satisfaction (1-5 or 1-10) |
| `nps_score` | integer | Net Promoter Score — likelihood to recommend (0-10) |
| `customer_effort_score` | integer | How easy it was to get their issue resolved (1-5) |
| `would_recommend` | boolean | Whether the customer would recommend your service |
| `feedback_summary` | string | Detailed customer feedback and suggestions |

#### Quality & Compliance

| Field Key | Type | Description |
|---|---|---|
| `compliance_verified` | boolean | Whether all compliance requirements were met |
| `quality_score` | number | Overall quality assessment score (1-10) |
| `supervisor_review_needed` | boolean | Whether the call requires supervisor review |
| `appropriate_greeting` | boolean | Whether the agent used the proper greeting |
| `excessive_hold_time` | boolean | Whether customer was placed on hold for too long |

### 2.3 Custom Fields (User-Defined)

Users can still define fully custom extraction fields beyond the templates. These are stored in `agents.extraction_fields` with the existing `{name, type, description}` schema.

### 2.4 Output Structure

Every call's `extracted_data` JSONB column will contain a flat JSON object:

```json
{
  "call_summary": "Customer called to reschedule their dental appointment from March 20 to March 25. The agent confirmed the new slot.",
  "call_successful": true,
  "success_score": 9,
  "success_description": "Appointment was successfully rescheduled with confirmation.",
  "customer_sentiment": "positive",
  "customer_frustrated": false,
  "script_followed": true,

  "appointment_booked": false,
  "appointment_rescheduled": true,
  "booking_status": "confirmed",
  "appointment_date": "2026-03-25",
  "appointment_time": "10:30 AM",
  "booking_details": {
    "type": "dental_checkup",
    "doctor": "Dr. Patel",
    "original_date": "2026-03-20"
  },

  "patient_name": "Rahul Sharma",
  "insurance_verified": true,

  "_extraction_version": "1.0",
  "_extracted_at": "2026-03-19T14:30:00Z",
  "_model_used": "gpt-4o-mini"
}
```

**Storage design:** Flat keys (no nesting by category). Categories are a **configuration concept**, not a storage concept. The GIN index on `extracted_data` works best with flat keys. Use `jsonb_path_exists` or `->` operators for querying.

---

## 3. Agent-Level Configuration

### 3.1 Updated `PostCallExtractionSettings`

```typescript
interface PostCallExtractionSettings {
  enabled: boolean;                    // Master toggle — default: true

  // Default fields — always extracted unless manually disabled
  defaults: {
    callSummary: boolean;              // default: true
    successEvaluation: boolean;        // default: true (boolean + score + description)
    customerSentiment: boolean;        // default: true
    customerFrustrated: boolean;       // default: true
    scriptFollowed: boolean;           // default: true
  };

  // Template categories — opt-in groups
  enabledCategories: string[];         // e.g., ["appointment", "sales"]

  // Fine-grained per-field disabling within enabled categories
  disabledFields: string[];            // e.g., ["discount_requested", "booking_details"]

  // Fully custom fields (existing extraction_fields behavior)
  customFields: ExtractionField[];
}

interface ExtractionField {
  name: string;
  type: "string" | "boolean" | "number" | "integer" | "array" | "object";
  description: string;
  options?: string[];                  // For enum-like string fields
}
```

### 3.2 Backend Config — Agent `config.settings`

```json
{
  "settings": {
    "postCallExtraction": {
      "enabled": true,
      "defaults": {
        "callSummary": true,
        "successEvaluation": true,
        "customerSentiment": true,
        "customerFrustrated": true,
        "scriptFollowed": true
      },
      "enabledCategories": ["appointment"],
      "disabledFields": []
    }
  }
}
```

No schema change to `agents.extraction_fields` — custom fields are still stored there.

### 3.3 Template Catalog (Static Backend Constant)

The catalog lives as a single Python constant. It is **not** stored per-agent — each agent only references which categories to enable.

**File:** `backend/app/modules/pipeline/extraction_templates.py`

```python
EXTRACTION_TEMPLATES: dict[str, dict] = {
    "appointment": {
        "label": "Appointment",
        "icon": "calendar",
        "description": "Track appointment bookings, cancellations, and rescheduling",
        "fields": [
            {"name": "appointment_booked", "type": "boolean", "description": "Tracks if a customer booked an appointment"},
            {"name": "appointment_cancelled", "type": "boolean", "description": "Track when appointments are cancelled"},
            # ... all appointment fields
        ],
    },
    "sales": { ... },
    "support": { ... },
    "customer_experience": { ... },
    "quality_compliance": { ... },
}

DEFAULT_FIELDS: list[dict] = [
    {"name": "call_summary", "type": "string", "description": "2-3 sentence summary of the call", "group": "callSummary"},
    {"name": "call_successful", "type": "boolean", "description": "Whether the call's main objective was achieved", "group": "successEvaluation"},
    {"name": "success_score", "type": "number", "description": "Rate call success 1-10", "group": "successEvaluation"},
    {"name": "success_description", "type": "string", "description": "Qualitative assessment of call performance", "group": "successEvaluation"},
    {"name": "customer_sentiment", "type": "string", "description": "Overall emotional tone: positive, neutral, negative", "group": "customerSentiment"},
    {"name": "customer_frustrated", "type": "boolean", "description": "Whether the customer expressed frustration", "group": "customerFrustrated"},
    {"name": "script_followed", "type": "boolean", "description": "Whether the agent followed the prescribed script", "group": "scriptFollowed"},
]
```

---

## 4. CRM Writeback

### 4.1 Current Writeback Paths

| Path | When | How | Mapping Source |
|---|---|---|---|
| **Celery `process_call` CRM push** | After every call (step 4 of Celery pipeline) | `_push_to_crm()` → `CrmDataService.push_call_to_crm()` | Tenant-global `crm_integrations.config.field_mappings` |
| **Campaign writeback** | After each campaign call completes | Celery task `campaign_crm_writeback` → Zoho upsert | `campaigns.writeback_mapping` |

**Important:** CRM push already runs for **all calls** (inbound, outbound, test) via the Celery `process_call` task. The gap is that it only uses tenant-global field mappings — there's no per-agent mapping.

### 4.2 Unified Writeback Design

Both paths are unified so that:

1. **Every call** (inbound, outbound, campaign, test) can write data back to CRM
2. Writeback mapping is configurable **at the agent level** (not just campaign or tenant-global)
3. Template fields work seamlessly with CRM field mapping

#### New Flow

```
Call Ends
  ↓
Post-Call Extraction (LLM)
  ↓ extracted_data written to calls.extracted_data
  ↓
CRM Writeback Decision
  ├── Is CRM integration connected for this tenant? → No → Skip
  ├── Is writeback enabled on this agent? → No → Skip
  └── Yes → Resolve mapping → Push to CRM
      ├── Campaign call? → Use campaign.writeback_mapping (override)
      └── Non-campaign call? → Use agent.crmWriteback.mapping
          └── Fallback → Tenant-global field_mappings
```

### 4.3 Agent-Level Writeback Configuration

New section in the agent config:

```typescript
interface AgentWritebackSettings {
  enabled: boolean;                        // Master toggle — default: false
  mapping: Record<string, string>;         // extracted_data key → CRM field API name
  autoMapDefaults: boolean;                // Auto-map standard fields to well-known CRM fields
  crmModule: string;                       // Target CRM module: "Contacts", "Leads", "Deals"
}
```

**Example agent config:**

```json
{
  "settings": {
    "crmWriteback": {
      "enabled": true,
      "mapping": {
        "appointment_date": "Appointment_Date",
        "appointment_time": "Appointment_Time",
        "booking_status": "Booking_Status_c",
        "call_summary": "Description",
        "customer_sentiment": "Sentiment_c",
        "lead_status": "Lead_Status",
        "sale_completed": "Sale_Completed_c"
      },
      "autoMapDefaults": true,
      "crmModule": "Contacts"
    }
  }
}
```

### 4.4 Mapping Priority Chain

When a call ends and CRM writeback triggers, the mapping is resolved in this order:

1. **Campaign `writeback_mapping`** — highest priority, if the call belongs to a campaign
2. **Agent `config.settings.crmWriteback.mapping`** — per-agent mapping
3. **Tenant-global `crm_integrations.config.field_mappings`** — fallback for unmapped fields

### 4.5 Writeback Operations

| Operation | Description | CRM Action |
|---|---|---|
| **Field Update** | Write extracted_data values to CRM record fields | `PUT /crm/v8/{module}/{record_id}` |
| **Call Activity Log** | Create a Call activity in CRM | `POST /crm/v8/Calls` |
| **Note Attachment** | Attach transcript + analysis as a Note | `POST /crm/v8/Notes` |
| **Contact Auto-Create** | Create CRM record for unknown callers | `POST /crm/v8/Contacts/upsert` |

### 4.6 Writeback Status Tracking

```
calls.writeback_status:
  NULL     → CRM writeback not applicable (no integration or not enabled)
  pending  → Writeback queued
  synced   → Successfully written to CRM
  failed   → Writeback failed (error in writeback_error)
  skipped  → No matching CRM record found and auto-create is off
```

### 4.7 CRM Provider Support

| CRM | Status | Writeback | Call Log | Notes |
|---|---|---|---|---|
| Zoho CRM | ✅ Connected | ✅ Field update | ✅ Call activity | ✅ Notes |
| HubSpot | 🔜 Planned | 🔜 | 🔜 | 🔜 |
| Salesforce | 🔜 Planned | 🔜 | 🔜 | 🔜 |
| Freshdesk | 🔜 Planned | 🔜 | 🔜 | 🔜 |

---

## 5. Data Flow — End to End

```
                          ┌─────────────────────────────┐
                          │       AGENT CONFIG           │
                          │                             │
                          │  postCallExtraction:        │
                          │    defaults: {summary, ...} │
                          │    enabledCategories: [apt] │
                          │    customFields: [...]      │
                          │                             │
                          │  crmWriteback:              │
                          │    enabled: true            │
                          │    mapping: {field→crm}     │
                          └──────────┬──────────────────┘
                                     │
    ┌─────────────┐                  │
    │ Call Starts  │                  │
    │ (Pipecat)    │                  │
    └──────┬──────┘                  │
           │                         │
           │ transcript frames       │
           ▼                         │
    ┌─────────────┐                  │
    │ Call Ends    │                  │
    │ Orchestrator │                  │
    └──────┬──────┘                  │
           │                         │
           ├─── Save transcript ───► calls.transcript (JSONB)
           │                         │
           ▼                         ▼
    ┌─────────────────────────────────────────────┐
    │           POST-CALL EXTRACTION              │
    │                                             │
    │  1. Resolve fields:                         │
    │     defaults + template fields + custom     │
    │                                             │
    │  2. Build LLM prompt with field list        │
    │                                             │
    │  3. Call LLM (gpt-4o-mini, response_format: │
    │     json_object)                            │
    │                                             │
    │  4. Add meta: _extraction_version,          │
    │     _extracted_at, _model_used              │
    │                                             │
    │  5. Persist → calls.extracted_data          │
    └──────┬────────────────────────┬─────────────┘
           │                        │
           ▼                        ▼
    ┌──────────────┐    ┌────────────────────────┐
    │ SphereVoice Dashboard │    │     CRM WRITEBACK      │
    │               │    │                        │
    │  Call Detail  │    │  1. Check CRM connected│
    │  Modal shows  │    │  2. Resolve mapping    │
    │  extracted_   │    │     (campaign > agent > │
    │  data fields  │    │      tenant-global)    │
    │               │    │  3. Map fields → CRM   │
    │  Analytics    │    │  4. Zoho upsert/update │
    │  aggregates   │    │  5. Log CRM call       │
    │  across calls │    │  6. Attach note        │
    └──────────────┘    │  7. Update writeback_  │
                        │     status              │
                        └────────────────────────┘
```

---

## 6. Extraction Engine Changes

### 6.0 Consolidation: Merge Dual Extraction Paths

**Problem:** Today there are two independent extraction code paths:

1. **Inline** (`extraction.py`) — runs in orchestrator `handle_call_ended()`, uses agent's custom extraction fields + 3 standard toggles, uses agent's configured LLM provider via `httpx`.
2. **Celery worker** (`post_call.py`) — runs as async task, hardcodes 4 fields (`call_summary`, `user_sentiment`, `call_successful`, `key_topics`), has Azure OpenAI → OpenAI → basic fallback.

Both write to `calls.extracted_data`, so the Celery worker can overwrite the inline result.

**Solution:** Consolidate into a single `resolve_extraction_fields()` → LLM call, executed in the Celery `process_call` task (so it doesn't block the FastAPI process). The orchestrator's inline extraction is removed; everything goes through the worker.

```
handle_call_ended()                  process_call (Celery)
  ↓                                    ↓
  Save transcript + status             1. resolve_extraction_fields(agent)
  enqueue process_call ─────────────►  2. Build prompt + call LLM (agent's provider)
                                       3. Add meta fields
                                       4. Persist → calls.extracted_data
                                       5. Upload recording
                                       6. Dispatch webhooks (call_ended + extraction_complete)
                                       7. CRM writeback
```

### 6.1 Field Resolution

```python
def resolve_extraction_fields(agent) -> list[dict]:
    """Merge default + template + custom fields based on agent config."""
    from app.modules.pipeline.extraction_templates import (
        DEFAULT_FIELDS, EXTRACTION_TEMPLATES,
    )

    config = (agent.config or {}).get("settings", {}).get("postCallExtraction", {})
    defaults_config = config.get("defaults", {})
    enabled_categories = config.get("enabledCategories", [])
    disabled_fields = set(config.get("disabledFields", []))

    fields = []

    # Add enabled default fields
    for field in DEFAULT_FIELDS:
        group = field.get("group", "")
        if defaults_config.get(group, True):  # Default: enabled
            fields.append(field)

    # Add template category fields
    for category in enabled_categories:
        template = EXTRACTION_TEMPLATES.get(category.lower())
        if template:
            for field in template["fields"]:
                if field["name"] not in disabled_fields:
                    fields.append(field)

    # Add custom extraction fields
    custom = getattr(agent, "extraction_fields", None) or []
    fields.extend(custom)

    return fields
```

### 6.2 Updated Extraction Runner

```python
async def run_post_call_extraction(db, call_id, agent, transcript):
    # 1. Resolve all fields to extract
    fields = resolve_extraction_fields(agent)
    if not fields:
        return {}

    # 2. Build prompt + call LLM
    prompt = build_extraction_prompt(fields, transcript)
    extracted = await _call_llm_for_extraction(agent, prompt)

    # 3. Add metadata
    extracted["_extraction_version"] = "1.0"
    extracted["_extracted_at"] = datetime.now(UTC).isoformat()
    extracted["_model_used"] = getattr(agent, "llm_model", None) or "gpt-4o-mini"

    # 4. Persist to call record
    await CallService.update_call(db, call_id, extracted_data=extracted, ...)

    # 5. Trigger CRM writeback (if enabled)
    crm_cfg = (agent.config or {}).get("settings", {}).get("crmWriteback", {})
    if crm_cfg.get("enabled"):
        await trigger_crm_writeback(db, call_id, agent, extracted)

    return extracted
```

---

## 7. API Changes

### 7.1 New Endpoint — Template Catalog

```
GET /api/v1/extraction-templates
```

Returns the full template catalog for the frontend picker.

**Response:**

```json
{
  "templates": {
    "appointment": {
      "label": "Appointment",
      "icon": "calendar",
      "description": "Track appointment bookings, cancellations, and rescheduling",
      "fields": [
        {"name": "appointment_booked", "type": "boolean", "description": "..."}
      ]
    }
  },
  "defaults": [
    {"name": "call_summary", "type": "string", "description": "...", "group": "callSummary"}
  ]
}
```

### 7.2 Agent Config

`POST/PUT /api/v1/agents` — `config.settings` now accepts `postCallExtraction` (expanded) and `crmWriteback` sections as described in §3 and §4.3. No schema change to the `extraction_fields` column.

### 7.3 Agent Writeback Mapping Shortcut

```
GET  /api/v1/agents/{agent_id}/writeback-mapping
PUT  /api/v1/agents/{agent_id}/writeback-mapping
```

Convenience endpoints. Read/write from `config.settings.crmWriteback.mapping`.

### 7.4 Manual Re-extraction

```
POST /api/v1/calls/{call_id}/extract
```

Re-runs extraction with the agent's current config. For backfilling or re-running after template changes.

---

## 8. Database Changes

### 8.1 Migration — Writeback Columns on `calls`

```sql
ALTER TABLE calls ADD COLUMN writeback_status VARCHAR(20);
ALTER TABLE calls ADD COLUMN writeback_error TEXT;
ALTER TABLE calls ADD COLUMN writeback_completed_at TIMESTAMPTZ;

CREATE INDEX idx_calls_writeback_status ON calls (writeback_status)
  WHERE writeback_status IS NOT NULL;
```

### 8.2 No Changes Needed

- `agents.extraction_fields` — custom fields still stored here
- `agents.config` — already JSONB, new keys go in `settings`
- `calls.extracted_data` — already JSONB with GIN index
- `campaign_contacts.writeback_status` — stays as-is for campaign use case
- `crm_integrations.config.field_mappings` — stays as tenant-global fallback

---

## 9. Frontend Changes

### 9.1 Agent Settings — Post-Call Extraction Tab

```
┌─────────────────────────────────────────────────────────────────┐
│  Post-Call Extraction                               [Enabled ✓] │
│                                                                 │
│  ── Default Fields ──────────────────────────────────────────── │
│  ☑ Call Summary          ☑ Success Evaluation                   │
│  ☑ Customer Sentiment    ☑ Customer Frustrated                  │
│  ☑ Script Followed                                              │
│                                                                 │
│  ── Template Categories ─────────────────────────────────────── │
│                                                                 │
│  [📅 Appointment]  [💰 Sales]  [🎧 Support]  [😊 CX]  [🛡 QA]  │
│   ✓ Enabled                                                     │
│                                                                 │
│   ☑ appointment_booked       boolean                            │
│   ☑ appointment_cancelled    boolean                            │
│   ☑ appointment_rescheduled  boolean                            │
│   ☑ booking_status           string                             │
│   ☑ appointment_date         string                             │
│   ☑ appointment_time         string                             │
│   ☐ booking_details          object    ← disabled by user       │
│                                                                 │
│  ── Custom Fields ───────────────────────────────────────────── │
│  ┌──────────────────┬────────┬────────────────────────────────┐ │
│  │ patient_name     │ string │ Full name of the patient       │ │
│  │ insurance_id     │ string │ Patient insurance ID number    │ │
│  └──────────────────┴────────┴────────────────────────────────┘ │
│  + Add Custom Field                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Agent Settings — CRM Writeback Tab

Reuse the existing `StepWritebackMapping` component from campaigns:

```
┌─────────────────────────────────────────────────────────────────┐
│  CRM Writeback                                        [Enabled] │
│                                                                 │
│  Target Module: [Contacts ▾]                                    │
│                                                                 │
│  Field Mappings                            [Auto-Map Matching]  │
│  ┌──────────────────────┬──┬──────────────────────────────────┐ │
│  │  call_summary        │→ │  Description                     │ │
│  │  appointment_date    │→ │  Appointment_Date                │ │
│  │  booking_status      │→ │  Booking_Status_c                │ │
│  │  customer_sentiment  │→ │  Sentiment_c                     │ │
│  └──────────────────────┴──┴──────────────────────────────────┘ │
│                                                                 │
│  + Add Mapping                                                  │
│                                                                 │
│  ℹ Unmapped fields: success_score, customer_frustrated          │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 Call Detail Modal — Grouped Extracted Data

```
┌──────────────────────────────────────────────────────────────┐
│  Call Analysis                                               │
│  Summary: "Customer rescheduled dental appointment..."       │
│  Successful: ✓ Yes    Score: 9/10    Sentiment: 😊 Positive  │
│                                                              │
│  Appointment                                                 │
│  Booked: No    Rescheduled: ✓ Yes    Status: Confirmed       │
│  Date: 2026-03-25    Time: 10:30 AM                          │
│                                                              │
│  Custom                                                      │
│  Patient Name: Rahul Sharma    Insurance Verified: ✓         │
│                                                              │
│  CRM Writeback: ✓ Synced at 14:32 IST                       │
└──────────────────────────────────────────────────────────────┘
```

### 9.4 Analytics Dashboard — New Widgets

With standardized field names, we can build dashboard aggregations:

- **Success Rate** — `COUNT(call_successful = true) / COUNT(*)` across calls
- **Average Success Score** — `AVG(success_score)` with trend line
- **Sentiment Distribution** — Pie chart of `customer_sentiment` values
- **Appointment Booking Rate** — For agents with appointment template
- **Average Resolution Time** — For agents with support template
- **Revenue Generated** — `SUM(revenue_amount)` for sales agents
- **Frustration Rate** — `COUNT(customer_frustrated = true) / COUNT(*)`

---

## 10. Cost & Performance

### 10.1 LLM Token Cost per Call

| Component | Tokens | Notes |
|---|---|---|
| System/instruction prompt | ~100 | Static overhead |
| Default fields (7 fields) | ~150 | Always included |
| One template category (~7 fields) | ~200 | Per enabled category |
| Custom fields (5 avg) | ~150 | Per agent |
| Transcript (5-min call) | ~1500-2000 | Proportional to call length |
| **Total (typical)** | **~2100** | With 1 template + 5 custom |

**Cost at GPT-4o-mini pricing:** ~$0.0003 per call (negligible).  
**Cost at GPT-4o pricing:** ~$0.01 per call (for higher accuracy).

### 10.2 CRM API Limits

| CRM | Rate Limit | Mitigation |
|---|---|---|
| Zoho CRM | 100 API calls/minute (Standard) | Celery rate limiter, exponential backoff |
| HubSpot | 100 calls/10 seconds (private app) | Queue-based batching |
| Salesforce | 100,000 calls/day | Unlikely to hit for SphereVoice volumes |

### 10.3 Extraction Latency

- LLM extraction: 1-3 seconds (async, after call ends — no user impact)
- CRM writeback: 500ms-2s per record (async Celery task)
- Total post-call processing: completes within 5 seconds of call end

---

## 11. Backward Compatibility

| Concern | Mitigation |
|---|---|
| Existing `extraction_fields` on agents | These become "custom fields" — no migration needed |
| Existing `extracted_data` on calls | Old data has no `_extraction_version` — queries check for its absence |
| Existing 3 toggle booleans (`callSummary`, `successBoolean`, `userSentiment`) | Map to new `defaults` config; old config still works |
| Existing campaign `writeback_mapping` | Priority chain: campaign mapping > agent mapping > tenant-global |
| Existing `crm_integrations.config.field_mappings` | Stays as tenant-global fallback when no agent mapping is configured |

---

## 12. Implementation Plan

### Phase 1 — Consolidate + Template Catalog + Expanded Defaults

- [ ] **Consolidate dual extraction paths** — remove inline extraction from orchestrator; move all extraction logic into the Celery `process_call` task using the unified `resolve_extraction_fields()`
- [ ] Create `backend/app/modules/pipeline/extraction_templates.py` with all template definitions
- [ ] Add `GET /api/v1/extraction-templates` endpoint
- [ ] Update `resolve_extraction_fields()` in `extraction.py` to merge defaults + templates + custom
- [ ] Add `_extraction_version`, `_extracted_at`, `_model_used` meta fields to extraction output
- [ ] Unify LLM provider resolution: Agent's provider → Azure OpenAI → OpenAI → basic fallback
- [ ] Set consistent `max_tokens=1000` and transcript truncation limit (~24k chars)
- [ ] Frontend: Template category picker in agent settings extraction tab
- [ ] Frontend: Show/hide individual fields within enabled categories
- [ ] Add `post_call_extraction_duration_seconds` Prometheus metric

### Phase 2 — Agent-Level CRM Writeback

- [ ] Alembic migration: Add `writeback_status`, `writeback_error`, `writeback_completed_at` to `calls`
- [ ] Add `crmWriteback` section to agent `config.settings` schema
- [ ] Update `_push_to_crm()` in Celery worker to resolve mapping: campaign > agent > tenant-global
- [ ] Frontend: CRM writeback mapping tab in agent settings (reuse campaign `StepWritebackMapping`)
- [ ] Frontend: Writeback status indicator in call detail modal
- [ ] Include `extracted_data` in `extraction_complete` webhook payload (already done in Celery path)

### Phase 3 — Analytics + Dashboard

- [ ] Backend: Add aggregate queries for new standard fields to analytics service
- [ ] Frontend: Dashboard widgets for success rate, sentiment, frustration, etc.
- [ ] Frontend: Grouped display of extracted data in call detail modal (by template category)
- [ ] Export: Include extracted_data fields in CSV/JSON call export
- [ ] Add backfill endpoint `POST /api/v1/calls/{call_id}/extract` for re-extraction

### Phase 4 — Multi-CRM

- [ ] Abstract CRM client interface from `ZohoCrmClient`
- [ ] HubSpot OAuth + CRM client implementation
- [ ] Salesforce OAuth + CRM client implementation
- [ ] Frontend: CRM selection in integration settings

---

## 13. Files to Create / Modify

| File | Action | Description |
|---|---|---|
| `backend/app/modules/pipeline/extraction_templates.py` | **Create** | Template catalog constants (`EXTRACTION_TEMPLATES`, `DEFAULT_FIELDS`) |
| `backend/app/modules/pipeline/extraction.py` | Modify | `resolve_extraction_fields()`, `build_extraction_prompt()`, meta fields |
| `backend/app/workers/post_call.py` | Modify | Use unified `resolve_extraction_fields()`, remove hardcoded 4-field prompt, add agent provider resolution |
| `backend/app/modules/pipeline/orchestrator.py` | Modify | Remove inline extraction call; rely on Celery `process_call` only |
| `backend/app/modules/calls/models.py` | Modify | Add `writeback_status`, `writeback_error`, `writeback_completed_at` columns |
| `backend/app/modules/calls/schemas.py` | Modify | Add writeback fields to `CallResponse` and `CallUpdateRequest` |
| `backend/app/modules/calls/router.py` | Modify | Add `POST /api/v1/calls/{call_id}/extract` re-extraction endpoint |
| `backend/app/modules/agents/router.py` | Modify | Add `GET /api/v1/extraction-templates` endpoint |
| `backend/app/modules/integrations/crm_data.py` | Modify | Accept agent-level writeback mapping in `push_call_to_crm()` |
| `backend/alembic/versions/xxx_add_call_writeback.py` | **Create** | Migration for new `calls` columns |
| `backend/tests/test_pipeline/test_extraction.py` | **Create** | Unit tests for field resolution, prompt building, meta fields |
| `frontend/src/modules/agents/components/agent-settings.tsx` | Modify | Expanded `PostCallExtractionSettings`, template picker, writeback tab |
| `frontend/src/modules/calls/components/call-detail-modal.tsx` | Modify | Grouped extracted data display, writeback status |

---

## 14. Prompt Engineering

### 14.1 Extraction Prompt Template

```
You are a data extraction assistant. Extract the following fields
from the call transcript below. Return ONLY a valid JSON object
with the field names as keys. If a field cannot be determined from
the transcript, set its value to null.

Fields to extract:
- "call_summary" (string): A 2-3 sentence summary of what the call was about
- "call_successful" (boolean): Whether the call's main objective was achieved
- "success_score" (number): Rate call success on a scale of 1-10
- "customer_sentiment" (string): Overall caller sentiment — one of: positive, neutral, negative
- "appointment_booked" (boolean): Tracks if a customer booked an appointment
[... all resolved fields ...]

Transcript:
ai: Hello, thank you for calling Dr. Patel's office. How can I help you today?
user: Hi, I need to reschedule my appointment from March 20th to the 25th.
[... full transcript ...]
```

### 14.2 LLM Configuration

| Parameter | Value | Rationale |
|---|---|---|
| `model` | Agent's `llm_model` or `gpt-4o-mini` fallback | Matches agent's configured provider |
| `temperature` | `0.0` | Deterministic extraction, no creative variance |
| `response_format` | `{"type": "json_object"}` | Guarantees valid JSON output |
| `max_tokens` | `500` (Celery) / `unset` (inline) | Should be set to ~1000 to handle large field sets |
| Transcript truncation | `[:8000]` chars (Celery) / none (inline) | Must be unified; target ~6000 tokens of transcript |

### 14.3 Prompt Optimization Notes

- **Field order matters.** Put high-priority fields (summary, success) first — LLMs pay more attention to early instructions
- **Type hints in prompt** constrain output. Use `(boolean)`, `(number)`, `(string: one of X, Y, Z)` for enum-like fields
- **Array fields** (`products_discussed`, `key_topics`): Instruct "Return as a JSON array of strings"
- **Object fields** (`booking_details`): Provide example sub-keys in the description
- **Null handling**: Explicit instruction "set to null if not determinable" prevents hallucination

---

## 15. Webhook Integration

### 15.1 Webhook Events

The post-call pipeline fires two webhook events:

| Event | When | Payload Includes |
|---|---|---|
| `call_ended` | Immediately after call status → completed | `call_id`, `agent_id`, `duration`, `status`, `from/to_number` |
| `extraction_complete` | After LLM extraction finishes | All of `call_ended` + `extracted_data` (full JSON object) |

### 15.2 Webhook Payload for `extraction_complete`

```json
{
  "event": "extraction_complete",
  "call_id": "uuid",
  "tenant_id": "uuid",
  "agent_id": "uuid",
  "direction": "inbound",
  "duration_seconds": 180,
  "extracted_data": {
    "call_summary": "...",
    "call_successful": true,
    "appointment_booked": true,
    "appointment_date": "2026-03-25",
    "_extraction_version": "1.0"
  }
}
```

### 15.3 Use Cases for Webhooks

- External analytics systems (Mixpanel, Amplitude) ingesting call outcomes
- CRM systems not natively supported (custom webhook → Zapier/Make → CRM)
- Notification systems (Slack alert when `customer_frustrated = true`)
- Call quality dashboards (external BI tool aggregating `quality_score`)

---

## 16. Tenant Isolation & Security

### 16.1 Data Access Control

| Data | Isolation Mechanism | Who Can Access |
|---|---|---|
| `calls.extracted_data` | RLS policy on `calls.tenant_id` | Tenant members only |
| `agents.extraction_fields` | RLS policy on `agents.tenant_id` | Tenant members only |
| `agents.config.crmWriteback` | Part of agent config — same RLS | Tenant members only |
| `crm_integrations.config.field_mappings` | RLS on `crm_integrations.tenant_id` | Tenant admins |
| Template catalog | Static constant — no tenant data | Everyone (public, read-only) |

### 16.2 CRM Credential Security

- CRM OAuth tokens stored encrypted (AES-256-GCM) in `crm_integrations.access_token_encrypted`
- Refresh tokens similarly encrypted in `crm_integrations.refresh_token_encrypted`
- Zoho API calls use tenant-scoped `ZohoCrmClient` — token refresh is transparent
- Extracted data written to CRM is **not re-encrypted** — it's already decrypted business data

### 16.3 LLM Data Privacy

- Transcripts are sent to the agent's configured LLM provider (OpenAI, Azure OpenAI, Groq, etc.)
- No transcript data is stored by the extraction system beyond what's already in `calls.transcript`
- Extracted data is a **subset** of the transcript — no new PII is generated

### 16.4 Published Agent Snapshots

When a call uses a published agent, extraction fields come from the **published snapshot** (`agent_versions`), not the current draft. This ensures:
- Changing extraction fields on the draft doesn't affect live calls
- Backfilling can re-run with the snapshot config from that agent version

---

## 17. Observability & Monitoring

### 17.1 Prometheus Metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `worker_tasks_total` | Counter | `task_name=process_call`, `status=success/failure` | Total post-call tasks processed |
| `worker_task_duration_seconds` | Histogram | `task_name=process_call` | End-to-end processing time |
| `post_call_extraction_duration_seconds` | Histogram | `model`, `field_count` | LLM extraction latency (new) |
| `crm_writeback_total` | Counter | `status=success/failed/skipped` | CRM writeback outcomes (existing in campaigns) |

### 17.2 Structured Logging

Key log events in the pipeline:

```
post_call_processing_started    call_id=<uuid>
post_call_extraction_success    call_id=<uuid> sentiment=positive
post_call_extraction_llm_failed call_id=<uuid>                     # LLM call failed
recording_uploaded              call_id=<uuid> blob_url=<url>
webhooks_dispatched             call_id=<uuid> event_type=extraction_complete webhook_count=2
crm_call_pushed                 call_id=<uuid> who_id=<zoho_id> call_logged=true note_added=true
crm_push_skipped_no_integration tenant_id=<uuid>
post_call_processing_complete   call_id=<uuid> extracted_keys=[call_summary, ...] crm_pushed=true
```

### 17.3 Alerting Rules

| Alert | Condition | Severity |
|---|---|---|
| Extraction failure rate > 10% | `rate(worker_tasks_total{status="failure"}[5m]) / rate(worker_tasks_total[5m]) > 0.1` | Warning |
| CRM writeback failure rate > 20% | `rate(crm_writeback_total{status="failed"}[5m]) > 0.2` | Warning |
| Extraction latency P95 > 10s | `histogram_quantile(0.95, post_call_extraction_duration_seconds) > 10` | Warning |
| Post-call queue depth > 100 | Celery queue size for `process_call` | Critical |

---

## 18. Error Handling & Retry

### 18.1 Celery Task Retry

The `process_call` task has `max_retries=3`. Retry scenarios:

| Failure | Retry? | Behavior |
|---|---|---|
| LLM API timeout/5xx | Yes | Retry with exponential backoff |
| LLM API 401/403 (bad key) | No | Fail immediately, log warning |
| CRM API failure | No (CRM push is non-fatal) | Log warning, continue pipeline |
| Recording upload failure | No | Log warning, continue with extraction |
| DB connection error | Yes | Retry with backoff |

### 18.2 Graceful Degradation

```python
# Extraction fallback chain:
# 1. Agent's configured LLM provider (via httpx)
# 2. Azure OpenAI (if AZURE_OPENAI_ENDPOINT set)
# 3. OpenAI direct (if OPENAI_API_KEY set)
# 4. Basic fallback: word count summary, neutral sentiment, call_successful=false
```

### 18.3 Idempotency

- Re-running extraction on the same call overwrites `extracted_data` (not additive)
- CRM writeback uses Zoho upsert (not insert) — safe to retry
- Recording upload uses `overwrite=True` — safe to retry

---

## 19. Testing Strategy

### 19.1 Unit Tests

| Test | File | What It Covers |
|---|---|---|
| `test_resolve_extraction_fields()` | `tests/test_pipeline/test_extraction.py` | Default fields, template merging, disabled fields, custom fields |
| `test_build_extraction_prompt()` | `tests/test_pipeline/test_extraction.py` | Prompt correctness, field ordering, transcript formatting |
| `test_extraction_meta_fields()` | `tests/test_pipeline/test_extraction.py` | `_extraction_version`, `_extracted_at`, `_model_used` added correctly |
| `test_writeback_mapping_priority()` | `tests/test_pipeline/test_extraction.py` | Campaign > agent > tenant-global chain |

### 19.2 Integration Tests

| Test | What It Covers |
|---|---|
| `test_post_call_extraction_e2e()` | Full flow: call ends → extraction → `extracted_data` persisted |
| `test_crm_writeback_mapping()` | Extracted fields → CRM field names via mapping → Zoho upsert payload |
| `test_extraction_with_published_snapshot()` | Uses snapshot config, not draft |
| `test_extraction_no_transcript()` | Graceful return of empty dict |

### 19.3 Manual Testing

1. Create agent with appointment template + custom fields enabled
2. Make a test call about booking an appointment
3. Verify call detail modal shows grouped extracted data
4. Verify CRM record (if Zoho connected) has mapped fields updated
5. Verify `extraction_complete` webhook fires with correct payload

---

## 20. Migration & Backfill

### 20.1 Existing Calls

Existing calls have `extracted_data` with the legacy 3-4 field format:

```json
{"call_summary": "...", "user_sentiment": "neutral", "call_successful": false}
```

These calls will **not** have `_extraction_version`. Analytics queries should handle both:

```sql
-- New format
SELECT * FROM calls WHERE extracted_data->>'_extraction_version' = '1.0';

-- Legacy format (no version key)
SELECT * FROM calls WHERE extracted_data->>'_extraction_version' IS NULL;
```

### 20.2 Backfill Script

For agents that now have templates enabled, a backfill script can re-extract existing calls:

```python
# POST /api/v1/calls/{call_id}/extract
# Re-runs extraction with agent's current config
# Only works if call has transcript
```

**Constraints:**
- Only re-extract calls that have a transcript
- Use batch processing (not all at once) to respect LLM rate limits
- Cost consideration: ~$0.0003/call × 1000 calls = $0.30

### 20.3 Schema Version Bumps

When new default fields are added in the future:
1. Bump `_extraction_version` to `"1.1"`, `"2.0"`, etc.
2. New fields return `null` for calls extracted with older versions
3. Dashboard widgets check version before aggregating new fields
