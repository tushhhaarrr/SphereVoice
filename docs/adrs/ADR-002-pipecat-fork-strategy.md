# ADR-002: Pipecat Package-First Strategy

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Backend Lead, Full engineering team  
**Technical Story:** SphereVoice uses Pipecat as its voice pipeline engine. We need a dependency strategy that keeps us on the supported upstream package while ensuring SphereVoice-specific behavior stays in SphereVoice code.

---

## Context

[Pipecat](https://github.com/pipecat-ai/pipecat) (Apache-2.0) is an open-source Python framework for building real-time voice AI agents. It provides:

- Frame-based pipeline architecture for audio processing
- Built-in service classes for STT (Deepgram, AssemblyAI), LLM (OpenAI, Groq, Anthropic), TTS (Cartesia, ElevenLabs, LMNT)
- Voice Activity Detection via SileroVADAnalyzer
- Transport layers (LiveKit, WebSocket)
- Context aggregation and turn management

SphereVoice depends heavily on Pipecat for its core voice pipeline. We evaluated two dependency strategies:

1. **PyPI install** — `pip install pipecat-ai[extras]` from the public registry
2. **Private fork** — Fork to `Sphere/pipecat`, maintain a `SphereVoice-main` branch, install from Git

## Decision

**Use the upstream `pipecat-ai` package as the default dependency** and keep SphereVoice-specific logic in the SphereVoice repository:

```
pip install "pipecat-ai[livekit,deepgram,openai,groq,anthropic,cartesia,elevenlabs,lmnt,silero]==0.0.104"
```

### Implementation Guidelines

| Item | Detail |
|------|--------|
| **Primary dependency** | Pin `pipecat-ai` to an exact version in `backend/requirements.txt` |
| **Custom behavior** | Build custom `FrameProcessor`s, services, orchestration, and adapters inside `backend/app/modules/pipeline/` |
| **Upgrade process** | Test package upgrades in SphereVoice before changing the pin |
| **Fallback for framework debugging** | Clone upstream separately in a scratch location if deep framework debugging is needed |
| **Fork policy** | Avoid a long-lived SphereVoice fork; only consider a short-lived patch fork if an urgent upstream defect blocks production |

## Rationale

### Why Package-First over a Fork

| Factor | Package-First | Long-Lived Fork |
|--------|---------------|----------------|
| **Custom FrameProcessors** | Implement in SphereVoice code using Pipecat extension points | Patch framework internals |
| **Provider/service composition** | Build adapters and orchestration in SphereVoice modules | Encode product logic in the fork |
| **Upgrades** | Controlled by exact version pin | Controlled by merge cadence and manual conflict resolution |
| **Operational burden** | Low | High |
| **Divergence risk** | Low | High |
| **Emergency patch path** | Temporary override only if required | Permanent maintenance burden |

SphereVoice already gets the key extension points it needs from upstream Pipecat: custom `FrameProcessor`s, transport configuration, service composition, tool/function schemas, and pipeline orchestration. Those are sufficient for SphereVoice's agent behavior, RAG insertion, provider selection, and latency tuning at the application layer without carrying a fork as the default dependency.

### Why Not a Long-Lived Fork

The main risk is **merge drift**: once product behavior starts living in a fork, every upstream update becomes a framework-maintenance task. That shifts engineering time away from SphereVoice features and reliability work.

If an upstream defect ever blocks production, the exception path is a short-lived patch while SphereVoice either contributes a fix upstream or removes the patch in a later package upgrade.

## Consequences

### Positive
- Default install path is simple and reproducible
- SphereVoice-specific behavior stays in the SphereVoice repository where it is easier to test and review
- Upgrading Pipecat becomes a normal dependency-management task instead of a fork-maintenance exercise
- Reduced risk of hidden framework drift

### Negative
- Deep framework bugs may occasionally require temporary patching or waiting for upstream fixes
- Some optimizations may need to be expressed through public extension points rather than framework edits

### Risks
- **Risk:** Upstream package upgrades introduce breaking changes (Probability: Medium, Impact: High)  
  **Mitigation:** Pin exact versions, run SphereVoice pipeline tests before changing the pin, and keep SphereVoice customizations outside the framework dependency.

## Related ADRs
- [ADR-005: LiveKit for WebRTC/SIP, Pipecat for Pipeline](./ADR-005-livekit-pipecat-split.md)
