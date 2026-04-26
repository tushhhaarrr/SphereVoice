# SphereVoice — ACR Module (Azure Container Registry)

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

variable "sku" {
  type        = string
  default     = "Basic"
  description = "ACR SKU (Basic for dev, Standard for prod)"
}

variable "admin_enabled" {
  type        = bool
  default     = true
  description = "Enable admin user for docker push/pull"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ── Azure Container Registry ───────────────────────────────
resource "azurerm_container_registry" "main" {
  name                = "SphereVoice${var.environment}acr"
  resource_group_name = var.rg_name
  location            = var.location
  sku                 = var.sku
  admin_enabled       = var.admin_enabled

  tags = merge(var.tags, {
    module = "acr"
  })
}

# ── Outputs ─────────────────────────────────────────────────
output "acr_id" {
  value = azurerm_container_registry.main.id
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "acr_admin_username" {
  value     = azurerm_container_registry.main.admin_username
  sensitive = true
}

output "acr_admin_password" {
  value     = azurerm_container_registry.main.admin_password
  sensitive = true
}
