# SphereVoice — Azure Service Bus Module
#
# Provisions a Service Bus namespace + queues for Celery task
# routing.  Dev uses Basic SKU, prod uses Standard (sessions,
# dead-letter, duplicate detection).

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
  description = "Service Bus SKU: Basic (dev) or Standard (prod)"
}

variable "queue_prefix" {
  type        = string
  default     = "SphereVoice"
  description = "Prefix for all queue names"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ── Namespace ───────────────────────────────────────────────
resource "azurerm_servicebus_namespace" "main" {
  name                          = "SphereVoice-${var.environment}-servicebus"
  location                      = var.location
  resource_group_name           = var.rg_name
  sku                           = var.sku
  minimum_tls_version           = "1.2"
  public_network_access_enabled = var.environment != "production"

  tags = merge(var.tags, {
    module = "servicebus"
  })
}

# ── Celery default queue ────────────────────────────────────
resource "azurerm_servicebus_queue" "celery_default" {
  name         = "${var.queue_prefix}-celery"
  namespace_id = azurerm_servicebus_namespace.main.id

  # Messages survive restarts — main advantage over Redis broker
  max_delivery_count = 10
  lock_duration      = "PT5M"

  # 14-day TTL (Basic max); prevents unbounded queue growth
  default_message_ttl = "P14D"

  # Dead-letter on expiration so failed tasks are inspectable
  dead_lettering_on_message_expiration = true
}

# ── Post-call extraction queue ──────────────────────────────
resource "azurerm_servicebus_queue" "post_call" {
  name         = "${var.queue_prefix}-post-call"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 5
  lock_duration                        = "PT5M"
  default_message_ttl                  = "P7D"
  dead_lettering_on_message_expiration = true
}

# ── Embeddings queue ────────────────────────────────────────
resource "azurerm_servicebus_queue" "embeddings" {
  name         = "${var.queue_prefix}-embeddings"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 5
  lock_duration                        = "PT10M"
  default_message_ttl                  = "P7D"
  dead_lettering_on_message_expiration = true
}

# ── Webhook delivery queue ──────────────────────────────────
resource "azurerm_servicebus_queue" "webhook_delivery" {
  name         = "${var.queue_prefix}-webhook-delivery"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 10
  lock_duration                        = "PT2M"
  default_message_ttl                  = "P3D"
  dead_lettering_on_message_expiration = true
}

# ── CRM sync queue ─────────────────────────────────────────
resource "azurerm_servicebus_queue" "crm_sync" {
  name         = "${var.queue_prefix}-crm-sync"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 5
  lock_duration                        = "PT5M"
  default_message_ttl                  = "P7D"
  dead_lettering_on_message_expiration = true
}

# ── Website crawl queue ─────────────────────────────────────
resource "azurerm_servicebus_queue" "website_crawl" {
  name         = "${var.queue_prefix}-website-crawl"
  namespace_id = azurerm_servicebus_namespace.main.id

  max_delivery_count                   = 3
  lock_duration                        = "PT10M"
  default_message_ttl                  = "P7D"
  dead_lettering_on_message_expiration = true
}

# ── Outputs ─────────────────────────────────────────────────
output "namespace_id" {
  value = azurerm_servicebus_namespace.main.id
}

output "namespace_name" {
  value = azurerm_servicebus_namespace.main.name
}

output "connection_string" {
  value     = azurerm_servicebus_namespace.main.default_primary_connection_string
  sensitive = true
}

output "primary_key" {
  value     = azurerm_servicebus_namespace.main.default_primary_key
  sensitive = true
}
