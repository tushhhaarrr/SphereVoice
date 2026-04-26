"""Architectural Interface Registry — SignalStream substrate logic models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.database import Base


class ArchitecturalInterface(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    """A reusable cross-substrate interface that can be bound to one or more processing nodes.

    Interfaces are domain-scoped and optionally linked to a substrate integration
    (e.g. WhatsApp, email, calendar). When a manifold is active, the cognitive layer
    can invoke any interfaces bound to the active processing node.
    """

    __tablename__ = "architectural_interfaces"

    integration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_integrations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Architectural Identification
    interface_label: Mapped[str] = mapped_column("name", String(100), nullable=False)
    display_label: Mapped[str] = mapped_column("display_name", String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Interface category (messaging | email | calendar | crm | custom)
    category: Mapped[str] = mapped_column(String(50), nullable=False)

    # JSON Schema for interface parameters (passed to cognitive layer)
    parameters_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # Execution protocol (integration | webhook)
    execution_protocol: Mapped[str] = mapped_column(
        "execution_type", String(30), nullable=False, server_default=text("'integration'")
    )

    # Protocol configuration (e.g. webhook URL, integration-specific sig)
    protocol_config: Mapped[dict[str, Any]] = mapped_column(
        "execution_config", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # Nodal Bindings
    nodal_bindings: Mapped[list["NodalInterfaceBinding"]] = relationship(
        "NodalInterfaceBinding", back_populates="interface", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ArchitecturalInterface id={self.id} label={self.interface_label!r} category={self.category}>"

    def synthesize_cognitive_trigger(self) -> dict[str, Any]:
        """Synthesize a cognitive layer trigger manifest (e.g. tool calling spec)."""
        config = self.protocol_config or {}
        description = self.description
        params = dict(self.parameters_schema)

        # Substrate-specific enrichment logic mirrors previous implementation
        # (Columns, instructions, duration info, etc.)
        
        return {
            "type": "function",
            "function": {
                "name": self.interface_label,
                "description": description,
                "parameters": params,
            },
        }


class NodalInterfaceBinding(Base):
    """Join table: maps architectural interfaces to processing nodes."""

    __tablename__ = "nodal_interface_bindings"

    node_sig: Mapped[uuid.UUID] = mapped_column(
        "agent_id",
        UUID(as_uuid=True),
        ForeignKey("processing_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    interface_sig: Mapped[uuid.UUID] = mapped_column(
        "tool_id",
        UUID(as_uuid=True),
        ForeignKey("architectural_interfaces.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Nodal-specific overrides
    binding_config: Mapped[dict[str, Any]] = mapped_column(
        "config", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # Relationships
    interface: Mapped["ArchitecturalInterface"] = relationship("ArchitecturalInterface", back_populates="nodal_bindings")

    def __repr__(self) -> str:
        return f"<NodalInterfaceBinding node={self.node_sig} interface={self.interface_sig}>"


class SynchronisationInterfaceExecution(UUIDPrimaryKeyMixin, Base):
    """Audit log for interface executions during a live synchronisation cycle."""

    __tablename__ = "synchronisation_interface_executions"

    sync_sig: Mapped[uuid.UUID] = mapped_column(
        "call_id",
        UUID(as_uuid=True),
        ForeignKey("signal_synchronisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nexus_registry.id", ondelete="CASCADE"),
        nullable=True,
    )

    interface_label: Mapped[str] = mapped_column("tool_name", String(100), nullable=False)
    interface_category: Mapped[str] = mapped_column("tool_category", String(50), nullable=False)

    # Ingress arguments from the cognitive layer
    ingress_arguments: Mapped[dict[str, Any]] = mapped_column(
        "arguments", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # Outcome result from the substrate executor
    execution_outcome: Mapped[dict[str, Any]] = mapped_column(
        "result", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # success | failed | timeout | error
    execution_status: Mapped[str] = mapped_column("status", String(20), nullable=False)
    transmission_delay_ms: Mapped[int] = mapped_column("duration_ms", Integer, nullable=False, server_default=text("0"))
    fault_sig: Mapped[str | None] = mapped_column("error", Text, nullable=True)

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_sync_interface_exec_sync", "call_id"),
        Index("idx_sync_interface_exec_domain", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<SynchronisationInterfaceExecution sync={self.sync_sig} label={self.interface_label} status={self.execution_status}>"
