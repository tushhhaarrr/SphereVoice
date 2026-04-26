# SphereVoice — VM Module (LiveKit Server on Azure B2s VM)
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

# resource "azurerm_linux_virtual_machine" "livekit" { ... }
# resource "azurerm_network_interface" "livekit" { ... }
# resource "azurerm_network_security_group" "livekit" { ... }
