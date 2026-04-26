# SphereVoice Refactoring Task List

## Progress Tracking
- [x] Initial research and plan expansion
- [x] Create `TransmissionOverheadAudit` service
- [x] Rebrand `pricing/schemas.py`
- [x] Rebrand `pricing/service.py`
- [x] Rebrand `pricing/exchange_rate.py` (SubstrateConversionService)
- [x] Update `pipeline/__init__.py` exports
- [ ] Phase 4: Final Domain Alignment
    - [/] Rebrand `pricing/models.py` (SpectralProviderBenchmark)
    - [ ] Rebrand `pricing/router.py`
    - [ ] Rebrand `pipeline/services/stt.py` (PerceptionSignalCollector)
    - [ ] Rebrand `pipeline/services/llm.py` (CognitiveNexusBlueprint)
    - [ ] Rebrand `pipeline/services/tts.py` (SynthesisNexusBlueprint)
    - [ ] Rebrand `pipeline/services/vocabulary.py` (lexical_domain)
    - [ ] Rebrand `pipeline/services/sarvam_text_filter.py`
    - [ ] Rebrand `pipeline/services/smallest_tts.py`
    - [ ] Rebrand `pipeline/services/groq_llm.py`
    - [ ] Cleanup `pipeline/orchestrator.py` imports
    - [ ] Global verification and path cleanup
- [ ] Final Build & Verification

## Legacy Rebranding Tasks
- [x] Global Search and Replace "Gorillaa" -> "Sphere AI"
- [x] Global Search and Replace "VOX" -> "SphereVoice"
- [x] Scrub original author metadata (Girish Ban)
- [x] Rewrite project-wide documentation (README)

## Deep Anonymization Layers
- [/] Layer 1: Identity & Provisioning (Backend Auth)
    - [x] Anonymize `auth/service.py`
    - [x] Anonymize `auth/router.py`
    - [x] Anonymize `auth/schemas.py`
    - [ ] Verify Frontend Login with new endpoints
- [ ] Layer 2: Signal Entities (Backend Agents)
    - [ ] Rename `agents` module to `entities`
    - [ ] Refactor `Agent` model to `SignalProcessor`
    - [ ] Anonymize Service and Router
- [ ] Layer 3: Synchronous Sessions (Backend Pipeline/Calls)
    - [ ] Rename `calls` module to `sessions`
    - [ ] Anonymize real-time logic
- [ ] Layer 4: Interface Overhaul (Frontend)
    - [ ] Rename React Components to match new domain
    - [ ] Update Auth API client
- [ ] Layer 5: Substrate (Infrastructure)
    - [ ] Anonymize Docker Compose service names
    - [ ] Rename Terraform resource identifiers
