# SphereVoice — Redis Module (Azure Cache for Redis)

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
  default     = "Basic"
  description = "Redis SKU (Basic for dev, Standard for prod)"
}

variable "family" {
  type        = string
  default     = "C"
  description = "Redis family (C = Basic/Standard, P = Premium)"
}

variable "capacity" {
  type        = number
  default     = 0
  description = "Cache size (0 = 250MB for Basic, 1 = 1GB, etc.)"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ── Azure Cache for Redis ───────────────────────────────────
resource "azurerm_redis_cache" "main" {
  name                          = "SphereVoice-${var.environment}-redis"
  location                      = var.location
  resource_group_name           = var.rg_name
  capacity                      = var.capacity
  family                        = var.family
  sku_name                      = var.sku_name
  minimum_tls_version           = "1.2"
  public_network_access_enabled = var.environment != "production"

  redis_configuration {
    maxmemory_policy = "allkeys-lru"
  }

  tags = merge(var.tags, {
    module = "redis"
  })
}

# ── Firewall rule: allow Azure services ─────────────────────
resource "azurerm_redis_firewall_rule" "allow_azure" {
  name                = "AllowAzureServices"
  redis_cache_name    = azurerm_redis_cache.main.name
  resource_group_name = var.rg_name
  start_ip            = "0.0.0.0"
  end_ip              = "0.0.0.0"
}

# ── Outputs ─────────────────────────────────────────────────
output "redis_id" {
  value = azurerm_redis_cache.main.id
}

output "redis_hostname" {
  value = azurerm_redis_cache.main.hostname
}

output "redis_port" {
  value = azurerm_redis_cache.main.ssl_port
}

output "redis_primary_key" {
  value     = azurerm_redis_cache.main.primary_access_key
  sensitive = true
}

output "redis_connection_string" {
  value     = "rediss://:${azurerm_redis_cache.main.primary_access_key}@${azurerm_redis_cache.main.hostname}:${azurerm_redis_cache.main.ssl_port}/0"
  sensitive = true
}
