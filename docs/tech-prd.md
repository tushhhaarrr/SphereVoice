# SphereVoice - Product Requirements Document (PRD)

**Product:** SphereVoice (Voice AI Agent Platform)  
**Company:** Sphere AI  
**Version:** 1.0  
**Status:** Planning & Architecture Phase  
**Last Updated:** March 3, 2026  
**Document Owner:** Technical Architecture Team

---

## How to Read the SphereVoice Documents

| Document | Purpose | Audience |
|----------|---------|----------|
| **prd.md** | WHAT we're building and WHY — features, user experience, business value | Everyone (product, engineering, leadership) |
| **tech-prd.md** (this file) | HOW we're building it — architecture, schemas, APIs, code, infrastructure | Engineering team |
| **retell-audit.md** | Competitive reference — Retell AI feature audit with SphereVoice gap analysis | Product & Engineering |

Both documents are kept in sync. The PRD drives feature scope; the Tech PRD drives implementation. If they ever conflict, raise it immediately.

---

## Executive Summary

SphereVoice is Sphere AI's internal ultra-low latency voice AI platform for delivering calling agent solutions to US and Indian clients. It enables employees to create, configure, and manage voice AI agents using a provider-agnostic architecture with enterprise-grade reliability.

**Key Differentiators:**
- ✅ Provider-agnostic architecture (no vendor lock-in)
- ✅ Monorepo (Turborepo) + modular monolith backend (domain modules with explicit boundaries)
- ✅ Sub-300ms target latency (Pipecat pipeline framework with Deepgram Flux + Groq/GPT-4o-mini + Cartesia Sonic-3)
- ✅ Pipecat as the voice pipeline engine via the pinned upstream package, with SphereVoice-owned custom processors and orchestration
- ✅ Visual conversation flow builder + prompt-based agents
- ✅ Complete multi-tenancy with client isolation
- ✅ Production-grade observability and monitoring
- ✅ Portable infrastructure (easy migration when Azure credits expire)

**Target Launch:** Near-complete feature parity with Retell AI before first client deployment

---

## Table of Contents

1. [Product Vision & Goals](#1-product-vision--goals)
2. [User Personas](#2-user-personas)
3. [Feature Specifications - V1](#3-feature-specifications---v1)
4. [Technical Architecture](#4-technical-architecture)
5. [Data Models & Schema](#5-data-models--schema)
6. [API Design](#6-api-design)
7. [Voice Pipeline Architecture](#7-voice-pipeline-architecture)
8. [Provider Abstraction Layer](#8-provider-abstraction-layer)
9. [Security & Compliance](#9-security--compliance)
10. [Observability & Monitoring](#10-observability--monitoring)
11. [Infrastructure & DevOps](#11-infrastructure--devops)
12. [Build Sequence & Milestones](#12-build-sequence--milestones)
13. [Future Roadmap (V1.1, V2)](#13-future-roadmap-v11-v2)
14. [Success Metrics](#14-success-metrics)
15. [Risk Mitigation](#15-risk-mitigation)

---

## 1. Product Vision & Goals

### Vision Statement
SphereVoice is the internal platform that empowers Sphere AI employees to deliver world-class voice AI agents to clients with complete provider flexibility, enterprise-grade reliability, and zero vendor lock-in.

### Primary Goals

**Business Goals:**
- Enable Sphere AI to compete with Retell AI, VAPI, and similar platforms
- Maintain complete control over the voice AI pipeline
- Achieve cost efficiency through provider flexibility
- Scale to 1000+ concurrent calls without architecture changes

**Technical Goals:**
- Sub-300ms end-to-end latency (STT → LLM → TTS) with a hard ceiling of 500ms P99
- 99.9% uptime SLA for voice calls
- Complete provider abstraction (swap providers without code changes)
- Multi-region deployment (US + India)
- Portable infrastructure (migrate off Azure in <2 weeks when needed)

**User Goals (Employees):**
- Create and deploy voice agents in <30 minutes
- Monitor live calls with real-time transcription
- Analyze call performance and optimize agent configurations
- Manage multiple clients with complete data isolation

---

## 2. User Personas

### Primary Persona: Sphere Employee (Platform Operator)

**Role:** Voice AI Engineer / Account Manager  
**Responsibilities:**
- Create and configure voice agents for clients
- Manage provider API keys and telephony numbers
- Monitor live calls and agent performance
- Optimize agent configurations based on analytics
- Troubleshoot issues and provide client support

**Pain Points:**
- Need to quickly deploy agents without vendor lock-in
- Must maintain sub-300ms P50 / sub-500ms P99 latency for quality conversations
- Require visibility into live calls for quality assurance
- Need detailed analytics to optimize cost vs. quality tradeoffs

**Success Criteria:**
- Can deploy a production-ready agent in <30 minutes
- Has real-time visibility into all active calls
- Can switch providers without downtime
- Receives alerts for any quality/performance issues

### Secondary Persona: Client (Read-Only Observer)

**Role:** Business Owner / Operations Manager  
**Access Level:** Read-only dashboard  
**Needs:**
- View their tenant's call history and transcripts
- See analytics (call volume, duration, success rate)
- Review agent performance metrics
- Download call recordings and transcripts

**Constraints:**
- Cannot see provider details (which STT/LLM/TTS is used)
- Cannot see costs or billing breakdowns
- Cannot modify agent configurations
- Cannot access other clients' data

---

## 3. Feature Specifications - V1

### 3.1 Provider Management

**Description:** Centralized management of API keys for STT, LLM, TTS, and Telephony providers.

**User Stories:**
- As an employee, I can add API keys for different providers (Deepgram, OpenAI, ElevenLabs, Twilio, etc.)
- As an employee, I can test provider credentials to ensure they work
- As an employee, I can set default provider keys (Sphere account) or per-client keys
- As an employee, I can view provider usage statistics and costs
- As an employee, I can enable/disable providers without deleting keys

**Functional Requirements:**

**FR-PM-001:** System shall support adding API keys for the following provider categories:
- Speech-to-Text (STT): Deepgram (Nova-3, Flux), AssemblyAI, Azure Speech, OpenAI Whisper
- Large Language Models (LLM): OpenAI (GPT-4o, GPT-4o-mini), Anthropic (Claude), Azure OpenAI, Groq (llama-3)
- Text-to-Speech (TTS): Cartesia (Sonic-3), ElevenLabs (Turbo v2.5), OpenAI TTS, LMNT, PlayHT, Azure Speech
- Telephony: Twilio, Plivo, Vonage, Telnyx

**FR-PM-002:** System shall encrypt all API keys at rest using AES-256 encryption

**FR-PM-003:** System shall provide a "Test Connection" feature for each provider

**FR-PM-004:** System shall support two key management modes:
- **Default Keys:** Sphere-wide API keys (used by default for all agents)
- **Per-Client Keys:** Tenant-specific API keys (override defaults)

**FR-PM-005:** System shall track provider usage metrics:
- Total API calls per provider
- Total cost per provider (aggregated across all clients)
- Average latency per provider
- Error rate per provider

**UI Components:**
- Provider list page (filterable by category: STT, LLM, TTS, Telephony)
- Add/Edit provider modal (name, category, API key input, test button)
- Provider detail page (usage stats, associated agents, test logs)
- Tenant-specific provider override interface

**Non-Functional Requirements:**
- API key encryption must use Azure Key Vault or equivalent
- Provider test must complete within 5 seconds
- Support for at least 50 concurrent provider keys

---

### 3.2 Agent Builder - Conversation Flow

**Description:** Visual node-based editor for creating deterministic conversation flows.

**User Stories:**
- As an employee, I can create a conversation flow agent using a drag-and-drop canvas
- As an employee, I can add different node types (Conversation, Function, Logic Split, Call Transfer, etc.)
- As an employee, I can connect nodes to define conversation paths
- As an employee, I can configure each node's behavior (prompts, conditions, API endpoints)
- As an employee, I can save, version, and publish agent flows

**Functional Requirements:**

**FR-AF-001:** System shall provide a visual canvas for building conversation flows using React Flow library

**FR-AF-002:** System shall support the following node types in V1:
1. **Conversation Node** - AI speaks and listens
2. **Function Node** - Calls external API or webhook
3. **Logic Split Node** - Branches based on conditions
4. **Call Transfer Node** - Transfers to human or phone number
5. **Press Digit Node** - Sends DTMF tones
6. **Extract Variable Node** - Pulls structured data from conversation
7. **SMS Node** - Sends SMS during call
8. **Ending Node** - Terminates conversation

**FR-AF-003:** Each Conversation Node shall have:
- Prompt/instruction for the AI
- Expected user response patterns
- Timeout settings
- Voice settings override (optional)

**FR-AF-004:** Each Function Node shall have:
- HTTP endpoint URL
- Request method (GET, POST, PUT, DELETE)
- Request headers and body template
- Response mapping (extract variables from response)
- Error handling configuration

**FR-AF-005:** Each Logic Split Node shall have:
- Condition builder (variable comparisons, regex matching)
- Multiple output paths (if/else if/else)
- Default path for unmatched conditions

**FR-AF-006:** System shall support execution modes:
- **Flex Mode:** AI moves between nodes based on conversation context
- **Rigid Mode:** AI follows nodes sequentially step-by-step

**FR-AF-007:** System shall support reusable components:
- Library Components (shared across all agents)
- Agent Components (scoped to specific agent)

**FR-AF-008:** System shall support agent versioning:
- Draft versions (not published)
- Published versions (immutable, can be rolled back)
- Version history viewer

**FR-AF-009:** System shall validate flows before publishing:
- All nodes must be connected
- No orphaned nodes (except Entry and Ending)
- All required fields populated
- Function endpoints reachable

**UI Components:**
- Canvas with zoom/pan controls
- Node palette (drag to add nodes)
- Node editor panel (configure selected node)
- Flow settings panel (global prompt, execution mode, providers)
- Version history sidebar
- Publish/Save Draft buttons

**Non-Functional Requirements:**
- Canvas must support at least 100 nodes without performance degradation
- Auto-save every 30 seconds
- Undo/redo support (up to 50 actions)
- Flow validation must complete in <2 seconds

---

### 3.3 Agent Builder - Single Prompt

**Description:** Simple prompt-based agent for quick deployment without flow complexity.

**User Stories:**
- As an employee, I can create a single prompt agent with one system prompt
- As an employee, I can define callable functions (transfer, end call, custom APIs)
- As an employee, I can configure welcome messages and dynamic variables
- As an employee, I can select which providers to use (STT, LLM, TTS)

**Functional Requirements:**

**FR-AS-001:** System shall provide a text editor for system prompt with:
- Syntax highlighting
- Variable insertion (`{{variable_name}}`)
- Character count
- Prompt templates library

**FR-AS-002:** System shall support dynamic variables:
- Pre-defined variables (caller_name, caller_number, call_time, etc.)
- Custom variables (defined per agent)
- Default values for missing variables

**FR-AS-003:** System shall support welcome message configuration:
- "AI speaks first" mode (agent greets caller)
- "User speaks first" mode (agent waits for user)
- Dynamic message (generated based on context)

**FR-AS-004:** System shall allow defining callable functions:
- Built-in functions: `transfer_call`, `end_call`, `send_sms`
- Custom functions: HTTP endpoint, method, parameters

**FR-AS-005:** System shall provide function call examples/testing

**UI Components:**
- System prompt editor (textarea with variable picker)
- Welcome message configurator
- Functions list (add/edit/remove functions)
- Dynamic variables manager
- Provider selection (STT, LLM, TTS dropdowns)

**Non-Functional Requirements:**
- Prompt editor must support at least 10,000 characters
- Variable substitution must not add >10ms latency

---

### 3.4 Global Agent Settings

**Description:** Configuration options that apply to both Conversation Flow and Single Prompt agents.

**Functional Requirements:**

**FR-GS-001:** Voice & Language Settings:
- Language selector (English, Spanish, Hindi, etc.)
- Voice provider selector (ElevenLabs, OpenAI TTS, PlayHT, Azure Speech)
- Voice selection (filtered by gender, accent, type)
- Voice speed slider (0.5x - 2.0x)
- Voice volume slider (-10dB to +10dB)
- Dynamic speed adjustment toggle

**FR-GS-002:** LLM Settings:
- Model selector (GPT-4o, GPT-4o-mini, Claude, Groq llama-3, etc.)
- Temperature slider (0.0 - 1.0)
- Structured output toggle (JSON schema enforcement)

**FR-GS-003:** Knowledge Base Integration:
- Attach knowledge bases (multi-select)
- Retrieval settings (chunk count, similarity threshold)

**FR-GS-004:** Speech Settings:
- Background sound selector (None, Office, Café, etc.)
- Responsiveness slider (how fast agent responds while user speaking)
- Pronunciation guide (custom phonetics: "Sphere" → "guh-rill-ah")

**FR-GS-005:** Realtime Transcription Settings:
- Denoising mode (Remove noise, Remove noise + background, None)
- Transcription mode (Optimize for speed, Optimize for accuracy, Custom)
- Vocabulary specialization (General, Medical, Legal, etc.)
- Boosted keywords (comma-separated list for improved accuracy)

**FR-GS-006:** Call Settings:
- Voicemail detection (Hang up, Leave voicemail)
- IVR hangup detection toggle
- User keypad input detection toggle
- End call on silence (timeout in seconds)
- Max call duration (slider, 1-60 minutes)
- Ring duration (slider, 5-60 seconds)

**FR-GS-007:** Post-Call Data Extraction:
- Pre-built extraction fields:
  - Call summary
  - Call successful (boolean)
  - User sentiment (positive/neutral/negative)
- Custom extraction fields (unlimited):
  - Field name
  - Field type (text, boolean, number, select)
  - Extraction prompt/question

**FR-GS-008:** Security & Fallback Settings:
- Data storage settings (Everything, Selective scrubbing)
- Data retention period (7/30/90 days, or custom)
- Secure webhook URLs toggle (adds signatures, 24-hour expiry)
- Fallback voice (automatic or specific voice ID)
- Default dynamic variables (fallback values)

**FR-GS-009:** Webhook Settings:
- Agent-level webhook URL
- Webhook timeout (slider, 1-30 seconds)
- Webhook events selector (multi-select):
  - call_started
  - call_ended
  - transcription_updated
  - function_called
  - error_occurred

**UI Components:**
- Tabbed settings panel (Voice, LLM, Speech, Call, Data Extraction, Security, Webhooks)
- Each tab has collapsible sections
- Real-time preview where applicable (voice playback, transcription test)

---

### 3.5 Knowledge Base

**Description:** Centralized repository for documents that agents can reference during conversations.

**User Stories:**
- As an employee, I can create named knowledge bases
- As an employee, I can upload files (PDF, DOCX, TXT) to a knowledge base
- As an employee, I can paste text directly into a knowledge base
- As an employee, I can attach knowledge bases to agents
- As an employee, I can configure retrieval settings (chunk count, similarity threshold)

**Functional Requirements:**

**FR-KB-001:** System shall support two ingestion methods in V1:
- **File Upload:** PDF, DOCX, TXT (up to 100MB per file)
- **Text Input:** Direct paste/type (up to 50,000 characters)

**FR-KB-002:** System shall process uploaded documents:
- Extract text from PDFs/DOCX
- Chunk text into embeddings (configurable chunk size: 256-2048 tokens)
- Generate vector embeddings using OpenAI text-embedding-3-small or Azure OpenAI

**FR-KB-003:** System shall store embeddings in vector database:
- PostgreSQL with pgvector extension (portable solution)
- Support similarity search via cosine similarity

**FR-KB-004:** System shall allow configuring retrieval settings per agent:
- Number of chunks to retrieve (1-10, default 3)
- Similarity threshold (0.0-1.0, default 0.7)

**FR-KB-005:** System shall support knowledge base versioning:
- Track changes to documents
- Ability to revert to previous versions

**FR-KB-006:** System shall support knowledge base sharing:
- Private (only specific agents)
- Tenant-wide (all agents in a tenant)
- Global (all agents across all tenants)

**UI Components:**
- Knowledge base list page (search, filter by tenant)
- Create/Edit knowledge base modal (name, description, sharing settings)
- Document manager (upload, add text, delete, view chunks)
- Agent attachment interface (multi-select knowledge bases)
- Retrieval settings configurator

**Non-Functional Requirements:**
- Document processing must complete within 60 seconds for files <10MB
- Embedding generation must use batch API calls (up to 100 chunks at once)
- Vector search must return results in <500ms

---

### 3.6 Phone Number Management

**Description:** Buy and manage phone numbers, assign them to agents.

**User Stories:**
- As an employee, I can buy phone numbers through the platform
- As an employee, I can assign phone numbers to specific agents
- As an employee, I can view all phone numbers and their assignments
- As an employee, I can configure inbound/outbound settings per number

**Functional Requirements:**

**FR-PN-001:** System shall integrate with telephony providers:
- Twilio (primary)
- Plivo (alternative)
- Vonage (alternative)
- Telnyx (alternative)

**FR-PN-002:** System shall allow searching and buying phone numbers:
- Search by country, area code, or pattern
- Filter by capabilities (Voice, SMS, MMS)
- Display monthly cost per number
- One-click purchase

**FR-PN-003:** System shall support number assignment:
- Assign number to specific agent (one-to-one)
- Unassign/reassign numbers
- View number status (active, inactive, in-use)

**FR-PN-004:** System shall configure number routing:
- Inbound calls route to assigned agent
- Webhook URL for call events
- Fallback number (if agent unavailable)

**FR-PN-005:** System shall display number details:
- Phone number
- Country/region
- Assigned agent
- Monthly cost
- Total calls handled
- Date purchased

**UI Components:**
- Phone numbers list page (search, filter by status/agent)
- Buy number modal (search, results list, purchase confirmation)
- Number detail page (assignment, routing config, usage stats)
- Bulk actions (assign multiple numbers, release numbers)

**Non-Functional Requirements:**
- Number search must return results in <3 seconds
- Number purchase must complete in <10 seconds
- Support for at least 1000 phone numbers per tenant

---

### 3.7 Call History

**Description:** Comprehensive logging of all calls with transcripts, recordings, and metadata.

**User Stories:**
- As an employee, I can view all calls across all clients
- As an employee, I can filter calls by client, agent, date, status, sentiment, etc.
- As an employee, I can listen to call recordings and read transcripts
- As an employee, I can export call data (CSV, JSON)
- As a client, I can view only my tenant's calls (read-only)

**Functional Requirements:**

**FR-CH-001:** System shall log all call details:
- Call ID (unique identifier)
- Tenant (client)
- Agent used
- From number
- To number
- Direction (inbound/outbound)
- Start time
- End time
- Duration (seconds)
- Status (completed, failed, no-answer, busy)
- Disconnection reason
- Cost (calculated from provider usage)

**FR-CH-002:** System shall store call recordings:
- Recording URL (Azure Blob Storage)
- Recording format (MP3, 128kbps)
- Recording duration
- Ability to play inline (web player)

**FR-CH-003:** System shall store full call transcripts:
- Speaker-labeled turns (AI, User)
- Timestamps per turn
- Confidence scores
- Highlight function calls and transfers

**FR-CH-004:** System shall extract post-call data:
- All configured extraction fields (from agent settings)
- Store as structured JSON
- Index for fast filtering

**FR-CH-005:** System shall support advanced filtering:
- **Base filters:** Agent, Call ID, Type, Duration range, From, To, Sentiment, Disconnection reason, Status, Successful (yes/no), Latency range
- **Post-call filters:** Any custom extraction field (e.g., "appointment_booked = true")
- **Metadata filters:** Custom metadata fields
- **Dynamic variable filters:** Filter by runtime variables

**FR-CH-006:** System shall support customizable column view:
- Default columns: Time, Duration, From, To, Status, Sentiment, Cost
- Optional columns: Agent, Tenant, End Reason, Latency, any extraction field
- Save column preferences per user

**FR-CH-007:** System shall support bulk actions:
- Export selected calls (CSV, JSON)
- Delete calls (with confirmation)
- Assign custom tags/labels

**FR-CH-008:** System shall implement client access control:
- Clients see only their tenant's calls
- Clients cannot see cost, provider details, or agent configuration
- Employees see all calls across all tenants

**UI Components:**
- Call history table (sortable, filterable, paginated)
- Advanced filter panel (collapsible, save filters)
- Call detail modal (recording player, transcript viewer, metadata)
- Export modal (select format, date range, filters)
- Custom attributes manager (define tags/labels)

**Non-Functional Requirements:**
- Table must support pagination (50/100/200 calls per page)
- Filters must apply in <1 second
- Call detail modal must load in <2 seconds
- Transcript must render incrementally (don't wait for full load)
- Support for at least 1 million call records without performance degradation

---

### 3.8 Live Call Monitoring

**Description:** Real-time dashboard showing active calls with live transcription.

**User Stories:**
- As an employee, I can see all currently active calls
- As an employee, I can view live transcription of any active call
- As an employee, I can see call metadata (duration, agent, caller info)
- As an employee, I can end a call manually if needed

**Functional Requirements:**

**FR-LM-001:** System shall display active calls in real-time:
- Call ID
- Tenant (client)
- Agent name
- From number
- To number
- Duration (live counter)
- Status (ringing, in-progress, on-hold)

**FR-LM-002:** System shall provide live transcription:
- Speaker-labeled turns (AI, User)
- Streaming updates (new text appears as spoken)
- Auto-scroll to latest message
- Timestamps

**FR-LM-003:** System shall display call metrics in real-time:
- Current latency (STT → LLM → TTS)
- Turn count (number of exchanges)
- Function calls made
- Sentiment indicator (live)

**FR-LM-004:** System shall support call actions:
- End call (with confirmation)
- View full call details (opens Call History entry)
- Copy call ID

**FR-LM-005:** System shall use WebSocket for real-time updates:
- Connect to WebSocket on page load
- Subscribe to call events (start, update, end)
- Reconnect automatically on disconnect

**UI Components:**
- Active calls grid (cards or table view)
- Call detail panel (click a call to expand)
- Live transcription viewer (auto-scrolling)
- Call metrics cards (latency, turn count, sentiment)
- Refresh indicator (connection status)

**Non-Functional Requirements:**
- WebSocket updates must arrive in <100ms
- Page must support monitoring up to 100 concurrent calls
- Transcription must update in real-time (no buffering >1 second)
- Auto-reconnect on WebSocket disconnect within 3 seconds

---

### 3.9 Analytics Dashboard

**Description:** High-level metrics and charts for monitoring platform performance.

**User Stories:**
- As an employee, I can view aggregate metrics (total calls, average duration, etc.)
- As an employee, I can filter analytics by tenant, agent, date range
- As an employee, I can view time-series charts (calls over time, latency trends)
- As a client, I can view analytics for my tenant only

**Functional Requirements:**

**FR-AD-001:** System shall display metric cards:
- **Total Calls** (filterable by agent)
- **Average Call Duration**
- **Total Call Duration** (minutes)
- **Average End-to-End Latency**
- **Concurrency Used** (current and peak)
- **Call Transfer Rate** (% of calls transferred to human)
- **Voicemail Rate** (% of calls ending in voicemail)
- **Success Rate** (based on post-call extraction)

**FR-AD-002:** System shall provide time-series charts:
- Calls over time (day/week/month granularity)
- Latency trends (P50, P95, P99)
- Sentiment distribution (positive/neutral/negative)
- Call duration distribution (histogram)

**FR-AD-003:** System shall support filtering:
- Date range picker (last 7 days, 30 days, custom)
- Tenant filter (multi-select)
- Agent filter (multi-select)
- Status filter (completed, failed, etc.)

**FR-AD-004:** System shall support export:
- Export charts as PNG/SVG
- Export data as CSV

**FR-AD-005:** System shall implement client access control:
- Clients see only their tenant's analytics
- Employees see aggregated analytics across all tenants

**UI Components:**
- Metric cards grid (responsive, 2-4 columns)
- Time-series charts (Recharts/tremor)
- Filter panel (date range, org, agent)
- Export buttons
- Day/Week/Month toggle per chart

**Non-Functional Requirements:**
- Metrics must load in <3 seconds
- Charts must update in <2 seconds when filters change
- Support for querying up to 1 year of historical data

---

### 3.10 Agent Templates

**Description:** Pre-built agent configurations for common use cases.

**User Stories:**
- As an employee, I can create an agent from a template
- As an employee, I can customize the template after creation
- As an employee, I can save my own agents as templates

**Functional Requirements:**

**FR-AT-001:** System shall provide 8 built-in templates in V1:
1. **Patient Screening** (Healthcare)
2. **Real Estate Lead Qualification**
3. **Medical Center Receptionist**
4. **Real Estate Appointment Setter**
5. **Delivery Customer Support**
6. **Dental Outbound Sales**
7. **Retail Receptionist**
8. **Education Program Appointment Setter**

**FR-AT-002:** Each template shall include:
- Pre-configured conversation flow or prompt
- Sample functions (transfer, booking, etc.)
- Recommended voice settings
- Sample post-call extraction fields
- Knowledge base suggestions

**FR-AT-003:** System shall allow creating custom templates:
- Save any agent as a template
- Define template scope (private, tenant-wide, global)
- Add template description and tags

**FR-AT-004:** System shall support template versioning:
- Update templates without affecting agents created from older versions

**UI Components:**
- Template gallery (cards with preview)
- Template detail modal (description, preview flow, sample transcript)
- "Use Template" button (creates new agent from template)
- "Save as Template" button (in agent editor)

**Non-Functional Requirements:**
- Templates must load in <1 second
- Creating agent from template must complete in <3 seconds

---

### 3.11 User Management & Roles

**Description:** Manage employees and client users with role-based access control.

**User Stories:**
- As an admin, I can invite employees to the platform
- As an admin, I can assign roles (Admin, Developer, Read-Only)
- As an admin, I can create client users with read-only access
- As an admin, I can deactivate users

**Functional Requirements:**

**FR-UM-001:** System shall support three built-in roles for employees:
- **Admin:** Full access including user management, all tenants (billing deferred to V1.1)
- **Developer:** Full functional access (create/edit agents, manage providers), no user management
- **Read-Only:** View-only access to all data, no create/edit/delete

**FR-UM-002:** System shall support client user role:
- **Client User:** Access only to their tenant's data (calls, analytics)
- Read-only access (cannot modify agents or settings)

**FR-UM-003:** System shall support user invitation:
- Send email invite with magic link or password setup
- Set role during invitation
- Assign to tenant (for client users)

**FR-UM-004:** System shall support user management:
- View all users (filterable by role, tenant, status)
- Edit user role
- Deactivate/reactivate users
- Reset user password

**FR-UM-005:** System shall audit user actions:
- Log all create/update/delete actions
- Store: user, action, resource, timestamp
- Viewable by admins

**UI Components:**
- Users list page (table with search/filter)
- Invite user modal (email, role, tenant)
- Edit user modal (role, status)
- Audit log viewer (filterable table)

**Non-Functional Requirements:**
- User invitation email must send within 30 seconds
- Audit logs must retain for at least 90 days
- Support for at least 500 users

---

## 4. Technical Architecture

### 4.1 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND LAYER                          │
│  ┌──────────────────────┐        ┌──────────────────────────┐  │
│  │  Employee Dashboard  │        │  Client Dashboard        │  │
│  │  (Next.js + shadcn)  │        │  (Read-Only View)        │  │
│  └──────────────────────┘        └──────────────────────────┘  │
│                           │                                     │
│                           ├─── REST API ────────────────┐       │
│                           │                             │       │
│                           └─── WebSocket ──────┐        │       │
└───────────────────────────────────────────────┼────────┼───────┘
                                                │        │
┌───────────────────────────────────────────────┼────────┼───────┐
│                        BACKEND LAYER          │        │       │
│  ┌────────────────────────────────────────────▼────────▼────┐  │
│  │              FastAPI Application Server                 │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │ REST API     │  │ WebSocket    │  │ Auth Service │  │  │
│  │  │ Endpoints    │  │ Server       │  │ (Auth.js)    │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │    Voice Pipeline (Pipecat — Sphere/pipecat fork)      │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │  │
│  │  │ Call     │  │ STT Svc  │  │ LLM Svc  │  │ TTS Svc │ │  │
│  │  │ Manager  │  │(Deepgram)│  │(OpenAI/  │  │(Cartesia│ │  │
│  │  │          │  │          │  │ Groq)    │  │/11Labs) │ │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Provider Abstraction Layer                  │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │  │
│  │  │ STT Factory │  │ LLM Factory │  │ TTS Factory │     │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Background Workers (Celery)                 │  │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────────┐  │  │
│  │  │ Post-Call  │  │ Embedding  │  │ Recording        │  │  │
│  │  │ Processing │  │ Generator  │  │ Transcoder       │  │  │
│  │  └────────────┘  └────────────┘  └──────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────┐
│                       DATA LAYER                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │   PostgreSQL    │  │     Redis       │  │  Azure Blob    │ │
│  │   (Azure)       │  │   (Azure)       │  │   Storage      │ │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌──────────┐  │ │
│  │  │ Agents    │  │  │  │ Sessions  │  │  │  │Recordings│  │ │
│  │  │ Calls     │  │  │  │ Cache     │  │  │  │KB Files  │  │ │
│  │  │ Providers │  │  │  │ Queue     │  │  │  │          │  │ │
│  │  │ KB (pgvec)│  │  │  │ Pub/Sub   │  │  │  │          │  │ │
│  │  └───────────┘  │  │  └───────────┘  │  │  └──────────┘  │ │
│  └─────────────────┘  └─────────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────┐
│                    REALTIME MEDIA LAYER                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    LiveKit Server                        │  │
│  │                    (Azure VM)                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │ WebRTC       │  │ Media        │  │ SIP Gateway  │  │  │
│  │  │ Server       │  │ Processor    │  │ (Telephony)  │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────┐
│                   EXTERNAL INTEGRATIONS                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  STT     │  │  LLM     │  │  TTS     │  │  Telephony   │   │
│  │ Deepgram │  │  OpenAI  │  │ElevenLabs│  │   Twilio     │   │
│  │Assembly  │  │ Anthropic│  │ PlayHT   │  │   Plivo      │   │
│  │  Azure   │  │   Groq   │  │  OpenAI  │  │   Vonage     │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────┼─────────────────────────────────┐
│                   OBSERVABILITY LAYER                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │   Sentry     │  │ Azure Monitor│  │  OpenTelemetry       │ │
│  │ (Errors)     │  │ (Logs/Metrics)│  │  (Tracing)          │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Component Breakdown

**Frontend (Next.js 15)**
- **Pages:**
  - `/dashboard` - Main analytics overview
  - `/agents` - Agent list and builder
  - `/agents/[id]` - Agent detail and editor
  - `/providers` - Provider management
  - `/phone-numbers` - Phone number management
  - `/calls` - Call history
  - `/live` - Live call monitoring
  - `/knowledge-base` - KB management
  - `/settings` - User, billing, webhooks
  - `/client/[tenantId]` - Client read-only dashboard

- **Shared Components:**
  - Agent Flow Builder (React Flow)
  - Prompt Editor (Monaco/CodeMirror)
  - Call Player (audio with transcript sync)
  - Real-time transcription viewer
  - Analytics charts (Recharts)
  - Filter panels
  - Data tables (TanStack Table)

**Backend (FastAPI — Modular Monolith)**

The backend is a single FastAPI application deployed as one container, organized internally into **self-contained domain modules**. Each module owns its models, schemas, routes, and service logic. Modules communicate only through their public `__init__.py` API — never by importing each other's internals directly. `import-linter` enforces this in CI.

- **Domain Modules** (under `backend/app/modules/`):
  - `auth` - Authentication, JWT issuance, RBAC, tenant context
  - `agents` - Agent CRUD, versioning, configuration, templates
  - `providers` - Provider key encryption, CRUD, connection testing
  - `calls` - Call history, call lifecycle, outbound calls
  - `pipeline` - Pipecat voice pipeline, CallOrchestrator, PipecatProviderFactory
  - `knowledge_base` - KB ingestion, chunking, embedding, vector search, RAG retrieval
  - `phone_numbers` - Telephony integration (Twilio/Plivo), number purchase/routing
  - `analytics` - Metrics aggregation, time-series, dashboard data
  - `webhooks` - Webhook registration, delivery, retry, dead letter

- **Shared Kernel** (`backend/app/core/`):
  - `config.py` - Settings via pydantic-settings
  - `database.py` - Async SQLAlchemy engine + session factory
  - `security.py` - JWT decode, password hashing
  - `encryption.py` - AES-256-GCM for provider keys
  - `dependencies.py` - `get_db`, `get_current_user`, `get_tenant`
  - `middleware.py` - Tenant context, CORS, request ID injection
  - `exceptions.py` - Structured error responses
  - `base_model.py` - TimestampMixin, TenantMixin for SQLAlchemy

- **Core Services** (within their respective modules):
  - `pipeline/orchestrator.py` - `CallOrchestrator` — manages call lifecycle
  - `pipeline/factory.py` - `PipecatProviderFactory` — maps DB config → Pipecat services
  - `pipeline/flow_engine.py` - `AgentExecutor` — runs conversation flows
  - `knowledge_base/retriever.py` - `KnowledgeRetriever` — vector search for RAG
  - `webhooks/service.py` - `WebhookDispatcher` — sends webhook events

- **Module Boundary Rules:**
  - ✅ Import from `modules.agents` (public `__init__.py`) — allowed
  - ❌ Import from `modules.agents.service` directly — blocked by `import-linter`
  - ✅ Shared kernel (`core/*`) importable by all modules
  - ✅ Workers import from module public APIs only

- **Extraction Path:** If a module outgrows the monolith (e.g., `pipeline` needs separate scaling), promote its `router.py` to a standalone FastAPI app and replace internal imports with HTTP/gRPC. This is a 1-day operation per module.

**Workers (Celery — cross-module tasks)**
- `post_call.py` - Transcribe and store (imports from `calls` + `pipeline` modules)
- `embeddings.py` - Chunk and embed KB documents (imports from `knowledge_base` module)
- `webhook_delivery.py` - Retry logic for failed webhooks (imports from `webhooks` module)
- `retention.py` - Delete based on retention policy (imports from `calls` module)

**WebRTC/Media (LiveKit)**
- Handles real-time audio streams
- SIP gateway for telephony integration
- Media processing (noise reduction, echo cancellation)
- Recording to Azure Blob Storage

---

### 4.3 Technology Stack Summary

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Frontend Framework** | Next.js 15.1.6 (App Router) | Best React framework, portable, excellent DX |
| **UI Library** | shadcn/ui + Tailwind CSS 3.4.1 | Copy-paste components, no vendor lock-in |
| **State Management** | TanStack Query 5.51.21 + Zustand 4.5.5 | Server state (Query) + client state (Zustand) |
| **Flow Builder** | React Flow 11.11.4 | Industry standard for node editors |
| **Forms** | React Hook Form 7.53.0 + Zod 3.23.8 | Performant forms, type-safe validation |
| **Charts** | Recharts 2.13.0 | Battle-tested, good documentation |
| **Data Tables** | TanStack Table 8.20.5 | Headless, performant, feature-rich |
| **Backend Framework** | FastAPI 0.115.0 (Python 3.11) | Async/await, excellent for streaming, auto docs |
| **Database** | PostgreSQL 15 (Azure) | Production-grade, pgvector for embeddings |
| **ORM** | SQLAlchemy 2.0.35 (async) | Industry standard, great migrations |
| **Migrations** | Alembic 1.13.1 | Companion to SQLAlchemy, reliable schema migrations |
| **Cache/Queue** | Redis 7.2 (Azure) | Standard protocol, fast, pub/sub support |
| **Task Queue** | Celery 5.4.0 + Redis | Battle-tested background jobs |
| **Object Storage** | Azure Blob (S3 API) | Free with credits, S3-compatible for portability |
| **Voice Pipeline** | Pipecat — pinned upstream package | Upstream `pipecat-ai` package with built-in services for Deepgram, OpenAI, Cartesia, ElevenLabs, Groq, Anthropic; SileroVAD, context aggregators, ServiceSwitcher, and OpenTelemetry tracing. SphereVoice-specific processors, orchestration, and provider policies live in the SphereVoice repo. |
| **WebRTC/SIP** | LiveKit Server + Pipecat LiveKitTransport | LiveKit handles WebRTC/SIP bridging; Pipecat's LiveKitTransport connects as a room participant to receive/send audio frames |
| **Auth** | Auth.js 5.0.0-beta.25 / `next-auth@5` (frontend session) + FastAPI JWT (API auth) | Auth.js v5 handles frontend session/OAuth with native Next.js 15 App Router support (Edge-compatible, async API). FastAPI issues JWT tokens for API calls. Frontend authenticates via Auth.js, which calls FastAPI `/api/v1/auth/login` to obtain JWT. All subsequent API requests use the JWT Bearer token. |
| **Error Tracking** | Sentry (sentry-sdk 2.14.0) | Best error tracking, portable |
| **Logging** | Azure Monitor | Free with credits, structured logs |
| **Metrics** | Prometheus 2.54 + Grafana 11.2 | Open source, portable |
| **Tracing** | OpenTelemetry 1.27.0 | Industry standard, cloud-agnostic |
| **IaC** | Terraform 1.9.x | Portable across clouds (NOT ARM templates) |
| **Containers** | Docker + Docker Compose | Standard format, portable |
| **CI/CD** | GitHub Actions | Free, cloud-agnostic |

---

### 4.3.1 Pipecat Package Strategy

SphereVoice installs Pipecat from the **pinned upstream package** and keeps product-specific behavior in the SphereVoice repository instead of a long-lived fork.

| Item | Detail |
|------|--------|
| **Package source** | `pipecat-ai` from PyPI |
| **Version policy** | Exact version pin in `backend/requirements.txt` |
| **Custom behavior** | Implemented in `backend/app/modules/pipeline/` |
| **Upgrade path** | Bump the pinned package version only after SphereVoice smoke tests pass |
| **Debugging fallback** | Clone upstream separately only when framework-level debugging is needed |

**What the package-first model enables:**
1. **Custom FrameProcessors** — SphereVoice-specific processors (latency tracker, prompt injector, recording tee, RAG injection) live in SphereVoice code
2. **Provider/service composition** — STT, LLM, and TTS selection stays in SphereVoice orchestration code
3. **Lower maintenance overhead** — Upgrades are handled as dependency changes instead of fork merges
4. **Safer boundaries** — Product logic remains testable in the SphereVoice repo instead of being hidden in framework patches

**Upgrade cadence:**
- Keep Pipecat pinned to an exact version in `backend/requirements.txt`
- Test package bumps with SphereVoice pipeline smoke tests before merge
- Prefer upstream contributions over maintaining private framework patches

**requirements.txt entry:**
```
pipecat-ai[livekit,deepgram,openai,groq,anthropic,cartesia,elevenlabs,lmnt,silero]==0.0.104
```

---

### 4.4 Deployment Architecture

**Azure Resources (Free with Credits):**
- Azure Database for PostgreSQL (Flexible Server) - 2 vCores, 8GB RAM
- Azure Cache for Redis (Standard C1) - 1GB
- Azure Blob Storage (Hot tier) - 100GB
- Azure Container Apps (2 instances, 1 vCPU, 2GB RAM each)
- Azure VM (Standard B2s) for LiveKit - 2 vCPUs, 4GB RAM
- Azure Monitor + Application Insights

**Estimated Azure Pay-As-You-Go Cost: ~$250-350/month**  
Fully covered by Azure credits ($5,000-10,000) for 6-12 months. Post-credits, migrate core services to Supabase/Railway targeting <$150/month (see Risk Mitigation).

**Terraform Structure:**
```
terraform/
├── environments/
│   ├── dev/
│   │   └── main.tf
│   ├── staging/
│   │   └── main.tf
│   └── production/
│       └── main.tf
├── modules/
│   ├── database/
│   ├── redis/
│   ├── storage/
│   ├── container_apps/
│   ├── vm/
│   └── monitoring/
└── variables.tf
```

**Deployment Regions:**
- **Primary:** Azure Central India — resource group: `SphereVoice-Sphere`
- **Future:** Azure East US (US clients), Azure West US (failover)

**Traffic Routing:**
- Azure Front Door for global load balancing
- Route to nearest region based on caller location

---

## 5. Data Models & Schema

### 5.1 Core Tables

**tenants**
```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) DEFAULT 'active', -- active, suspended, deleted
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tenants_slug ON tenants(slug);
CREATE INDEX idx_tenants_status ON tenants(status);
```

**users**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL, -- admin, developer, read_only, client_user
    tenant_id UUID REFERENCES tenants(id), -- NULL for employees, set for client users
    password_hash VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_role ON users(role);
```

**provider_keys**
```sql
CREATE TABLE provider_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- NULL for Sphere default keys
    provider_name VARCHAR(100) NOT NULL, -- deepgram, openai, elevenlabs, twilio, etc.
    provider_category VARCHAR(50) NOT NULL, -- stt, llm, tts, telephony
    api_key_encrypted TEXT NOT NULL, -- AES-256 encrypted
    is_default BOOLEAN DEFAULT false, -- Sphere default key
    is_active BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}', -- Additional provider-specific config
    last_tested_at TIMESTAMPTZ,
    test_status VARCHAR(20), -- success, failed, pending
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_provider_keys_tenant ON provider_keys(tenant_id);
CREATE INDEX idx_provider_keys_category ON provider_keys(provider_category);
CREATE INDEX idx_provider_keys_default ON provider_keys(is_default) WHERE is_default = true;
CREATE UNIQUE INDEX idx_provider_keys_tenant_name ON provider_keys(tenant_id, provider_name) 
    WHERE tenant_id IS NOT NULL;
```

**agents**
```sql
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- conversation_flow, single_prompt
    status VARCHAR(20) DEFAULT 'draft', -- draft, published, archived
    
    -- Provider selections (references provider_keys, or NULL for default)
    stt_provider_id UUID REFERENCES provider_keys(id),
    llm_provider_id UUID REFERENCES provider_keys(id),
    tts_provider_id UUID REFERENCES provider_keys(id),
    telephony_provider_id UUID REFERENCES provider_keys(id),
    
    -- Configuration
    config JSONB NOT NULL DEFAULT '{}', -- Flow nodes, prompts, settings, etc.
    
    -- Global settings
    language VARCHAR(10) DEFAULT 'en-US',
    voice_id VARCHAR(100),
    voice_speed DECIMAL(3,2) DEFAULT 1.0,
    voice_volume DECIMAL(3,2) DEFAULT 1.0,
    
    -- LLM settings
    llm_model VARCHAR(100),
    llm_temperature DECIMAL(3,2) DEFAULT 0.7,
    
    -- Call settings
    max_call_duration_seconds INT DEFAULT 3600,
    end_on_silence_seconds INT DEFAULT 10,
    voicemail_detection VARCHAR(20) DEFAULT 'hang_up', -- hang_up, leave_voicemail
    
    -- Post-call extraction
    extraction_fields JSONB DEFAULT '[]', -- Array of extraction field configs
    
    -- Webhook
    webhook_url TEXT,
    webhook_events TEXT[] DEFAULT '{}',
    
    -- Versioning
    version INT DEFAULT 0,
    published_at TIMESTAMPTZ,
    
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agents_tenant ON agents(tenant_id);
CREATE INDEX idx_agents_type ON agents(type);
CREATE INDEX idx_agents_status ON agents(status);
```

**agent_versions**
```sql
CREATE TABLE agent_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    version INT NOT NULL,
    config JSONB NOT NULL, -- Full snapshot of agent config at this version
    published_at TIMESTAMPTZ NOT NULL,
    published_by UUID REFERENCES users(id),
    
    UNIQUE(agent_id, version)
);

CREATE INDEX idx_agent_versions_agent ON agent_versions(agent_id);
```

**knowledge_bases**
```sql
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE, -- NULL for global KB
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sharing_scope VARCHAR(20) DEFAULT 'private', -- private, tenant, global
    
    -- Retrieval settings
    default_chunk_count INT DEFAULT 3,
    default_similarity_threshold DECIMAL(3,2) DEFAULT 0.7,
    
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kb_tenant ON knowledge_bases(tenant_id);
CREATE INDEX idx_kb_scope ON knowledge_bases(sharing_scope);
```

**kb_documents**
```sql
CREATE TABLE kb_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(20) NOT NULL, -- file, text
    file_url TEXT, -- Azure Blob URL if type=file
    content TEXT, -- Raw text if type=text
    processed_at TIMESTAMPTZ,
    chunk_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kb_docs_kb ON kb_documents(kb_id);
```

**kb_embeddings**
```sql
-- Requires pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE kb_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    kb_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INT NOT NULL,
    embedding vector(1536), -- OpenAI text-embedding-3-small dimension
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kb_embeddings_doc ON kb_embeddings(document_id);
CREATE INDEX idx_kb_embeddings_kb ON kb_embeddings(kb_id);
-- Vector index for similarity search
CREATE INDEX idx_kb_embeddings_vector ON kb_embeddings USING ivfflat (embedding vector_cosine_ops);
```

**agent_knowledge_bases**
```sql
-- Many-to-many relationship
CREATE TABLE agent_knowledge_bases (
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    kb_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    
    -- Override retrieval settings per agent
    chunk_count INT,
    similarity_threshold DECIMAL(3,2),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (agent_id, kb_id)
);

CREATE INDEX idx_agent_kb_agent ON agent_knowledge_bases(agent_id);
CREATE INDEX idx_agent_kb_kb ON agent_knowledge_bases(kb_id);
```

**phone_numbers**
```sql
CREATE TABLE phone_numbers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    country_code VARCHAR(5),
    provider_name VARCHAR(50) NOT NULL, -- twilio, plivo, vonage, telnyx
    provider_sid TEXT, -- Provider's identifier for this number
    
    -- Assignment
    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,
    
    -- Routing
    fallback_number VARCHAR(20),
    webhook_url TEXT,
    
    -- Capabilities
    capabilities JSONB DEFAULT '{}', -- {voice: true, sms: true, mms: false}
    
    -- Costs
    monthly_cost DECIMAL(10,4),
    
    status VARCHAR(20) DEFAULT 'active', -- active, inactive
    purchased_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_phone_numbers_tenant ON phone_numbers(tenant_id);
CREATE INDEX idx_phone_numbers_agent ON phone_numbers(agent_id);
CREATE INDEX idx_phone_numbers_status ON phone_numbers(status);
```

**calls**
```sql
CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    phone_number_id UUID REFERENCES phone_numbers(id) ON DELETE SET NULL,
    
    -- Call details
    from_number VARCHAR(20) NOT NULL,
    to_number VARCHAR(20) NOT NULL,
    direction VARCHAR(20) NOT NULL, -- inbound, outbound
    
    -- Timing
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    duration_seconds INT,
    
    -- Status
    status VARCHAR(20) NOT NULL, -- ringing, in-progress, completed, failed, no-answer, busy
    disconnection_reason VARCHAR(100),
    
    -- Recording
    recording_url TEXT,
    recording_duration_seconds INT,
    
    -- Transcript
    transcript JSONB, -- Array of {speaker, text, timestamp, confidence}
    
    -- Metrics
    turn_count INT DEFAULT 0,
    avg_latency_ms INT,
    
    -- Post-call extraction
    extracted_data JSONB DEFAULT '{}', -- {call_summary, user_sentiment, custom_fields...}
    extraction_completed_at TIMESTAMPTZ,
    
    -- Costs (calculated from provider usage)
    stt_cost DECIMAL(10,4),
    llm_cost DECIMAL(10,4),
    tts_cost DECIMAL(10,4),
    telephony_cost DECIMAL(10,4),
    total_cost DECIMAL(10,4),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    dynamic_variables JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_calls_tenant ON calls(tenant_id);
CREATE INDEX idx_calls_agent ON calls(agent_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_started_at ON calls(started_at);
CREATE INDEX idx_calls_direction ON calls(direction);
-- GIN index for filtering by extracted_data fields
CREATE INDEX idx_calls_extracted_data ON calls USING GIN (extracted_data);
```

**call_events**
```sql
CREATE TABLE call_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL, -- call_started, transcription_update, function_called, call_ended, etc.
    event_data JSONB NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_call_events_call ON call_events(call_id);
CREATE INDEX idx_call_events_type ON call_events(event_type);
CREATE INDEX idx_call_events_timestamp ON call_events(timestamp);
```

**webhooks**
```sql
CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES agents(id) ON DELETE CASCADE, -- NULL for tenant-level webhooks
    
    url TEXT NOT NULL,
    events TEXT[] NOT NULL, -- Array of event names to subscribe to
    timeout_seconds INT DEFAULT 10,
    is_active BOOLEAN DEFAULT true,
    
    -- Security
    secret TEXT, -- For signing webhook payloads
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_webhooks_tenant ON webhooks(tenant_id);
CREATE INDEX idx_webhooks_agent ON webhooks(agent_id);
```

**webhook_deliveries**
```sql
CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    call_id UUID REFERENCES calls(id) ON DELETE CASCADE,
    
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    
    -- Delivery status
    status VARCHAR(20) NOT NULL, -- pending, delivered, failed
    attempts INT DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    response_status_code INT,
    response_body TEXT,
    error_message TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_webhook_deliveries_webhook ON webhook_deliveries(webhook_id);
CREATE INDEX idx_webhook_deliveries_status ON webhook_deliveries(status);
CREATE INDEX idx_webhook_deliveries_created_at ON webhook_deliveries(created_at);
```

**audit_logs**
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    
    action VARCHAR(100) NOT NULL, -- create_agent, update_provider, delete_call, etc.
    resource_type VARCHAR(50) NOT NULL, -- agent, provider, call, user, etc.
    resource_id UUID,
    
    changes JSONB, -- Old and new values
    ip_address INET,
    user_agent TEXT,
    
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_tenant ON audit_logs(tenant_id);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
```

---

### 5.2 Multi-Tenancy Strategy

**Row-Level Security (RLS):**
```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
-- ... etc

-- Example policy: Users can only access their tenant's data
CREATE POLICY tenant_isolation_policy ON agents
    FOR ALL
    TO authenticated_users
    USING (
        tenant_id = current_setting('app.current_tenant_id')::UUID
        OR current_setting('app.user_role') = 'admin'
    );
```

**Application-Level Enforcement:**
- Every API request includes tenant context
- Middleware validates user access to tenant
- Database queries automatically filter by tenant_id
- Admins can impersonate tenants for support

---

## 6. API Design

### 6.1 API Principles

- RESTful design with resource-oriented URLs
- JSON request/response bodies
- JWT authentication (Bearer token)
- Pagination for list endpoints (limit/offset or cursor)
- Filtering via query parameters
- Versioning via URL prefix (`/api/v1/...`)
- OpenAPI 3.0 documentation (auto-generated by FastAPI)

### 6.2 Authentication

**POST /api/v1/auth/login**
```json
Request:
{
  "email": "user@Sphere.ai",
  "password": "securepass"
}

Response:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": "uuid",
    "email": "user@Sphere.ai",
    "name": "John Doe",
    "role": "developer",
    "tenant_id": "uuid"
  }
}
```

**POST /api/v1/auth/refresh**
```json
Request:
{
  "refresh_token": "eyJ..."
}

Response:
{
  "access_token": "eyJ..."
}
```

---

### 6.3 Provider Management

**GET /api/v1/providers**
```
Query params: ?category=stt&is_active=true

Response:
{
  "providers": [
    {
      "id": "uuid",
      "provider_name": "deepgram",
      "provider_category": "stt",
      "is_default": true,
      "is_active": true,
      "last_tested_at": "2026-02-28T10:00:00Z",
      "test_status": "success",
      "created_at": "2026-01-15T08:00:00Z"
    }
  ],
  "total": 10
}
```

**POST /api/v1/providers**
```json
Request:
{
  "provider_name": "deepgram",
  "provider_category": "stt",
  "api_key": "your-api-key",
  "is_default": true,
  "config": {
    "model": "flux-general-en",
    "language": "en-US",
    "eager_eot_threshold": 0.5,
    "eot_threshold": 0.8
  }
}

Response:
{
  "id": "uuid",
  "provider_name": "deepgram",
  "provider_category": "stt",
  "is_default": true,
  "created_at": "2026-02-28T12:00:00Z"
}
```

**POST /api/v1/providers/{id}/test**
```json
Response:
{
  "status": "success",
  "latency_ms": 245,
  "message": "Connection successful"
}
```

---

### 6.4 Agent Management

**GET /api/v1/agents**
```
Query params: ?tenant_id=uuid&status=published&type=conversation_flow

Response:
{
  "agents": [
    {
      "id": "uuid",
      "tenant_id": "uuid",
      "name": "Dental Receptionist",
      "type": "conversation_flow",
      "status": "published",
      "version": 3,
      "created_at": "2026-02-15T10:00:00Z",
      "updated_at": "2026-02-28T14:00:00Z"
    }
  ],
  "total": 25,
  "page": 1,
  "limit": 50
}
```

**GET /api/v1/agents/{id}**
```json
Response:
{
  "id": "uuid",
  "tenant_id": "uuid",
  "name": "Dental Receptionist",
  "type": "conversation_flow",
  "status": "published",
  "config": {
    "execution_mode": "flex",
    "nodes": [...],
    "edges": [...]
  },
  "stt_provider_id": "uuid",
  "llm_provider_id": "uuid",
  "tts_provider_id": "uuid",
  "language": "en-US",
  "voice_id": "elevenlabs-voice-123",
  "llm_model": "gpt-4o-mini",
  "llm_temperature": 0.7,
  "extraction_fields": [
    {
      "name": "appointment_booked",
      "type": "boolean",
      "prompt": "Was an appointment successfully booked?"
    }
  ],
  "webhook_url": "https://client.com/webhook",
  "webhook_events": ["call_ended"],
  "version": 3,
  "created_at": "2026-02-15T10:00:00Z"
}
```

**POST /api/v1/agents**
```json
Request:
{
  "tenant_id": "uuid",
  "name": "Dental Receptionist",
  "type": "conversation_flow",
  "config": {
    "execution_mode": "flex",
    "nodes": [...],
    "edges": [...]
  },
  "stt_provider_id": "uuid",
  "llm_provider_id": "uuid",
  "tts_provider_id": "uuid",
  "language": "en-US",
  "voice_id": "elevenlabs-voice-123"
}

Response:
{
  "id": "uuid",
  "status": "draft",
  "version": 0,
  "created_at": "2026-02-28T15:00:00Z"
}
```

**PUT /api/v1/agents/{id}**
```json
Request:
{
  "name": "Updated Name",
  "config": {...}
}

Response:
{
  "id": "uuid",
  "version": 1,
  "updated_at": "2026-02-28T15:30:00Z"
}
```

**POST /api/v1/agents/{id}/publish**
```json
Response:
{
  "id": "uuid",
  "status": "published",
  "version": 1,
  "published_at": "2026-02-28T16:00:00Z"
}
```

**GET /api/v1/agents/{id}/versions**
```json
Response:
{
  "versions": [
    {
      "version": 3,
      "published_at": "2026-02-28T14:00:00Z",
      "published_by": "uuid"
    },
    {
      "version": 2,
      "published_at": "2026-02-20T10:00:00Z",
      "published_by": "uuid"
    }
  ]
}
```

---

### 6.5 Knowledge Base

**POST /api/v1/knowledge-bases**
```json
Request:
{
  "name": "Dental Procedures KB",
  "description": "Common dental procedures and FAQs",
  "tenant_id": "uuid",
  "sharing_scope": "tenant"
}

Response:
{
  "id": "uuid",
  "name": "Dental Procedures KB",
  "created_at": "2026-02-28T10:00:00Z"
}
```

**POST /api/v1/knowledge-bases/{id}/documents**
```json
Request (multipart/form-data):
file: <PDF file>
name: "Dental FAQ.pdf"

Response:
{
  "document_id": "uuid",
  "name": "Dental FAQ.pdf",
  "type": "file",
  "file_url": "https://blob.azure.com/...",
  "status": "processing"
}
```

**POST /api/v1/knowledge-bases/{id}/documents/text**
```json
Request:
{
  "name": "Office Hours",
  "content": "Our office is open Monday-Friday 9am-5pm..."
}

Response:
{
  "document_id": "uuid",
  "name": "Office Hours",
  "type": "text",
  "status": "processing"
}
```

**GET /api/v1/knowledge-bases/{id}/search**
```
Query: ?q=office hours&limit=3

Response:
{
  "results": [
    {
      "chunk_text": "Our office is open Monday-Friday 9am-5pm...",
      "similarity": 0.92,
      "document_name": "Office Hours",
      "metadata": {}
    }
  ]
}
```

---

### 6.6 Phone Numbers

**GET /api/v1/phone-numbers/search**
```
Query: ?country=US&area_code=415&limit=10

Response:
{
  "numbers": [
    {
      "phone_number": "+14155551234",
      "country_code": "US",
      "capabilities": {
        "voice": true,
        "sms": true
      },
      "monthly_cost": 1.00
    }
  ]
}
```

**POST /api/v1/phone-numbers/purchase**
```json
Request:
{
  "phone_number": "+14155551234",
  "tenant_id": "uuid",
  "provider_name": "twilio"
}

Response:
{
  "id": "uuid",
  "phone_number": "+14155551234",
  "status": "active",
  "purchased_at": "2026-02-28T12:00:00Z"
}
```

**PUT /api/v1/phone-numbers/{id}/assign**
```json
Request:
{
  "agent_id": "uuid"
}

Response:
{
  "id": "uuid",
  "phone_number": "+14155551234",
  "agent_id": "uuid"
}
```

---

### 6.7 Calls

**GET /api/v1/calls**
```
Query params: ?tenant_id=uuid&status=completed&start_date=2026-02-01&end_date=2026-02-28&limit=50&offset=0

Response:
{
  "calls": [
    {
      "id": "uuid",
      "tenant_id": "uuid",
      "agent_id": "uuid",
      "from_number": "+14155551234",
      "to_number": "+14155555678",
      "direction": "inbound",
      "started_at": "2026-02-28T10:00:00Z",
      "ended_at": "2026-02-28T10:05:30Z",
      "duration_seconds": 330,
      "status": "completed",
      "recording_url": "https://blob.azure.com/...",
      "extracted_data": {
        "call_summary": "Customer scheduled appointment for teeth cleaning",
        "user_sentiment": "positive",
        "appointment_booked": true
      },
      "total_cost": 0.52
    }
  ],
  "total": 1250,
  "page": 1,
  "limit": 50
}
```

**GET /api/v1/calls/{id}**
```json
Response:
{
  "id": "uuid",
  "tenant_id": "uuid",
  "agent_id": "uuid",
  "from_number": "+14155551234",
  "to_number": "+14155555678",
  "direction": "inbound",
  "started_at": "2026-02-28T10:00:00Z",
  "ended_at": "2026-02-28T10:05:30Z",
  "duration_seconds": 330,
  "status": "completed",
  "recording_url": "https://blob.azure.com/...",
  "transcript": [
    {
      "speaker": "ai",
      "text": "Hello, thank you for calling Bright Dental. How can I help you today?",
      "timestamp": "2026-02-28T10:00:02Z",
      "confidence": 0.98
    },
    {
      "speaker": "user",
      "text": "Hi, I'd like to schedule a teeth cleaning.",
      "timestamp": "2026-02-28T10:00:05Z",
      "confidence": 0.95
    }
  ],
  "extracted_data": {
    "call_summary": "Customer scheduled appointment for teeth cleaning",
    "user_sentiment": "positive",
    "appointment_booked": true
  },
  "avg_latency_ms": 420,
  "turn_count": 12,
  "total_cost": 0.52
}
```

**POST /api/v1/calls** (Initiate outbound call — single call V1; batch calling V1.1)
```json
Request:
{
  "agent_id": "uuid",
  "to_number": "+14155555678",
  "from_number": "+14155551234",
  "dynamic_variables": {
    "customer_name": "Jane Doe",
    "appointment_date": "2026-03-05"
  }
}

Response:
{
  "call_id": "uuid",
  "status": "initiated",
  "started_at": "2026-02-28T14:00:00Z"
}
```

---

### 6.8 Live Monitoring (WebSocket)

**WebSocket /ws/live-calls**

```
Connection: Upgrade to WebSocket
Authorization: Bearer <token>

Client -> Server:
{
  "action": "subscribe",
  "tenant_id": "uuid" // Optional, omit for all tenants (admin only)
}

Server -> Client (on new call):
{
  "event": "call_started",
  "data": {
    "call_id": "uuid",
    "tenant_id": "uuid",
    "agent_id": "uuid",
    "from_number": "+14155551234",
    "to_number": "+14155555678",
    "started_at": "2026-02-28T15:00:00Z"
  }
}

Server -> Client (transcription update):
{
  "event": "transcription_update",
  "data": {
    "call_id": "uuid",
    "speaker": "user",
    "text": "I need to reschedule my appointment",
    "timestamp": "2026-02-28T15:02:15Z",
    "confidence": 0.96
  }
}

Server -> Client (call ended):
{
  "event": "call_ended",
  "data": {
    "call_id": "uuid",
    "ended_at": "2026-02-28T15:05:30Z",
    "duration_seconds": 330,
    "status": "completed"
  }
}
```

---

### 6.9 Analytics

**GET /api/v1/analytics/metrics**
```
Query: ?tenant_id=uuid&start_date=2026-02-01&end_date=2026-02-28

Response:
{
  "total_calls": 1250,
  "avg_call_duration_seconds": 285,
  "total_call_duration_seconds": 356250,
  "avg_latency_ms": 425,
  "concurrency_used": 15,
  "concurrency_peak": 48,
  "call_transfer_rate": 0.08,
  "voicemail_rate": 0.12,
  "success_rate": 0.87
}
```

**GET /api/v1/analytics/time-series**
```
Query: ?metric=call_count&granularity=day&start_date=2026-02-01&end_date=2026-02-28

Response:
{
  "metric": "call_count",
  "granularity": "day",
  "data": [
    {
      "timestamp": "2026-02-01T00:00:00Z",
      "value": 42
    },
    {
      "timestamp": "2026-02-02T00:00:00Z",
      "value": 38
    }
  ]
}
```

---

## 7. Voice Pipeline Architecture

### 7.1 Voice Pipeline Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                     INBOUND CALL FLOW                            │
└──────────────────────────────────────────────────────────────────┘

1. Caller dials phone number (+14155551234)
        │
        ▼
2. Twilio/Plivo receives call
        │
        ▼
3. Twilio sends webhook to SphereVoice: POST /api/v1/webhooks/inbound
        │
        ▼
4. SphereVoice looks up phone_number -> agent_id
        │
        ▼
5. SphereVoice initiates LiveKit room for this call
        │
        ▼
6. SphereVoice sends TwiML/XML response to Twilio:
   "Connect to LiveKit SIP endpoint"
        │
        ▼
7. Twilio forwards audio to LiveKit via SIP
        │
        ▼
8. LiveKit receives audio stream
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│     STREAMING VOICE PIPELINE (Pipecat — Sphere/pipecat fork)   │
└──────────────────────────────────────────────────────────────────┘

Pipecat is an open-source Python framework (Apache-2.0) for building
real-time voice AI agents. SphereVoice maintains a fork at
`github.com/Sphere/pipecat` (branch `SphereVoice-main`) to allow deep
customisation of frame processors, transport internals, and
latency-critical hot paths without waiting on upstream releases.
Upstream changes are tracked via `upstream/main` and merged regularly.

The fork provides a frame-based pipeline architecture with built-in
service classes for all major STT/LLM/TTS providers, voice activity
detection, context aggregation, and transport layers.

SphereVoice uses the fork as its voice pipeline engine. LiveKit handles the
WebRTC/SIP media layer; Pipecat's LiveKitTransport connects to
LiveKit as a room participant and processes audio frames through
the pipeline. For direct telephony WebSocket, Pipecat also supports
FastAPIWebsocketTransport + TwilioFrameSerializer/PlivoFrameSerializer.

┌─────────────────────────────────────────────────────────┐
│              Pipecat Pipeline (per call)                 │
│                                                         │
│  transport.input()    ← LiveKitTransport receives audio │
│        │                                                │
│        ▼                                                │
│  ┌─────────────────┐  SileroVADAnalyzer (on-device,     │
│  │  VAD + STT      │  <10ms) detects voice activity    │
│  │  (DeepgramSTT   │  DeepgramSTTService streams to    │
│  │   Service)      │  Deepgram Flux or Nova-3          │
│  └─────────────────┘                                    │
│        │                                                │
│        ▼                                                │
│  ┌─────────────────┐  LLMContextAggregatorPair manages  │
│  │  context_agg    │  turn-taking — collects user text, │
│  │   .user()       │  appends to conversation context   │
│  └─────────────────┘                                    │
│        │                                                │
│        ▼                                                │
│  ┌─────────────────┐  Agent Executor injects flow/prompt │
│  │  LLM Service    │  FAST: GroqLLMService ~50ms TTFT  │
│  │  (OpenAI/Groq/  │  STD:  OpenAILLMService ~120ms    │
│  │   Anthropic)    │  FULL: AnthropicLLMService ~200ms  │
│  └─────────────────┘                                    │
│        │                                                │
│        ▼                                                │
│  ┌─────────────────┐  Pipecat buffers on sentence bounds │
│  │  TTS Service    │  FAST: CartesiaTTSService ~60ms    │
│  │  (Cartesia/     │  STD:  ElevenLabsTTSService ~100ms │
│  │   ElevenLabs)   │  ALT:  OpenAI TTS / LMNT          │
│  └─────────────────┘                                    │
│        │                                                │
│        ▼                                                │
│  transport.output()   → LiveKitTransport sends audio    │
│        │                                                │
│        ▼                                                │
│  ┌─────────────────┐                                    │
│  │  context_agg    │  Appends assistant response to     │
│  │   .assistant()  │  conversation context for next turn│
│  └─────────────────┘                                    │
└─────────────────────────────────────────────────────────┘
        │
        ▼
LiveKit Server (WebRTC/SIP bridge)
        │
        ▼
Twilio/Plivo (SIP)
        │
        ▼
Caller hears AI response

Alternative Transport (Direct Telephony WebSocket):
For simpler deployments without LiveKit, Pipecat can connect
directly to Twilio/Plivo via FastAPIWebsocketTransport with
TwilioFrameSerializer or PlivoFrameSerializer. This receives
the media stream WebSocket from the telephony provider and
processes it through the same Pipecat pipeline.

┌──────────────────────────────────────────────────────────────────┐
│                      LATENCY BREAKDOWN                           │
└──────────────────────────────────────────────────────────────────┘

Formula:  totalLatency = eou_delay + llm_ttft + tts_ttfb

Target: <300ms P50  |  <500ms P99  (end-to-end first-byte audio)

                          FAST STACK (P50)          STANDARD STACK (P50)
                          ──────────────────         ──────────────────
EOU Detection:            30-60ms  (Deepgram Flux    80-120ms (Nova-3 VAD
                          EagerEndOfTurn,             endpointing, eot_threshold=0.8)
                          eager_eot_threshold=0.5)
STT (final transcript):  (included in EOU)           (included in EOU)
LLM (TTFT):              40-80ms  (Groq llama-3)    150-250ms (GPT-4o streaming)
TTS (TTFB):              50-80ms  (Cartesia Sonic-3) 80-130ms (ElevenLabs Turbo v2.5)
Network overhead:         20-40ms  (regional deploy)  30-50ms  (regional deploy)
                          ──────────────────         ──────────────────
Total (P50):              ~140-260ms                  ~340-550ms

Fast Stack: Deepgram Flux + Groq + Cartesia Sonic-3
Standard Stack: Deepgram Nova-3 + GPT-4o + ElevenLabs Turbo v2.5

Latency-Critical Optimizations:
✅ Pipecat (forked as `Sphere/pipecat`) as the pipeline framework — eliminates
   ~60-70% of custom real-time audio orchestration code; provides
   battle-tested frame processing, buffering, and streaming
✅ DeepgramSTTService with Flux model (`nova-3-general` on Pipecat)
   for lowest-latency streaming transcription
✅ SileroVADAnalyzer built into Pipecat's LiveKitParams for
   accurate voice activity detection (<10ms)
✅ LLMContextAggregatorPair for automatic turn management
   (collects user text, sends to LLM, appends assistant response)
✅ Stream-all architecture: Pipecat Pipeline processes frames
   through STT→LLM→TTS fully streaming with sentence-boundary
   TTS dispatch (built into Pipecat's frame processors)
✅ Use fastest LLM for simple conversational turns (Groq for
   llama-3, GPT-4o-mini for medium complexity, GPT-4o only for
   complex reasoning or tool-use turns)
✅ CartesiaTTSService for lowest TTFB; ElevenLabsTTSService
   (`optimize_streaming_latency=3`) as high-quality alternative
✅ ServiceSwitcher wraps providers for runtime hot-swap and
   failover without adding latency on the happy path
✅ Cache TTS audio for deterministic responses (greetings, FAQs,
   hold messages) — eliminates TTS latency entirely for cached turns
✅ Regional deployment: US-East + Mumbai; route to nearest region
✅ Pipecat OpenTelemetry integration: TTFB spans per service
   (STT, LLM, TTS) for granular latency monitoring
✅ Use 16kHz mono PCM (linear16) for telephony — no transcoding
```

---

### 7.2 Key Components

**CallOrchestrator (FastAPI Service)**
```python
class CallOrchestrator:
    """
    Manages the full lifecycle of a call:
    1. Receives inbound webhook from Twilio/Plivo
    2. Creates LiveKit room
    3. Initializes VoicePipeline
    4. Logs call to database
    5. Streams events to WebSocket clients
    6. Triggers post-call processing
    """
    
    async def handle_inbound_call(
        self,
        from_number: str,
        to_number: str,
        call_sid: str,
        provider: str
    ) -> TwiMLResponse:
        # Look up phone number -> agent
        phone_number = await self.db.get_phone_number(to_number)
        agent = await self.db.get_agent(phone_number.agent_id)
        
        # Create call record
        call = await self.db.create_call(
            tenant_id=phone_number.tenant_id,
            agent_id=agent.id,
            from_number=from_number,
            to_number=to_number,
            direction="inbound",
            status="ringing"
        )
        
        # Create LiveKit room
        room = await self.livekit.create_room(call.id)
        
        # Generate LiveKit token for Pipecat agent participant
        token = await self.livekit.create_agent_token(room.name)
        
        # Initialize Pipecat voice pipeline
        pipeline = VoicePipeline(
            call_id=call.id,
            agent=agent,
            livekit_url=self.livekit.url,
            livekit_token=token,
            room_name=room.name,
        )
        await pipeline.start()
        
        # Return TwiML to connect Twilio to LiveKit
        return TwiMLResponse.connect_to_sip(room.sip_uri)
```

**VoicePipeline (Core Streaming Logic — Pipecat `pipecat-ai`)**
```python
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.transports.livekit import LiveKitTransport, LiveKitParams


class VoicePipeline:
    """
    Orchestrates the ultra-low-latency STT → LLM → TTS streaming pipeline
    using the Sphere Pipecat fork (Sphere/pipecat) with LiveKitTransport.
    
    Pipecat provides:
    - Built-in service classes for Deepgram, OpenAI, Groq, Anthropic,
      Cartesia, ElevenLabs, LMNT, and more
    - Frame-based pipeline architecture for composable real-time audio
    - SileroVADAnalyzer for voice activity detection (<10ms)
    - LLMContextAggregatorPair for automatic turn management
    - ServiceSwitcher for runtime provider hot-swap
    - OpenTelemetry integration with TTFB span metrics per service
    - TwilioFrameSerializer / PlivoFrameSerializer for direct telephony
    
    SphereVoice adds:
    - PipecatProviderFactory: maps DB agent config → Pipecat service instances
    - Agent Executor: conversation flow engine (node-based) + single prompt
    - Knowledge Base: RAG injection via custom Pipecat processor
    - Post-call processing, recording storage, analytics, and webhooks
    
    Latency target: <300ms P50 (EOU → first audio byte to caller)
    Formula:  totalLatency = eou_delay + llm_ttft + tts_ttfb
    
    NOTE (v0.0.99+ API changes):
    - OpenAILLMContext is deprecated → use LLMContext
    - llm.create_context_aggregator() is deprecated → use LLMContextAggregatorPair directly
    - vad_analyzer on transport params is deprecated → pass via LLMUserAggregatorParams
    - allow_interruptions in PipelineParams is deprecated → handled by user_turn_strategies
    """
    
    def __init__(self, call_id, agent, livekit_url, livekit_token, room_name):
        self.call_id = call_id
        self.agent = agent
        self.livekit_url = livekit_url
        self.livekit_token = livekit_token
        self.room_name = room_name
        
    async def start(self):
        """
        Build and run the Pipecat pipeline:
        
        transport.input() → STT → context_aggregator.user()
          → LLM → TTS → transport.output() → context_aggregator.assistant()
        
        Pipecat handles all streaming, buffering, sentence splitting,
        and turn management internally. SphereVoice only needs to configure
        the services and provide the agent prompt.
        """
        # --- Transport (LiveKit) ---
        transport = LiveKitTransport(
            url=self.livekit_url,
            token=self.livekit_token,
            room_name=self.room_name,
            params=LiveKitParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_in_sample_rate=16000,
                audio_out_sample_rate=16000,
            ),
        )
        
        # --- STT (Deepgram Flux for lowest latency) ---
        stt = await PipecatProviderFactory.get_stt(self.agent)
        
        # --- LLM (Groq for speed, GPT-4o for complexity) ---
        llm = await PipecatProviderFactory.get_llm(self.agent)
        
        # --- TTS (Cartesia Sonic-3 for lowest TTFB) ---
        tts = await PipecatProviderFactory.get_tts(self.agent)
        
        # --- Context & Turn Management (v0.0.99+ universal API) ---
        system_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        context = LLMContext(messages)
        
        # LLMContextAggregatorPair replaces llm.create_context_aggregator()
        # VAD is now configured here (not on transport params)
        context_aggregator = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer(),
            ),
        )
        
        # --- Assemble Pipeline ---
        pipeline = Pipeline([
            transport.input(),                # Receives audio frames from LiveKit
            stt,                              # Deepgram STT (streaming transcription)
            context_aggregator.user(),        # Collects user text + VAD turn detection
            llm,                              # LLM generates response (streaming)
            tts,                              # TTS synthesizes audio (streaming)
            transport.output(),               # Sends audio frames to LiveKit
            context_aggregator.assistant(),   # Appends response to context
        ])
        
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,          # OpenTelemetry TTFB/latency spans
                enable_usage_metrics=True,    # Token/character usage tracking
            ),
        )
        
        # --- Register SphereVoice event handlers ---
        @transport.event_handler("on_first_participant_joined")
        async def on_joined(transport, participant):
            # Deliver welcome message (if "AI speaks first" mode)
            if self.agent.config.get("welcome_message"):
                await task.queue_frames([
                    context_aggregator.user().get_context_frame(),
                ])
        
        # --- Run ---
        runner = PipelineRunner(handle_sigint=True)
        await runner.run(task)
    
    def _build_system_prompt(self) -> str:
        """Build system prompt from agent config (flow or single prompt)"""
        if self.agent.type == "conversation_flow":
            node = self.agent.config.get("start_node")
            return self._build_flow_prompt(node)
        return self.agent.config.get("system_prompt", "")
    
    def _build_flow_prompt(self, node: dict) -> str:
        """Build prompt from conversation flow node"""
        # Inject node instructions, conversation history, KB context
        prompt_parts = [node.get("system_prompt", "")]
        if node.get("instructions"):
            prompt_parts.append(f"\nCurrent step: {node['instructions']}")
        return "\n".join(prompt_parts)
```

**Alternative: Direct Twilio WebSocket (bypasses LiveKit)**
```python
from pipecat.transports.fastapi_websocket import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)
from pipecat.serializers.twilio import TwilioFrameSerializer


async def handle_twilio_websocket(websocket, stream_sid, call_sid):
    """
    For deployments that don't need LiveKit, Pipecat can
    connect directly to Twilio's media stream WebSocket.
    Pipecat auto-handles audio serialization via TwilioFrameSerializer.
    """
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            serializer=TwilioFrameSerializer(stream_sid),
        ),
    )
    # Same pipeline assembly as above (stt → llm → tts)
    # ...
```

---

### 7.3 Provider Abstraction Implementation

> **Architecture Change (v1.3):** With Pipecat as the pipeline framework, SphereVoice no longer needs
> custom `STTProvider` / `LLMProvider` / `TTSProvider` base classes or concrete implementations.
> Pipecat provides production-grade service classes for all supported providers out of the box
> (e.g., `DeepgramSTTService`, `OpenAILLMService`, `CartesiaTTSService`). SphereVoice's provider
> abstraction is now a **factory layer** that reads provider configuration from the database
> and instantiates the correct Pipecat service. Provider hot-swap is handled by Pipecat's
> built-in `ServiceSwitcher`. Cost tracking uses Pipecat's `enable_usage_metrics` spans.

**PipecatProviderFactory (Maps DB Config → Pipecat Services)**
```python
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.tts import OpenAITTSService


class PipecatProviderFactory:
    """
    Maps SphereVoice agent DB config → Pipecat service instances.
    
    Pipecat provides built-in service classes for all major providers.
    This factory reads provider_key config from the database, decrypts
    API keys, and instantiates the correct Pipecat service class.
    
    This replaces the custom STTProvider/LLMProvider/TTSProvider base
    classes from v1.2. No custom streaming logic is needed — Pipecat
    handles all audio frame processing, buffering, and streaming.
    """
    
    # --- Registry (same providers as before, now using Pipecat classes) ---
    
    STT_PROVIDERS = {
        "deepgram_flux": "deepgram",     # ← RECOMMENDED: Lowest latency (Flux model)
        "deepgram": "deepgram",          #   Solid default (Nova-3)
        "assemblyai": "assemblyai",
        "azure_speech": "azure_speech",
        "openai_whisper": "openai_whisper",
    }
    
    LLM_PROVIDERS = {
        "groq": "groq",                  # ← RECOMMENDED for speed: ~50ms TTFT
        "openai": "openai",              #   GPT-4o-mini (~120ms) or GPT-4o (~200ms)
        "anthropic": "anthropic",
        "azure_openai": "azure_openai",
    }
    
    TTS_PROVIDERS = {
        "cartesia": "cartesia",           # ← RECOMMENDED: Lowest TTFB (~60ms, Sonic-3)
        "elevenlabs": "elevenlabs",       #   High quality (Turbo v2.5, ~100ms TTFB)
        "openai_tts": "openai_tts",
        "lmnt": "lmnt",                  #   Fast alternative, real-time voice AI optimized
        "playht": "playht",
        "azure_speech": "azure_speech",
    }
    
    @staticmethod
    async def get_stt(agent) -> "BaseSTTService":
        """Get Pipecat STT service from agent's provider config"""
        key = await db.get_provider_key(agent.stt_provider_id)
        api_key = decrypt(key.api_key_encrypted)
        config = key.config or {}
        
        if key.provider_name in ("deepgram", "deepgram_flux"):
            model = config.get("model", "nova-3-general")
            return DeepgramSTTService(
                api_key=api_key,
                live_options=LiveOptions(
                    model=model,
                    language=config.get("language", "en-US"),
                    encoding="linear16",
                    sample_rate=16000,
                    smart_format=True,
                    # Flux-specific options (ignored by Nova-3)
                    # EagerEndOfTurn + EndOfTurn for speculative LLM dispatch
                ),
            )
        elif key.provider_name == "assemblyai":
            from pipecat.services.assemblyai.stt import AssemblyAISTTService
            return AssemblyAISTTService(api_key=api_key)
        elif key.provider_name == "azure_speech":
            from pipecat.services.azure.stt import AzureSTTService
            return AzureSTTService(api_key=api_key, region=config.get("region"))
        
        raise ValueError(f"Unknown STT provider: {key.provider_name}")
        
    @staticmethod
    async def get_llm(agent) -> "BaseLLMService":
        """Get Pipecat LLM service from agent's provider config"""
        key = await db.get_provider_key(agent.llm_provider_id)
        api_key = decrypt(key.api_key_encrypted)
        config = key.config or {}
        
        if key.provider_name == "openai":
            return OpenAILLMService(
                api_key=api_key,
                model=config.get("model", "gpt-4o-mini"),
            )
        elif key.provider_name == "groq":
            return GroqLLMService(
                api_key=api_key,
                model=config.get("model", "llama-3.3-70b-versatile"),
            )
        elif key.provider_name == "anthropic":
            return AnthropicLLMService(
                api_key=api_key,
                model=config.get("model", "claude-sonnet-4-20250514"),
            )
        elif key.provider_name == "azure_openai":
            from pipecat.services.azure.llm import AzureLLMService
            return AzureLLMService(
                api_key=api_key,
                endpoint=config.get("endpoint"),
                model=config.get("model", "gpt-4o-mini"),
            )
        
        raise ValueError(f"Unknown LLM provider: {key.provider_name}")
    
    @staticmethod
    async def get_tts(agent) -> "BaseTTSService":
        """Get Pipecat TTS service from agent's provider config"""
        key = await db.get_provider_key(agent.tts_provider_id)
        api_key = decrypt(key.api_key_encrypted)
        config = key.config or {}
        
        if key.provider_name == "cartesia":
            return CartesiaTTSService(
                api_key=api_key,
                voice_id=config.get("voice_id", "default"),
                model=config.get("model", "sonic-3"),
            )
        elif key.provider_name == "elevenlabs":
            return ElevenLabsTTSService(
                api_key=api_key,
                voice_id=config.get("voice_id", "default"),
                model=config.get("model", "eleven_turbo_v2_5"),
                optimize_streaming_latency=config.get("optimize_streaming_latency", 3),
            )
        elif key.provider_name == "openai_tts":
            return OpenAITTSService(
                api_key=api_key,
                voice=config.get("voice", "alloy"),
            )
        elif key.provider_name == "lmnt":
            from pipecat.services.lmnt.tts import LMNTTTSService
            return LMNTTTSService(
                api_key=api_key,
                voice_id=config.get("voice_id", "default"),
            )
        
        raise ValueError(f"Unknown TTS provider: {key.provider_name}")
```

**Provider Hot-Swap (Pipecat ServiceSwitcher)**
```python
from pipecat.pipeline.service_switcher import ServiceSwitcher, ServiceSwitcherStrategyManual

# Example: allow runtime switching between STT providers
stt_switcher = ServiceSwitcher(
    services=[
        await PipecatProviderFactory.get_stt(agent),           # Primary (Deepgram Flux)
        await PipecatProviderFactory.get_stt_fallback(agent),  # Fallback (Deepgram Nova-3)
    ],
    strategy_type=ServiceSwitcherStrategyManual,
)

# Switch at runtime (e.g., on primary provider error)
await stt_switcher.switch_to(1)  # Switch to fallback index 1
```

**Cost Tracking**
```python
# Pipecat's enable_usage_metrics=True emits OpenTelemetry spans
# with token counts, character counts, and duration. SphereVoice hooks
# into these spans to calculate per-call costs.

# Example span attributes (emitted by Pipecat automatically):
# - stt.duration_seconds
# - llm.prompt_tokens, llm.completion_tokens
# - tts.characters_synthesized
# SphereVoice maps these to provider pricing for cost-per-call calculation.
```

---

## 8. Security & Compliance

### 8.1 Data Encryption

**At Rest:**
- API keys: AES-256 encryption using Azure Key Vault
- Call recordings: Azure Blob Storage with encryption enabled
- Database: Azure PostgreSQL encryption at rest (enabled by default)
- Backups: Encrypted using Azure Backup

**In Transit:**
- All API traffic: HTTPS/TLS 1.3
- WebSocket connections: WSS (WebSocket Secure)
- Database connections: SSL/TLS
- Provider API calls: HTTPS
- SIP/WebRTC: SRTP (Secure Real-time Transport Protocol)

---

### 8.2 Authentication & Authorization

**Authentication:**
- JWT tokens (access + refresh)
- Access token expiry: 1 hour
- Refresh token expiry: 7 days
- Token signing: RSA-256

**Authorization:**
- Role-based access control (RBAC)
- Resource-level permissions (tenant-scoped)
- Row-level security (PostgreSQL RLS)

**API Key Encryption:**
```python
from cryptography.fernet import Fernet
import base64

class KeyEncryption:
    def __init__(self, master_key: str):
        # Master key from Azure Key Vault
        self.cipher = Fernet(base64.b64encode(master_key.encode()))
        
    def encrypt(self, plaintext: str) -> str:
        return self.cipher.encrypt(plaintext.encode()).decode()
        
    def decrypt(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode()).decode()
```

---

### 8.3 Data Retention

**Configurable per tenant:**
- Call recordings: 7/30/90 days or custom
- Transcripts: 7/30/90 days or custom
- Call metadata: Permanent (for billing/analytics)
- Audit logs: 90 days minimum

**Automatic cleanup:**
- Celery periodic task runs daily
- Deletes expired recordings/transcripts from Blob Storage
- Soft-deletes database records (maintains call IDs for references)

---

### 8.4 Compliance Considerations

**GDPR (if serving EU clients):**
- Right to access: API endpoint to export user data
- Right to erasure: Delete call recordings/transcripts on request
- Data portability: Export in standard formats (JSON, CSV)

**HIPAA (for healthcare clients):**
- Business Associate Agreement (BAA) with Azure
- Encrypted storage and transmission
- Audit logs for all access to PHI
- Data residency controls (US-only storage for HIPAA data)

**PCI-DSS (if handling payment info):**
- Do NOT store credit card numbers in calls
- Use tokenization for payment references
- Redact sensitive info from transcripts

---

## 9. Observability & Monitoring

### 9.1 Structured Logging

**Log Format (JSON):**
```json
{
  "timestamp": "2026-02-28T15:30:45.123Z",
  "level": "INFO",
  "service": "voice-pipeline",
  "correlation_id": "call-uuid-12345",
  "message": "LLM response generated",
  "context": {
    "call_id": "uuid",
    "agent_id": "uuid",
    "tenant_id": "uuid",
    "latency_ms": 285,
    "tokens": 42
  }
}
```

**Log Levels:**
- DEBUG: Detailed diagnostic info (disabled in production)
- INFO: General operational events
- WARNING: Unexpected but handled situations
- ERROR: Errors that need attention
- CRITICAL: System failures

**Correlation IDs:**
- Every request gets a unique correlation ID
- Propagated across all service calls
- Enables distributed tracing

---

### 9.2 Metrics

**Key Metrics to Track:**

**System Metrics:**
- API request rate (requests/second)
- API latency (P50, P95, P99)
- Error rate (errors/minute)
- Database connection pool usage
- Redis connection count
- CPU/Memory usage per service

**Call Metrics:**
- Active calls (gauge)
- Call start rate (calls/minute)
- Call duration (histogram)
- Call success rate (%)
- Call error rate (errors/minute)

**Voice Pipeline Metrics:**
- STT latency (ms, histogram)
- LLM latency (ms, histogram)
- TTS latency (ms, histogram)
- End-to-end latency (ms, histogram)
- Turn count per call (histogram)

**Provider Metrics:**
- Provider API latency (per provider)
- Provider error rate (per provider)
- Provider cost (per call, aggregated)

**Business Metrics:**
- Total calls today/week/month
- Total cost today/week/month
- Cost per call (by tenant)
- Active tenants
- Active agents

---

### 9.3 Distributed Tracing

**OpenTelemetry Instrumentation:**
```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

@app.post("/api/v1/calls")
async def create_call(request: CallRequest):
    with tracer.start_as_current_span("create_call") as span:
        span.set_attribute("tenant_id", request.tenant_id)
        span.set_attribute("agent_id", request.agent_id)
        
        # Create call
        call = await call_orchestrator.handle_inbound_call(request)
        
        span.set_attribute("call_id", call.id)
        return call
```

**Trace Flow:**
```
HTTP Request
  └─> API Handler (create_call)
      └─> Database Query (get_agent)
      └─> LiveKit (create_room)
      └─> VoicePipeline (start)
          └─> STT (transcribe_stream)
          └─> LLM (generate_stream)
          └─> TTS (synthesize_stream)
```

---

### 9.4 Alerting

**Alert Channels:**
- Sentry (for errors)
- Azure Monitor Alerts (for metrics)
- Slack webhook (for critical alerts)
- Email (for summary reports)

**Alert Rules:**

**Critical Alerts (immediate notification):**
- API error rate >5% for 5 minutes
- Database connection pool exhausted
- Redis unavailable
- LiveKit server down
- Provider API failing (>10% error rate)

**Warning Alerts (notification within 15 minutes):**
- API latency P95 >2 seconds
- Active calls >80% of concurrency limit
- Disk space >80% on any VM
- High memory usage (>85%)

**Info Alerts (daily summary):**
- Total calls today
- Total cost today
- Top errors by count
- Slow API endpoints

---

## 10. Infrastructure & DevOps

### 10.1 Terraform Configuration

**Directory Structure:**
```
terraform/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tfvars
│   │   └── terraform.tfstate
│   ├── staging/
│   │   ├── main.tf
│   │   ├── variables.tfvars
│   │   └── terraform.tfstate
│   └── production/
│       ├── main.tf
│       ├── variables.tfvars
│       └── terraform.tfstate
├── modules/
│   ├── database/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── redis/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── storage/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── container_apps/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── vm/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── monitoring/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── provider.tf
└── variables.tf
```

**Example Module (Database):**
```hcl
# modules/database/main.tf

resource "azurerm_postgresql_flexible_server" "main" {
  name                   = var.server_name
  resource_group_name    = var.resource_group_name
  location              = var.location
  version               = "15"
  administrator_login    = var.admin_username
  administrator_password = var.admin_password
  
  storage_mb = 32768  # 32GB
  
  sku_name = "B_Standard_B2s"  # 2 vCores, 8GB RAM
  
  backup_retention_days = 7
  geo_redundant_backup_enabled = false
  
  high_availability {
    mode = "Disabled"  # Enable in production
  }
}

resource "azurerm_postgresql_flexible_server_database" "SphereVoice" {
  name      = "SphereVoice"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# Enable pgvector extension
resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "vector"
}
```

---

### 10.2 CI/CD Pipeline

**GitHub Actions Workflow:**
```yaml
# .github/workflows/deploy.yml

name: Deploy SphereVoice

on:
  push:
    branches: [main, staging, dev]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-cov
          
      - name: Run tests
        run: |
          cd backend
          pytest --cov=app tests/
          
      - name: Lint
        run: |
          cd backend
          pip install black flake8
          black --check app/
          flake8 app/
          
  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Login to Azure Container Registry
        uses: azure/docker-login@v1
        with:
          login-server: ${{ secrets.ACR_LOGIN_SERVER }}
          username: ${{ secrets.ACR_USERNAME }}
          password: ${{ secrets.ACR_PASSWORD }}
          
      - name: Build and push backend
        run: |
          cd backend
          docker build -t ${{ secrets.ACR_LOGIN_SERVER }}/SphereVoice-backend:${{ github.sha }} .
          docker push ${{ secrets.ACR_LOGIN_SERVER }}/SphereVoice-backend:${{ github.sha }}
          
      - name: Build and push frontend
        run: |
          cd frontend
          docker build -t ${{ secrets.ACR_LOGIN_SERVER }}/SphereVoice-frontend:${{ github.sha }} .
          docker push ${{ secrets.ACR_LOGIN_SERVER }}/SphereVoice-frontend:${{ github.sha }}
          
  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      
      - name: Azure Login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
          
      - name: Deploy to Azure Container Apps
        run: |
          az containerapp update \
            --name SphereVoice-backend \
            --resource-group SphereVoice-Sphere \
            --image ${{ secrets.ACR_LOGIN_SERVER }}/SphereVoice-backend:${{ github.sha }}
```

---

### 10.3 Docker Configuration

**Backend Dockerfile:**
```dockerfile
# backend/Dockerfile

FROM python:3.11.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pipecat — install from Sphere fork with all provider extras:
# pip install "pipecat-ai[daily,livekit,deepgram,openai,groq,anthropic,cartesia,elevenlabs,lmnt,silero,azure]==0.0.104"

# Copy application code
COPY . .

# Run as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Frontend Dockerfile:**
```dockerfile
# frontend/Dockerfile

FROM node:20.18-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

# Production image
FROM node:20.18-alpine

WORKDIR /app

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "start"]
```

**docker-compose.yml (Local Development):**
```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: SphereVoice_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/SphereVoice_dev
      REDIS_URL: redis://redis:6379
      AZURE_STORAGE_CONNECTION_STRING: ${AZURE_STORAGE_CONNECTION_STRING}
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app
      
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/node_modules
      
  celery-worker:
    build: ./backend
    command: celery -A app.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/SphereVoice_dev
      REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis
      
volumes:
  postgres_data:
  redis_data:
```

---

## 11. Build Sequence & Milestones

### 11.1 Phase 1: Foundation (Weeks 1-4)

**Week 1: Infrastructure Setup**
- [ ] Setup Azure subscription and credits
- [ ] Terraform modules for database, Redis, storage
- [ ] Deploy dev environment
- [ ] Setup GitHub repository and CI/CD
- [ ] Configure Sentry for error tracking

**Week 2: Database & Auth**
- [ ] Database schema implementation (all tables)
- [ ] pgvector extension setup
- [ ] Migrations with Alembic
- [ ] Auth.js v5 (`next-auth@5`) integration
- [ ] User management API endpoints

**Week 3: Provider Abstraction**
- [ ] STT provider interfaces and implementations
- [ ] LLM provider interfaces and implementations
- [ ] TTS provider interfaces and implementations
- [ ] Provider factory pattern
- [ ] Provider key encryption/decryption

**Week 4: Basic API**
- [ ] Provider management endpoints (CRUD)
- [ ] Agent management endpoints (CRUD)
- [ ] Phone number search/purchase endpoints
- [ ] Basic authentication and authorization

**Deliverable:** Working API with provider management and auth

---

### 11.2 Phase 2: Voice Pipeline (Weeks 5-8)

**Week 5: LiveKit + Pipecat Package Setup**
- [ ] Pin the upstream `pipecat-ai` package version in `backend/requirements.txt`
- [ ] Document SphereVoice-owned extension points in `backend/app/modules/pipeline/`
- [ ] Deploy LiveKit server on Azure VM
- [ ] SIP gateway configuration
- [ ] Install from pinned package: `pip install -r requirements.txt`
- [ ] Pipecat LiveKitTransport integration test
- [ ] Audio streaming tests (LiveKit ↔ Pipecat)
- [ ] Set up CI job: dependency upgrade smoke tests for Pipecat version bumps

**Week 6: STT Integration (Pipecat Services)**
- [ ] DeepgramSTTService configuration (Flux + Nova-3 models)
- [ ] PipecatProviderFactory — STT factory method
- [ ] SileroVADAnalyzer setup and tuning
- [ ] ServiceSwitcher for STT fallback (Deepgram → AssemblyAI)
- [ ] Transcription streaming validation

**Week 7: LLM Integration (Pipecat Services)**
- [ ] OpenAILLMService + GroqLLMService configuration
- [ ] AnthropicLLMService configuration
- [ ] PipecatProviderFactory — LLM factory method
- [ ] LLMContextAggregatorPair for turn management
- [ ] Function calling via Pipecat FunctionSchema + register_function()

**Week 8: TTS Integration + Full Pipeline**
- [ ] CartesiaTTSService + ElevenLabsTTSService configuration
- [ ] PipecatProviderFactory — TTS factory method
- [ ] Full Pipecat Pipeline assembly (transport → STT → LLM → TTS)
- [ ] PipelineRunner + PipelineTask with metrics
- [ ] End-to-end call test (inbound call → Pipecat pipeline → response)
- [ ] Latency measurement and tuning (<300ms P50 target)

**Deliverable:** End-to-end Pipecat voice pipeline (STT → LLM → TTS) via LiveKit

---

### 11.3 Phase 3: Agent Builder (Weeks 9-12)

**Week 9: Single Prompt Agent**
- [ ] Prompt editor UI (Monaco/CodeMirror)
- [ ] Dynamic variables system
- [ ] Welcome message configuration
- [ ] Function calling setup
- [ ] Agent testing interface

**Week 10-11: Conversation Flow Builder**
- [ ] React Flow canvas setup
- [ ] Node types implementation (Conversation, Function, Logic Split, Transfer, Ending)
- [ ] Node editor panels
- [ ] Edge connections and validation
- [ ] Flow execution engine

**Week 12: Agent Settings & Publishing**
- [ ] Global settings UI (Voice, LLM, Speech, Call settings)
- [ ] Post-call extraction configuration
- [ ] Webhook configuration
- [ ] Agent versioning system
- [ ] Publish/rollback functionality

**Deliverable:** Fully functional agent builder (both types)

---

### 11.4 Phase 4: Call Management (Weeks 13-16)

**Week 13: Inbound Calls**
- [ ] Twilio webhook integration
- [ ] Call routing (phone number → agent)
- [ ] Call record creation
- [ ] LiveKit room initialization
- [ ] Call status tracking

**Week 14: Call History**
- [ ] Call history API endpoints
- [ ] Advanced filtering system
- [ ] Transcript storage and retrieval
- [ ] Recording storage (Azure Blob)
- [ ] Call detail view UI

**Week 15: Live Monitoring**
- [ ] WebSocket server for real-time events
- [ ] Active calls dashboard
- [ ] Live transcription streaming
- [ ] Call metrics (latency, turn count)
- [ ] Manual call termination

**Week 16: Post-Call Processing**
- [ ] Celery worker for background jobs
- [ ] Post-call data extraction (LLM-based)
- [ ] Recording transcoding
- [ ] Webhook delivery system
- [ ] Data retention cleanup

**Deliverable:** Complete call lifecycle management

---

### 11.5 Phase 5: Knowledge Base & Analytics (Weeks 17-20)

**Week 17: Knowledge Base**
- [ ] File upload (PDF, DOCX, TXT)
- [ ] Text extraction and chunking
- [ ] Embedding generation (OpenAI)
- [ ] pgvector storage
- [ ] Similarity search API

**Week 18: RAG Integration**
- [ ] Knowledge base attachment to agents
- [ ] Retrieval during conversations
- [ ] Context injection into prompts
- [ ] Retrieval settings configuration

**Week 19-20: Analytics Dashboard**
- [ ] Metrics calculation (call count, duration, latency, etc.)
- [ ] Time-series charts (Recharts)
- [ ] Filter panel (date range, org, agent)
- [ ] Export functionality
- [ ] Client read-only dashboard

**Deliverable:** Knowledge base and analytics

---

### 11.6 Phase 6: Polish & Launch Prep (Weeks 21-24)

**Week 21: Agent Templates**
- [ ] 8 pre-built templates
- [ ] Template gallery UI
- [ ] Template customization flow
- [ ] Save custom templates

**Week 22: User Management**
- [ ] User invitation system
- [ ] Role-based access control (Admin, Developer, Read-Only, Client)
- [ ] Tenant management
- [ ] Audit log viewer

**Week 23: Testing & QA**
- [ ] End-to-end testing (Playwright)
- [ ] Load testing (Locust)
- [ ] Security audit
- [ ] Performance optimization
- [ ] Bug fixes

**Week 24: Documentation & Launch**
- [ ] User documentation
- [ ] API documentation (OpenAPI)
- [ ] Deployment runbook
- [ ] Production environment setup
- [ ] First client onboarding

**Deliverable:** Production-ready SphereVoice

---

## 12. Future Roadmap (V1.1, V2)

### V1.1 Enhancements (Post-Launch, Months 7-9)

**Additional Node Types:**
- [ ] Agent Transfer node (transfer between SphereVoice agents)
- [ ] MCP node (Model Context Protocol integration)

**Batch Calling:**
- [ ] CSV upload for recipient lists
- [ ] Scheduling and time windows
- [ ] Concurrency management
- [ ] Batch call analytics

**Billing & Usage Tracking:**
- [ ] Per-client cost tracking and billing dashboard
- [ ] Invoice generation
- [ ] Usage-based pricing tiers

**Enhanced Analytics:**
- [ ] Sentiment trend charts
- [ ] Funnel analysis (call outcomes)
- [ ] A/B testing framework (compare agents/providers)
- [ ] Cost breakdown by provider

**Web Crawling for Knowledge Base:**
- [ ] URL crawler for website ingestion
- [ ] Auto-sync for updated content

---

### V2 Vision (Months 10-12)

**AI Quality Assurance:**
- [ ] Automated call quality scoring
- [ ] Hallucination detection
- [ ] Word Error Rate (WER) calculation
- [ ] Sentiment accuracy validation

**Chat Agents:**
- [ ] Text-based chat interface (in addition to voice)
- [ ] Chat history logging
- [ ] Shared agent configuration (voice + chat)

**Advanced Alerting:**
- [ ] Custom alert rules builder
- [ ] PagerDuty/Slack/Webhook integrations
- [ ] Alert history and acknowledgment

**Multi-Region Expansion:**
- [ ] Europe deployment (GDPR compliance)
- [ ] Asia-Pacific deployment
- [ ] Automatic region routing based on caller

**Custom LLM Support:**
- [ ] Bring your own LLM endpoint
- [ ] Self-hosted LLM integration (Ollama, vLLM)

---

## 13. Success Metrics

### 13.1 Technical Metrics

**Performance:**
- ✅ P50 end-to-end latency <300ms, P95 <450ms, P99 <500ms
- ✅ API P95 response time <200ms
- ✅ Database query P95 <50ms
- ✅ 99.9% API uptime

**Scalability:**
- ✅ Support 1000+ concurrent calls
- ✅ Handle 10,000+ calls per day
- ✅ Store 1M+ call records without degradation

**Quality:**
- ✅ <1% error rate for API requests
- ✅ <2% call drop rate
- ✅ 95%+ transcription accuracy (via STT providers)

---

### 13.2 Business Metrics

**Adoption:**
- ✅ 10+ clients onboarded in first 3 months
- ✅ 50+ agents deployed in production
- ✅ 10,000+ calls handled in first quarter

**Cost Efficiency:**
- ✅ Infrastructure ~$250-350/month on Azure (covered by credits); target <$150/month post-migration
- ✅ Average cost per call <$0.60
- ✅ 60%+ gross margin on voice services

**User Satisfaction:**
- ✅ <30 minutes to deploy first agent (employee UX)
- ✅ 90%+ client satisfaction with call quality
- ✅ <5 minutes response time for critical support issues

---

## 14. Risk Mitigation

### 14.1 Technical Risks

**Risk: Provider API Downtime**
- **Mitigation:** Implement fallback providers (if Deepgram fails, switch to AssemblyAI)
- **Mitigation:** Cache common responses (greetings, FAQs)
- **Mitigation:** Circuit breakers to prevent cascading failures

**Risk: Latency Exceeds 500ms**
- **Mitigation:** Regional deployment (US + India)
- **Mitigation:** Use fastest providers (Groq for simple prompts, Deepgram for STT)
- **Mitigation:** Optimize LLM prompts (shorter prompts = faster responses)
- **Mitigation:** Cache embeddings for knowledge base

**Risk: Database Performance Degradation**
- **Mitigation:** Connection pooling (max 20 connections)
- **Mitigation:** Read replicas for analytics queries
- **Mitigation:** Proper indexing on all query columns
- **Mitigation:** Partition large tables (calls table by month)

**Risk: WebRTC/SIP Complexity**
- **Mitigation:** Use LiveKit (battle-tested, managed SFU)
- **Mitigation:** Thorough testing before production
- **Mitigation:** Document troubleshooting steps

---

### 14.2 Business Risks

**Risk: Azure Credits Run Out Earlier Than Expected**
- **Mitigation:** Monitor credit usage weekly
- **Mitigation:** Have Terraform configs ready for Supabase/Railway migration
- **Mitigation:** Test migration plan on staging environment
- **Mitigation:** Azure pay-as-you-go is ~$250-350/month; post-credit migration targets <$150/month

**Risk: Provider Costs Higher Than Expected**
- **Mitigation:** Track cost per call in real-time
- **Mitigation:** Implement provider switching based on cost
- **Mitigation:** Negotiate volume discounts with providers
- **Mitigation:** Offer clients tiered pricing (budget vs premium)

**Risk: Client Data Loss**
- **Mitigation:** Daily database backups (7-day retention)
- **Mitigation:** Geo-redundant storage for recordings
- **Mitigation:** Point-in-time recovery for PostgreSQL
- **Mitigation:** Test restore procedures monthly

---

### 14.3 Security Risks

**Risk: API Key Leakage**
- **Mitigation:** All keys encrypted at rest (AES-256)
- **Mitigation:** Keys never logged or exposed in errors
- **Mitigation:** Rotate keys every 90 days
- **Mitigation:** Use Azure Key Vault for master encryption key

**Risk: Unauthorized Access to Client Data**
- **Mitigation:** Row-level security in PostgreSQL
- **Mitigation:** JWT token expiry (1 hour)
- **Mitigation:** IP whitelisting for admin accounts
- **Mitigation:** Audit logs for all data access

**Risk: DDoS Attack**
- **Mitigation:** Azure Front Door with WAF (Web Application Firewall)
- **Mitigation:** Rate limiting on all API endpoints
- **Mitigation:** Auto-scaling to handle traffic spikes

---

## 15. Appendix

### 15.1 Glossary

- **STT:** Speech-to-Text (transcription)
- **LLM:** Large Language Model (AI brain)
- **TTS:** Text-to-Speech (voice synthesis)
- **SIP:** Session Initiation Protocol (telephony signaling)
- **WebRTC:** Web Real-Time Communication (audio/video streaming)
- **VAD:** Voice Activity Detection (detect when user is speaking)
- **RAG:** Retrieval-Augmented Generation (knowledge base retrieval)
- **pgvector:** PostgreSQL extension for vector embeddings
- **DTMF:** Dual-Tone Multi-Frequency (keypad tones)
- **IVR:** Interactive Voice Response (automated phone menus)
- **Pipecat:** Open-source Python framework from `pipecat-ai/pipecat` (Apache-2.0) for building real-time voice AI agents; provides pipeline architecture, built-in provider services, VAD, turn management, and transport layers. SphereVoice uses the pinned upstream package and keeps custom behavior in repo code.

---

### 15.2 References

- [Retell AI Platform — Full Feature Audit](./retell-audit.md)
- [SphereVoice Product PRD](./prd.md)
- [SphereVoice Context Document](./claude.md)
- [Pipecat Documentation](https://docs.pipecat.ai/)
- [Pipecat Upstream Repository (pipecat-ai)](https://github.com/pipecat-ai/pipecat)
- [Pipecat LiveKitTransport](https://docs.pipecat.ai/api-reference/services/transport/livekit)
- [Pipecat TwilioFrameSerializer](https://docs.pipecat.ai/api-reference/utilities/audio/twilio-frame-serializer)
- [Pipecat ServiceSwitcher](https://docs.pipecat.ai/api-reference/processors/service-switcher)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LiveKit Server Documentation](https://docs.livekit.io/home/server/intro/)
- [LiveKit SIP Gateway](https://docs.livekit.io/home/server/sip/)
- [Deepgram Flux Model — Low-Latency Voice Agent STT](https://developers.deepgram.com/docs/model)
- [Deepgram v2 Listen API — EagerEndOfTurn & EndOfTurn](https://developers.deepgram.com/docs/flux/nova-3-migration)
- [Deepgram Nova-3 Streaming STT](https://developers.deepgram.com/docs/getting-started)
- [Cartesia Sonic-3 TTS](https://docs.cartesia.ai/)
- [ElevenLabs Streaming TTS API](https://elevenlabs.io/docs/api-reference)
- [LMNT Real-Time TTS](https://docs.lmnt.com/)
- [React Flow Documentation](https://reactflow.dev/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Azure Terraform Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-28 | Technical Team | Initial PRD |
| 1.1 | 2026-03-03 | Technical Team | Aligned with prd.md — clarified auth strategy, deferred billing to V1.1, updated cost estimates, annotated outbound call scope, added doc navigation |
| 1.2 | 2026-03-03 | Technical Team | Latency optimization — Deepgram Flux/EagerEndOfTurn, Cartesia Sonic-2, LiveKit AgentSession v1.x with VAD/turn-detection/noise-cancellation, FallbackAdapter, sub-300ms P50 target |
| 1.3 | 2026-03-04 | Technical Team | Adopted Pipecat (`pipecat-ai`) as voice pipeline framework — replaced custom VoicePipeline/ProviderFactory with Pipecat Pipeline, PipecatProviderFactory, LiveKitTransport, SileroVADAnalyzer, ServiceSwitcher; added TwilioFrameSerializer as alternative transport; LiveKit retained for WebRTC/SIP media layer |
| 1.4 | 2026-03-04 | Technical Team | Fork strategy — Pipecat installed from `Sphere/pipecat` fork (`SphereVoice-main` branch) instead of PyPI; enables deep customisation of frame processors, transport internals, and latency paths; upstream tracked via `upstream/main` with regular merges; Phase 2 build plan updated with fork setup tasks and CI merge-check |
| 1.5 | 2026-03-04 | Technical Team | Renamed `organization_id` → `tenant_id` across all schemas, APIs, code, and prose; `organizations` table → `tenants`; pinned all packages, Docker images, and CI actions to specific stable versions to prevent breaking changes |

---

**End of Document**