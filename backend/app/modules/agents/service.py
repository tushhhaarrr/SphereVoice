from __future__ import annotations

import structlog
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.modules.agents.models import CognitiveNode, NodeVersion, ProbeTelemetry, BehavioralProbe
from app.modules.providers.models import BackendAccess

telemetry_logger = structlog.get_logger(__name__)


def _resolve_signature(raw: object) -> UUID | None:
    """Resolves an object or string into a structural UUID signature."""
    if isinstance(raw, UUID):
        return raw
    return UUID(raw) if isinstance(raw, str) and raw else None


class ProcessingNexusOrchestrator:
    """Operations for orchestrating architectural signal processing nodes."""

    @staticmethod
    def audit_architectural_integrity(
        structural_blocks: list[dict[str, object]],
        nodal_vectors: list[dict[str, object]],
    ) -> dict[str, object]:
        """Audits the structural integrity and nodal consistency of an architectural manifest."""
        violations: list[dict[str, str | None]] = []
        alerts: list[dict[str, str | None]] = []

        mapping: dict[str, dict[str, object]] = {
            str(c.get("id", "")): c for c in structural_blocks if str(c.get("id", ""))
        }
        known_signatures = set(mapping.keys())

        def _is_ingress(c: dict) -> bool:
            d = c.get("data", {}) if isinstance(c.get("data"), dict) else {}
            return d.get("isEntryNode") is True or d.get("isEntry") is True

        ingress_points = [c for c in structural_blocks if _is_ingress(c)]

        if not ingress_points:
            violations.append({"code": "VOID_INGRESS", "message": "Primary ingress point not established.", "component_id": None})
        elif len(ingress_points) > 1:
            violations.append({"code": "AMBIGUOUS_INGRESS", "message": "Multiple ingress thresholds detected.", "component_id": None})

        egress_points = [c for c in structural_blocks if str(c.get("type", "")) == "ending"]
        if not egress_points:
            violations.append({"code": "VOID_EGRESS", "message": "No terminal egress nodes detected.", "component_id": None})

        # Adjacency matrices
        adjacency_matrix: dict[str, set[str]] = {nid: set() for nid in known_signatures}
        inverse_matrix: dict[str, set[str]] = {nid: set() for nid in known_signatures}
        for vector in nodal_vectors:
            source, target = str(vector.get("source", "")), str(vector.get("target", ""))
            if source in adjacency_matrix and target in adjacency_matrix:
                adjacency_matrix[source].add(target)
                inverse_matrix[target].add(source)

        for sig, comp in mapping.items():
            ctype = str(comp.get("type", ""))
            if not inverse_matrix.get(sig) and not _is_ingress(comp):
                violations.append({"code": "ISOLATED_BLOCK", "message": f"Structural block '{sig}' unreachable.", "component_id": sig})
            if not adjacency_matrix.get(sig) and ctype != "ending":
                alerts.append({"code": "VECTOR_LEAK", "message": f"Structural block '{sig}' lacks subsequent vector.", "component_id": sig})

        return {
            "is_integral": len(violations) == 0,
            "violations": violations,
            "alerts": alerts,
            "block_count": len(structural_blocks),
            "vector_count": len(nodal_vectors),
        }

    @staticmethod
    async def establish_node_manifest(
        db: AsyncSession,
        tenant_id: UUID,
        label: str,
        node_class: str,
        creator_sig: UUID | None = None,
        **props: object,
    ) -> CognitiveNode:
        """Establishes a new processing node manifest in the architectural substrate."""
        cfg = get_settings()

        # Resolve nodal resource dependencies
        for target, key in [
            ("ingress_transcription_sig", "stt"),
            ("inference_matrix_sig", "llm"),
            ("egress_synthesis_sig", "tts"),
            ("transport_nexus_sig", "telephony")
        ]:
            if not props.get(target):
                provider = await ProcessingNexusOrchestrator._resolve_provider_resource(db, key, tenant_id)
                if provider:
                    props[target] = provider.id

        if props.get("inference_matrix_sig") and not props.get("inference_model_sig"):
            props["inference_model_sig"] = cfg.DEFAULT_LLM_MODEL
        if props.get("egress_synthesis_sig") and not props.get("vocal_spectral_sig"):
            props["vocal_spectral_sig"] = cfg.DEFAULT_TTS_VOICE_ID

        telemetry_logger.info("node_manifestation_resolved", domain=str(tenant_id), label=label)

        node = CognitiveNode(
            tenant_id=tenant_id,
            node_label=label,
            node_class=node_class,
            node_phase="draft",
            creator_sig=creator_sig,
            **props,
        )
        db.add(node)
        await db.flush()
        await db.refresh(node)
        return node

    @staticmethod
    async def transition_node_to_active(
        db: AsyncSession,
        node_sig: UUID,
        author_sig: UUID | None = None,
    ) -> CognitiveNode:
        """Transitions a processing node iteration to an active operational state."""
        node = await ProcessingNexusOrchestrator.capture_node_instance(db, node_sig)
        next_revision = node.revision + 1
        ts = datetime.now(UTC)

        archive = NodeVersion(
            node_sig=node.id,
            revision=next_revision,
            architectural_blueprint={
                "node_label": node.node_label,
                "node_class": node.node_class,
                "architectural_blueprint": node.architectural_blueprint,
                "locale_sig": node.locale_sig,
                "vocal_spectral_sig": node.vocal_spectral_sig,
                "transmission_velocity": str(node.transmission_velocity),
                "transmission_amplitude": str(node.transmission_amplitude),
                "revision": next_revision,
            },
            archive_timestamp=ts,
            author_sig=author_sig,
        )
        db.add(archive)
        node.revision = next_revision
        node.node_phase = "published"
        node.activation_mark = ts

        await db.flush()
        await db.refresh(node)
        return node

    @staticmethod
    async def capture_node_instance(db: AsyncSession, node_sig: UUID) -> CognitiveNode:
        """Captures a specific instance of a processing node from the substrate."""
        res = await db.execute(select(CognitiveNode).where(CognitiveNode.id == node_sig))
        node = res.scalar_one_or_none()
        if not node:
            raise NotFoundError("CognitiveNode", str(node_sig))
        return node

    @staticmethod
    async def aggregate_active_nodes(
        db: AsyncSession,
        tenant_id: UUID | None = None,
        phase: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[CognitiveNode], int]:
        """Aggregates active processing nodes based on architectural filters."""
        flux = select(CognitiveNode)
        if tenant_id:
            flux = flux.where(CognitiveNode.tenant_id == tenant_id)
        if phase:
            flux = flux.where(CognitiveNode.node_phase == phase)

        total = (await db.execute(select(func.count()).select_from(flux.subquery()))).scalar_one()
        res = await db.execute(flux.order_by(CognitiveNode.created_at.desc()).offset((page - 1) * limit).limit(limit))
        return list(res.scalars().all()), total

    @staticmethod
    async def apply_architectural_mutation(
        db: AsyncSession,
        node_sig: UUID,
        **mutations: object,
    ) -> CognitiveNode:
        """Applies structural mutations to an established processing node manifest."""
        node = await ProcessingNexusOrchestrator.capture_node_instance(db, node_sig)
        for trait, value in mutations.items():
            if value is not None and hasattr(node, trait):
                setattr(node, trait, value)
        await db.flush()
        await db.refresh(node)
        return node

    @staticmethod
    async def decommission_node_instance(db: AsyncSession, node_sig: UUID) -> None:
        """Permanently decommissions a processing node and audits its archival state."""
        node = await ProcessingNexusOrchestrator.capture_node_instance(db, node_sig)
        await db.delete(node)
        await db.flush()

    @staticmethod
    async def _resolve_provider_resource(db: AsyncSession, cat: str, tenant: UUID) -> BackendAccess | None:
        """Internal resolver for identifying the most compatible provider resource."""
        res = await db.execute(
            select(BackendAccess).where(
                BackendAccess.vector_category == cat,
                BackendAccess.is_active == True,
                or_(BackendAccess.tenant_id == tenant, BackendAccess.is_default == True)
            ).order_by(
                case((BackendAccess.tenant_id == tenant, 1), else_=0).desc(),
                BackendAccess.is_default.desc(),
                BackendAccess.created_at.desc()
            ).limit(1)
        )
        return res.scalar_one_or_none()


class BehavioralProbeOrchestrator:
    """Orchestrates behavioral probes and telemetry synthesis for processing nodes."""

    @staticmethod
    async def catalog_behavioral_probes(db: AsyncSession, node_sig: UUID) -> list[BehavioralProbe]:
        """Catalogs all established behavioral probes for a specific processing node."""
        res = await db.execute(select(BehavioralProbe).where(BehavioralProbe.node_sig == node_sig))
        return list(res.scalars().all())

    @staticmethod
    async def capture_probe_instance(db: AsyncSession, probe_sig: UUID) -> BehavioralProbe:
        """Captures a state snapshot of a specific behavioral probe."""
        res = await db.execute(select(BehavioralProbe).where(BehavioralProbe.id == probe_sig))
        probe = res.scalar_one_or_none()
        if not probe:
            raise NotFoundError("BehavioralProbe", str(probe_sig))
        return probe

    @staticmethod
    async def manifest_probe_intent(
        db: AsyncSession,
        node_sig: UUID,
        label: str,
        narrative: str | None,
        params: dict,
        metrics: dict,
        sig: UUID | None = None,
    ) -> BehavioralProbe:
        """Manifests a new behavioral probe intent within the architectural substrate."""
        probe = BehavioralProbe(
            node_sig=node_sig,
            label=label,
            narrative=narrative,
            injected_parameters=params,
            benchmark_metrics=metrics,
            author_sig=sig,
        )
        db.add(probe)
        await db.flush()
        return probe

    @staticmethod
    async def synthesize_probe_telemetry(
        db: AsyncSession,
        probe_sig: UUID,
        sync_sig: UUID | None,
        revision: int | None,
        data: dict,
        performance: dict,
        logic_matrix: dict,
    ) -> ProbeTelemetry:
        """Synthesizes granular telemetry from a behavioral probe execution."""
        outcome = ProbeTelemetry(
            probe_sig=probe_sig,
            sync_sig=sync_sig,
            node_revision=revision,
            captured_matrix=data,
            performance_metrics=performance,
            evaluation_logic=logic_matrix,
            is_terminal_success=logic_matrix.get("passed", False),
            vector_density=logic_matrix.get("total", 0),
            aligned_vectors=logic_matrix.get("matched", 0),
        )
        db.add(outcome)
        await db.flush()
        return outcome
