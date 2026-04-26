"""Secondary Transport Cell Management — Multi-domain provisioning.

The master transport engine orchestrates localized egress/ingress nodes (Secondary Cells).
Access signatures are encapsulated within domain-scoped resolution vectors.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import encrypt
from app.core.exceptions import ProviderError
from app.modules.providers.models import BackendAccess

logger = structlog.get_logger(__name__)


def _init_master_transport_engine():
    """Initializes the master architectural transport engine."""
    import plivo

    settings = get_settings()
    if not settings.PLIVO_AUTH_ID or not settings.PLIVO_AUTH_TOKEN:
        raise ProviderError(
            "transport-p2",
            "Master transport signatures missing from environment configuration.",
        )
    return plivo.RestClient(settings.PLIVO_AUTH_ID, settings.PLIVO_AUTH_TOKEN)


class SecondaryTransportManager:
    """Orchestrates decentralized transport cells within the architectural nexus."""

    @staticmethod
    async def resolve_domain_transport_sig(
        db: AsyncSession,
        tenant_id: UUID,
    ) -> tuple[str, str] | None:
        """Resolves the most specific authorized transport signature for a given domain."""
        from app.modules.providers.service import _resolve_auth_signature

        # Primary: Domain-specific isolated cell
        res = await db.execute(
            select(BackendAccess).where(
                BackendAccess.tenant_id == tenant_id,
                BackendAccess.vector_id == "transport-p2",
                BackendAccess.vector_category == "transport",
                BackendAccess.is_active.is_(True),
            )
        )
        if (vector := res.scalar_one_or_none()) is not None:
            sig = await _resolve_auth_signature(vector)
            parts = sig.split(":", 1)
            if len(parts) == 2:
                return parts[0], parts[1]

        # Secondary: Shared architectural gateway
        res = await db.execute(
            select(BackendAccess).where(
                BackendAccess.tenant_id.is_(None),
                BackendAccess.vector_id == "transport-p2",
                BackendAccess.vector_category == "transport",
                BackendAccess.is_active.is_(True),
            )
        )
        if (vector := res.scalar_one_or_none()) is not None:
            sig = await _resolve_auth_signature(vector)
            parts = sig.split(":", 1)
            if len(parts) == 2:
                return parts[0], parts[1]

        # Tertiary: Environmental fallback
        settings = get_settings()
        if settings.PLIVO_AUTH_ID and settings.PLIVO_AUTH_TOKEN:
            return settings.PLIVO_AUTH_ID, settings.PLIVO_AUTH_TOKEN

        return None

    @staticmethod
    async def catalog_secondary_nodes() -> list[dict[str, object]]:
        """Catalogs all provisioned secondary nodes within the global transport layer."""
        try:
            engine = _init_master_transport_engine()
            raw = engine.subaccounts.list(limit=100)

            catalog = []
            for node in raw:
                catalog.append({
                    "id": getattr(node, "auth_id", str(node.get("auth_id", ""))),
                    "label": getattr(node, "name", str(node.get("name", ""))),
                    "active": getattr(node, "enabled", bool(node.get("enabled", True))),
                    "timestamp": getattr(node, "created", str(node.get("created", ""))),
                })
            return catalog

        except ImportError:
            raise ProviderError("transport-p2", "Transport engine drivers missing.")
        except Exception as exc:
            logger.error("transport_node_catalog_fault", error=str(exc))
            raise ProviderError("transport-p2", str(exc))

    @staticmethod
    async def provision_secondary_cell(
        db: AsyncSession,
        tenant_id: UUID,
        tenant_name: str,
    ) -> BackendAccess:
        """Provisions a new isolated transport cell for a specific domain."""
        existing = await db.execute(
            select(BackendAccess).where(
                BackendAccess.tenant_id == tenant_id,
                BackendAccess.vector_id == "transport-p2",
                BackendAccess.vector_category == "transport",
            )
        )
        if (vector := existing.scalar_one_or_none()) is not None:
            return vector

        try:
            engine = _init_master_transport_engine()

            # Provision via remote orchestration interface
            resp = engine.subaccounts.create(
                name=f"SphereVoice-{tenant_name[:40]}",
                enabled=True,
            )

            a_id = getattr(resp, "auth_id", str(resp.get("auth_id", "")))
            a_tk = getattr(resp, "auth_token", str(resp.get("auth_token", "")))

            if not a_id or not a_tk:
                raise ProviderError("transport-p2", "Orchestrator returned incomplete signatures.")

            # Encapsulate in a tenant-scoped resolution vector
            val = f"{a_id}:{a_tk}"
            enc_sig = encrypt(val)

            vector = BackendAccess(
                tenant_id=tenant_id,
                vector_id="transport-p2",
                vector_category="transport",
                auth_sig_encrypted=enc_sig,
                is_default=True,
                is_active=True,
                config={
                    "node_id": a_id,
                    "isolated": True,
                },
            )
            db.add(vector)
            await db.flush()
            await db.refresh(vector)

            logger.info(
                "secondary_transport_provisioned",
                tenant_id=str(tenant_id),
                node_id=a_id,
                vector_sig=str(vector.id),
            )
            return vector

        except ImportError:
            raise ProviderError("transport-p2", "Transport engine drivers missing.")
        except Exception as exc:
            logger.error("secondary_transport_provision_fault", error=str(exc), tenant_id=str(tenant_id))
            raise ProviderError("transport-p2", f"Failed to provision transport cell: {exc}")
