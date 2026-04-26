terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }

  backend "azurerm" {
    resource_group_name  = "SphereVoice-tfstate-rg"
    storage_account_name = "SphereVoicetfstatedev"
    container_name       = "tfstate"
    key                  = "dev.terraform.tfstate"
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
}

data "azurerm_client_config" "current" {}

# ── Variables ───────────────────────────────────────────────
variable "environment" {
  default = "dev"
}

variable "location" {
  default = "eastus"
}

variable "project" {
  default = "SphereVoice"
}

variable "db_admin_password" {
  type      = string
  sensitive = true
}

# ── Resource Group ──────────────────────────────────────────
resource "azurerm_resource_group" "main" {
  name     = "${var.project}-${var.environment}-rg"
  location = var.location

  tags = local.tags
}

# ── Local values ────────────────────────────────────────────
locals {
  tags = {
    project     = var.project
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ── Database (PostgreSQL 15 + pgvector) ─────────────────────
module "database" {
  source         = "../../modules/database"
  environment    = var.environment
  location       = var.location
  rg_name        = azurerm_resource_group.main.name
  sku_name       = "B_Standard_B1ms"
  storage_mb     = 32768
  admin_password = var.db_admin_password
  tags           = local.tags
}

# ── Redis (Azure Cache — pub/sub + rate limiting only) ────
module "redis" {
  source      = "../../modules/redis"
  environment = var.environment
  location    = var.location
  rg_name     = azurerm_resource_group.main.name
  sku_name    = "Basic"
  capacity    = 0
  tags        = local.tags
}

# ── Service Bus (Celery broker — durable task queues) ─────
module "servicebus" {
  source       = "../../modules/servicebus"
  environment  = var.environment
  location     = var.location
  rg_name      = azurerm_resource_group.main.name
  sku          = "Basic"
  queue_prefix = "SphereVoice"
  tags         = local.tags
}

# ── Storage (Azure Blob / S3-compatible) ────────────────────
module "storage" {
  source           = "../../modules/storage"
  environment      = var.environment
  location         = var.location
  rg_name          = azurerm_resource_group.main.name
  replication_type = "LRS"
  tags             = local.tags
}

# ── ACR (Azure Container Registry) ─────────────────────────
module "acr" {
  source      = "../../modules/acr"
  environment = var.environment
  location    = var.location
  rg_name     = azurerm_resource_group.main.name
  sku         = "Basic"
  tags        = local.tags
}

# ── Key Vault ──────────────────────────────────────────────
module "keyvault" {
  source           = "../../modules/keyvault"
  environment      = var.environment
  location         = var.location
  rg_name          = azurerm_resource_group.main.name
  tenant_id        = data.azurerm_client_config.current.tenant_id
  admin_object_ids = [data.azurerm_client_config.current.object_id]
  tags             = local.tags
}

# ── Monitoring (Log Analytics + App Insights) ───────────────
module "monitoring" {
  source            = "../../modules/monitoring"
  environment       = var.environment
  location          = var.location
  rg_name           = azurerm_resource_group.main.name
  retention_in_days = 30
  tags              = local.tags
}

# ── Container Apps (backend, frontend, celery) ──────────────
# module "container_apps" {
#   source      = "../../modules/container_apps"
#   environment = var.environment
#   location    = var.location
#   rg_name     = azurerm_resource_group.main.name
#   # Wired after first container image push
# }

# ── VM (LiveKit Server) ────────────────────────────────────
# module "vm" {
#   source      = "../../modules/vm"
#   environment = var.environment
#   location    = var.location
#   rg_name     = azurerm_resource_group.main.name
#   # Wired in Phase 4
# }

# ── Outputs ─────────────────────────────────────────────────
output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "database_connection_string" {
  value     = module.database.connection_string
  sensitive = true
}

output "database_fqdn" {
  value = module.database.server_fqdn
}

output "redis_connection_string" {
  value     = module.redis.redis_connection_string
  sensitive = true
}

output "redis_hostname" {
  value = module.redis.redis_hostname
}

output "servicebus_connection_string" {
  value     = module.servicebus.connection_string
  sensitive = true
}

output "servicebus_namespace" {
  value = module.servicebus.namespace_name
}

output "storage_blob_endpoint" {
  value = module.storage.primary_blob_endpoint
}

output "acr_login_server" {
  value = module.acr.acr_login_server
}

output "keyvault_uri" {
  value = module.keyvault.key_vault_uri
}

output "app_insights_connection_string" {
  value     = module.monitoring.app_insights_connection_string
  sensitive = true
}
