# Retell AI Platform — Full Feature Audit

**Purpose:** Competitive reference for the SphereVoice build  
**Audit Date:** February 2026  
**Auditor:** Sphere AI Team  
**Status:** Observation only — nothing was executed or modified on Retell  
**Last Updated:** March 3, 2026

---

## How This Document Fits

| Document | Purpose | Audience |
|----------|---------|----------|
| [prd.md](./prd.md) | WHAT we're building and WHY — features, user experience, business value | Everyone |
| [tech-prd.md](./tech-prd.md) | HOW we're building it — architecture, schemas, APIs, code, infrastructure | Engineering |
| **retell-audit.md** (this file) | Competitive reference — what Retell AI does, feature-by-feature, with SphereVoice gap analysis | Product & Engineering |

Use this audit to validate SphereVoice feature scope, identify gaps, and prioritize V1 vs V1.1 features. Each section includes a **SphereVoice Alignment** note mapping back to the PRD.

---

## Table of Contents

1. [Navigation Structure](#1-navigation-structure)
2. [Agents](#2-agents)
3. [Knowledge Base](#3-knowledge-base)
4. [Phone Numbers](#4-phone-numbers)
5. [Batch Call](#5-batch-call)
6. [Call History](#6-call-history)
7. [Chat History](#7-chat-history)
8. [Analytics](#8-analytics)
9. [AI Quality Assurance](#9-ai-quality-assurance)
10. [Alerting](#10-alerting)
11. [Billing](#11-billing)
12. [Settings](#12-settings)
13. [Overall Summary](#overall-platform-summary)
14. [SphereVoice Gap Analysis](#SphereVoice-gap-analysis)

---

## 1. NAVIGATION STRUCTURE

The left sidebar is organized into three sections:

**BUILD**: Agents, Knowledge Base
**DEPLOY**: Phone Numbers, Batch Call
**MONITOR**: Call History, Chat History, Analytics, AI Quality Assurance, Alerting (marked "New")
**SYSTEM**: Billing, Settings

The sidebar also shows a real-time status bar: Free Trial credit remaining ($10.00), Concurrency Used (0/20), and an "Add Payment" button.

---

## 2. AGENTS

This is the core feature and by far the most powerful part of the platform.

### Agent Types (4 types)
When creating a new agent, you choose one of:
- **Conversation Flow Agent** — Production-ready, deterministic conversations using a visual node-based flow builder. This is the flagship type.
- **Single Prompt Agent** — Simple, free-form LLM conversations driven by one large system prompt. Good for quick prototypes.
- **Multi-Prompt Agent (Legacy)** — Section-based prompt structure with branching logic. Older approach, still supported.
- **Custom LLM** — For compliance or heavy customization where you bring your own LLM endpoint.

Additionally, there are both **Voice Agents** and **Chat Agents** (two separate modalities).

**Quality Rating: 9/10** — Having four distinct agent architectures with a full visual flow builder is very sophisticated and rivals enterprise-grade systems.

> **SphereVoice Alignment:** SphereVoice V1 covers **Conversation Flow** and **Single Prompt** (prd.md §3.2, §3.3). Multi-Prompt and Custom LLM are not planned — acceptable since Multi-Prompt is legacy and Custom LLM is niche. Chat Agents are V2 scope (prd.md §8). ✅ Aligned.

---

### Conversation Flow Builder (Visual Node Editor)
This is a drag-and-drop canvas with the following node types:

| Node | Purpose |
|---|---|
| **Conversation** | A dialogue step where the AI speaks and listens |
| **Function** | Calls an external API or custom function |
| **Call Transfer** | Transfers the call to a human or another number |
| **Press Digit** | Sends DTMF tones (for IVR navigation) |
| **Logic Split** | Branches the flow based on conditions |
| **Agent Transfer** | Transfers to another Retell AI agent |
| **SMS** | Sends an SMS during a call |
| **Extract Variable** | Pulls structured data from the conversation |
| **MCP** | Model Context Protocol integration node |
| **Ending** | Terminates the call/flow |

The canvas has zoom/fit controls, supports multiple sub-flows ("Main Flow" tab + ability to add flows), and has a **Components** panel for reusable Library Components and Agent Components.

**Quality Rating: 9/10** — This is a genuinely excellent flow builder. The Logic Split, Agent Transfer, SMS, and Extract Variable nodes are especially powerful and rare in this space.

> **SphereVoice Alignment:** SphereVoice V1 supports 8 of 10 node types: Conversation, Function, Call Transfer, Press Digit, Logic Split, SMS, Extract Variable, Ending (prd.md §3.2). **Agent Transfer** and **MCP** are deferred to V1.1 (prd.md §8). ✅ Aligned.

---

### Single Prompt Agent Editor
- Large system prompt textarea with variable support (`{{variable_name}}`)
- Dynamic Variables documentation link
- **Welcome Message** section: can choose "AI speaks first" or "User speaks first", with a "Dynamic message" toggle
- **Functions** section: add callable functions (e.g., `transfer_call`, `end_call`, and custom ones)

**Quality Rating: 8/10** — Clean and functional.

> **SphereVoice Alignment:** Fully covered in prd.md §3.3, tech-prd.md §3.3. Variables, welcome message, functions all included. ✅ Aligned.

---

### LLM Options (supported models)
Retell hosts all of these natively — you don't need your own API keys:

**OpenAI**: GPT 5.2 ($0.056/min), GPT 5.1 ($0.04/min), GPT 5 ($0.04/min), GPT 5 mini ($0.012/min), GPT 5 nano ($0.003/min), GPT 4.1 ($0.045/min), GPT 4.1 mini ($0.016/min), GPT 4.1 nano ($0.004/min), GPT Realtime ($0.345/min), GPT Realtime mini ($0.07/min)

**Anthropic**: Claude 4.6 Sonnet ($0.08/min), Claude 4.5 Sonnet ($0.08/min), Claude 4.5 Haiku ($0.025/min)

**Google**: Gemini 3.0 Flash ($0.027/min), Gemini 2.5 Flash ($0.035/min), Gemini 2.5 Flash Lite ($0.006/min)

LLM Settings include: **Temperature** slider and **Structured Output** (JSON Schema enforcement toggle).

**Quality Rating: 10/10** — Best-in-class model selection with transparent per-minute pricing.

> **SphereVoice Alignment:** SphereVoice uses a BYOK (bring-your-own-key) model instead of hosting LLMs. Employees add their own OpenAI/Anthropic/Groq keys (prd.md §3.1). This is a deliberate strategic difference — no vendor lock-in, but requires more setup. Per-minute pricing is N/A since SphereVoice tracks cost-per-call from raw provider usage. ⚠️ Different by design.

---

### Voice / TTS Providers
The voice picker has full filtering by Gender, Accent, and Type. Supported providers:

- **MiniMax** (default, Retell-branded voices: Adrian, Andrew, Ashley, Brynne, Chloe, Cimo, Crystal, Daniel, Della, Grace, Hailey, Nia, etc.)
- **Fish Audio**
- **ElevenLabs**
- **Cartesia**
- **OpenAI**
- **Custom Providers** (bring your own TTS)

Voice Settings (per agent) include:
- **Voice Model**: e.g., Auto (Speech 2.8 Turbo)
- **Voice Speed**: slider + "Dynamically adjust based on user input" option
- **Voice Volume**: slider
- **Voice Emotion**: dropdown (None, + options)

**Quality Rating: 9/10** — Six providers plus custom is excellent. Dynamic speed adjustment is a standout feature.

> **SphereVoice Alignment:** SphereVoice V1 supports Cartesia (Sonic-3 — lowest TTFB), ElevenLabs (Turbo v2.5), OpenAI TTS, LMNT, PlayHT, and Azure Speech TTS via provider abstraction (tech-prd.md §7.3). Voice speed/volume sliders are in prd.md §3.4. MiniMax and Fish Audio are not planned — can be added later via the provider abstraction layer. Dynamic speed adjustment is a nice-to-have for V1.1. ✅ Core aligned, more providers than Retell for low-latency use cases.

---

### Global Agent Settings (right panel in both agent types)
Each agent has a comprehensive settings panel:

**Voice & Language**: Language selector (English + others), voice provider/voice selection

**Execution Mode** (Conversation Flow only):
- *Flex Mode* — All nodes share context; AI moves flexibly based on conversation
- *Rigid Mode* — AI follows nodes strictly step by step

**Global Prompt**: LLM model selector + full system prompt for the flow

**Knowledge Base**: Attach knowledge bases to the agent; Advanced setting to adjust KB Retrieval Chunks and Similarity threshold

**Speech Settings**:
- Background Sound (e.g., None, office, etc.)
- Responsiveness slider (controls how fast agent responds while user is speaking)
- Pronunciation guide (custom phonetics for words)

**Realtime Transcription Settings**:
- *Denoising Mode*: Remove noise, Remove noise + background, No denoising
- *Transcription Mode*: Optimize for speed, Optimize for accuracy, Custom
- *Vocabulary Specialization*: General, Medical (optimized for healthcare)
- *Boosted Keywords*: Custom comma-separated keywords to improve model accuracy

**Call Settings**:
- Voicemail Detection (hang up or leave voicemail)
- IVR Hangup (hang up if IVR system detected)
- User Keypad Input Detection
- End Call on Silence (configurable timeout)
- Max Call Duration slider
- Ring Duration slider

**Post-Call Data Extraction**:
Automatically extracts structured data from the call transcript after it ends. Pre-built fields include: Call Summary, Call Successful, User Sentiment, and any custom questions you define (e.g., "Do you currently have a steady place to live?", "Are you currently employed?", custom calculated fields). You can add unlimited custom extraction fields.

**Security & Fallback Settings**:
- Data Storage Settings (Everything, or selective scrubbing)
- Data retention period
- Opt In Secure URLs (adds security signatures to webhook URLs, 24-hour expiry)
- Fallback Voice ID (Automatic fallback or select a specific fallback voice)
- Default Dynamic Variables (set fallback values if variables aren't provided by endpoint)

**Webhook Settings**:
- Agent Level Webhook URL (to receive events)
- Webhook Timeout slider
- Webhook Events selector (choose which events trigger the webhook)

**MCPs** (Model Context Protocol):
- MCP integration panel — connects the agent to external MCP servers/tools

**Quality Rating: 9/10** — The depth of per-agent configuration is exceptional. The Vocabulary Specialization, Boosted Keywords, and dynamic variable fallbacks are production-grade features.

> **SphereVoice Alignment:** Most settings covered in prd.md §3.4 and tech-prd.md §3.4 (voice, LLM, speech, call settings, post-call extraction, webhooks, security). **Gaps for V1.1 consideration:** Background Sound, Pronunciation Guide, Vocabulary Specialization, Boosted Keywords, IVR Hangup detection, Denoising Mode. MCP is V1.1 (prd.md §8). ⚠️ Core aligned, advanced speech settings are gaps.

---

### Agent Versioning & Publishing
- **Publish** button with versioning (Draft - V0, etc.)
- **Version history** (clock icon) — review previous versions
- **Convert to Chat Agent** option (from the "..." menu)
- **Export** agent configuration

---

### Agent Simulation / Testing
- **Simulation tab**: Define test cases with a Prompt and Success Criteria; import test cases via CSV
- **Test Agent panel**: Test Audio (web call), Test Chat (text), and raw JSON mode
- Note: Call transfer is not supported in web call testing

**Quality Rating: 8/10** — Simulation with success criteria is a strong feature for QA. The web-call test is convenient.

> **SphereVoice Alignment:** SphereVoice V1 includes agent testing interface (prd.md §3.2) but **simulation with success criteria / CSV import is not in scope**. This is a strong candidate for V1.1+. The basic "test call" functionality is planned. ⚠️ Partial — test call yes, simulation framework no.

---

### Agent Templates (pre-built)
When creating a new agent, 8 templates are available:
1. Patient Screening
2. Real Estate Lead Qualification
3. Medical Center Receptionist
4. Real Estate AI Appointment Setter
5. Delivery Customer Support
6. Dental Outbound Sales
7. Retail Receptionist
8. Education Program Appointment Setter

**Quality Rating: 7/10** — Solid set of industry templates covering healthcare, real estate, retail, and education.

> **SphereVoice Alignment:** Same 8 templates planned for SphereVoice V1 (prd.md §3.10, tech-prd.md §3.10). ✅ Fully aligned.

---

### Agent Organization
- **Folders** — Create folder structure for organizing agents
- **Transfer Agents** — A dedicated category for routing/screening agents
- **Template Agents** — Separate category for saved templates
- **Import** — Import agent configurations
- **Search** across all agents

> **SphereVoice Alignment:** Folder organization, import/export, and Transfer Agents category are not in SphereVoice V1 scope. These are nice organizational features for V1.1+. ⚠️ Gap — minor, UX polish.

---

## 3. KNOWLEDGE BASE

Allows creating named knowledge bases that can be attached to agents.

Document ingestion methods:
- **Add Web Pages** — Crawl and sync a website URL
- **Upload Files** — PDF, DOCX, etc. up to 100MB
- **Add Text** — Manually typed/pasted articles

Advanced Setting: Adjust KB Retrieval Chunks and Similarity threshold (RAG tuning).

**Quality Rating: 8/10** — Three ingestion methods cover most use cases. The RAG tuning control is a nice advanced touch. Web crawling/syncing is particularly useful.

> **SphereVoice Alignment:** SphereVoice V1 supports File Upload and Add Text (prd.md §3.5, tech-prd.md §3.5). RAG tuning (chunk count, similarity threshold) is included. **Web crawling is deferred to V1.1** (prd.md §8). ✅ Core aligned, web crawl V1.1.

---

## 4. PHONE NUMBERS

Two ways to connect a phone number:
- **Buy New Number** — Purchase directly through Retell (via Twilio/Telnyx)
- **Connect via SIP Trunking** — Bring your own carrier/number

Search phone numbers. Each number gets assigned to an agent.

**Quality Rating: 8/10** — SIP trunking support is essential for enterprise use and it's there.

> **SphereVoice Alignment:** SphereVoice V1 supports buying numbers via Twilio/Plivo/Vonage/Telnyx and assigning to agents (prd.md §3.6, tech-prd.md §3.6). **SIP trunking is not in V1 scope** — should be evaluated for V1.1 if enterprise clients need BYOC. ⚠️ Gap — SIP trunking.

---

## 5. BATCH CALL

Send outbound calls to a large list of recipients at once.

Features:
- Batch Call Name
- From Number selector
- **Upload Recipients** via CSV (up to 50MB) — downloadable template provided
- **When to send**: Send Now or Schedule (future date/time)
- **When Calls Can Run**: Time window (e.g., 00:00–23:59, Mon–Sun) — for compliance/business hours
- **Reserved Concurrency for Other Calls**: Slider to reserve concurrent slots for inbound calls
- Shows Concurrency allocated to batch calling (e.g., 15)
- Cost: $0.005 per dial
- Save as Draft or Send

**Quality Rating: 8/10** — Well-designed batch calling with scheduling, time windows, and concurrency management. Business-hours controls are important for compliance.

> **SphereVoice Alignment:** **Batch calling is V1.1** (prd.md §8). SphereVoice V1 supports single outbound calls only (tech-prd.md §6.7). The scheduling, time windows, and concurrency management features here should inform the V1.1 design. ⚠️ Gap — intentionally deferred to V1.1.

---

## 6. CALL HISTORY

Full log of all calls with:

**Filters** (by category):
- *Base*: Agent, Call ID, Batch Call ID, Type, Duration, From, To, User Sentiment, Disconnection Reason, Call Status, Call Successful, E2E Latency
- *Post Call Analysis*: Filter by post-call extraction results (agent-specific)
- *Metadata*: Custom metadata fields
- *Dynamic Variables*: Filter by runtime variables

**Customizable columns**: Time, Duration, Channel Type, Cost, Session ID, End Reason, Session Status, User Sentiment, From, To, Direction, Session Outcome, End-to-End Latency, + all post-call extraction fields

**Custom Attributes**: Define your own attributes to tag calls

**Quality Rating: 9/10** — Exceptionally well-designed logging. Filtering by post-call extraction results is a killer feature for finding failed/successful calls at scale.

> **SphereVoice Alignment:** Fully covered in prd.md §3.7, tech-prd.md §3.7 including post-call extraction filtering, custom columns, bulk export, and access control. ✅ Fully aligned.

---

## 7. CHAT HISTORY

Same structure as Call History but for text/chat sessions. Columns: Time, Cost, Session ID, Session Status. Same filter and customize view capabilities.

**Quality Rating: 7/10** — Functional but lighter than call history, which makes sense given chat is a secondary channel.

> **SphereVoice Alignment:** Chat Agents (and thus Chat History) are V2 scope (prd.md §8). N/A for V1. ✅ Intentionally out of scope.

---

## 8. ANALYTICS

Dashboard with metric cards:
- **Call Counts** (total calls, filterable by agent)
- **Call Duration** (average/total)
- **Call Latency** (end-to-end)
- **Concurrency Used**
- **Call Transfer Rate**
- **Voicemail Rate**

Each card has Day/Week toggle for time-series charts. Date range selector and Filter available.

**Quality Rating: 7/10** — Covers the basics well. Not a deep BI tool, but sufficient for operational monitoring. Notable gap: no user-level funnel, no sentiment trend charts, no A/B comparison.

> **SphereVoice Alignment:** SphereVoice V1 analytics cover the same metric cards and time-series charts (prd.md §3.9, tech-prd.md §3.9). Sentiment trend charts, funnel analysis, and A/B testing are V1.1 (prd.md §8). ✅ Core aligned, advanced analytics V1.1.

---

## 9. AI QUALITY ASSURANCE

This is a premium add-on feature. It evaluates calls across multiple dimensions automatically:

Analyzed dimensions include:
- Audio quality (overlapping speech, tone, WER — Word Error Rate)
- Agent hallucinations
- Resolution accuracy
- User sentiment

**Interface**:
- *Call QA Overview* tab — aggregate scores (e.g., Average Score 87.00, Call Resolution Rate 75.00%, Calls Analyzed: 68 Completed / 240 Total)
- *Detailed Calls* tab — drill into individual calls
- Filter functionality
- **Configure QA Settings** — customize what gets evaluated

**Pricing**: First 100 minutes of analysis free, then paid.

**Quality Rating: 9/10** — Automated QA with hallucination detection and WER is extremely advanced. Very few platforms offer this. The aggregate scoring dashboard is excellent for team management.

> **SphereVoice Alignment:** **AI QA is V2 scope** (prd.md §8). This is one of Retell's strongest differentiators and should be a high priority for V2. SphereVoice V1 has no equivalent. ⚠️ Gap — V2.

---

## 10. ALERTING

Create automated alerts on key metrics. Notifies via email or webhook. Pre-built templates:

- **Payment Failure Rate Spike** — Number of API requests returning error code, Payment Failed, Rate limit
- **High Concurrency Spike** — Number of Calls/Chats, Concurrency Exhausted
- **LLM Retell Failure Surge** — Custom function failures, payment processing issues
- **TTS Provider Error Rate High** — Concurrency used count

Two tabs: *Alerting* (active alerts) and *Alert History*. Custom alerts can also be created.

**Quality Rating: 8/10** — Solid operational alerting. The pre-built templates cover the most critical failure modes. Having webhook delivery alongside email is good for teams already using incident tools (PagerDuty, Slack, etc.).

> **SphereVoice Alignment:** **Alerting is V2 scope** (prd.md §8). SphereVoice V1 relies on Sentry + Azure Monitor for operational alerting (tech-prd.md §9.4), but has no user-facing alerting UI. V2 should implement pre-built + custom alert rules. ⚠️ Gap — V2.

---

## 11. BILLING

**Billing History tab**: Invoice Created At, Amount, Details columns.

**Usage tab**:
- Usage period selector
- Total Cost card
- Call Minutes card
- Call + Chat Cost chart (Day/Week toggle, date range from Jan 31 to Feb 27)

Pricing model is **pay-per-minute** based on the LLM chosen.

**Quality Rating: 7/10** — Clean and simple. Lacks granular cost breakdown by agent or feature category, which would help at scale.

> **SphereVoice Alignment:** **Billing is V1.1** (prd.md §8, tech-prd.md §12). SphereVoice V1 tracks cost per call in the calls table (tech-prd.md §5.1) but has no billing UI or invoicing. V1.1 should include per-client cost tracking and billing dashboard. ⚠️ Gap — V1.1.

---

## 12. SETTINGS

Four sub-sections:

### Limits
- Concurrent Calls Limit (20 on current plan; "Adjust Limit" button)
- Concurrency Burst (up to 3× normal limit, max 300 additional calls at $0.10/min)
- LLM Token Limit (32,768 tokens)
- Telnyx CPS, Twilio CPS, Custom Telephony CPS (all currently 1)

### Reliability
- **System Outage Mode** — When enabled, outbound calls/SMS paused; inbound calls route to fallback
- **Opt In Stable Server** — Routes all calls/API requests to the stable server cluster

### API Keys
- Secret Key management
- Public Keys tab

### Webhooks (Global)
- Workspace-level webhook URL (separate from per-agent webhooks)
- Timeout configuration

### Workspace
- *General*: Workspace Name, Workspace ID
- *Users*: List of workspace users with email
- *Roles*: Three built-in roles — **Admin** (full control including billing), **Developer** (full functional access, no billing/org management), **Member** (read-only). Custom roles can be created via "Add Role".

**Quality Rating: 8/10** — Concurrency burst is a clever SLA feature. The role system is thoughtful with three tiers. Outage mode is a great enterprise reliability feature.

> **SphereVoice Alignment:** SphereVoice V1 covers roles (Admin, Developer, Read-Only, Client User — prd.md §3.11, tech-prd.md §3.11), API key management, and agent-level + global webhooks. **Gaps for V1.1+:** Concurrency Burst pricing, System Outage Mode, Stable Server routing, Custom Roles, CPS limits. ⚠️ Core aligned, enterprise reliability features are gaps.

---

## OVERALL PLATFORM SUMMARY

| Area | Rating | Notes |
|---|---|---|
| Agent Builder (Flow) | 9/10 | Visual node editor is genuinely best-in-class |
| Agent Builder (Prompt) | 8/10 | Clean, functional, good for quick builds |
| LLM Selection | 10/10 | Most comprehensive model menu in the space |
| Voice/TTS | 9/10 | 5 providers + custom, with per-voice settings |
| Knowledge Base | 8/10 | Web crawl + upload + text covers all cases |
| Phone Numbers | 8/10 | Buy or SIP trunking, solid |
| Batch Calling | 8/10 | Scheduling + compliance time windows |
| Call History | 9/10 | Post-call filter is a standout feature |
| Analytics | 7/10 | Basic but useful; lacks deeper BI |
| AI Quality Assurance | 9/10 | Hallucination detection + WER is very rare |
| Alerting | 8/10 | Pre-built + custom alerts with webhook delivery |
| Billing | 7/10 | Simple and clear; could use more granularity |
| Settings/Admin | 8/10 | Good role system, outage mode, burst concurrency |

**Overall: ~8.5/10** — Retell is a very mature, production-ready voice AI platform. Its biggest strengths are the visual Conversation Flow builder, the breadth of LLM/TTS providers, the post-call data extraction, and the AI QA system. The areas most worth improving if replicating are: deeper analytics/BI, richer billing breakdowns, and expanding the alerting/observability stack.

---

## SphereVoice Gap Analysis

A consolidated view of where SphereVoice stands relative to Retell, organized by release target.

### Fully Covered in SphereVoice V1

| Retell Feature | SphereVoice Reference |
|---|---|
| Conversation Flow Builder (8 of 10 node types) | prd.md §3.2, tech-prd.md §3.2 |
| Single Prompt Agent | prd.md §3.3, tech-prd.md §3.3 |
| Global Agent Settings (voice, LLM, speech, call, extraction, webhooks) | prd.md §3.4, tech-prd.md §3.4 |
| Knowledge Base (file upload + text, RAG tuning) | prd.md §3.5, tech-prd.md §3.5 |
| Phone Numbers (buy + assign via Twilio/Plivo/Vonage/Telnyx) | prd.md §3.6, tech-prd.md §3.6 |
| Call History (filters, post-call extraction, custom columns, export) | prd.md §3.7, tech-prd.md §3.7 |
| Live Call Monitoring (WebSocket, live transcript) | prd.md §3.8, tech-prd.md §3.8 |
| Analytics (metric cards, time-series, date range filters) | prd.md §3.9, tech-prd.md §3.9 |
| 8 Agent Templates | prd.md §3.10, tech-prd.md §3.10 |
| User Management (Admin, Developer, Read-Only, Client roles) | prd.md §3.11, tech-prd.md §3.11 |
| Agent Versioning & Publishing | prd.md §3.2, tech-prd.md §3.2 |
| Basic Agent Testing (test call) | prd.md §3.2 |

### Planned for SphereVoice V1.1 (Months 7-9)

| Retell Feature | Priority | Notes |
|---|---|---|
| Agent Transfer node | High | Transfer between SphereVoice agents |
| MCP node | High | Model Context Protocol integration |
| Batch Calling | High | CSV upload, scheduling, time windows, concurrency mgmt |
| Billing & Usage Dashboard | High | Per-client cost tracking, invoices |
| Web Crawling for KB | Medium | URL ingestion + auto-sync |
| Enhanced Analytics (sentiment trends, A/B, funnels) | Medium | Retell also lacks these |
| SIP Trunking (BYOC) | Medium | Enterprise clients may need this |
| Dynamic Voice Speed Adjustment | Low | Nice-to-have TTS feature |
| Agent Folder Organization | Low | UX polish |
| Simulation Framework (success criteria, CSV test cases) | Medium | Strong QA feature worth prioritizing |

### Planned for SphereVoice V2 (Months 10-12)

| Retell Feature | Priority | Notes |
|---|---|---|
| AI Quality Assurance (hallucination detection, WER, scoring) | High | Retell's strongest differentiator |
| Chat Agents + Chat History | High | Second modality |
| Alerting (pre-built + custom rules, webhook + email) | Medium | SphereVoice V1 uses Sentry/Azure Monitor for ops |
| Custom Roles | Low | SphereVoice V1 has 4 built-in roles |

### Strategic Differences (Not Gaps)

| Retell Approach | SphereVoice Approach | Rationale |
|---|---|---|
| Retell hosts all LLMs, users pick from menu | SphereVoice uses BYOK — employees add their own API keys | No vendor lock-in, per-client provider flexibility, cost control |
| Pay-per-minute pricing (bundled) | Track raw provider costs per call | Transparency, ability to negotiate volume discounts |
| Multi-Prompt Agent (legacy) | Not planned | Legacy architecture, no need to replicate |
| Custom LLM agent type | Not planned for V1 | Niche, can be added later via provider abstraction |
| Concurrency Burst pricing ($0.10/min overage) | Not planned | SphereVoice is internal — manage concurrency via infrastructure |
| System Outage Mode | Not planned for V1 | Can add as reliability feature in V1.1+ |

### Features SphereVoice Has That Retell Doesn't

| SphereVoice Feature | Details |
|---|---|
| Sub-300ms P50 latency pipeline | Deepgram Flux (EagerEndOfTurn) + Groq + Cartesia Sonic-3 fast stack; dual-stack architecture picks speed vs quality per turn |
| Multi-tenancy with RLS | PostgreSQL row-level security isolating client data at the database level |
| Pipecat pipeline framework | Voice AI engine built on the pinned upstream `pipecat-ai` package (from `pipecat-ai/pipecat`, Apache-2.0) with SphereVoice-owned processors, orchestration, and provider policies in the application code; built-in services for major STT/LLM/TTS providers, SileroVAD, ServiceSwitcher for hot-swap, and OpenTelemetry metrics |
| PipecatProviderFactory + ServiceSwitcher | Maps DB agent config → Pipecat service instances; runtime provider hot-swap with zero code changes; auto-failover via ServiceSwitcher |
| Noise cancellation (BVCTelephony) | LiveKit Krisp-based noise removal BEFORE STT — cleaner transcripts and faster endpointing |
| Self-hosted infrastructure | Full Terraform-managed deployment on Azure, portable to any cloud |
| LiveKit media layer | WebRTC/SIP bridging via open-source server (vs. Retell's proprietary media stack) |
| Client read-only dashboards | Clients get their own restricted view — Retell doesn't have multi-org client access |

---

**End of Document**

This audit is a competitive reference for the SphereVoice build. For feature definitions, see [prd.md](./prd.md). For technical implementation, see [tech-prd.md](./tech-prd.md).