"""Signal Propagation Matrix — Structural Schemas.

Request/response models for propagation campaign orchestration, target manifestation, 
and temporal vector telemetry synthesis.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Propagation Campaign Substrates ──────────────────────────


class SignalPropagationIntent(BaseModel):
    """Intent to manifest a new signal propagation campaign."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    node_sig: uuid.UUID = Field(..., alias="agent_id")
    ingress_origin: str = Field("crm", alias="source_type")
    ingress_config: dict[str, Any] = Field(default_factory=dict, alias="source_config")
    variable_matrix: dict[str, Any] = Field(default_factory=dict, alias="variable_mapping")
    egress_matrix: dict[str, Any] = Field(default_factory=dict, alias="writeback_mapping")
    transmission_origin: str | None = Field(None, alias="from_number")
    concurrency_ceiling: int = Field(default=5, ge=1, le=100, alias="max_concurrent")
    signal_density_per_min: int = Field(default=10, ge=1, le=60, alias="calls_per_minute")
    retry_ceiling: int = Field(default=2, ge=0, le=10, alias="max_retries")
    retry_horizon_min: int = Field(default=60, ge=1, alias="retry_delay_minutes")
    scheduled_horizon: datetime | None = Field(None, alias="scheduled_at")
    operational_window: dict[str, Any] | None = Field(None, alias="calling_window")
    variant_node_sig: uuid.UUID | None = Field(None, alias="variant_agent_id")
    split_ratio_percent: int = Field(default=50, ge=0, le=100, alias="ab_split_percent")


class SignalPropagationMutation(BaseModel):
    """Mutation intent for an existing signal propagation campaign state."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    node_sig: uuid.UUID | None = Field(default=None, alias="agent_id")
    ingress_origin: str | None = Field(default=None, alias="source_type")
    ingress_config: dict[str, Any] | None = Field(default=None, alias="source_config")
    variable_matrix: dict[str, Any] | None = Field(default=None, alias="variable_mapping")
    egress_matrix: dict[str, Any] | None = Field(default=None, alias="writeback_mapping")
    transmission_origin: str | None = Field(default=None, alias="from_number")
    concurrency_ceiling: int | None = Field(default=None, ge=1, le=100, alias="max_concurrent")
    signal_density_per_min: int | None = Field(default=None, ge=1, le=60, alias="calls_per_minute")
    retry_ceiling: int | None = Field(default=None, ge=0, le=10, alias="max_retries")
    retry_horizon_min: int | None = Field(default=None, ge=1, alias="retry_delay_minutes")
    scheduled_horizon: datetime | None = Field(None, alias="scheduled_at")
    operational_window: dict[str, Any] | None = Field(None, alias="calling_window")
    variant_node_sig: uuid.UUID | None = Field(None, alias="variant_agent_id")
    split_ratio_percent: int | None = Field(default=None, ge=0, le=100, alias="ab_split_percent")


class SignalPropagationManifest(BaseModel):
    """State snapshot of a manifested signal propagation campaign."""

    id: uuid.UUID
    nexus_sig: uuid.UUID = Field(..., alias="tenant_id")
    name: str
    description: str | None
    node_sig: uuid.UUID = Field(..., alias="agent_id")
    operational_phase: str = Field(..., alias="status")
    ingress_origin: str = Field(..., alias="source_type")
    ingress_config: dict[str, Any] = Field(..., alias="source_config")
    variable_matrix: dict[str, Any] = Field(..., alias="variable_mapping")
    egress_matrix: dict[str, Any] = Field(..., alias="writeback_mapping")
    transmission_origin: str | None = Field(..., alias="from_number")
    concurrency_ceiling: int = Field(..., alias="max_concurrent")
    signal_density_per_min: int = Field(..., alias="calls_per_minute")
    retry_ceiling: int = Field(..., alias="max_retries")
    retry_horizon_min: int = Field(..., alias="retry_delay_minutes")
    scheduled_horizon: datetime | None = Field(..., alias="scheduled_at")
    operational_window: dict[str, Any] | None = Field(..., alias="calling_window")
    variant_node_sig: uuid.UUID | None = Field(..., alias="variant_agent_id")
    split_ratio_percent: int = Field(..., alias="ab_split_percent")
    total_targets: int = Field(..., alias="total_contacts")
    terminal_signals: int = Field(..., alias="completed_calls")
    successful_signals: int = Field(..., alias="successful_calls")
    voided_signals: int = Field(..., alias="failed_calls")
    creator_sig: uuid.UUID | None = Field(..., alias="created_by")
    manifested_at: datetime = Field(..., alias="created_at")
    updated_at: datetime

    model_config = {"from_attributes": True}


class PropagationCampaignSnapshot(BaseModel):
    """Aggregated snapshot for propagation campaign cataloging."""

    id: uuid.UUID
    name: str
    phase: str = Field(..., alias="status")
    node_sig: uuid.UUID = Field(..., alias="agent_id")
    variant_node_sig: uuid.UUID | None = Field(None, alias="variant_agent_id")
    split_ratio: int = Field(50, alias="ab_split_percent")
    target_count: int = Field(..., alias="total_contacts")
    terminal_count: int = Field(..., alias="completed_calls")
    scheduled_horizon: datetime | None = Field(None, alias="scheduled_at")
    manifested_at: datetime = Field(..., alias="created_at")

    model_config = {"from_attributes": True}


class PropagationCampaignListWrapper(BaseModel):
    """Linear registry audit of propagation campaigns."""

    campaigns: list[PropagationCampaignSnapshot] = Field(..., alias="campaigns")
    total: int


# ── Propagation Target Schemas ─────────────────────────────


class PropagationTargetIntent(BaseModel):
    """Intent to manifest a single propagation target within a campaign."""

    transmission_uri: str = Field(..., min_length=1, max_length=30, alias="phone_number")
    external_record_sig: str | None = Field(None, alias="crm_record_id")
    external_module_sig: str | None = Field(None, alias="crm_module")
    target_metadata: dict[str, Any] = Field(default_factory=dict, alias="contact_data")
    attempt_ceiling: int = Field(default=3, ge=1, le=10, alias="max_attempts")
    priority_weight: int = Field(default=0, ge=0, alias="priority")


class PropagationTargetManifest(BaseModel):
    """State capture of an established propagation target."""

    id: uuid.UUID
    nexus_sig: uuid.UUID = Field(..., alias="tenant_id")
    campaign_sig: uuid.UUID = Field(..., alias="campaign_id")
    transmission_uri: str = Field(..., alias="phone_number")
    external_record_sig: str | None = Field(None, alias="crm_record_id")
    external_module_sig: str | None = Field(None, alias="crm_module")
    target_metadata: dict[str, Any] = Field(..., alias="contact_data")
    operational_phase: str = Field(..., alias="status")
    signal_sig: uuid.UUID | None = Field(None, alias="call_id")
    assigned_node_sig: uuid.UUID | None = Field(None, alias="assigned_agent_id")
    accumulation_count: int = Field(..., alias="attempt_count")
    attempt_ceiling: int = Field(..., alias="max_attempts")
    next_activation_horizon: datetime | None = Field(None, alias="next_retry_at")
    synthesized_data: dict[str, Any] | None = Field(None, alias="extracted_data")
    egress_status: str | None = Field(None, alias="writeback_status")
    egress_fault: str | None = Field(None, alias="writeback_error")
    interface_outcomes: list[dict[str, Any]] | None = Field(None, alias="tool_results")
    priority_weight: int = Field(..., alias="priority")
    manifested_at: datetime = Field(..., alias="created_at")
    updated_at: datetime

    model_config = {"from_attributes": True}


class PropagationTargetSnapshot(BaseModel):
    """Aggregated snapshot for propagation target auditing."""

    id: uuid.UUID
    transmission_uri: str = Field(..., alias="phone_number")
    external_record_sig: str | None = Field(None, alias="crm_record_id")
    external_module_sig: str | None = Field(None, alias="crm_module")
    target_metadata: dict[str, Any] = Field(default_factory=dict, alias="contact_data")
    phase: str = Field(..., alias="status")
    accumulation_count: int = Field(..., alias="attempt_count")
    signal_sig: uuid.UUID | None = Field(None, alias="call_id")
    manifested_at: datetime = Field(..., alias="created_at")

    model_config = {"from_attributes": True}


class PropagationTargetListWrapper(BaseModel):
    """Linear audit trail of propagation targets."""

    targets: list[PropagationTargetSnapshot] = Field(..., alias="contacts")
    total: int


# ── Operational Ingress & Probing ───────────────────────────


class IngressManifestRequest(BaseModel):
    """Batch intent for target manifestation via architectural ingress."""

    targets: list[PropagationTargetIntent] = Field(..., alias="contacts")


class IngressManifestOutcome(BaseModel):
    """Outcome of an architectural ingress manifestation event."""

    manifested: int = Field(..., alias="loaded")
    voided: int = Field(..., alias="skipped")


class IngressStreamProbing(BaseModel):
    """Probing request for linear stream data synthesis from CSV/Ingress."""

    structural_mapping: dict[str, str] = Field(
        ...,
        description="Maps SignalStream substrate fields to ingress source indices",
        alias="column_mapping"
    )


class IngressStreamOutcome(BaseModel):
    """Outcome of a linear stream data synthesis event."""

    manifested: int = Field(..., alias="loaded")
    voided: int = Field(..., alias="skipped")
    faulty_vectors: list[dict[str, Any]] = Field(default_factory=list, alias="invalid_rows")
