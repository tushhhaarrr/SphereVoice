# ADR-007: Feature Flags via Environment Variables

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Infra/DevOps, Full engineering team  
**Technical Story:** SphereVoice needs a mechanism to toggle features (e.g., experimental Pipecat features, new provider integrations, UI beta features) without redeploying. We need to decide on a feature flag system.

---

## Context

Feature flags are needed for:
- Enabling/disabling experimental voice pipeline features (e.g., new VAD modes or pipeline behaviors implemented in SphereVoice)
- Rolling out new provider integrations gradually
- A/B testing UI changes
- Disabling features quickly in production (kill switch)
- Gating features per tenant (future)

We evaluated three approaches:

1. **Dedicated feature flag service** — LaunchDarkly, Unleash, Flagsmith
2. **Database-backed flags** — Store flags in PostgreSQL, query per request
3. **Environment variables** — Simple `FEATURE_*` env vars, read at startup

## Decision

**Use environment variables for feature flags.** Flags follow the naming convention `FEATURE_<NAME>=true|false` and are read via `pydantic-settings` in the backend and `NEXT_PUBLIC_FEATURE_*` in the frontend.

### Implementation

**Backend (FastAPI):**
```python
# backend/app/core/config.py
class Settings(BaseSettings):
    # Feature flags
    FEATURE_EXPERIMENTAL_VAD: bool = False
    FEATURE_GROQ_PROVIDER: bool = True
    FEATURE_KNOWLEDGE_BASE: bool = False
    FEATURE_LIVE_MONITORING: bool = False
    FEATURE_WEBHOOKS: bool = False
    
    class Config:
        env_file = ".env"
```

**Frontend (Next.js):**
```typescript
// Read from process.env at build time
const FEATURES = {
  experimentalVad: process.env.NEXT_PUBLIC_FEATURE_EXPERIMENTAL_VAD === 'true',
  knowledgeBase: process.env.NEXT_PUBLIC_FEATURE_KNOWLEDGE_BASE === 'true',
  liveMonitoring: process.env.NEXT_PUBLIC_FEATURE_LIVE_MONITORING === 'true',
} as const;
```

**Docker Compose / Azure Container Apps:**
```yaml
environment:
  FEATURE_EXPERIMENTAL_VAD: "false"
  FEATURE_GROQ_PROVIDER: "true"
```

## Rationale

### Why Env Vars over Dedicated Service

| Factor | LaunchDarkly/etc. | DB-Backed Flags | Env Vars |
|--------|-------------------|-----------------|----------|
| **Cost** | $25-500+/mo | Free | Free |
| **Complexity** | SDK integration, dashboard | Query per request, admin UI | Zero — read at startup |
| **Runtime toggle** | Yes (instant) | Yes (query) | Requires restart/redeploy |
| **Per-tenant flags** | Yes | Yes | No (global only) |
| **Latency impact** | ~5ms per evaluation | ~1ms per query | Zero (read once) |
| **Team size fit** | 20+ engineers | 10+ engineers | 5 engineers |
| **Vendor lock-in** | Yes | No | No |

For a 5-person team building an internal platform, a dedicated feature flag service is overkill. The overhead of integrating, maintaining, and paying for LaunchDarkly is not justified when we have <20 flags and don't need per-tenant targeting (yet).

### Trade-off: No Runtime Toggle

The main downside is that flag changes require a container restart. In practice:
- Azure Container Apps supports zero-downtime restarts (rolling update)
- We deploy frequently (multiple times per week)
- Critical kill switches can use Redis-backed flags if needed (added later)
- The vast majority of feature flags are set at deploy time and don't change intra-deploy

### Migration Path

If SphereVoice grows beyond 5 engineers or needs per-tenant flags, we can migrate to:
1. **Database-backed flags** with a simple admin UI (1-2 day effort)
2. **Unleash** (open-source feature flag service, self-hosted) for full flag management

The env var naming convention (`FEATURE_*`) makes migration mechanical — replace env reads with flag service calls.

## Consequences

### Positive
- Zero additional infrastructure or cost
- No SDK integration or latency overhead
- Simple mental model — one `.env` file controls all flags
- pydantic-settings validates types at startup (boolean, not arbitrary strings)
- Works identically in local dev, CI, staging, production

### Negative
- Flag changes require container restart (not instant)
- No per-tenant or per-user targeting
- No flag evaluation audit trail (mitigated by deployment logs)
- No gradual rollout (percentage-based) — it's on or off

### Risks
- **Risk:** Need runtime flag changes for incident response  
  **Mitigation:** Critical kill switches can be promoted to Redis-backed checks with ~1ms overhead. Container restart takes <30s on Azure Container Apps.

## Related ADRs
- [ADR-008: Terraform for IaC](./ADR-008-terraform-iac.md)
