# SphereVoice — Integration Execution Plan (v2)

**Document:** End-to-End Integration — Connecting the Blocks  
**Product:** SphereVoice - Internal Voice AI Agent Platform  
**Company:** Sphere AI  
**Version:** 2.0  
**Date:** March 25, 2026  
**Scope:** 5 Phases across ~8 weeks  
**Prerequisite:** All Phase 0–12 deliverables from execution-plan.md are complete  

---

## Executive Summary

All core building blocks of SphereVoice are production-ready but exist as disconnected capabilities. This plan wires them into a seamless product where:

1. **Pre-call:** Agent fetches full CRM context about the caller/target
2. **During call:** Agent executes real-time tool calls (Calendly, CRM write, WhatsApp, email)
3. **Post-call:** Extracted data is automatically written back to CRM fields
4. **Testing:** Calls can be simulated with realistic CRM data and validated against expected outcomes
5. **Campaigns:** Fully polished outbound engine accessible from main navigation

### What's Built vs What's Wired

| Block | Built | Wired E2E | Gap |
|-------|-------|-----------|-----|
| CRM pre-call enrichment (Zoho) | ✅ | ✅ | Default fields only — no custom field selection |
| Active tool calls during call | ✅ | ⚠️ Partial | Sheets works; Calendar/WhatsApp/Email are stubs |
| Post-call extraction | ✅ | ✅ | — |
| CRM write-back after call | ✅ | ⚠️ Campaigns only | Inbound calls with CRM context don't write back |
| Campaign wizard + engine | ✅ | ✅ | Not discoverable (missing from sidebar nav) |
| Call testing (browser + phone) | ✅ | ✅ | No way to inject mock CRM context for testing |
| Agent-level CRM config | ❌ | ❌ | No per-agent writeback mapping or CRM field selection |

---

## Phase Overview

| Phase | Name | Duration | Focus | Key Deliverable |
|-------|------|----------|-------|-----------------|
| **P1** | Wire the Blocks | 1.5 weeks | Backend + Frontend | Inbound CRM writeback, agent CRM config, sidebar nav fix, test call CRM context |
| **P2** | Real Tool Integrations | 2 weeks | Backend + Pipeline | Calendly availability/booking, CRM mid-call write, WhatsApp send, email send |
| **P3** | Campaign Polish | 1.5 weeks | Frontend + Backend | CSV import, campaign clone, contact preview, real-time progress, campaign nav |
| **P4** | Call Simulation & QA | 1.5 weeks | Full Stack | Scenario-based testing, extraction validation, call replay |
| **P5** | Analytics, A/B & Scale | 1.5 weeks | Full Stack | Campaign analytics, A/B testing, scheduling, HubSpot CRM |

---

## Guiding Principles (Inherited + New)

| # | Principle |
|---|-----------|
| 1 | **Wire before build** — connect existing blocks before adding new ones |
| 2 | **One integration at a time** — ship Calendly fully before starting WhatsApp |
| 3 | **Agent-centric config** — all CRM/tool behavior is configured per-agent, not globally |
| 4 | **Graceful degradation** — if a tool call fails mid-call, the agent apologizes and continues |
| 5 | **Test what you ship** — every new integration gets a corresponding test scenario |

---

## Phase 1: Wire the Blocks (Week 1–2, first half)

**Goal:** Close the three biggest gaps — inbound CRM writeback, agent-level CRM config, and campaigns discoverability. After this phase, a user can configure an agent to read from CRM, have a call, and automatically write extracted data back to CRM — without needing a campaign.

**Exit Criteria:** Inbound call with known Zoho contact → extraction runs → data writes back to Zoho Lead/Contact fields. Campaigns link visible in sidebar.

### P1.1 — Add Campaigns to Main Sidebar Navigation

**Problem:** Campaigns exist at `/workspace/{tenantId}/campaigns` but there's no link in the main sidebar (`frontend/src/components/layout/sidebar.tsx`). Users can't discover the feature.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P1.1.1 | Add "Campaigns" nav item to `NAV_ITEMS` array in sidebar | FE | `frontend/src/components/layout/sidebar.tsx` | Link appears between "Live Calls" and "Phone Numbers" with `Megaphone` icon |
| P1.1.2 | Create top-level `/campaigns` route page | FE | `frontend/src/app/(dashboard)/campaigns/page.tsx` | Page redirects to workspace-scoped campaigns or shows tenant picker for admin |
| P1.1.3 | Create `/campaigns/new` route | FE | `frontend/src/app/(dashboard)/campaigns/new/page.tsx` | Uses CampaignWizard, infers tenant from user context |
| P1.1.4 | Create `/campaigns/[id]` route | FE | `frontend/src/app/(dashboard)/campaigns/[id]/page.tsx` | Uses CampaignDashboard component |

**Why this is P0:** A fully built feature that's invisible is worse than no feature.

---

### P1.2 — Agent-Level CRM Write-back Configuration

**Problem:** Write-back mapping only exists in Campaign config. For inbound calls, there's nowhere to say "after this agent's call, write `qualification_status` to Zoho `Lead_Status`."

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P1.2.1 | Add `crm_writeback_mapping` (JSONB) field to Agent model | BE | `backend/app/modules/agents/models.py` | Alembic migration adds nullable JSONB column, default `{}` |
| P1.2.2 | Add `crm_writeback_enabled` (Boolean) field to Agent model | BE | `backend/app/modules/agents/models.py` | Default `false`, same migration |
| P1.2.3 | Update Agent schemas to include new CRM fields | BE | `backend/app/modules/agents/schemas.py` | `AgentUpdate` and `AgentResponse` include `crm_writeback_mapping` and `crm_writeback_enabled` |
| P1.2.4 | Build "CRM Write-back" config section in Agent settings UI | FE | `frontend/src/modules/agents/components/agent-crm-config.tsx` (new) | Section shows: toggle to enable, mapping table (extraction field → CRM field name), save button |
| P1.2.5 | Integrate CRM config section into agent detail page | FE | `frontend/src/modules/agents/components/agent-detail-page.tsx` | New tab/section appears when editing agent, only shown when tenant has CRM integration |

**Schema for `crm_writeback_mapping`:**
```json
{
  "customer_name": "Full_Name",
  "qualification_status": "Lead_Status",
  "preferred_meeting_date": "Custom_Meeting_Date",
  "notes": "Description"
}
```

---

### P1.3 — Inbound Call CRM Write-back

**Problem:** When a known Zoho contact calls in, the agent enriches the call with their data, extracts fields post-call, but never writes anything back. The `campaign_crm_writeback` worker only fires for campaign contacts.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P1.3.1 | Create `inbound_crm_writeback` Celery task | BE | `backend/app/workers/post_call.py` or `backend/app/modules/integrations/workers.py` (new) | Task accepts `call_id`, fetches call → agent → CRM integration, applies mapping, writes to Zoho |
| P1.3.2 | Trigger writeback after extraction in orchestrator | BE | `backend/app/modules/pipeline/orchestrator.py` | After `run_post_call_extraction()` succeeds: if agent has `crm_writeback_enabled=True` AND call has `caller_crm_id` in dynamic vars → enqueue `inbound_crm_writeback.delay(call_id)` |
| P1.3.3 | Reuse Zoho write logic from campaign worker | BE | `backend/app/modules/integrations/crm_data.py` | Extract shared `write_to_crm(db, integration, crm_module, crm_record_id, field_mapping, extracted_data)` function used by both campaign and inbound writers |
| P1.3.4 | Add `crm_writeback_status` field to Call model | BE | `backend/app/modules/calls/models.py` | New field: `crm_writeback_status` (String, nullable) — values: `pending`, `success`, `failed`, `skipped` |
| P1.3.5 | Show CRM writeback status on Call detail UI | FE | `frontend/src/modules/calls/components/call-detail-modal.tsx` | Badge showing writeback status + mapped fields that were written |

**Data Flow (after this phase):**
```
Inbound Call → CRM Enrichment (pre-call) → Voice Pipeline → Call Ends
  → Post-Call Extraction → extracted_data saved to calls table
  → IF agent.crm_writeback_enabled AND call has caller_crm_id:
      → enqueue inbound_crm_writeback(call_id)
      → Worker: fetch call.extracted_data + agent.crm_writeback_mapping
      → Map: {"qualification_status": "Hot"} → {"Lead_Status": "Hot"}
      → Zoho API: PUT /crm/v8/Leads/{crm_id} with mapped fields
      → Update call.crm_writeback_status = "success" | "failed"
```

---

### P1.4 — Test Calls with CRM Context

**Problem:** Test calls don't inject CRM data, so you can't verify how the agent handles real customer scenarios (e.g., "Hi John, I see you're interested in our MBA program").

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P1.4.1 | Add "CRM Context" panel to test call UI | FE | `frontend/src/modules/agents/components/test-call-panel.tsx` | Expandable section with form fields matching the agent's expected variables (caller_name, caller_email, etc.) |
| P1.4.2 | Support preset test personas | FE | `frontend/src/modules/agents/components/test-personas.tsx` (new) | Dropdown with 3–5 common personas: "New Lead", "Returning Customer", "Angry Caller", or load from recent CRM contacts |
| P1.4.3 | Pass CRM context as `dynamic_variables` in test call request | FE | `frontend/src/modules/agents/hooks/use-test-call.ts` | `POST /api/v1/calls/test` body includes `dynamic_variables` from CRM context form |
| P1.4.4 | Validate dynamic_variables are injected into prompt during test calls | BE | `backend/app/modules/pipeline/orchestrator.py` | Verify test call path merges user-provided `dynamic_variables` with defaults — already works but needs explicit test |

**No backend change needed** — the `dynamic_variables` parameter already exists in the test call API. This is purely a frontend UX improvement.

---

### Phase 1 Gate

- [ ] Campaigns link visible in main sidebar for all users
- [ ] Agent detail page has CRM Write-back configuration section
- [ ] Inbound call from known Zoho contact → post-call extraction → automatic Zoho field update
- [ ] Test call UI allows injecting custom CRM context (caller name, email, company, etc.)
- [ ] `call.crm_writeback_status` visible on call detail page

---

## Phase 2: Real Tool Integrations (Week 2–4)

**Goal:** Replace stub tool executors with real integrations so agents can take actions during live calls — check calendar availability, book appointments, send WhatsApp messages, update CRM fields in real-time, and send follow-up emails.

**Exit Criteria:** During a live call, the agent can check Calendly availability, book a meeting, send a WhatsApp confirmation, and update the CRM Lead_Status — all verified via test call.

**Priority order:** Calendly > CRM real-time write > WhatsApp > Email

---

### P2.1 — Calendly / Cal.com Integration (Availability + Booking)

**Problem:** The calendar executor currently returns a static booking link. The agent can't check if a slot is available or actually book a meeting.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P2.1.1 | Add Cal.com API client (OAuth or API key) | BE | `backend/app/modules/integrations/calendar/calcom_client.py` (new) | Supports: `list_event_types()`, `get_availability(date_range)`, `create_booking(event_type, datetime, attendee)` |
| P2.1.2 | Add Calendly v2 API client | BE | `backend/app/modules/integrations/calendar/calendly_client.py` (new) | Supports: `list_event_types()`, `get_availability(date_range, event_type)`, `create_scheduling_link(event_type, prefill)` |
| P2.1.3 | Create `CalendarExecutor` with real API calls | BE | `backend/app/modules/tool_registry/executors/calendar.py` | Replaces stub; dispatches to Cal.com or Calendly based on tool config |
| P2.1.4 | Define two calendar tool schemas: `check_availability` and `book_appointment` | BE | `backend/app/modules/tool_registry/executors/calendar.py` | `check_availability(date, time_range)` → returns slots; `book_appointment(datetime, name, email)` → returns confirmation |
| P2.1.5 | Add calendar integration to tenant integrations UI | FE | `frontend/src/modules/integrations/` | Card for Cal.com / Calendly with API key input and connection test |
| P2.1.6 | Add calendar tool config to Agent tools panel | FE | `frontend/src/modules/agents/components/agent-tools-config.tsx` | When calendar tool is bound, show: event type selector, default duration, booking confirmation message |

**During-call flow:**
```
User: "Can I schedule a meeting for Friday?"
  → LLM calls check_availability(date="2026-03-27")
  → CalendarExecutor → Cal.com API → returns ["10:00 AM", "2:00 PM", "4:30 PM"]
  → LLM: "I have 10 AM, 2 PM, and 4:30 PM available on Friday. Which works best?"
User: "2 PM works"
  → LLM calls book_appointment(datetime="2026-03-27T14:00", name="John Doe", email="john@example.com")
  → CalendarExecutor → Cal.com API → creates booking → returns confirmation URL
  → LLM: "Done! I've booked you for Friday at 2 PM. You'll receive a calendar invite shortly."
```

---

### P2.2 — CRM Real-Time Write (Mid-Call Field Update)

**Problem:** CRM updates only happen post-call. During a call, the agent should be able to update a field immediately (e.g., mark lead as "Interested" mid-call, or update a contact's phone preference).

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P2.2.1 | Create `CrmWriteExecutor` | BE | `backend/app/modules/tool_registry/executors/crm_write.py` (new) | Accepts: `module`, `record_id`, `fields` dict; writes to Zoho via existing `ZohoCrmClient` |
| P2.2.2 | Auto-inject `caller_crm_id` and `caller_crm_module` into tool context | BE | `backend/app/modules/pipeline/flow_engine.py` | When CRM write tool is called, automatically populate `record_id` and `module` from the call's enrichment data |
| P2.2.3 | Define `update_crm_field` tool schema | BE | `backend/app/modules/tool_registry/executors/crm_write.py` | Function schema: `update_crm_field(field_name: str, value: str)` — restricted to fields listed in agent tool config |
| P2.2.4 | Add CRM write tool config in agent tools panel | FE | `frontend/src/modules/agents/components/agent-tools-config.tsx` | When CRM write tool is bound, show: allowed field names (restrict what LLM can update), confirmation behavior (ask before write / auto-write) |

**Safety guardrails:**
- Agent tool config defines allowed fields (e.g., only `Lead_Status`, `Description`) — LLM cannot update arbitrary fields
- Optional "confirm before write" mode where agent asks user before updating CRM
- All CRM writes are logged in `crm_sync_log` for audit

---

### P2.3 — WhatsApp Message Sending (Meta Cloud API)

**Problem:** The WhatsApp executor is a stub that logs but doesn't send.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P2.3.1 | Add Meta WhatsApp Cloud API client | BE | `backend/app/modules/integrations/messaging/whatsapp_client.py` (new) | Supports: `send_template_message(phone, template_name, params)`, `send_text_message(phone, text)` |
| P2.3.2 | Update `WhatsAppExecutor` with real API calls | BE | `backend/app/modules/tool_registry/executors/whatsapp.py` | Sends message via Meta Cloud API; returns delivery status |
| P2.3.3 | Add WhatsApp integration config (Meta Business ID, token) | BE | `backend/app/modules/integrations/messaging/` | Encrypted credential storage via existing `provider_keys` pattern |
| P2.3.4 | Add WhatsApp integration to tenant settings UI | FE | `frontend/src/modules/integrations/` | Card with API token input, business ID, phone number ID, test send button |
| P2.3.5 | Define `send_whatsapp` tool schema with template support | BE | `backend/app/modules/tool_registry/executors/whatsapp.py` | `send_whatsapp(to_phone: str, message: str)` — can auto-fill `to_phone` from caller's number |

**During-call flow:**
```
Agent: "I'll send you the brochure on WhatsApp right now."
  → LLM calls send_whatsapp(to_phone="+919876543210", message="Here's the MBA brochure: https://...")
  → WhatsAppExecutor → Meta Cloud API → message delivered
  → LLM: "Sent! Check your WhatsApp for the brochure."
```

---

### P2.4 — Email Sending (SendGrid/Postmark)

**Problem:** Email executor is a stub.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P2.4.1 | Add SendGrid email client | BE | `backend/app/modules/integrations/email/sendgrid_client.py` (new) | Supports: `send_email(to, subject, body_html, from_email)` |
| P2.4.2 | Update `EmailExecutor` with real SendGrid integration | BE | `backend/app/modules/tool_registry/executors/email.py` | Validates email, sends via SendGrid; returns delivery ID |
| P2.4.3 | Add email integration config to tenant settings | FE | `frontend/src/modules/integrations/` | Card with SendGrid API key, default from address, test send |
| P2.4.4 | Define `send_email` tool schema | BE | `backend/app/modules/tool_registry/executors/email.py` | `send_email(to_email: str, subject: str, body: str)` — auto-fill `to_email` from CRM context if available |

---

### P2.5 — Tool Execution Error Handling & Audit

**Problem:** When a tool call fails during a live call, the pipeline may hang or crash. Need graceful degradation.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P2.5.1 | Wrap all tool executor calls in try/catch with timeout | BE | `backend/app/modules/pipeline/flow_engine.py` | If tool call fails: return friendly error message to LLM ("I wasn't able to check the calendar right now, let me try another way") |
| P2.5.2 | Add tool execution timeout (default 10s) | BE | `backend/app/modules/tool_registry/executors/base.py` | `asyncio.wait_for()` wrapper; configurable per tool |
| P2.5.3 | Log all tool call results to `call_tool_executions` table | BE | `backend/app/modules/tool_registry/models.py` | New table: `call_id`, `tool_name`, `arguments`, `result`, `status`, `duration_ms`, `error` |
| P2.5.4 | Show tool execution log on call detail page | FE | `frontend/src/modules/calls/components/call-detail-modal.tsx` | Timeline section showing tool calls made during the call with results |

---

### Phase 2 Gate

- [ ] During a test call, agent checks Calendly availability and books an appointment
- [ ] During a call, agent updates a CRM field in real-time (with audit log)
- [ ] During a call, agent sends a WhatsApp message to the caller
- [ ] During a call, agent sends an email to the caller
- [ ] Failed tool calls return graceful error to LLM (no pipeline crash)
- [ ] All tool calls logged in `call_tool_executions` table and visible in UI

---

## Phase 3: Campaign Polish (Week 4–5.5)

**Goal:** Make the campaigns module production-complete with CSV import, cloning, real-time progress, and better contact management.

**Exit Criteria:** User can create a campaign from CSV upload, preview contacts before loading, clone an existing campaign, and see real-time call progress without refreshing.

---

### P3.1 — CSV Contact Import

**Problem:** Campaigns can only load contacts from Zoho CRM. Many users have contact lists in spreadsheets.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P3.1.1 | Create CSV parser service with column detection | BE | `backend/app/modules/campaigns/csv_parser.py` (new) | Accepts uploaded CSV, returns: column headers, row count, sample rows (first 5) |
| P3.1.2 | Add `POST /api/v1/campaigns/{id}/upload-csv` endpoint | BE | `backend/app/modules/campaigns/router.py` | Accepts multipart file upload, stores in blob storage, returns file_id + column headers + preview |
| P3.1.3 | Add `POST /api/v1/campaigns/{id}/load-from-csv` endpoint | BE | `backend/app/modules/campaigns/router.py` | Accepts file_id + column_mapping (which CSV column = phone, which = first_name, etc.); creates campaign_contacts rows |
| P3.1.4 | Build CSV upload + column mapping UI in wizard step | FE | `frontend/src/modules/campaigns/components/campaign-builder/step-csv-upload.tsx` (new) | File dropzone, column mapping dropdowns (Phone → CSV column, Name → CSV column), preview table |
| P3.1.5 | Update StepCrmSource to support CSV as source type | FE | `frontend/src/modules/campaigns/components/campaign-builder/step-crm-source.tsx` | Toggle between "CRM (Zoho)" and "CSV Upload" source type; show appropriate UI |

**CSV validation rules:**
- Must have a column mappable to phone number (E.164 or normalizable)
- Max 10,000 rows per upload (configurable via env var)
- Duplicate phone numbers within same campaign are deduplicated
- Invalid phone numbers are flagged with warning (not rejected)

---

### P3.2 — Contact Preview Before Loading

**Problem:** When loading contacts from CRM, users can't see what they're about to import.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P3.2.1 | Add `POST /api/v1/campaigns/{id}/preview-contacts` endpoint | BE | `backend/app/modules/campaigns/router.py` | Returns preview: total count, first 20 contacts (name, phone, email), applied filters |
| P3.2.2 | Build contact preview dialog | FE | `frontend/src/modules/campaigns/components/campaign-builder/contact-preview.tsx` (new) | Shows count + sample table + "Looks good, load all" button |
| P3.2.3 | Add preview step between CRM source config and variable mapping | FE | `frontend/src/modules/campaigns/components/campaign-builder/campaign-wizard.tsx` | After CRM source is configured, show preview before proceeding |

---

### P3.3 — Campaign Cloning

**Problem:** Creating similar campaigns requires recreating everything from scratch.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P3.3.1 | Add `POST /api/v1/campaigns/{id}/clone` endpoint | BE | `backend/app/modules/campaigns/router.py` | Creates new campaign with same config (agent, mappings, settings) but status=draft, no contacts |
| P3.3.2 | Add "Clone" button to campaign dashboard and campaign list | FE | `frontend/src/modules/campaigns/components/campaign-detail/campaign-dashboard.tsx`, `campaign-list.tsx` | Button opens confirm dialog, creates clone, navigates to new campaign |

---

### P3.4 — Real-Time Campaign Progress

**Problem:** Campaign dashboard requires manual refresh to see progress.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P3.4.1 | Add SSE endpoint `GET /api/v1/campaigns/{id}/stream` | BE | `backend/app/modules/campaigns/router.py` | Server-sent events: `call_started`, `call_completed`, `call_failed`, `stats_updated` |
| P3.4.2 | Publish campaign events from Celery worker to Redis pub/sub | BE | `backend/app/modules/campaigns/workers.py` | After each call completes, publish event to `campaign:{id}:events` channel |
| P3.4.3 | Connect campaign dashboard to SSE stream | FE | `frontend/src/modules/campaigns/hooks/use-campaign-stream.ts` (new) | Dashboard auto-updates stats cards and contacts table without refresh |
| P3.4.4 | Add live progress bar with ETA | FE | `frontend/src/modules/campaigns/components/campaign-detail/campaign-dashboard.tsx` | Shows: X/Y calls done, estimated completion time based on current rate |

**Fallback:** If SSE is problematic, use 5-second polling of stats endpoint (simpler, already works).

---

### P3.5 — Campaign Retry & Error Recovery

**Problem:** When a contact call fails, retry requires manual per-contact action. Bulk retry and smart retry policies are missing.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P3.5.1 | Add "Retry All Failed" button on campaign dashboard | FE | `frontend/src/modules/campaigns/components/campaign-detail/campaign-dashboard.tsx` | Button resets all `failed` contacts to `pending` and re-enqueues |
| P3.5.2 | Add `POST /api/v1/campaigns/{id}/retry-failed` endpoint | BE | `backend/app/modules/campaigns/router.py` | Resets all failed contacts (under max_attempts) to pending, re-enqueues |
| P3.5.3 | Show failure reason on contact detail | FE | `frontend/src/modules/campaigns/components/campaign-detail/contact-detail-dialog.tsx` | Display: error message, attempt count, last attempt timestamp, next retry time |

---

### Phase 3 Gate

- [ ] Campaign wizard supports CSV upload with column mapping
- [ ] Contact preview shows before loading from CRM
- [ ] Campaign cloning works from dashboard and list view
- [ ] Campaign progress updates in real-time (SSE or polling)
- [ ] "Retry All Failed" button works for bulk retry
- [ ] Failure reasons visible on contact detail

---

## Phase 4: Call Simulation & QA (Week 5.5–7)

**Goal:** Build a testing framework that lets users (and the team) run realistic call scenarios, validate agent behavior, and compare agent versions — without needing real callers.

**Exit Criteria:** User can create a test scenario with CRM data, run it against an agent, see transcript + extraction results, and compare with expected outcomes.

---

### P4.1 — Scenario-Based Test Calls

**Problem:** Test calls use blank context. You can't simulate "John calls about his MBA application" without a real call.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P4.1.1 | Create `test_scenarios` table | BE | `backend/app/modules/agents/models.py` | Fields: `agent_id`, `name`, `description`, `dynamic_variables` (JSONB), `expected_outcomes` (JSONB), `created_by` |
| P4.1.2 | Add CRUD endpoints for test scenarios | BE | `backend/app/modules/agents/router.py` | `POST/GET/PUT/DELETE /api/v1/agents/{id}/test-scenarios` |
| P4.1.3 | Build scenario manager UI | FE | `frontend/src/modules/agents/components/test-scenarios/` (new dir) | List of scenarios per agent, create/edit form with variable inputs + expected outcomes |
| P4.1.4 | "Run Scenario" button starts test call with pre-filled context | FE | `frontend/src/modules/agents/components/test-scenarios/run-scenario.tsx` (new) | Calls `POST /api/v1/calls/test` with scenario's `dynamic_variables`, opens transcript viewer |

**Scenario example:**
```json
{
  "name": "Hot MBA Lead Follow-up",
  "dynamic_variables": {
    "caller_name": "Rahul Sharma",
    "caller_email": "rahul@example.com",
    "caller_company": "TCS",
    "caller_city": "Mumbai",
    "caller_lead_status": "Warm Lead",
    "course_interest": "MBA"
  },
  "expected_outcomes": {
    "qualification_status": "Hot Lead",
    "preferred_meeting_date": "any_date",
    "contact_method": "whatsapp"
  }
}
```

---

### P4.2 — Post-Call Outcome Validation

**Problem:** After a test call, you manually check if the agent extracted the right data. No automated validation.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P4.2.1 | Add `test_call_results` table | BE | `backend/app/modules/agents/models.py` | Links `call_id` + `scenario_id`, stores: `extracted_data`, `expected_outcomes`, `match_results` (per-field pass/fail) |
| P4.2.2 | Build outcome matcher service | BE | `backend/app/modules/agents/test_matcher.py` (new) | Compares extracted_data vs expected_outcomes: exact match, contains, regex, `any_*` wildcards |
| P4.2.3 | Auto-run matcher when test call with scenario completes | BE | `backend/app/modules/pipeline/orchestrator.py` | If call was from a scenario → run matcher → store results |
| P4.2.4 | Build test results UI | FE | `frontend/src/modules/agents/components/test-scenarios/test-results.tsx` (new) | Table: field name, expected, actual, pass/fail badge; overall score |
| P4.2.5 | Scenario history: list all runs of a scenario with pass/fail | FE | `frontend/src/modules/agents/components/test-scenarios/scenario-history.tsx` (new) | Timeline showing each run: date, agent version, overall pass/fail, link to transcript |

---

### P4.3 — Agent Version Comparison

**Problem:** When you change an agent's prompt or config, there's no way to know if it got better or worse without manually testing.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P4.3.1 | "Run against version" — run scenario with a specific published version | BE | `backend/app/modules/calls/router.py` | `POST /api/v1/calls/test` accepts optional `agent_version` parameter |
| P4.3.2 | Side-by-side comparison view | FE | `frontend/src/modules/agents/components/test-scenarios/version-compare.tsx` (new) | Two-column layout: left = version N result, right = version N+1 result; field diffs highlighted |

---

### P4.4 — Tool Call Verification in Tests

**Problem:** Test calls execute real tool calls (send real WhatsApp, book real meetings). Need a "dry run" mode.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P4.4.1 | Add `dry_run` mode to all tool executors | BE | `backend/app/modules/tool_registry/executors/base.py` | When `dry_run=True`: skip actual API call, return mock success response, log what would have been sent |
| P4.4.2 | Enable dry_run for test calls by default | BE | `backend/app/modules/pipeline/orchestrator.py` | Test calls pass `dry_run=True` to tool executor context |
| P4.4.3 | Show "simulated" badge on tool calls in test transcript | FE | `frontend/src/modules/agents/components/transcript-display.tsx` | Tool call entries show "Simulated" tag with what would have been sent |

---

### Phase 4 Gate

- [ ] Test scenarios can be created with custom CRM context per agent
- [ ] Running a scenario auto-validates extraction results against expected outcomes
- [ ] Scenario history shows pass/fail over time across agent versions
- [ ] Side-by-side version comparison shows extraction diffs
- [ ] Tool calls in test mode are simulated (no real API calls) with logged output

---

## Phase 5: Analytics, A/B & Scale (Week 7–8.5)

**Goal:** Campaign-level analytics, A/B testing between agents, scheduled campaigns, and HubSpot CRM support.

**Exit Criteria:** Campaign dashboard shows conversion funnel, A/B test compares two agents on split contact list, campaigns can be scheduled for future start.

---

### P5.1 — Campaign Analytics Dashboard

**Problem:** Campaign dashboard shows raw counts but no conversion analysis or cost insights.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P5.1.1 | Add `GET /api/v1/campaigns/{id}/analytics` endpoint | BE | `backend/app/modules/campaigns/router.py` | Returns: connection rate, avg call duration, extraction complete rate, CRM writeback success rate, cost per contact, total cost, conversion funnel stages |
| P5.1.2 | Build campaign analytics tab on dashboard | FE | `frontend/src/modules/campaigns/components/campaign-detail/campaign-analytics.tsx` (new) | Charts: conversion funnel (contacted → answered → qualified → meeting booked), cost breakdown, avg duration, status distribution pie chart |
| P5.1.3 | Add "Analytics" nav tab on campaign detail page | FE | `frontend/src/modules/campaigns/components/campaign-detail/campaign-dashboard.tsx` | Tab bar: Overview | Contacts | Analytics |
| P5.1.4 | Export analytics as PDF report | FE | `frontend/src/modules/campaigns/components/campaign-detail/campaign-analytics.tsx` | "Download Report" button generates summary PDF |

---

### P5.2 — A/B Testing (Two Agents, One Contact List)

**Problem:** No way to compare which agent prompt/config performs better on real calls.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P5.2.1 | Add `variant_agent_id` and `ab_split_percent` to Campaign model | BE | `backend/app/modules/campaigns/models.py` | Optional second agent; `ab_split_percent` (0–100, default 50) controls split |
| P5.2.2 | Split contact assignment in campaign worker | BE | `backend/app/modules/campaigns/workers.py` | When dequeuing a contact, assign to variant_agent based on split percent (random or deterministic round-robin) |
| P5.2.3 | Add `assigned_agent_id` to CampaignContact model | BE | `backend/app/modules/campaigns/models.py` | Tracks which agent variant handled each contact |
| P5.2.4 | Add A/B config step to campaign wizard | FE | `frontend/src/modules/campaigns/components/campaign-builder/step-ab-test.tsx` (new) | Optional step: select variant agent, set split percentage |
| P5.2.5 | A/B results view on campaign analytics | FE | `frontend/src/modules/campaigns/components/campaign-detail/campaign-analytics.tsx` | Side-by-side: Agent A vs Agent B — connection rate, qualification rate, avg duration, cost |

---

### P5.3 — Campaign Scheduling

**Problem:** Campaigns must be started manually. No way to schedule a campaign for Monday 9 AM.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P5.3.1 | Add Celery Beat task for scheduled campaign start | BE | `backend/app/workers/celery_app.py` | Periodic task (every 1 minute): query campaigns where `status='scheduled'` AND `scheduled_at <= now()` → start them |
| P5.3.2 | Add schedule picker to campaign call settings step | FE | `frontend/src/modules/campaigns/components/campaign-builder/step-call-settings.tsx` | Date/time picker for `scheduled_at` with timezone selector; or "Start immediately" toggle |
| P5.3.3 | Show scheduled time on campaign list and dashboard | FE | `frontend/src/modules/campaigns/components/campaign-list.tsx` | "Scheduled for Mon Mar 30, 9:00 AM IST" badge |

---

### P5.4 — HubSpot CRM Integration

**Problem:** Only Zoho CRM is production-ready. HubSpot client exists but is incomplete.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P5.4.1 | Complete HubSpot OAuth flow (authorization + token refresh) | BE | `backend/app/modules/integrations/crm/hubspot_client.py` | Full OAuth 2.0: authorization URL → callback → access_token + refresh_token → encrypted storage |
| P5.4.2 | Implement HubSpot contacts/companies/deals API methods | BE | `backend/app/modules/integrations/crm/hubspot_client.py` | `list_contacts()`, `find_contact_by_phone()`, `update_contact()`, `log_call()` |
| P5.4.3 | Normalize HubSpot responses to SphereVoice format | BE | `backend/app/modules/integrations/crm/hubspot_client.py` | Map HubSpot fields to same keys used by Zoho (Full_Name, Email, Phone, Company, etc.) |
| P5.4.4 | Add HubSpot integration card to frontend | FE | `frontend/src/modules/integrations/` | OAuth connect button, show connected status, test connection |
| P5.4.5 | Test: pre-call enrichment from HubSpot + post-call writeback | BE | Integration test | Call with HubSpot contact → agent gets context → extraction → writeback to HubSpot contact |

---

### P5.5 — Campaign Templates

**Problem:** Every campaign starts from scratch. Common patterns (lead qualification, appointment setting, follow-up) should have templates.

| # | Task | Owner | File(s) | Acceptance Criteria |
|---|------|-------|---------|---------------------|
| P5.5.1 | Create `campaign_templates` seed data | BE | `backend/app/modules/campaigns/templates.py` (new) | 3–5 templates: "Lead Qualification", "Appointment Setting", "Follow-up Call", "Survey", "Announcement" — each with pre-filled variable_mapping, writeback_mapping, call_settings |
| P5.5.2 | Add "Start from template" option to campaign wizard | FE | `frontend/src/modules/campaigns/components/campaign-builder/campaign-wizard.tsx` | Template selector as step 0, pre-fills wizard data |

---

### Phase 5 Gate

- [ ] Campaign analytics tab shows conversion funnel, cost per contact, status distribution
- [ ] A/B test campaign splits contacts between two agents with comparative analytics
- [ ] Scheduled campaigns auto-start at configured time
- [ ] HubSpot CRM: connect → pre-call enrich → post-call writeback (full loop)
- [ ] Campaign templates available as starting points

---

## Cross-Phase: Quality & Safety Requirements

These apply to ALL phases and must be verified at each gate:

### Security

| Requirement | Implementation |
|-------------|----------------|
| CRM credentials encrypted at rest | AES-256-GCM via existing `encryption.py` (already done) |
| Tool API keys never in logs | Sanitize executor logs to strip keys/tokens |
| WhatsApp messages rate-limited | Per-tenant rate limit (100 messages/hour default) |
| CSV uploads validated | Max 10MB, sanitize filenames, virus scan if available |
| CRM write operations audited | Every field update logged in `crm_sync_log` with user/call context |

### Observability

| Requirement | Implementation |
|-------------|----------------|
| Tool call latency tracked | OTEL span per tool execution: `tool.execute` with attributes: `tool.name`, `tool.type`, `tool.duration_ms` |
| CRM API call metrics | Counter: `crm_api_calls_total{provider, operation, status}` |
| Campaign progress metrics | Gauge: `campaign_calls_active{campaign_id}`, Counter: `campaign_calls_total{status}` |
| Test scenario pass rate | Counter: `test_scenario_runs_total{agent_id, result}` |

### Testing Strategy

| Test Type | Scope | Runs When |
|-----------|-------|-----------|
| Unit tests | Tool executors, CSV parser, outcome matcher | Every PR (CI) |
| Integration tests | CRM read/write, tool call during pipeline | Every PR (CI) |
| E2E test call | Full pipeline: enrich → call → extract → writeback | Post-deploy (daily) |
| Load test | 50 concurrent campaign calls | Pre-Phase 5 gate |

---

## Dependency Graph

```
Phase 1 (Wire the Blocks)
  ├── P1.1 Sidebar nav (no deps — do first)
  ├── P1.2 Agent CRM config (no deps)
  ├── P1.3 Inbound CRM writeback (depends on P1.2)
  └── P1.4 Test CRM context (no deps)

Phase 2 (Tool Integrations) — depends on Phase 1 complete
  ├── P2.1 Calendly (independent)
  ├── P2.2 CRM real-time write (independent)
  ├── P2.3 WhatsApp (independent)
  ├── P2.4 Email (independent)
  └── P2.5 Error handling (do last — wraps all executors)

Phase 3 (Campaign Polish) — can run parallel with Phase 2
  ├── P3.1 CSV import (independent)
  ├── P3.2 Contact preview (independent)
  ├── P3.3 Campaign clone (independent)
  ├── P3.4 Real-time progress (independent)
  └── P3.5 Retry improvements (independent)

Phase 4 (Call Simulation) — depends on Phase 2 (needs real tools for dry run)
  ├── P4.1 Scenarios (independent)
  ├── P4.2 Outcome validation (depends on P4.1)
  ├── P4.3 Version comparison (depends on P4.2)
  └── P4.4 Dry run mode (depends on Phase 2 executors)

Phase 5 (Analytics & Scale) — depends on Phase 3 + 4
  ├── P5.1 Campaign analytics (depends on Phase 3)
  ├── P5.2 A/B testing (depends on P5.1)
  ├── P5.3 Scheduling (independent)
  ├── P5.4 HubSpot (independent — can start earlier)
  └── P5.5 Templates (independent)
```

**Parallelization opportunity:** Phase 2 and Phase 3 can run in parallel with different engineers. Phase 2 is backend-heavy (tool integrations), Phase 3 is frontend-heavy (campaign UX).

---

## File Index: Key Files Modified Per Phase

### Phase 1

| File | Change |
|------|--------|
| `frontend/src/components/layout/sidebar.tsx` | Add Campaigns nav item |
| `frontend/src/app/(dashboard)/campaigns/` | New route pages |
| `backend/app/modules/agents/models.py` | Add `crm_writeback_mapping`, `crm_writeback_enabled` |
| `backend/app/modules/agents/schemas.py` | Update schemas |
| `backend/app/modules/pipeline/orchestrator.py` | Trigger inbound CRM writeback |
| `backend/app/modules/integrations/crm_data.py` | Extract shared `write_to_crm()` |
| `backend/app/modules/calls/models.py` | Add `crm_writeback_status` |
| `frontend/src/modules/agents/components/agent-crm-config.tsx` | New component |
| `frontend/src/modules/agents/components/test-call-panel.tsx` | Add CRM context inputs |

### Phase 2

| File | Change |
|------|--------|
| `backend/app/modules/integrations/calendar/` | New directory: Cal.com + Calendly clients |
| `backend/app/modules/integrations/messaging/` | New directory: WhatsApp client |
| `backend/app/modules/integrations/email/` | New directory: SendGrid client |
| `backend/app/modules/tool_registry/executors/calendar.py` | Replace stub with real integration |
| `backend/app/modules/tool_registry/executors/whatsapp.py` | Replace stub with real integration |
| `backend/app/modules/tool_registry/executors/email.py` | Replace stub with real integration |
| `backend/app/modules/tool_registry/executors/crm_write.py` | New executor |
| `backend/app/modules/pipeline/flow_engine.py` | Add tool error handling |
| `backend/app/modules/tool_registry/models.py` | Add `call_tool_executions` table |

### Phase 3

| File | Change |
|------|--------|
| `backend/app/modules/campaigns/csv_parser.py` | New: CSV parsing service |
| `backend/app/modules/campaigns/router.py` | Add CSV, preview, clone, stream endpoints |
| `frontend/src/modules/campaigns/components/campaign-builder/step-csv-upload.tsx` | New component |
| `frontend/src/modules/campaigns/components/campaign-builder/contact-preview.tsx` | New component |
| `frontend/src/modules/campaigns/hooks/use-campaign-stream.ts` | New hook |

### Phase 4

| File | Change |
|------|--------|
| `backend/app/modules/agents/models.py` | Add `test_scenarios`, `test_call_results` tables |
| `backend/app/modules/agents/test_matcher.py` | New: outcome comparison service |
| `backend/app/modules/tool_registry/executors/base.py` | Add `dry_run` mode |
| `frontend/src/modules/agents/components/test-scenarios/` | New directory: scenario CRUD + results UI |

### Phase 5

| File | Change |
|------|--------|
| `backend/app/modules/campaigns/models.py` | Add `variant_agent_id`, `ab_split_percent`, `assigned_agent_id` |
| `backend/app/modules/campaigns/workers.py` | A/B split logic |
| `backend/app/modules/integrations/crm/hubspot_client.py` | Complete implementation |
| `frontend/src/modules/campaigns/components/campaign-detail/campaign-analytics.tsx` | New component |
| `frontend/src/modules/campaigns/components/campaign-builder/step-ab-test.tsx` | New component |

---

## Success Metrics

After all 5 phases, SphereVoice should demonstrate:

| Metric | Target |
|--------|--------|
| **End-to-end CRM loop** | Inbound call → enrich → converse → extract → CRM writeback in < 5 seconds post-call |
| **Tool call success rate** | > 95% of tool calls complete without error during live calls |
| **Campaign completion rate** | > 90% of contacts reach a terminal state (completed/no_answer/busy) |
| **CRM writeback success rate** | > 98% of writeback attempts succeed on first try |
| **Test scenario coverage** | Every agent template has ≥ 3 test scenarios with expected outcomes |
| **Time to create campaign** | < 5 minutes from "New Campaign" to "Start" with CRM source |
| **Time to create campaign (CSV)** | < 3 minutes from CSV upload to "Start" |
