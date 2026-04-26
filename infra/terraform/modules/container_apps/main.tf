# SphereVoice — Container Apps Module (Azure Container Apps)
# Implemented in Phase 1

variable "environment" {
  type = string
}

variable "location" {
  type = string
}

variable "rg_name" {
  type = string
}

# resource "azurerm_container_app_environment" "main" { ... }
# resource "azurerm_container_app" "backend" { ... }
# resource "azurerm_container_app" "frontend" { ... }
# resource "azurerm_container_app" "celery_worker" { ... }
