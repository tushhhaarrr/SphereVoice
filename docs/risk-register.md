# SphereVoice — Risk Register

**Last Updated:** 2026-03-04  
**Review Cadence:** Every phase gate (bi-weekly)

---

## Risk Matrix

| Probability ↓ / Impact → | Low | Medium | High | Critical |
|---------------------------|-----|--------|------|----------|
| **High** | | | | |
| **Medium** | | R-3 | R-1, R-4 | |
| **Low** | | R-5 | | R-2 |

---

## Active Risks

### R-1: Pipecat Package Upgrade Regressions

| Field | Value |
|-------|-------|
| **ID** | R-1 |
| **Probability** | Medium |
| **Impact** | High |
| **Owner** | Backend Lead (BL) |
| **Status** | Open — monitoring |

**Description:**  
SphereVoice uses the pinned upstream `pipecat-ai` package directly. A future Pipecat package upgrade could change pipeline, processor, transport, or service interfaces in ways that break SphereVoice's pipeline code.

**Mitigation Plan:**
1. **Exact version pin** — `requirements.txt` pins a specific package version, not a floating range
2. **Staged upgrade testing** — Any Pipecat version change runs pipeline smoke tests before merge
3. **SphereVoice-owned customization** — Keep custom logic in SphereVoice code to reduce dependency drift
4. **Upstream contributions** — Generic improvements can still be PR'd upstream when useful
5. **Test coverage** — Pipeline tests cover all SphereVoice-specific Pipecat usage patterns

**Trigger:** A proposed Pipecat package version bump or an upstream release note that affects transports, processors, or service contracts

**Contingency:** If a breaking change lands upstream, keep the current pinned package version until SphereVoice compatibility work is complete; only use a temporary patch override if production is blocked.

---

### R-2: Latency Exceeds 500ms P99

| Field | Value |
|-------|-------|
| **ID** | R-2 |
| **Probability** | Low |
| **Impact** | Critical |
| **Owner** | Backend Lead (BL) |
| **Status** | Open — monitoring |

**Description:**  
SphereVoice targets sub-300ms P50 and sub-500ms P99 end-to-end latency (first audio byte). If the voice pipeline exceeds these targets, conversation quality degrades noticeably — users perceive >500ms delays as the AI being "slow" or "broken."

**Latency Budget:**
```
EOU Detection:  30-60ms  (Deepgram Flux EagerEndOfTurn)
LLM TTFT:       40-80ms  (Groq llama-3)
TTS TTFB:       50-80ms  (Cartesia Sonic-3)
Network:        20-40ms  (regional deployment)
Total P50:      ~140-260ms ✅
```

**Mitigation Plan:**
1. **Fast stack as default** — Deepgram Flux + Groq + Cartesia Sonic-3 for all new agents
2. **Latency metrics in OpenTelemetry** — P50, P95, P99 per pipeline stage, alerted via Grafana
3. **Pipecat `enable_metrics=True`** — Pipeline-level timing for every frame processor
4. **Per-provider latency dashboards** — Identify which provider is causing spikes
5. **Provider failover** — Pipecat `ServiceSwitcher` swaps to backup provider on timeout (e.g., Groq → GPT-4o-mini)
6. **Regional deployment** — Co-locate LiveKit, Pipecat, and database in the same Azure region

**Trigger:** P99 latency exceeds 500ms for >5% of calls in any 1-hour window

**Contingency:** Switch agent to Fast stack. If still exceeding, reduce LLM max_tokens, disable knowledge base retrieval for affected calls, or downgrade to simpler system prompt.

---

### R-3: Azure Credits Exhausted Early

| Field | Value |
|-------|-------|
| **ID** | R-3 |
| **Probability** | Medium |
| **Impact** | Medium |
| **Owner** | Infra/DevOps (IN) |
| **Status** | Open — monitoring |

**Description:**  
SphereVoice runs on Azure free credits. If credits are consumed faster than expected (e.g., due to higher than planned usage, forgotten resources, or expensive services), the platform goes down.

**Current Budget:** Estimated 6 months of credits at planned usage levels.

**Mitigation Plan:**
1. **Weekly credit alert** — Azure budget alert at 25%, 50%, 75%, 90% thresholds
2. **Cost tagging** — All Terraform resources tagged with `project=SphereVoice`, enabling per-service cost tracking
3. **Right-sizing** — Start with smallest SKUs (B-series VMs, basic tiers), scale up only when needed
4. **Portable Terraform** — All infrastructure defined in Terraform modules. Cloud migration is a provider swap, not a rewrite.
5. **Dev environment shutdown** — Non-production environments auto-stop outside business hours

**Trigger:** Credits consumption reaches 50% before halfway through the timeline

**Contingency:** 
1. Immediately audit and stop unused resources
2. Downgrade expensive services (e.g., smaller PostgreSQL SKU)
3. If credits will run out, execute migration plan: swap Terraform providers to Railway/DigitalOcean/AWS (estimated: <2 weeks)

---

### R-4: LiveKit SIP Complexity

| Field | Value |
|-------|-------|
| **ID** | R-4 |
| **Probability** | Medium |
| **Impact** | High |
| **Owner** | Backend Lead (BL) |
| **Status** | Open — spike in Phase 0 |

**Description:**  
LiveKit's SIP gateway is used to bridge Twilio/Plivo phone calls into LiveKit rooms. SIP configuration is complex (trunk setup, DTMF handling, codec negotiation, NAT traversal), and issues could delay the voice pipeline integration in Phase 4.

**Mitigation Plan:**
1. **Spike in Phase 0** — Proof-of-concept: Twilio → LiveKit SIP → audio in room. Document all configuration steps.
2. **Fallback path documented** — Pipecat supports `FastAPIWebsocketTransport + TwilioFrameSerializer` for direct Twilio WebSocket without LiveKit. Same pipeline code, different transport.
3. **Step-by-step runbook** — Document LiveKit SIP trunk configuration, Twilio TwiML, and test procedures
4. **Community resources** — LiveKit has active Discord and documentation for SIP; engage early with questions

**Trigger:** Phase 4, Day 3 — if SIP trunk is not connecting reliably

**Contingency:** Switch to direct Twilio WebSocket transport (Pipecat `FastAPIWebsocketTransport + TwilioFrameSerializer`). This bypasses LiveKit for audio transport while keeping the same Pipecat pipeline. LiveKit can be added back later for WebRTC browser calls and recording.

---

### R-5: Team Member Departure

| Field | Value |
|-------|-------|
| **ID** | R-5 |
| **Probability** | Low |
| **Impact** | High |
| **Owner** | All |
| **Status** | Open — mitigating continuously |

**Description:**  
With a 5-person team, losing any member significantly impacts velocity. Critical knowledge areas (voice pipeline, infrastructure, flow builder) have single owners.

**Mitigation Plan:**
1. **Documented ADRs** — All architectural decisions recorded with context and rationale
2. **Pair programming** — Critical modules reviewed by at least 2 team members
3. **PR reviews** — Every PR requires ≥1 approval, spreading knowledge across the team
4. **Runbooks** — Operations documentation for deployment, monitoring, incident response
5. **Bus factor ≥ 2** — For each critical area, at least 2 people can modify and deploy:
   - Voice pipeline: BL (primary) + BE (secondary)
   - Infrastructure: IN (primary) + BL (secondary)
   - Frontend: FL (primary) + FE (secondary)
   - Database: BE (primary) + IN (secondary)

**Trigger:** Team member gives notice

**Contingency:** Immediate knowledge transfer sessions. Prioritize documentation of undocumented decisions. Adjust phase timeline based on remaining capacity.

---

## Risk Review Process

1. **Every phase gate:** Review all active risks. Update probability/impact if new information available.
2. **New risk identified:** Add to register with full template. Assign owner. Discuss mitigation in standup.
3. **Risk materialized:** Execute contingency plan. Post-mortem after resolution. Update register with lessons learned.
4. **Risk closed:** Move to "Closed Risks" section with resolution summary and date.

---

## Closed Risks

_None yet._
