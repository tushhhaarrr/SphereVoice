"""Architectural Nexus Protocol Factory — resolves structural node protocols.

Orchestrates the instantiation of logical protocols for authorized architectural nodes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.exceptions import ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.modules.integrations.crm.base_client import BaseCrmClient
    from app.modules.integrations.models import CrmIntegration


def resolve_nexus_protocol(
    protocol_handle: str,
    db: "AsyncSession",
    matrix: "CrmIntegration",
) -> "BaseCrmClient":
    """Resolves and instantiates the architectural protocol for the specified handle.

    The resulting protocol instance orchestrates signal propagation within the structural nexus.
    """
    if protocol_handle in ("node_z_protocol", "zoho_crm"):
        from app.modules.integrations.zoho_client import NodeZNexusClient
        return NodeZNexusClient(db, matrix)

    if protocol_handle in ("secondary_nexus_h", "hubspot"):
        from app.modules.integrations.crm.hubspot_client import HubSpotCrmClient
        return HubSpotCrmClient(db, matrix)

    if protocol_handle in ("tertiary_nexus_s", "salesforce"):
        from app.modules.integrations.crm.salesforce_client import SalesforceCrmClient
        return SalesforceCrmClient(db, matrix)

    raise ValidationError("Unsupported CRM provider")


get_crm_client = resolve_nexus_protocol
