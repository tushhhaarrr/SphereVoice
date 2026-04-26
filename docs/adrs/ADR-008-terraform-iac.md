# ADR-008: Terraform for IaC, No ARM Templates

**Status:** Accepted  
**Date:** 2026-03-04  
**Deciders:** Infra/DevOps, Full engineering team  
**Technical Story:** SphereVoice runs on Azure (free credits) but must be portable — when credits expire, we may migrate to another cloud or self-hosted infrastructure. We need an Infrastructure as Code (IaC) tool that supports Azure today and is portable tomorrow.

---

## Context

SphereVoice's Azure infrastructure includes:
- PostgreSQL 15 Flexible Server (with pgvector)
- Redis 7.2 (Azure Cache)
- Azure Blob Storage (S3-compatible API)
- Azure Container Registry (ACR)
- Azure Container Apps (backend + frontend)
- Azure VM (LiveKit Server)
- Azure Key Vault (encryption master key)
- Azure Monitor + App Insights (observability)

We evaluated three IaC approaches:

1. **ARM templates** — Azure's native IaC format (JSON/Bicep)
2. **Terraform** — HashiCorp's cloud-agnostic IaC tool
3. **Pulumi** — Code-first IaC (TypeScript/Python)

## Decision

**Use Terraform 1.9.x with the Azure provider (`azurerm`).** All infrastructure is defined in Terraform modules under `infra/terraform/`.

### Directory Structure

```
infra/terraform/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   └── terraform.tfvars
│   ├── staging/
│   │   ├── main.tf
│   │   └── terraform.tfvars
│   └── production/
│       ├── main.tf
│       └── terraform.tfvars
└── modules/
    ├── database/      # PostgreSQL + pgvector
    ├── redis/         # Azure Cache for Redis
    ├── storage/       # Blob Storage
    ├── container_apps/ # Backend + Frontend containers
    ├── vm/            # LiveKit Server VM
    └── monitoring/    # Azure Monitor + App Insights
```

### Conventions

- **State:** Remote state in Azure Storage backend (one state file per environment)
- **Modules:** Reusable modules with `variables.tf`, `main.tf`, `outputs.tf`
- **Environments:** Environment-specific `terraform.tfvars` for variable overrides
- **Naming:** All resources prefixed with `SphereVoice-{env}-` (e.g., `SphereVoice-dev-postgres`)
- **Tagging:** All resources tagged with `project=SphereVoice`, `environment={env}`, `managed_by=terraform`

## Rationale

### Why Terraform over ARM/Bicep

| Factor | ARM/Bicep | Terraform | Pulumi |
|--------|-----------|-----------|--------|
| **Cloud portability** | Azure only | Any cloud (Azure, AWS, GCP, DO) | Any cloud |
| **Migration risk** | Rewrite if leaving Azure | Swap provider, keep structure | Swap provider, keep structure |
| **Language** | JSON (ARM) / DSL (Bicep) | HCL (simple, declarative) | TypeScript/Python (imperative) |
| **Learning curve** | Medium (Azure-specific) | Low (widely known) | Medium (code complexity) |
| **Community** | Azure community | Largest IaC community | Growing |
| **Module ecosystem** | Azure-only modules | Huge module registry | Growing |
| **State management** | Azure manages | Remote backend (Azure Storage) | Managed service or self-hosted |
| **Team familiarity** | Low | High | Low |

Key decision driver: **Portability.** SphereVoice runs on Azure because of free credits, but the plan explicitly calls for migration readiness. Terraform's provider model means we can swap `azurerm` for `aws` or `digitalocean` and keep the module structure. ARM templates would be useless outside Azure.

### Why Not Pulumi

Pulumi's code-first approach (TypeScript/Python) is powerful but adds complexity:
- IaC tied to a programming language runtime
- Harder to review — IaC looks like application code
- Smaller ecosystem than Terraform
- For 5 engineers, Terraform's declarative HCL is simpler and more predictable

## Consequences

### Positive
- All infrastructure is version-controlled, reproducible, and reviewable
- Cloud-portable — can migrate off Azure with provider swap
- Module pattern enables environment parity (dev ≅ staging ≅ production)
- Large ecosystem of Terraform modules and documentation
- `terraform plan` provides a preview of all infrastructure changes before apply

### Negative
- Terraform state must be managed carefully (remote backend, locking)
- HCL can be verbose for complex configurations
- Must keep Terraform version and provider versions pinned
- Two-step process (plan + apply) adds friction vs. portal clicks

### Risks
- **Risk:** Terraform state corruption or drift  
  **Mitigation:** Remote state in Azure Storage with locking enabled. State backup before destructive operations. CI runs `terraform plan` on every PR.
- **Risk:** Azure credits expire, need to migrate quickly  
  **Mitigation:** Terraform modules are provider-agnostic in structure. Swap `azurerm` resources for equivalent providers. Estimated migration: <2 weeks for a new cloud.

## Related ADRs
- [ADR-007: Feature Flags via Environment Variables](./ADR-007-feature-flags-env-vars.md)
