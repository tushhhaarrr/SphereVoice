# ADR-005: LiveKit for WebRTC/SIP, Pipecat for Pipeline

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Backend Lead, Full engineering team  
**Technical Story:** SphereVoice needs to handle real-time audio between phone callers and AI agents. This requires two distinct capabilities: (1) media transport — receiving audio from telephony providers and relaying it via WebRTC/SIP, and (2) voice pipeline — processing that audio through STT → LLM → TTS. We need to decide how to split these responsibilities.

---

## Context

A typical voice AI call flows:

```
Caller → Twilio (SIP) → [Media Transport] → [Voice Pipeline] → [Media Transport] → Twilio → Caller
```

We need:
- **Media transport:** WebRTC/SIP bridging, audio codec handling, room management, recording
- **Voice pipeline:** VAD, STT, LLM inference, TTS, turn management, context aggregation

We evaluated three architectures:

1. **LiveKit for everything** — Use LiveKit Agents SDK for both media transport and AI pipeline
2. **Pipecat for everything** — Use Pipecat's FastAPIWebsocketTransport + TwilioFrameSerializer for direct telephony
3. **Split: LiveKit for media, Pipecat for pipeline** — LiveKit handles WebRTC/SIP; Pipecat connects as a LiveKit room participant

## Decision

**Split: LiveKit handles WebRTC/SIP media transport. Pipecat handles the voice AI pipeline.**

### Architecture

```
Phone Call → Twilio → LiveKit (SIP Gateway) → LiveKit Room
                                                    ↕
                                              Pipecat Pipeline
                                              (LiveKitTransport)
                                                    │
                                              STT → LLM → TTS
                                                    │
                                              LiveKit Room → Twilio → Caller
```

**LiveKit responsibilities:**
- SIP gateway (receives calls from Twilio/Plivo)
- WebRTC room management (participants, tracks, subscriptions)
- Audio codec handling and transcoding
- Recording (server-side composite recording)
- Scalable media routing

**Pipecat responsibilities (via `LiveKitTransport`):**
- Joins the LiveKit room as an AI participant
- Receives audio frames from the transport
- Runs the STT → LLM → TTS pipeline
- Sends synthesized audio back through the transport
- VAD (SileroVADAnalyzer), turn management, context aggregation

### Alternative Transport (Fallback)

For simpler deployments or LiveKit SIP issues, Pipecat can connect directly to Twilio via:
```python
FastAPIWebsocketTransport + TwilioFrameSerializer
```
This receives Twilio's media stream WebSocket directly and processes through the same pipeline. No LiveKit required. Available as a fallback path.

## Rationale

### Why Split over Single-System

| Factor | LiveKit Only | Pipecat Only | Split |
|--------|-------------|-------------|-------|
| **SIP handling** | Native SIP gateway | No SIP — WebSocket only | LiveKit SIP gateway |
| **WebRTC** | Native | Via LiveKitTransport | Native |
| **Pipeline flexibility** | LiveKit Agents SDK (less mature) | Frame-based pipeline (battle-tested) | Pipecat pipeline |
| **Provider abstraction** | Build custom | Built-in service classes for all providers | Built-in |
| **VAD** | LiveKit's VAD (cloud) | SileroVADAnalyzer (on-device, <10ms) | On-device VAD |
| **Scaling** | LiveKit scales media | Single process per call | LiveKit scales media, Pipecat scales pipeline |
| **Recording** | Server-side recording | Must implement | LiveKit recording |
| **Latency** | Good | Excellent (direct frame control) | Excellent (Pipecat frame control) |

Key insight: **LiveKit is excellent at media transport but its Agents SDK is less mature than Pipecat for AI pipelines.** Pipecat has production-grade service classes for Deepgram, Groq, Cartesia, etc., with built-in streaming, buffering, and turn management. Using Pipecat's `LiveKitTransport` gives us the best of both worlds.

### Risk: LiveKit SIP Complexity

If LiveKit's SIP gateway proves too complex or unreliable, we can fall back to Pipecat's `FastAPIWebsocketTransport + TwilioFrameSerializer` for direct Twilio WebSocket connection. The Pipecat pipeline code remains identical — only the transport layer changes.

## Consequences

### Positive
- LiveKit handles the complex WebRTC/SIP media layer — battle-tested, scales well
- Pipecat provides the AI pipeline framework — production-grade provider services, VAD, turn management
- Clear separation of concerns: media transport vs. AI pipeline
- Fallback path (direct WebSocket) available if LiveKit SIP has issues
- Recording handled natively by LiveKit
- Can scale LiveKit and Pipecat independently

### Negative
- Two systems to deploy and monitor (LiveKit server + Pipecat processes)
- LiveKit requires a dedicated VM (not containerized easily)
- Extra network hop (LiveKit ↔ Pipecat) adds ~5-10ms latency
- Must keep LiveKit server SDK and Pipecat LiveKitTransport versions in sync

### Risks
- **Risk:** LiveKit SIP gateway complexity delays Phase 4 (Probability: Medium, Impact: High)  
  **Mitigation:** Spike in Phase 0. Fallback to `FastAPIWebsocketTransport + TwilioFrameSerializer`. Document both paths.
- **Risk:** Extra network hop exceeds latency budget  
  **Mitigation:** Co-locate LiveKit and Pipecat on same network. Measured overhead is 5-10ms — well within 300ms budget.

## Related ADRs
- [ADR-002: Pipecat Fork Strategy](./ADR-002-pipecat-fork-strategy.md)
