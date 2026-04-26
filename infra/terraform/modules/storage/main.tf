# SphereVoice — Storage Module (Azure Blob Storage / S3-compatible)

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

variable "account_tier" {
  type        = string
  default     = "Standard"
  description = "Storage account tier"
}

variable "replication_type" {
  type        = string
  default     = "LRS"
  description = "Storage replication type (LRS for dev, GRS for prod)"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ── Storage Account ─────────────────────────────────────────
resource "azurerm_storage_account" "main" {
  name                          = "SphereVoice${var.environment}storage"
  resource_group_name           = var.rg_name
  location                      = var.location
  account_tier                  = var.account_tier
  account_replication_type      = var.replication_type
  min_tls_version               = "TLS1_2"
  allow_nested_items_to_be_public = false

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 7
    }

    container_delete_retention_policy {
      days = 7
    }
  }

  tags = merge(var.tags, {
    module = "storage"
  })
}

# ── Blob Containers ─────────────────────────────────────────
resource "azurerm_storage_container" "recordings" {
  name                  = "recordings"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "knowledge_base" {
  name                  = "knowledge-base"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

# ── Lifecycle policy: auto-delete old recordings ────────────
resource "azurerm_storage_management_policy" "retention" {
  storage_account_id = azurerm_storage_account.main.id

  rule {
    name    = "recordings-retention"
    enabled = true

    filters {
      prefix_match = ["recordings/"]
      blob_types   = ["blockBlob"]
    }

    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = 90
      }
    }
  }
}

# ── Outputs ─────────────────────────────────────────────────
output "storage_account_id" {
  value = azurerm_storage_account.main.id
}

output "storage_account_name" {
  value = azurerm_storage_account.main.name
}

output "primary_blob_endpoint" {
  value = azurerm_storage_account.main.primary_blob_endpoint
}

output "primary_access_key" {
  value     = azurerm_storage_account.main.primary_access_key
  sensitive = true
}

output "recordings_container" {
  value = azurerm_storage_container.recordings.name
}

output "knowledge_base_container" {
  value = azurerm_storage_container.knowledge_base.name
}
