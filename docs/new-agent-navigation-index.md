# New Agent Navigation Index

This file is the working map for anything related to creating, editing, publishing, templating, and testing agents in SphereVoice.

If you need to make a new agent flow end to end, start with the route pages, then the frontend agent module, then the backend `agents` and `analytics` modules.

## Fast Start

Use this order when you need to trace or change the new-agent flow:

1. Product intent
   - [prd.md](./prd.md)
   - [tech-prd.md](./tech-prd.md)
   - [retell-audit.md](./retell-audit.md)
   - [execution-plan.md](./execution-plan.md)
2. Frontend route entry points
   - [../frontend/src/app/(dashboard)/workspace/[tenantId]/agents/page.tsx](../frontend/src/app/(dashboard)/workspace/%5BtenantId%5D/agents/page.tsx)
   - [../frontend/src/app/(dashboard)/workspace/[tenantId]/agents/[id]/page.tsx](../frontend/src/app/(dashboard)/workspace/%5BtenantId%5D/agents/%5Bid%5D/page.tsx)
   - [../frontend/src/app/(dashboard)/agents/[id]/page.tsx](../frontend/src/app/(dashboard)/agents/%5Bid%5D/page.tsx)
   - [../frontend/src/app/(dashboard)/agents/templates/page.tsx](../frontend/src/app/(dashboard)/agents/templates/page.tsx)
3. Frontend module barrels and UI
   - [../frontend/src/modules/agents/index.ts](../frontend/src/modules/agents/index.ts)
   - [../frontend/src/modules/analytics/components/template-gallery.tsx](../frontend/src/modules/analytics/components/template-gallery.tsx)
4. Backend API and service layer
   - [../backend/app/modules/agents/router.py](../backend/app/modules/agents/router.py)
   - [../backend/app/modules/agents/service.py](../backend/app/modules/agents/service.py)
   - [../backend/app/modules/analytics/router.py](../backend/app/modules/analytics/router.py)
   - [../backend/app/modules/analytics/service.py](../backend/app/modules/analytics/service.py)
5. Tests
   - [../backend/tests/test_agents/test_agents_api.py](../backend/tests/test_agents/test_agents_api.py)

## End-to-End New Agent Flow

### Direct agent creation

1. Tenant workspace agent list page renders the workspace-scoped list and the `New Agent` button.
   - [../frontend/src/app/(dashboard)/workspace/[tenantId]/agents/page.tsx](../frontend/src/app/(dashboard)/workspace/%5BtenantId%5D/agents/page.tsx)
   - [../frontend/src/modules/agents/components/agent-list.tsx](../frontend/src/modules/agents/components/agent-list.tsx)
2. `CreateAgentDialog` collects the minimal fields for a draft agent.
   - [../frontend/src/modules/agents/components/create-agent-dialog.tsx](../frontend/src/modules/agents/components/create-agent-dialog.tsx)
3. `useCreateAgent` sends `POST /api/v1/agents`.
   - [../frontend/src/modules/agents/hooks/use-agents.ts](../frontend/src/modules/agents/hooks/use-agents.ts)
4. Backend router accepts the request and delegates to `AgentService.create_agent`.
   - [../backend/app/modules/agents/router.py](../backend/app/modules/agents/router.py)
   - [../backend/app/modules/agents/service.py](../backend/app/modules/agents/service.py)
5. The UI redirects to the agent detail editor.
   - [../frontend/src/modules/agents/components/agent-detail-page.tsx](../frontend/src/modules/agents/components/agent-detail-page.tsx)

### Template-based creation

1. Templates page renders the gallery.
   - [../frontend/src/app/(dashboard)/agents/templates/page.tsx](../frontend/src/app/(dashboard)/agents/templates/page.tsx)
2. `TemplateGallery` opens the create-from-template dialog.
   - [../frontend/src/modules/analytics/components/template-gallery.tsx](../frontend/src/modules/analytics/components/template-gallery.tsx)
3. `useTemplateToAgent` sends `POST /api/v1/analytics/templates/{id}/use`.
   - [../frontend/src/modules/analytics/hooks/use-templates.ts](../frontend/src/modules/analytics/hooks/use-templates.ts)
4. Backend `TemplateService.create_agent_from_template` builds agent payload, then `AgentService.create_agent` persists it.
   - [../backend/app/modules/analytics/router.py](../backend/app/modules/analytics/router.py)
   - [../backend/app/modules/analytics/service.py](../backend/app/modules/analytics/service.py)

### Publish and runtime behavior

1. Draft edits update the mutable `agents` row.
2. Publishing creates an immutable `agent_versions` snapshot and increments `version`.
   - [../backend/app/modules/agents/service.py](../backend/app/modules/agents/service.py)
3. Runtime calls use the latest published snapshot, not newer unpublished draft edits.
   - [../backend/app/modules/pipeline/orchestrator.py](../backend/app/modules/pipeline/orchestrator.py)

If a live or test call does not reflect your latest editor change, check whether the agent was published after that change.

## File Map

### Frontend route files

- [../frontend/src/app/(dashboard)/workspace/[tenantId]/agents/page.tsx](../frontend/src/app/(dashboard)/workspace/%5BtenantId%5D/agents/page.tsx): Workspace-scoped agent list page. This is the main entry point for creating a new agent.
- [../frontend/src/app/(dashboard)/workspace/[tenantId]/agents/[id]/page.tsx](../frontend/src/app/(dashboard)/workspace/%5BtenantId%5D/agents/%5Bid%5D/page.tsx): Workspace-scoped agent detail page.
- [../frontend/src/app/(dashboard)/agents/[id]/page.tsx](../frontend/src/app/(dashboard)/agents/%5Bid%5D/page.tsx): Global agent detail route.
- [../frontend/src/app/(dashboard)/agents/templates/page.tsx](../frontend/src/app/(dashboard)/agents/templates/page.tsx): Template gallery route.

### Frontend agents module

- [../frontend/src/modules/agents/index.ts](../frontend/src/modules/agents/index.ts): Public barrel. Import from here instead of deep internal paths when wiring pages.
- [../frontend/src/modules/agents/components/agent-list.tsx](../frontend/src/modules/agents/components/agent-list.tsx): Renders agent table, workspace-mode state, publish action, delete action, and the create dialog trigger.
- [../frontend/src/modules/agents/components/create-agent-dialog.tsx](../frontend/src/modules/agents/components/create-agent-dialog.tsx): Minimal draft-agent creation form.
- [../frontend/src/modules/agents/components/agent-detail-page.tsx](../frontend/src/modules/agents/components/agent-detail-page.tsx): Main editor for prompt agents and flow agents.
- [../frontend/src/modules/agents/components/agent-settings.tsx](../frontend/src/modules/agents/components/agent-settings.tsx): Shared per-agent settings UI.
- [../frontend/src/modules/agents/components/flow-agent-settings-panel.tsx](../frontend/src/modules/agents/components/flow-agent-settings-panel.tsx): Flow-agent-specific settings panel.
- [../frontend/src/modules/agents/components/flow-builder](../frontend/src/modules/agents/components/flow-builder): Canvas, node config, and flow editor implementation.
- [../frontend/src/modules/agents/components/prompt-editor.tsx](../frontend/src/modules/agents/components/prompt-editor.tsx): Single-prompt editing UI with variables.
- [../frontend/src/modules/agents/components/function-calling-config.tsx](../frontend/src/modules/agents/components/function-calling-config.tsx): Callable function configuration for prompt agents.
- [../frontend/src/modules/agents/components/publish-dialog.tsx](../frontend/src/modules/agents/components/publish-dialog.tsx): Publish UX.
- [../frontend/src/modules/agents/components/version-history-sidebar.tsx](../frontend/src/modules/agents/components/version-history-sidebar.tsx): Version history and rollback UI.
- [../frontend/src/modules/agents/components/test-call-panel.tsx](../frontend/src/modules/agents/components/test-call-panel.tsx): Test-call UI.
- [../frontend/src/modules/agents/components/transcript-display.tsx](../frontend/src/modules/agents/components/transcript-display.tsx): Transcript rendering used by testing flows.
- [../frontend/src/modules/agents/hooks/use-agents.ts](../frontend/src/modules/agents/hooks/use-agents.ts): Query and mutation hooks for CRUD and publish.
- [../frontend/src/modules/agents/hooks/use-agent-versions.ts](../frontend/src/modules/agents/hooks/use-agent-versions.ts): Version history and rollback hooks.
- [../frontend/src/modules/agents/hooks/use-test-call.ts](../frontend/src/modules/agents/hooks/use-test-call.ts): Test-call state and network hooks.
- [../frontend/src/modules/agents/types/index.ts](../frontend/src/modules/agents/types/index.ts): Frontend `Agent`, `AgentType`, and request/response types.
- [../frontend/src/modules/agents/types/flow.ts](../frontend/src/modules/agents/types/flow.ts): Flow-node and flow-edge types.
- [../frontend/src/modules/agents/lib/flow-interop.ts](../frontend/src/modules/agents/lib/flow-interop.ts): Flow normalization and API serialization.

### Frontend analytics/template files that also affect new-agent work

- [../frontend/src/modules/analytics/components/template-gallery.tsx](../frontend/src/modules/analytics/components/template-gallery.tsx): Template selection and create-from-template dialog.
- [../frontend/src/modules/analytics/components/save-as-template-dialog.tsx](../frontend/src/modules/analytics/components/save-as-template-dialog.tsx): Save an existing agent as a reusable template.
- [../frontend/src/modules/analytics/components/retell-template-import-dialog.tsx](../frontend/src/modules/analytics/components/retell-template-import-dialog.tsx): Import path for Retell-based template workflows.
- [../frontend/src/modules/analytics/hooks/use-templates.ts](../frontend/src/modules/analytics/hooks/use-templates.ts): Template list, create, and template-to-agent hooks.

### Backend agents module

- [../backend/app/modules/agents/__init__.py](../backend/app/modules/agents/__init__.py): Public module exports.
- [../backend/app/modules/agents/router.py](../backend/app/modules/agents/router.py): REST endpoints for list, create, detail, update, delete, publish, versions, rollback, and flow validation.
- [../backend/app/modules/agents/service.py](../backend/app/modules/agents/service.py): Business logic for CRUD, publish snapshots, rollback, and flow validation.
- [../backend/app/modules/agents/models.py](../backend/app/modules/agents/models.py): SQLAlchemy models for `agents`, `agent_versions`, and `agent_knowledge_bases`.
- [../backend/app/modules/agents/schemas.py](../backend/app/modules/agents/schemas.py): Pydantic request/response schema definitions.

### Backend analytics/template files that also affect new-agent work

- [../backend/app/modules/analytics/router.py](../backend/app/modules/analytics/router.py): Template API endpoints, including `POST /templates/{id}/use`.
- [../backend/app/modules/analytics/service.py](../backend/app/modules/analytics/service.py): Template visibility rules and template-to-agent payload creation.
- [../backend/app/modules/analytics/models.py](../backend/app/modules/analytics/models.py): Template persistence model definitions.
- [../backend/app/modules/analytics/schemas.py](../backend/app/modules/analytics/schemas.py): Template request/response schemas.

### Runtime and tests

- [../backend/app/modules/pipeline/orchestrator.py](../backend/app/modules/pipeline/orchestrator.py): Runtime agent resolution. This is where published snapshots are applied.
- [../backend/tests/test_agents/test_agents_api.py](../backend/tests/test_agents/test_agents_api.py): Primary API coverage for create, list, update, delete, publish, versions, and snapshot behavior.

## Directory Snapshot

```text
frontend/src/modules/agents/
  index.ts
  components/
    agent-detail-page.tsx
    agent-list.tsx
    agent-settings.tsx
    create-agent-dialog.tsx
    flow-agent-settings-panel.tsx
    flow-builder/
    function-calling-config.tsx
    prompt-editor.tsx
    publish-dialog.tsx
    test-call-panel.tsx
    transcript-display.tsx
    version-history-sidebar.tsx
  hooks/
    use-agent-versions.ts
    use-agents.ts
    use-test-call.ts
  types/
    flow.ts
    index.ts
  lib/
    flow-interop.ts

frontend/src/modules/analytics/
  components/
    retell-template-import-dialog.tsx
    save-as-template-dialog.tsx
    template-gallery.tsx
  hooks/
    use-templates.ts

backend/app/modules/agents/
  __init__.py
  models.py
  router.py
  schemas.py
  service.py

backend/app/modules/analytics/
  __init__.py
  models.py
  router.py
  schemas.py
  service.py
```

## Common Change Recipes

### If you only want to create a new draft agent from the UI

You usually only need to inspect these files:

- [../frontend/src/app/(dashboard)/workspace/[tenantId]/agents/page.tsx](../frontend/src/app/(dashboard)/workspace/%5BtenantId%5D/agents/page.tsx)
- [../frontend/src/modules/agents/components/agent-list.tsx](../frontend/src/modules/agents/components/agent-list.tsx)
- [../frontend/src/modules/agents/components/create-agent-dialog.tsx](../frontend/src/modules/agents/components/create-agent-dialog.tsx)
- [../frontend/src/modules/agents/hooks/use-agents.ts](../frontend/src/modules/agents/hooks/use-agents.ts)
- [../backend/app/modules/agents/router.py](../backend/app/modules/agents/router.py)
- [../backend/app/modules/agents/service.py](../backend/app/modules/agents/service.py)

### If you are adding a new agent field

Update all of these together:

- [../backend/app/modules/agents/models.py](../backend/app/modules/agents/models.py)
- [../backend/app/modules/agents/schemas.py](../backend/app/modules/agents/schemas.py)
- [../backend/app/modules/agents/service.py](../backend/app/modules/agents/service.py)
- [../backend/app/modules/pipeline/orchestrator.py](../backend/app/modules/pipeline/orchestrator.py)
- [../frontend/src/modules/agents/types/index.ts](../frontend/src/modules/agents/types/index.ts)
- [../frontend/src/modules/agents/components/agent-detail-page.tsx](../frontend/src/modules/agents/components/agent-detail-page.tsx)
- Relevant settings component under [../frontend/src/modules/agents/components](../frontend/src/modules/agents/components)
- [../backend/tests/test_agents/test_agents_api.py](../backend/tests/test_agents/test_agents_api.py)

### If you are adding a new agent type

Start here:

- [../frontend/src/modules/agents/types/index.ts](../frontend/src/modules/agents/types/index.ts)
- [../frontend/src/modules/agents/components/create-agent-dialog.tsx](../frontend/src/modules/agents/components/create-agent-dialog.tsx)
- [../frontend/src/modules/agents/components/agent-list.tsx](../frontend/src/modules/agents/components/agent-list.tsx)
- [../frontend/src/modules/agents/components/agent-detail-page.tsx](../frontend/src/modules/agents/components/agent-detail-page.tsx)
- [../backend/app/modules/agents/schemas.py](../backend/app/modules/agents/schemas.py)
- [../backend/app/modules/agents/models.py](../backend/app/modules/agents/models.py)
- [../backend/app/modules/agents/service.py](../backend/app/modules/agents/service.py)
- [../backend/tests/test_agents/test_agents_api.py](../backend/tests/test_agents/test_agents_api.py)
- [prd.md](./prd.md)
- [tech-prd.md](./tech-prd.md)

### If you are changing template-based creation

Start here:

- [../frontend/src/app/(dashboard)/agents/templates/page.tsx](../frontend/src/app/(dashboard)/agents/templates/page.tsx)
- [../frontend/src/modules/analytics/components/template-gallery.tsx](../frontend/src/modules/analytics/components/template-gallery.tsx)
- [../frontend/src/modules/analytics/hooks/use-templates.ts](../frontend/src/modules/analytics/hooks/use-templates.ts)
- [../backend/app/modules/analytics/router.py](../backend/app/modules/analytics/router.py)
- [../backend/app/modules/analytics/service.py](../backend/app/modules/analytics/service.py)
- [../backend/app/modules/agents/service.py](../backend/app/modules/agents/service.py)

## Important Notes

- New agent creation is intentionally workspace-scoped. The `New Agent` button is disabled outside a tenant workspace.
- Direct creation and template creation use different backend modules. Direct creation is in `agents`; template creation starts in `analytics` and then delegates into `agents`.
- Publishing is a separate step from saving. Draft changes are not the same thing as runtime changes.
- If you are touching flow data, also inspect [../frontend/src/modules/agents/lib/flow-interop.ts](../frontend/src/modules/agents/lib/flow-interop.ts) and the flow-builder directory.
