# SphereVoice — Key Vault Module (Azure Key Vault)

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

variable "tenant_id" {
  type        = string
  description = "Azure AD tenant ID"
}

variable "sku_name" {
  type        = string
  default     = "standard"
  description = "Key Vault SKU (standard or premium)"
}

variable "admin_object_ids" {
  type        = list(string)
  default     = []
  description = "Azure AD Object IDs that should have full access to the vault"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ── Key Vault ───────────────────────────────────────────────
resource "azurerm_key_vault" "main" {
  name                          = "SphereVoice-${var.environment}-kv"
  location                      = var.location
  resource_group_name           = var.rg_name
  tenant_id                     = var.tenant_id
  sku_name                      = var.sku_name
  soft_delete_retention_days    = 7
  purge_protection_enabled      = var.environment == "production"
  enable_rbac_authorization     = false
  public_network_access_enabled = true

  tags = merge(var.tags, {
    module = "keyvault"
  })
}

# ── Access policy for admins ────────────────────────────────
resource "azurerm_key_vault_access_policy" "admin" {
  for_each = toset(var.admin_object_ids)

  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = var.tenant_id
  object_id    = each.value

  key_permissions = [
    "Get", "List", "Create", "Delete", "Update", "Import", "Backup", "Restore", "Recover", "Purge",
  ]

  secret_permissions = [
    "Get", "List", "Set", "Delete", "Backup", "Restore", "Recover", "Purge",
  ]
}

# ── Encryption master key (AES-256 for provider key encryption) ──
resource "azurerm_key_vault_key" "encryption_master" {
  name         = "SphereVoice-encryption-master-key"
  key_vault_id = azurerm_key_vault.main.id
  key_type     = "RSA"
  key_size     = 2048

  key_opts = [
    "encrypt",
    "decrypt",
    "wrapKey",
    "unwrapKey",
  ]

  depends_on = [azurerm_key_vault_access_policy.admin]
}

# ── Outputs ─────────────────────────────────────────────────
output "key_vault_id" {
  value = azurerm_key_vault.main.id
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}

output "key_vault_name" {
  value = azurerm_key_vault.main.name
}

output "encryption_key_id" {
  value = azurerm_key_vault_key.encryption_master.id
}

output "encryption_key_version" {
  value = azurerm_key_vault_key.encryption_master.version
}
