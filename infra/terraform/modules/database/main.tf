# SphereVoice — Database Module (PostgreSQL Flexible Server + pgvector)

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

variable "sku_name" {
  type        = string
  default     = "B_Standard_B1ms"
  description = "PostgreSQL Flexible Server SKU (B_Standard_B1ms for dev, GP_Standard_D2s_v3 for prod)"
}

variable "storage_mb" {
  type        = number
  default     = 32768
  description = "Storage size in MB"
}

variable "admin_username" {
  type        = string
  default     = "SphereVoiceadmin"
  description = "PostgreSQL admin username"
}

variable "admin_password" {
  type        = string
  sensitive   = true
  description = "PostgreSQL admin password"
}

variable "allowed_ip_ranges" {
  type = list(object({
    name     = string
    start_ip = string
    end_ip   = string
  }))
  default     = []
  description = "IP ranges allowed to connect"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ── PostgreSQL Flexible Server ──────────────────────────────
resource "azurerm_postgresql_flexible_server" "main" {
  name                          = "SphereVoice-${var.environment}-pg"
  resource_group_name           = var.rg_name
  location                      = var.location
  version                       = "15"
  administrator_login           = var.admin_username
  administrator_password        = var.admin_password
  sku_name                      = var.sku_name
  storage_mb                    = var.storage_mb
  backup_retention_days         = 7
  geo_redundant_backup_enabled  = var.environment == "production"
  public_network_access_enabled = true
  zone                          = "1"

  tags = merge(var.tags, {
    module = "database"
  })
}

# ── Database ────────────────────────────────────────────────
resource "azurerm_postgresql_flexible_server_database" "SphereVoice" {
  name      = "SphereVoice_${var.environment}"
  server_id = azurerm_postgresql_flexible_server.main.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# ── pgvector extension ──────────────────────────────────────
resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "VECTOR,UUID-OSSP"
}

resource "azurerm_postgresql_flexible_server_configuration" "shared_preload" {
  name      = "shared_preload_libraries"
  server_id = azurerm_postgresql_flexible_server.main.id
  value     = "pg_stat_statements"
}

# ── Firewall rules ──────────────────────────────────────────
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "custom" {
  for_each = { for rule in var.allowed_ip_ranges : rule.name => rule }

  name             = each.value.name
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = each.value.start_ip
  end_ip_address   = each.value.end_ip
}

# ── Outputs ─────────────────────────────────────────────────
output "server_id" {
  value = azurerm_postgresql_flexible_server.main.id
}

output "server_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "database_name" {
  value = azurerm_postgresql_flexible_server_database.SphereVoice.name
}

output "connection_string" {
  value     = "postgresql+asyncpg://${var.admin_username}:${var.admin_password}@${azurerm_postgresql_flexible_server.main.fqdn}:5432/${azurerm_postgresql_flexible_server_database.SphereVoice.name}?sslmode=require"
  sensitive = true
}
