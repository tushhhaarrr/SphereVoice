# SphereVoice — Monitoring Module (Azure Monitor, App Insights, Log Analytics)

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

variable "retention_in_days" {
  type        = number
  default     = 30
  description = "Log Analytics workspace retention period"
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ── Log Analytics Workspace ─────────────────────────────────
resource "azurerm_log_analytics_workspace" "main" {
  name                = "SphereVoice-${var.environment}-logs"
  location            = var.location
  resource_group_name = var.rg_name
  sku                 = "PerGB2018"
  retention_in_days   = var.retention_in_days

  tags = merge(var.tags, {
    module = "monitoring"
  })
}

# ── Application Insights ────────────────────────────────────
resource "azurerm_application_insights" "main" {
  name                = "SphereVoice-${var.environment}-appinsights"
  location            = var.location
  resource_group_name = var.rg_name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"

  tags = merge(var.tags, {
    module = "monitoring"
  })
}

# ── Action Group for alerts ─────────────────────────────────
resource "azurerm_monitor_action_group" "critical" {
  name                = "SphereVoice-${var.environment}-critical-alerts"
  resource_group_name = var.rg_name
  short_name          = "SphereVoicecrit"

  tags = merge(var.tags, {
    module = "monitoring"
  })
}

# ── Alert: High error rate ──────────────────────────────────
resource "azurerm_monitor_metric_alert" "high_error_rate" {
  name                = "SphereVoice-${var.environment}-high-5xx-rate"
  resource_group_name = var.rg_name
  scopes              = [azurerm_application_insights.main.id]
  description         = "Alert when 5xx error rate exceeds threshold"
  severity            = 1
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "Microsoft.Insights/components"
    metric_name      = "requests/failed"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 10
  }

  action {
    action_group_id = azurerm_monitor_action_group.critical.id
  }

  tags = merge(var.tags, {
    module = "monitoring"
  })
}

# ── Scheduled Query Alert: High Call Failure Rate ───────────
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "high_call_failure_rate" {
  name                = "SphereVoice-${var.environment}-high-call-failure-rate"
  location            = var.location
  resource_group_name = var.rg_name
  description         = "Call failure rate exceeds 10% over 5 minutes"
  severity            = 1
  enabled             = true

  scopes                = [azurerm_log_analytics_workspace.main.id]
  evaluation_frequency  = "PT5M"
  window_duration       = "PT15M"
  target_resource_types = ["Microsoft.OperationalInsights/workspaces"]

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where Log_s has '"event":"call_ended"' or Log_s has '"event":"call_failed"'
      | extend parsed = parse_json(Log_s)
      | extend status = tostring(parsed.status)
      | summarize total = count(), failed = countif(status == "failed") by bin(TimeGenerated, 5m)
      | where total > 0
      | extend failure_rate = todouble(failed) / todouble(total)
      | where failure_rate > 0.1
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.critical.id]
  }

  tags = merge(var.tags, { module = "monitoring" })
}

# ── Scheduled Query Alert: Pipeline Circuit Breaker ─────────
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "pipeline_circuit_breaker" {
  name                = "SphereVoice-${var.environment}-pipeline-circuit-breaker"
  location            = var.location
  resource_group_name = var.rg_name
  description         = "Pipeline circuit breaker activated — provider in error loop"
  severity            = 1
  enabled             = true

  scopes                = [azurerm_log_analytics_workspace.main.id]
  evaluation_frequency  = "PT5M"
  window_duration       = "PT5M"
  target_resource_types = ["Microsoft.OperationalInsights/workspaces"]

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where Log_s has '"event":"circuit_breaker_tripped"'
      | summarize breaker_count = count() by bin(TimeGenerated, 5m)
      | where breaker_count > 0
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.critical.id]
  }

  tags = merge(var.tags, { module = "monitoring" })
}

# ── Scheduled Query Alert: Pipeline Init Failures ───────────
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "pipeline_init_failures" {
  name                = "SphereVoice-${var.environment}-pipeline-init-failures"
  location            = var.location
  resource_group_name = var.rg_name
  description         = "New calls failing to initialize pipelines"
  severity            = 1
  enabled             = true

  scopes                = [azurerm_log_analytics_workspace.main.id]
  evaluation_frequency  = "PT5M"
  window_duration       = "PT15M"
  target_resource_types = ["Microsoft.OperationalInsights/workspaces"]

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where Log_s has '"event":"pipeline_init_failed"'
      | summarize init_failures = count() by bin(TimeGenerated, 5m)
      | where init_failures > 2
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.critical.id]
  }

  tags = merge(var.tags, { module = "monitoring" })
}

# ── Scheduled Query Alert: High Pipeline Retry Rate ─────────
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "high_pipeline_retries" {
  name                = "SphereVoice-${var.environment}-high-pipeline-retries"
  location            = var.location
  resource_group_name = var.rg_name
  description         = "Pipeline retry rate elevated — transient provider errors"
  severity            = 2
  enabled             = true

  scopes                = [azurerm_log_analytics_workspace.main.id]
  evaluation_frequency  = "PT5M"
  window_duration       = "PT15M"
  target_resource_types = ["Microsoft.OperationalInsights/workspaces"]

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where Log_s has '"event":"pipeline_retry"'
      | summarize retry_count = count() by bin(TimeGenerated, 5m)
      | where retry_count > 5
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.critical.id]
  }

  tags = merge(var.tags, { module = "monitoring" })
}

# ── Scheduled Query Alert: No Active Calls Despite Traffic ──
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "no_active_calls" {
  name                = "SphereVoice-${var.environment}-no-active-calls"
  location            = var.location
  resource_group_name = var.rg_name
  description         = "No active calls despite recent traffic — possible systemic failure"
  severity            = 2
  enabled             = true

  scopes                = [azurerm_log_analytics_workspace.main.id]
  evaluation_frequency  = "PT15M"
  window_duration       = "PT1H"
  target_resource_types = ["Microsoft.OperationalInsights/workspaces"]

  criteria {
    query                   = <<-KQL
      let recent_calls = ContainerAppConsoleLogs_CL
        | where TimeGenerated > ago(1h)
        | where Log_s has '"event":"call_started"'
        | summarize call_count = count();
      let active_now = ContainerAppConsoleLogs_CL
        | where TimeGenerated > ago(15m)
        | where Log_s has '"event":"call_started"'
        | summarize active = count();
      recent_calls
      | join kind=cross active_now on 1==1
      | where call_count > 10 and active == 0
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.critical.id]
  }

  tags = merge(var.tags, { module = "monitoring" })
}

# ── Scheduled Query Alert: High HTTP Latency ────────────────
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "high_http_latency" {
  name                = "SphereVoice-${var.environment}-high-http-latency"
  location            = var.location
  resource_group_name = var.rg_name
  description         = "HTTP P95 latency above 2 seconds"
  severity            = 2
  enabled             = true

  scopes                = [azurerm_log_analytics_workspace.main.id]
  evaluation_frequency  = "PT5M"
  window_duration       = "PT15M"
  target_resource_types = ["Microsoft.OperationalInsights/workspaces"]

  criteria {
    query                   = <<-KQL
      ContainerAppConsoleLogs_CL
      | where Log_s has '"event":"http_request"'
      | extend parsed = parse_json(Log_s)
      | extend duration_ms = todouble(parsed.duration_ms)
      | summarize p95 = percentile(duration_ms, 95) by bin(TimeGenerated, 5m)
      | where p95 > 2000
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0
  }

  action {
    action_groups = [azurerm_monitor_action_group.critical.id]
  }

  tags = merge(var.tags, { module = "monitoring" })
}

# ── Outputs ─────────────────────────────────────────────────
output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.main.id
}

output "log_analytics_workspace_key" {
  value     = azurerm_log_analytics_workspace.main.primary_shared_key
  sensitive = true
}

output "app_insights_id" {
  value = azurerm_application_insights.main.id
}

output "app_insights_instrumentation_key" {
  value     = azurerm_application_insights.main.instrumentation_key
  sensitive = true
}

output "app_insights_connection_string" {
  value     = azurerm_application_insights.main.connection_string
  sensitive = true
}
