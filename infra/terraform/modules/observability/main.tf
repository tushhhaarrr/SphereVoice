# SphereVoice — Self-Hosted Observability Module
# Deploys: Container App running Grafana + Loki + Tempo + Prometheus + OTEL Collector
# Storage: Azure Blob Storage for Loki chunks and Tempo trace blocks
# This replaces Azure Monitor/App Insights dependency entirely.

# ── Variables ───────────────────────────────────────────────
variable "environment" {
  type        = string
  description = "Deployment environment (dev, staging, production)"
}

variable "location" {
  type        = string
  description = "Azure region"
}

variable "rg_name" {
  type        = string
  description = "Resource group name"
}

variable "container_app_environment_id" {
  type        = string
  description = "Container Apps Environment ID (shared with other apps)"
}

variable "acr_login_server" {
  type        = string
  description = "ACR login server (e.g. SphereVoiceSphereacr.azurecr.io)"
}

variable "acr_username" {
  type        = string
  description = "ACR admin username"
  sensitive   = true
}

variable "acr_password" {
  type        = string
  description = "ACR admin password"
  sensitive   = true
}

variable "backend_fqdn" {
  type        = string
  description = "Backend Container App FQDN for Prometheus to scrape (e.g. SphereVoice-backend.internal:8000)"
}

variable "grafana_admin_password" {
  type        = string
  description = "Grafana admin password"
  sensitive   = true
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ── Storage Account for Loki + Tempo ────────────────────────
resource "azurerm_storage_account" "observability" {
  name                     = "SphereVoice${var.environment}obsdata"
  resource_group_name      = var.rg_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    delete_retention_policy {
      days = 7
    }
  }

  tags = merge(var.tags, {
    module = "observability"
  })
}

# Blob containers
resource "azurerm_storage_container" "loki_chunks" {
  name                  = "SphereVoice-loki-chunks"
  storage_account_id    = azurerm_storage_account.observability.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "tempo_traces" {
  name                  = "SphereVoice-tempo-traces"
  storage_account_id    = azurerm_storage_account.observability.id
  container_access_type = "private"
}

# Get storage access key
data "azurerm_storage_account" "observability" {
  name                = azurerm_storage_account.observability.name
  resource_group_name = var.rg_name

  depends_on = [azurerm_storage_account.observability]
}

# ── Container App: SphereVoice-observability ────────────────────────
resource "azurerm_container_app" "observability" {
  name                         = "SphereVoice-${var.environment}-observability"
  container_app_environment_id = var.container_app_environment_id
  resource_group_name          = var.rg_name
  revision_mode                = "Single"

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "observability"
      image  = "${var.acr_login_server}/SphereVoice-observability:latest"
      cpu    = 2.0
      memory = "4Gi"

      # Grafana
      env {
        name  = "GF_SECURITY_ADMIN_USER"
        value = "admin"
      }
      env {
        name        = "GF_SECURITY_ADMIN_PASSWORD"
        secret_name = "grafana-password"
      }

      # Azure Blob Storage (for Loki + Tempo)
      env {
        name  = "AZURE_STORAGE_ACCOUNT"
        value = azurerm_storage_account.observability.name
      }
      env {
        name        = "AZURE_STORAGE_ACCESS_KEY"
        secret_name = "storage-key"
      }
      env {
        name  = "LOKI_AZURE_CONTAINER"
        value = "SphereVoice-loki-chunks"
      }
      env {
        name  = "TEMPO_AZURE_CONTAINER"
        value = "SphereVoice-tempo-traces"
      }

      # Prometheus backend target
      env {
        name  = "BACKEND_METRICS_TARGET"
        value = var.backend_fqdn
      }

      # Liveness probe on Grafana
      liveness_probe {
        path      = "/api/health"
        port      = 3000
        transport = "HTTP"

        initial_delay    = 30
        interval_seconds = 30
        timeout          = 10
      }
    }

    volume {
      name         = "obs-data"
      storage_type = "EmptyDir"
    }
  }

  secret {
    name  = "grafana-password"
    value = var.grafana_admin_password
  }

  secret {
    name  = "storage-key"
    value = data.azurerm_storage_account.observability.primary_access_key
  }

  ingress {
    external_traffic_weight {
      latest_revision = true
      percentage      = 100
    }
    target_port = 3000
    transport   = "http"

    # Expose OTEL Collector gRPC port for internal backend→collector traffic
    # NOTE: additionalPortMappings is set via REST API / az CLI since the
    # AzureRM provider may not yet support it in the ingress block.
    # Port 4317 (internal-only) must be added after terraform apply:
    #   az rest --method PATCH --url ".../containerApps/SphereVoice-...-observability?api-version=2024-03-01" \
    #     --body '{"properties":{"configuration":{"ingress":{"additionalPortMappings":[{"external":false,"targetPort":4317}]}}}}'

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  registry {
    server               = var.acr_login_server
    username             = var.acr_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = var.acr_password
  }

  tags = merge(var.tags, {
    module = "observability"
  })
}

# ── Outputs ─────────────────────────────────────────────────
output "grafana_url" {
  value       = "https://${azurerm_container_app.observability.ingress[0].fqdn}"
  description = "Grafana dashboard URL"
}

output "otel_endpoint" {
  value       = "http://SphereVoice-${var.environment}-observability:4317"
  description = "OTLP gRPC endpoint for backend to send traces"
}

output "storage_account_name" {
  value = azurerm_storage_account.observability.name
}
