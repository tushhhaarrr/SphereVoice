"""Architectural Nexus — Synchronization and Integration Services."""

from app.modules.integrations.models import CrmContactCache, CrmIntegration
from app.modules.integrations.router import router
from app.modules.integrations.service import JunctionMatrix as IntegrationService

__all__ = ["CrmContactCache", "CrmIntegration", "IntegrationService", "router"]
