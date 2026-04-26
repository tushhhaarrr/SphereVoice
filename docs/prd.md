# SphereVoice - Product Requirements Document

**Product:** SphereVoice - Internal Voice AI Agent Platform  
**Company:** Sphere AI  
**Version:** 1.0  
**Target Launch:** 6 months from project start  
**Last Updated:** March 4, 2026

---

## How to Read the SphereVoice Documents

| Document | Purpose | Audience |
|----------|---------|----------|
| **prd.md** (this file) | WHAT we're building and WHY — features, user experience, business value | Everyone (product, engineering, leadership) |
| **tech-prd.md** | HOW we're building it — architecture, schemas, APIs, code, infrastructure | Engineering team |
| **retell-audit.md** | Competitive reference — Retell AI feature audit with SphereVoice gap analysis | Product & Engineering |

Both documents are kept in sync. The PRD drives feature scope; the Tech PRD drives implementation. If they ever conflict, raise it immediately.

---

## 1. Product Overview

### What is SphereVoice?

SphereVoice is Sphere AI's internal platform for building and managing voice AI calling agents for clients. Employees use SphereVoice to create, configure, and monitor voice agents that handle phone calls for client businesses.

**Think of it as:** "Our own Retell AI" — complete control over the voice AI pipeline without vendor lock-in. See [retell-audit.md](./retell-audit.md) for a full feature-by-feature comparison.

### Why SphereVoice?

**Business Goals:**
- Compete with Retell AI and VAPI by owning the entire stack
- Maintain provider flexibility (switch AI services without rebuilding)
- Scale to 1000+ concurrent calls with predictable costs
- Deliver sub-300ms P50 response time for natural conversations (hard ceiling: 500ms P99)

**Key Differentiators:**
- No hardcoded providers - employees choose STT/LLM/TTS per agent
- Pipecat as the voice pipeline engine via the pinned upstream package, with SphereVoice-specific processors and orchestration implemented in the SphereVoice codebase
- Multi-tenant from day one - complete client isolation
- Portable infrastructure - easy migration when Azure credits expire
- Enterprise-grade reliability - production patterns from the start

---

## 2. Users & Access

### Primary Users: Sphere Employees

**Who they are:**
- Voice AI engineers who create agents for clients
- Account managers who monitor client performance
- Support staff who troubleshoot issues

**What they can do:**
- Full access to create, edit, and manage all agents
- Add and test provider API keys (Deepgram, OpenAI, ElevenLabs, Twilio)
- Monitor all live calls across all clients
- View analytics and call history for all tenants

**Roles:**
- **Admin:** Full access including user management (billing is post-V1)
- **Developer:** Create/edit agents, manage providers, view all data
- **Read-Only:** View-only access to all data

### Secondary Users: Clients (Read-Only)

**Who they are:**
- Business owners who purchased voice AI services from Sphere

**What they can see:**
- Their own call history and transcripts
- Their agent performance metrics (call volume, duration, success rate)
- Call recordings and analytics for their tenant

**What they CANNOT see:**
- Which providers are being used (STT/LLM/TTS details)
- Cost breakdowns or billing information
- Agent configuration or prompts
- Other clients' data

---

## 3. Core Features (V1)

### 3.1 Provider Management

Employees manage API keys for all voice services in one place.

**Providers to Support:**
- **Speech-to-Text (STT):** Deepgram (Flux model ★, Nova-3), AssemblyAI, Azure Speech, OpenAI Whisper
- **Language Models (LLM):** Groq (llama-3 ★ — fastest TTFT), OpenAI (GPT-4o, GPT-4o-mini), Anthropic (Claude), Azure OpenAI
- **Text-to-Speech (TTS):** Cartesia (Sonic-3 ★ — lowest TTFB), ElevenLabs (Turbo v2.5), OpenAI TTS, LMNT, PlayHT, Azure Speech
- **Telephony:** Twilio, Plivo, Vonage, Telnyx

> ★ = Recommended for lowest latency stack

**Key Features:**
- Add new provider API keys with encrypted storage
- Test connection before saving (verify credentials work)
- Set default provider keys (Sphere account) OR override per client
- View usage stats per provider (calls made, costs, error rates)
- Enable/disable providers without deleting keys

**Why this matters:** Flexibility to switch providers per client based on cost, quality, or language needs without changing any code.

---

### 3.2 Agent Builder - Conversation Flow

Visual node-based editor for creating deterministic conversation flows (like Retell's flagship feature).

**Node Types (V1):**
1. **Conversation Node:** AI speaks and listens to user
2. **Function Node:** Call external API or webhook
3. **Logic Split Node:** Branch conversation based on conditions
4. **Call Transfer Node:** Transfer to human agent or phone number
5. **Press Digit Node:** Send DTMF tones (for IVR navigation)
6. **Extract Variable Node:** Pull structured data from conversation
7. **SMS Node:** Send text message during call
8. **Ending Node:** Terminate the conversation

**How It Works:**
- Drag nodes onto a canvas
- Connect nodes with lines to define flow
- Configure each node (prompts, API endpoints, conditions)
- Save as draft or publish to production
- Version control - rollback to previous versions if needed

**Execution Modes:**
- **Flex Mode:** AI moves between nodes naturally based on context
- **Rigid Mode:** AI follows nodes step-by-step sequentially

**Example Use Case:** Dental appointment booking
1. Conversation: "Hi, how can I help you?"
2. Logic Split: If user says "appointment" → go to booking flow
3. Function: Check available slots via API
4. Conversation: "We have 2pm or 4pm available"
5. Function: Book appointment via API
6. SMS: Send confirmation text to user
7. Ending: "All set! Have a great day"

---

### 3.3 Agent Builder - Single Prompt

Simpler alternative to flow builder for straightforward use cases.

**What It Is:**
- One large system prompt that defines agent behavior
- No visual nodes - just text-based configuration
- AI uses the prompt to guide the entire conversation

**Key Features:**
- Rich text editor with variable support (`{{customer_name}}`)
- Define callable functions (transfer_call, end_call, custom APIs)
- Configure welcome message (AI speaks first or waits for user)
- Dynamic variables with default values

**When to Use:**
- Simple use cases (FAQs, basic routing)
- Quick prototypes before building full flows
- Agents that don't need complex branching logic

---

### 3.4 Agent Configuration (Global Settings)

Settings that apply to both agent types (flow and prompt).

**Voice & Language:**
- Select language (English, Spanish, Hindi, etc.)
- Choose TTS provider and specific voice (filter by gender, accent)
- Adjust voice speed (0.5x - 2.0x) with dynamic adjustment option
- Set voice volume

**LLM Settings:**
- Select model (GPT-4o, GPT-4o-mini, Claude, Groq, etc.)
- Set temperature (creativity level)
- Enable structured output (enforce JSON responses)

**Knowledge Base Integration:**
- Attach one or more knowledge bases to agent
- Configure retrieval settings (how many chunks, similarity threshold)

**Speech Settings:**
- Add background sound (office ambiance, café, etc.)
- Set responsiveness (how fast agent interrupts)
- Add pronunciation guide (custom phonetics for brand names)

**Transcription Settings:**
- Denoising mode (remove background noise)
- Optimize for speed vs accuracy
- Vocabulary specialization (medical, legal, general)
- Boost specific keywords for better recognition

**Call Behavior:**
- Voicemail detection (hang up or leave message)
- IVR detection (hang up if automated system detected)
- End call after silence (timeout in seconds)
- Maximum call duration (1-60 minutes)

**Post-Call Data Extraction:**
- Automatically extract structured data after each call
- Pre-built fields: call summary, success boolean, user sentiment
- Custom fields: unlimited (e.g., "appointment_booked", "reason_for_call")
- Data becomes filterable in call history

**Webhooks:**
- Set webhook URL to receive real-time call events
- Choose which events to send (call_started, call_ended, transcription_updated, etc.)
- Configure timeout and retry logic

---

### 3.5 Knowledge Base

Centralized document storage that agents can reference during calls.

**Document Ingestion (V1):**
- **File Upload:** PDF, DOCX, TXT (up to 100MB per file)
- **Text Input:** Direct paste/type (up to 50,000 characters)

**How It Works:**
- Documents are chunked into smaller pieces
- Each chunk gets converted to vector embeddings
- During calls, agent searches for relevant chunks based on user question
- Top matching chunks are injected into AI context

**Management:**
- Create multiple knowledge bases per tenant
- Attach one or more KBs to any agent
- Configure retrieval (how many results, similarity threshold)
- Version control (track changes, revert if needed)

**Sharing:**
- Private (specific agents only)
- Tenant-wide (all agents in one client tenant)
- Global (all agents across all clients)

**Example:** Dental clinic agent has KB with:
- Office policies (hours, payment methods, insurance)
- Procedure descriptions (cleanings, fillings, root canals)
- Common FAQs (parking, what to bring, cancellation policy)

---

### 3.6 Phone Number Management

Buy and assign phone numbers to agents.

**Features:**
- Search available numbers by country, area code, or pattern
- Purchase numbers directly through platform (via Twilio/Plivo)
- Assign number to specific agent (one-to-one)
- Configure routing (fallback number if agent unavailable)
- View number details (cost, capabilities, call volume)

**How Calls Work:**
1. Customer calls the phone number
2. Twilio/Plivo receives the call
3. Sends webhook to SphereVoice with call details
4. SphereVoice looks up which agent is assigned to that number
5. SphereVoice creates a LiveKit room and connects Twilio/Plivo via SIP
6. Pipecat’s LiveKitTransport joins the room and receives audio frames
7. Audio flows through the Pipecat pipeline (STT → LLM → TTS)
8. Conversation begins

**Outbound Calls (V1):**
- Single outbound calls are supported in V1 (trigger via API with dynamic variables)
- Batch/scheduled calling is deferred to V1.1

---

### 3.7 Call History

Comprehensive log of all calls with advanced filtering.

**What's Logged:**
- Call metadata (date, time, duration, from/to numbers)
- Full transcript with speaker labels and timestamps
- Recording audio file (playable in browser)
- Post-call extracted data (all custom fields)
- Cost breakdown (STT + LLM + TTS + telephony)
- Status and disconnection reason
- Performance metrics (latency, turn count)

**Filtering & Search:**
- Filter by tenant, agent, date range, status, sentiment
- Filter by any post-call extraction field (e.g., "show me all successful appointment bookings")
- Filter by call outcome, duration, cost range
- Save filter presets for quick access

**Customizable Columns:**
- Choose which columns to display in table
- Reorder columns via drag-and-drop
- Save column preferences per user

**Actions:**
- Play recording with synchronized transcript
- Export calls to CSV or JSON
- Delete calls (with confirmation)
- Add custom tags/labels

**Access Control:**
- Employees see all calls across all clients
- Clients see only their own tenant's calls (read-only)

---

### 3.8 Live Call Monitoring

Real-time dashboard showing active calls.

**What Employees See:**
- List of all currently active calls
- Call details (caller, agent, duration counter)
- Live transcription (updates as conversation happens)
- Real-time metrics (current latency, turn count)
- Call status (ringing, in-progress, on-hold)

**Actions:**
- View live transcript for any active call
- End call manually if needed
- Copy call ID for reference
- Click to open full call details

**Technology:**
- WebSocket connection for instant updates
- Auto-reconnect if connection drops
- No refresh needed - updates appear live

**Use Cases:**
- Quality assurance (listen to ensure agent is working correctly)
- Intervention (end a call if something goes wrong)
- Support (help troubleshoot client issues in real-time)

---

### 3.9 Analytics Dashboard

High-level metrics for monitoring platform performance.

**Metric Cards:**
- Total calls (today, this week, this month)
- Average call duration
- Average end-to-end latency
- Concurrency used (current and peak)
- Call transfer rate (% of calls sent to human)
- Voicemail rate (% ending in voicemail)
- Success rate (based on post-call extraction)

**Time-Series Charts:**
- Calls over time (by day, week, or month)
- Latency trends (P50, P95, P99)
- Sentiment distribution (positive/neutral/negative pie chart)
- Call duration distribution (histogram)

**Filtering:**
- Date range picker (last 7 days, 30 days, custom range)
- Filter by tenant (single or multiple)
- Filter by agent (single or multiple)
- Filter by call status (completed, failed, etc.)

**Export:**
- Download charts as images (PNG/SVG)
- Export raw data as CSV

**Access Control:**
- Employees see aggregated data across all clients
- Clients see only their tenant's analytics

---

### 3.10 Agent Templates

Pre-built agent configurations for common use cases.

**8 Built-in Templates (V1):**
1. Patient Screening (Healthcare)
2. Real Estate Lead Qualification
3. Medical Center Receptionist
4. Real Estate Appointment Setter
5. Delivery Customer Support
6. Dental Outbound Sales
7. Retail Receptionist
8. Education Program Appointment Setter

**What's Included in a Template:**
- Pre-configured conversation flow or prompt
- Sample functions (transfer, booking, etc.)
- Recommended voice and LLM settings
- Sample post-call extraction fields
- Knowledge base suggestions

**Using Templates:**
- Browse template gallery
- Preview template (see flow diagram or prompt)
- Click "Use Template" to create new agent from it
- Customize as needed for specific client

**Creating Custom Templates:**
- Save any agent as a template
- Define scope (private, tenant-wide, global)
- Add description and tags for discoverability

---

### 3.11 User Management

Manage employees and client users with role-based access.

**User Roles:**
- **Admin (Employee):** Full access including user management (billing deferred to V1.1)
- **Developer (Employee):** Create/edit agents, manage providers, view all data
- **Read-Only (Employee):** View-only access to all data
- **Client User:** Access only to their tenant's data (read-only)

**Features:**
- Invite users via email (magic link or password setup)
- Assign role during invitation
- Assign client users to specific tenant
- Edit user role or deactivate users
- View audit log (who did what, when)

**Audit Logging:**
- Track all create/update/delete actions
- Store: user, action type, resource, timestamp
- Viewable by admins
- Retained for 90 days minimum

---

## 4. Voice Pipeline (How Calls Actually Work)

This is the technical "magic" that makes real-time conversations possible. Understanding this helps explain why SphereVoice is powerful.

### The Streaming Pipeline

SphereVoice uses **Pipecat** via the pinned upstream `pipecat-ai` package. SphereVoice-specific behavior stays in the SphereVoice codebase through custom processors, orchestration, provider selection, and transport configuration. Pipecat provides the frame-based pipeline architecture, built-in service classes for major STT/LLM/TTS providers, voice activity detection (SileroVAD), automatic turn management, and transport layers for LiveKit and telephony.

When a call happens, audio flows through the Pipecat pipeline in real-time:

**Step 1: Audio In + Speech-to-Text (STT)**
- Customer speaks into phone
- Twilio/Plivo forwards audio to LiveKit via SIP
- Pipecat’s LiveKitTransport receives audio frames from the LiveKit room
- SileroVADAnalyzer (built into Pipecat) detects voice activity (<10ms latency)
- Audio streams to Pipecat’s DeepgramSTTService (Flux model for lowest latency)
- Text chunks arrive as customer is still speaking

**Step 2: Language Model (LLM)**
- Transcribed text sent to LLM (Groq for speed, GPT-4o for complexity)
- LLM generates response based on:
  - Agent's system prompt or current conversation node
  - Full conversation history
  - Retrieved knowledge base chunks (if applicable)
- Response streams back token-by-token (word-by-word)

**Step 3: Text-to-Speech (TTS)**
- LLM response sent to Pipecat's TTS service (CartesiaTTSService with Sonic-3 for lowest TTFB, ElevenLabsTTSService for highest quality)
- Provider converts text to natural-sounding speech
- Audio streams back in chunks — Pipecat starts TTS on first sentence boundary, not end of full response

**Step 4: Back to Customer (via LiveKit)**
- Pipecat’s LiveKitTransport sends audio frames back through the LiveKit room
- LiveKit streams audio through the SIP gateway to Twilio/Plivo
- Audio plays through phone to customer
- Customer hears AI response within ~150-300ms of finishing their sentence

> **Note:** Pipecat is installed from the pinned upstream package rather than a SphereVoice-maintained fork. As of Pipecat v0.0.99+, context management uses the universal `LLMContext` and `LLMContextAggregatorPair` API (replacing the deprecated `OpenAILLMContext`). Pipecat orchestrates the full STT→LLM→TTS pipeline with built-in voice activity detection (SileroVAD), turn management, provider switching (ServiceSwitcher), and OpenTelemetry metrics. LiveKit handles the WebRTC/SIP media layer (bridging Twilio/Plivo audio to Pipecat via LiveKitTransport). Twilio/Plivo only handle telephony (receiving/placing calls). See tech-prd.md §4.3.1 for package strategy details.

### Why Sub-300ms Matters

**Target: End-to-end latency under 300ms P50, hard ceiling 500ms P99**

In human conversation, pauses longer than 300ms start to feel sluggish. At 500ms+ the AI sounds robotic and awkward. Our target is to be indistinguishable from human response times.

**Latency Formula:** `totalLatency = eou_delay + llm_ttft + tts_ttfb`

**Fast Stack (Deepgram Flux + Groq + Cartesia):**
- EOU Detection: 30-60ms (Deepgram Flux EagerEndOfTurn)
- LLM (TTFT): 40-80ms (Groq llama-3)
- TTS (TTFB): 50-80ms (Cartesia Sonic-3)
- Network: 20-40ms (regional deployment)
- **Total P50: ~140-260ms** ✅

**Standard Stack (Deepgram Nova-3 + GPT-4o + ElevenLabs):**
- EOU Detection: 80-120ms (Nova-3 endpointing)
- LLM (TTFT): 150-250ms (GPT-4o streaming)
- TTS (TTFB): 80-130ms (ElevenLabs Turbo v2.5)
- Network: 30-50ms (regional deployment)
- **Total P50: ~340-550ms** ⚠️ (use for complex reasoning only)

**How We Achieve This:**
- Use Pipecat via the pinned upstream package as the pipeline framework — handles all real-time audio streaming, buffering, sentence splitting, and turn management
- Pipecat’s SileroVADAnalyzer for accurate voice activity detection (<10ms)
- Pipecat’s LLMContextAggregatorPair for automatic turn management
- Use Deepgram Flux model via Pipecat’s DeepgramSTTService for lowest-latency STT
- Stream everything — Pipecat processes frames through STT→LLM→TTS fully streaming
- Use fastest providers by default (Groq for speed, GPT-4o only when reasoning requires it)
- ServiceSwitcher (Pipecat built-in) for provider hot-swap and failover
- Cache deterministic TTS responses (greetings, FAQs) — eliminates TTS latency entirely
- Deploy regionally (US-East + Mumbai) — route callers to nearest region
- Pipecat’s OpenTelemetry integration for TTFB spans per service

---

## 5. Platform Architecture Principles

### Provider Abstraction

**The Problem:** If we hardcode Deepgram for STT, we're locked in. If Deepgram raises prices or has downtime, we're stuck.

**The Solution:** Pipecat provides built-in service classes for all major STT/LLM/TTS providers. SphereVoice adds a `PipecatProviderFactory` that reads agent config from the database and instantiates the correct Pipecat service.

For example, switching from Deepgram STT to AssemblyAI means changing one config value in the dashboard — the factory creates the right Pipecat service class automatically, with zero code changes.

**Why It Matters:**
- Test multiple providers to find best quality/cost
- Switch providers per client based on requirements
- Use fallback providers if primary fails (Pipecat’s ServiceSwitcher)
- Negotiate better pricing (we're not locked in)

### Multi-Tenancy

**The Problem:** Client A's data must NEVER be visible to Client B.

**The Solution:** Every database table has a `tenant_id` column. Every query automatically filters by tenant. Row-level security enforces this at the database level.

**Why It Matters:**
- One client's issue never affects another
- Clients trust their data is isolated
- Easy to add new clients (just create tenant)
- Can offer client-specific pricing/features

### Portability

**The Problem:** Azure gives us free credits now, but credits will run out. We could get locked into expensive Azure services.

**The Solution:** Use standard protocols everywhere (PostgreSQL, Redis, S3 API, Docker). Wrap all cloud-specific code behind interfaces.

**Why It Matters:**
- When Azure credits expire, migrate to cheaper alternatives in ~2 weeks
- Not dependent on any single cloud provider
- Can negotiate better pricing (we're not locked in)
- Business continuity if a provider shuts down

---

## 6. Build Plan (How to Execute)

### Timeline: 24 Weeks (6 Months)

#### Phase 1: Foundation (Weeks 1-4)

**Goal:** Infrastructure and core APIs working

**What to Build:**
- Setup Azure (database, Redis, storage) using Terraform
- Create database schema (all tables)
- Build authentication system (login, roles)
- Provider management API (add/test/list provider keys)
- Basic agent CRUD API (create/read/update/delete agents)

**Deliverable:** API server running with auth and provider management

---

#### Phase 2: Voice Pipeline (Weeks 5-8)

**Goal:** End-to-end voice calls working

**What to Build:**
- Setup LiveKit server for real-time audio (SIP gateway, WebRTC rooms)
- Install Pipecat from fork (`Sphere/pipecat@SphereVoice-main`) with provider extras (Deepgram, OpenAI, Cartesia, Silero)
- Build PipecatProviderFactory (maps DB agent config → Pipecat service instances)
- Assemble Pipecat Pipeline: LiveKitTransport → STT → LLM → TTS
- Configure SileroVADAnalyzer + LLMContextAggregatorPair for turn management
- Test full call flow (inbound call → Pipecat pipeline → call end)

**Deliverable:** Can make a real phone call and have a conversation with an AI agent via Pipecat

---

#### Phase 3: Agent Builder (Weeks 9-12)

**Goal:** Employees can create agents via UI

**What to Build:**
- Single Prompt agent editor (text editor, functions, settings)
- Conversation Flow canvas (React Flow integration)
- All 8 node types (Conversation, Function, Logic Split, Transfer, SMS, Extract, Digit, Ending)
- Node configuration panels (edit each node's settings)
- Agent versioning (save drafts, publish, rollback)
- Agent testing interface (test calls before publishing)

**Deliverable:** Full-featured agent builder (both types)

---

#### Phase 4: Call Management (Weeks 13-16)

**Goal:** Track and monitor all calls

**What to Build:**
- Phone number management (search, buy, assign to agents)
- Inbound call routing (phone number → agent lookup)
- Call history API (list, filter, detail view)
- Call history UI (table with filters, player, transcript)
- Live monitoring (WebSocket server, active calls dashboard)
- Recording storage (upload to Azure Blob, retrieve for playback)
- Post-call processing (extract structured data, send webhooks)

**Deliverable:** Complete call lifecycle management

---

#### Phase 5: Knowledge Base & Analytics (Weeks 17-20)

**Goal:** Knowledge base and reporting

**What to Build:**
- Knowledge base management (create, upload files, add text)
- Document processing (chunk text, generate embeddings)
- Vector search (pgvector integration)
- RAG integration (retrieve relevant chunks during calls)
- Analytics dashboard (metric cards, time-series charts)
- Filtering and date range selection
- Client read-only dashboard (same views, restricted data)

**Deliverable:** Knowledge base working + analytics dashboard

---

#### Phase 6: Polish & Launch (Weeks 21-24)

**Goal:** Production-ready platform

**What to Build:**
- 8 agent templates (pre-built configurations)
- User management (invite, roles, audit log)
- Comprehensive testing (end-to-end, load testing)
- Security audit (penetration testing, vulnerability scan)
- Performance optimization (database indexing, caching)
- Documentation (user guide, API docs)
- Production deployment (setup prod environment)
- Client onboarding (first 3 clients)

**Deliverable:** Production-ready SphereVoice, first clients using it

---

## 7. Success Metrics

### Technical Metrics

**Performance:**
- End-to-end latency P50 < 300ms, P95 < 450ms, P99 < 500ms
- API response time P95 < 200ms
- 99.9% uptime

**Scale:**
- Support 1000+ concurrent calls
- Handle 10,000+ calls per day
- Store 1M+ call records without slowdown

**Quality:**
- < 1% API error rate
- < 2% call drop rate
- 95%+ transcription accuracy (via provider)

### Business Metrics

**Adoption:**
- 10+ clients onboarded in first 3 months
- 50+ agents deployed in production
- 10,000+ calls handled in first quarter

**Cost Efficiency:**
- Infrastructure ~$250-350/month on Azure pay-as-you-go; target <$150/month after migrating to Supabase/Railway post-credits
- Average cost per call < $0.60
- 60%+ gross margin on voice services

**User Satisfaction:**
- < 30 minutes to deploy first agent (employee experience)
- 90%+ client satisfaction with call quality
- < 5 minute response time for critical issues

---

## 8. What's NOT in V1 (Future Roadmap)

### V1.1 (Months 7-9, Post-Launch)

**Additional Node Types:**
- Agent Transfer node (transfer between SphereVoice agents)
- MCP node (Model Context Protocol integration)

**Batch Calling:**
- Upload CSV of recipients
- Schedule calls for future time
- Set business hours restrictions
- Concurrency management for batches

**Billing & Usage Tracking:**
- Per-client cost tracking and billing dashboard
- Invoice generation
- Usage-based pricing tiers

**Enhanced Analytics:**
- Sentiment trend charts
- Funnel analysis (conversion rates)
- A/B testing framework
- Cost breakdown by provider

**Web Crawling for Knowledge Base:**
- Auto-sync website content
- Scheduled re-crawling for updates

### V2 (Months 10-12)

**AI Quality Assurance:**
- Automated call quality scoring
- Hallucination detection
- Word Error Rate calculation
- Sentiment accuracy validation

**Chat Agents:**
- Text-based chat (in addition to voice)
- Shared agent config (one agent, voice + chat)
- Chat history logging

**Advanced Alerting:**
- Custom alert rules builder
- PagerDuty/Slack integrations
- Alert history and acknowledgment

---

## 9. Key Decisions & Trade-offs

### Why Visual Flow Builder + Single Prompt?

**Decision:** Support both agent types

**Reasoning:**
- Flow builder is powerful but takes longer to configure
- Single prompt is fast but less deterministic
- Clients need both: flows for complex (appointment booking), prompts for simple (FAQ)
- Matches Retell's approach (industry standard)

### Why NOT Default Providers?

**Decision:** Employees must add provider API keys, no defaults

**Reasoning:**
- Avoids vendor lock-in (not dependent on any provider)
- Flexibility per client (Client A uses Deepgram, Client B uses AssemblyAI)
- Cost control (negotiate volume discounts, switch if prices rise)
- Quality optimization (test providers, pick best for each use case)

**Trade-off:** Slightly more setup work (must add keys), but worth the flexibility

### Why Azure First?

**Decision:** Start with Azure, design for easy migration

**Reasoning:**
- We have $5,000-10,000 in free Azure credits (huge savings)
- Credits cover 100% of infrastructure for 6-12 months
- Use standard protocols (PostgreSQL, Redis, S3 API) so migration is easy
- When credits expire, migrate to Supabase/Railway (~$150/month vs $830/month Azure)

**Trade-off:** Some initial Azure setup work, but saves $10,000+ in first year

### Why 24 Weeks (6 Months)?

**Decision:** 6 months to V1 with 5-person team

**Reasoning:**
- This is a complex platform (8 major features, voice pipeline, multi-tenancy)
- Cutting corners = technical debt = slower long-term
- 6 months allows proper testing and polish
- Could accelerate to 4 months with 8-person team, but quality might suffer

**Trade-off:** Longer time-to-market, but launch with quality product that scales

---

## 10. Risk Mitigation

### Technical Risks

**Risk:** Latency exceeds 500ms → Feels unnatural
- **Mitigation:** Use fastest providers (Groq, Deepgram), streaming everywhere, regional deployment

**Risk:** Provider API downtime → Calls fail
- **Mitigation:** Implement fallback providers, circuit breakers, cached responses

**Risk:** Database performance degrades at scale
- **Mitigation:** Proper indexing, read replicas, connection pooling, partition large tables

### Business Risks

**Risk:** Azure credits run out earlier than expected
- **Mitigation:** Monitor usage weekly, have migration plan tested
- **Mitigation:** Azure pay-as-you-go is ~$250-350/month; post-credit migration to Supabase/Railway targets <$150/month

**Risk:** Provider costs higher than expected
- **Mitigation:** Track cost per call, switch to cheaper providers, negotiate volume discounts

**Risk:** Client data loss
- **Mitigation:** Daily backups (7-day retention), geo-redundant storage, test restore procedures monthly

---

## Appendix: Key Terms

**STT:** Speech-to-Text (transcribes audio to text)  
**LLM:** Large Language Model (AI brain that generates responses)  
**TTS:** Text-to-Speech (converts text to natural voice)  
**WebRTC:** Real-time audio/video streaming technology  
**RAG:** Retrieval-Augmented Generation (AI retrieves relevant docs before responding)  
**pgvector:** PostgreSQL extension for vector embeddings (powers knowledge base search)  
**Multi-tenant:** One platform, many clients, complete data isolation  
**Provider Abstraction:** Swappable providers (swap Deepgram for AssemblyAI with config change)  
**LiveKit:** Open-source real-time media server handling WebRTC/SIP bridging for voice calls  
**Pipecat:** Open-source Python framework from `pipecat-ai/pipecat` (Apache-2.0) for building real-time voice AI agents; provides pipeline architecture, built-in provider services, VAD, turn management, and transport layers. SphereVoice uses the pinned upstream package and keeps custom behavior in the SphereVoice codebase.  
**SIP:** Session Initiation Protocol (telephony signaling between Twilio and LiveKit)

---

**End of Document**

This PRD defines WHAT we're building and WHY. For technical implementation details (architecture, schemas, APIs, code), see [tech-prd.md](./tech-prd.md). For competitive reference, see [retell-audit.md](./retell-audit.md).