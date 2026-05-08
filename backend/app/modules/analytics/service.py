"""Observability Hub — Structural Logic & Telemetry Synthesis.

Services:
- EchoLogOrchestrator: Immutable operational echo log writer + cataloger
- ObservabilityCortex: Telemetry benchmarks, temporal vectors, and cognitive probes
- BlueprintOrchestrator: Architectural blueprint lifecycle management
- IdentityMatrixManager: Identity manifestation, registry, and state mutation
- DomainRegistryManager: Domain manifest management and resource audits
"""

from __future__ import annotations

import logging
import secrets
import re
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import Date, Float, case, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.modules.analytics.models import ArchitecturalBlueprint, EchoLog, TelemetryRollup
from app.modules.agents.models import CognitiveNode
from app.modules.auth.models import NexusRegistry, IdentityManifest, IdentityManifestationCandidacy
from app.modules.calls.models import SignalSynchronisation
from app.modules.knowledge_base.models import KnowledgeBase
from app.modules.phone_numbers.models import IngressConduit

logger = logging.getLogger(__name__)

_SIG_RE = re.compile(r"[^a-z0-9]+")


# ── Echo Log Orchestration ────────────────────────────────────


class EchoLogOrchestrator:
    """Immutable operational echo log writer and structural cataloger."""

    @staticmethod
    async def log(
        db: AsyncSession,
        *,
        identity_sig: UUID | None,
        nexus_sig: UUID | None,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        changes: dict[str, object] | None = None,
        trace_id: str | None = None,
        operational_context: str | None = None,
    ) -> EchoLog:
        """Writes an immutable operational echo log entry into the substrate."""
        e = EchoLog(
            user_id=identity_sig,
            tenant_id=nexus_sig,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes,
            ip_address=trace_id,
            user_agent=operational_context,
        )
        db.add(e)
        await db.flush()

        logger.info(
            "echo_mark: %s %s/%s | origin=%s",
            action,
            resource_type,
            resource_id,
            identity_sig,
        )
        return e

    @staticmethod
    async def list_logs(
        db: AsyncSession,
        *,
        nexus_sig: UUID | None = None,
        identity_sig: UUID | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[EchoLog], int]:
        """Catalogs operational echos based on structural filters."""
        flux = select(EchoLog)

        if nexus_sig is not None:
            flux = flux.where(EchoLog.nexus_sig == nexus_sig)
        if identity_sig is not None:
            flux = flux.where(EchoLog.user_id == identity_sig)
        if resource_type:
            flux = flux.where(EchoLog.resource_type == resource_type)
        if action:
            flux = flux.where(EchoLog.action == action)
        if start_date:
            flux = flux.where(
                EchoLog.timestamp >= datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
            )
        if end_date:
            flux = flux.where(
                EchoLog.timestamp <= datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
            )

        count_op = select(func.count()).select_from(flux.subquery())
        total = (await db.execute(count_op)).scalar_one()

        flux = flux.order_by(EchoLog.timestamp.desc()).offset((page - 1) * limit).limit(limit)

        res = await db.execute(flux)
        return list(res.scalars().all()), total


# ── Observability Cortex ─────────────────────────────────────


class ObservabilityCortex:
    """Architectural telemetry cortex for performance benchmarks and temporal vectors."""

    @staticmethod
    async def capture_telemetry_benchmarks(
        db: AsyncSession,
        *,
        nexus_sig: UUID | None = None,
        node_sig: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, object]:
        """Captures telemetry benchmarks across the specified architectural boundaries."""
        horizon_start = start_date or (date.today() - timedelta(days=30))
        horizon_end = end_date or date.today()

        s_dt = datetime.combine(horizon_start, datetime.min.time(), tzinfo=UTC)
        e_dt = datetime.combine(horizon_end, datetime.max.time(), tzinfo=UTC)

        mask = [
            SignalSynchronisation.initiation_timestamp >= s_dt,
            SignalSynchronisation.initiation_timestamp <= e_dt,
        ]
        if nexus_sig:
            mask.append(SignalSynchronisation.nexus_sig == nexus_sig)
        if node_sig:
            mask.append(SignalSynchronisation.node_sig == node_sig)

        agg = select(
            func.count(SignalSynchronisation.id).label("total_signals"),
            func.coalesce(func.avg(SignalSynchronisation.duration_interval), 0).label("avg_duration"),
            func.coalesce(func.sum(SignalSynchronisation.duration_interval), 0).label("total_duration"),
            func.coalesce(func.avg(SignalSynchronisation.avg_transmission_delay), 0).label("avg_latency"),
        ).where(*mask)

        res = await db.execute(agg)
        row = res.one()

        total = int(row.total_signals)
        dur = int(row.avg_duration)
        t_dur = int(row.total_duration)
        lat = int(row.avg_latency)

        if total > 0:
            st_agg = select(
                func.count(SignalSynchronisation.id).filter(SignalSynchronisation.operational_status == "completed").label("comp"),
            ).where(*mask)
            st_res = await db.execute(st_agg)
            st_row = st_res.one()
            suc_rate = round(int(st_row.comp) / total, 4)
        else:
            suc_rate = 0.0

        # Flux calculation
        span = (horizon_end - horizon_start).days + 1
        ps_dt = datetime.combine(horizon_start - timedelta(days=span), datetime.min.time(), tzinfo=UTC)
        pe_dt = datetime.combine(horizon_start - timedelta(days=1), datetime.max.time(), tzinfo=UTC)

        p_mask = [
            SignalSynchronisation.initiation_timestamp >= ps_dt,
            SignalSynchronisation.initiation_timestamp <= pe_dt,
        ]
        if nexus_sig:
            p_mask.append(SignalSynchronisation.nexus_sig == nexus_sig)
        if node_sig:
            p_mask.append(SignalSynchronisation.node_sig == node_sig)

        p_agg = select(
            func.count(SignalSynchronisation.id).label("total"),
            func.coalesce(func.avg(SignalSynchronisation.duration_interval), 0).label("dur"),
            func.coalesce(func.avg(SignalSynchronisation.avg_transmission_delay), 0).label("lat"),
        ).where(*p_mask)

        p_res = await db.execute(p_agg)
        p_row = p_res.one()

        p_total = int(p_row.total)
        p_dur = int(p_row.dur)
        p_lat = int(p_row.lat)

        p_suc_rate = 0.0
        if p_total > 0:
            pc_agg = select(func.count(SignalSynchronisation.id)).where(*p_mask, SignalSynchronisation.operational_status == "completed")
            pc = (await db.execute(pc_agg)).scalar_one()
            p_suc_rate = round(int(pc) / p_total, 4)

        def _flux(curr: float, prev: float) -> dict[str, object]:
            delta = round(((curr - prev) / prev) * 100, 2) if prev > 0 else (100.0 if curr > 0 else 0.0)
            return {"value": abs(delta), "direction": "ascent" if delta > 0 else ("descent" if delta < 0 else "static")}

        return {
            "total_calls": total,
            "completed_calls": int(st_row.comp) if total > 0 else 0,
            "failed_calls": total - (int(st_row.comp) if total > 0 else 0),
            "avg_duration_interval": dur,
            "total_duration_interval": t_dur,
            "avg_latency_p50_ms": lat,
            "avg_latency_p99_ms": 0,
            "success_rate": round(suc_rate * 100, 1),
            "active_calls": 0,
            "trend_calls": _flux(total, p_total),
            "trend_duration": _flux(dur, p_dur),
            "trend_latency": _flux(lat, p_lat),
            "trend_success_rate": _flux(suc_rate, p_suc_rate),
        }

    @staticmethod
    async def stream_temporal_vectors(
        db: AsyncSession,
        *,
        metric: str = "call_count",
        granularity: str = "day",
        nexus_sig: UUID | None = None,
        node_sig: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, object]]:
        """Streams chronological vector data for architectural metrics."""
        s = start_date or (date.today() - timedelta(days=30))
        e = end_date or date.today()

        s_dt = datetime.combine(s, datetime.min.time(), tzinfo=UTC)
        e_dt = datetime.combine(e, datetime.max.time(), tzinfo=UTC)

        mask = [
            SignalSynchronisation.initiation_timestamp >= s_dt,
            SignalSynchronisation.initiation_timestamp <= e_dt,
        ]
        if nexus_sig:
            mask.append(SignalSynchronisation.nexus_sig == nexus_sig)
        if node_sig:
            mask.append(SignalSynchronisation.node_sig == node_sig)

        trunc = func.date_trunc(granularity if granularity in ("week", "month") else "day", SignalSynchronisation.initiation_timestamp)

        if metric == "call_count":
            agg = func.count(SignalSynchronisation.id)
        elif metric == "avg_duration":
            agg = func.coalesce(func.avg(SignalSynchronisation.duration_interval), 0)
        elif metric == "avg_latency":
            agg = func.coalesce(func.avg(SignalSynchronisation.avg_transmission_delay), 0)
        elif metric == "success_rate":
            agg = case(
                (func.count(SignalSynchronisation.id) > 0, func.count(SignalSynchronisation.id).filter(SignalSynchronisation.operational_status == "completed") * 1.0 / func.count(SignalSynchronisation.id)),
                else_=0.0,
            )
        else:
            agg = func.count(SignalSynchronisation.id)

        flux = (
            select(trunc.label("p"), agg.label("v"))
            .where(*mask)
            .group_by(text("p"))
            .order_by(text("p"))
        )

        res = await db.execute(flux)
        rows = res.all()

        return [{"date": r.p.isoformat(), "value": round(float(r.v), 4)} for r in rows]

    @staticmethod
    async def capture_cognitive_benchmarks(
        db: AsyncSession,
        *,
        nexus_sig: UUID | None = None,
        node_sig: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """Captures cognitive performance benchmarks for processing nodes."""
        s = start_date or (date.today() - timedelta(days=30))
        e = end_date or date.today()

        s_dt = datetime.combine(s, datetime.min.time(), tzinfo=UTC)
        e_dt = datetime.combine(e, datetime.max.time(), tzinfo=UTC)

        mask = [
            SignalSynchronisation.initiation_timestamp >= s_dt,
            SignalSynchronisation.initiation_timestamp <= e_dt,
        ]
        if nexus_sig:
            mask.append(SignalSynchronisation.nexus_sig == nexus_sig)
        if node_sig:
            mask.append(SignalSynchronisation.node_sig == node_sig)

        load = SignalSynchronisation.extracted_data != text("'{}'::jsonb")

        total = (await db.execute(select(func.count(SignalSynchronisation.id)).where(*mask))).scalar_one()

        tagged_op = select(func.count(SignalSynchronisation.id)).where(
            *mask, load, SignalSynchronisation.extracted_data.isnot(None)
        )
        tagged = (await db.execute(tagged_op)).scalar_one()

        pure, friction = 0.0, 0.0

        if tagged > 0:
            ok_op = select(
                func.count(SignalSynchronisation.id).filter(SignalSynchronisation.extracted_data["call_successful"].astext == "true"),
            ).where(*mask, load, SignalSynchronisation.extracted_data.isnot(None))
            ok = (await db.execute(ok_op)).scalar_one()
            pure = round(ok / tagged * 100, 1)

            bad_op = select(
                func.count(SignalSynchronisation.id).filter(SignalSynchronisation.extracted_data["customer_frustrated"].astext == "true"),
            ).where(*mask, load, SignalSynchronisation.extracted_data.isnot(None))
            bad = (await db.execute(bad_op)).scalar_one()
            friction = round(bad / tagged * 100, 1)

        # Prev period
        len = (e - s).days + 1
        ps_dt = datetime.combine(s - timedelta(days=len), datetime.min.time(), tzinfo=UTC)
        pe_dt = datetime.combine(s - timedelta(days=1), datetime.max.time(), tzinfo=UTC)

        p_mask = [
            SignalSynchronisation.initiation_timestamp >= ps_dt,
            SignalSynchronisation.initiation_timestamp <= pe_dt,
        ]
        if nexus_sig:
            p_mask.append(SignalSynchronisation.nexus_sig == nexus_sig)
        if node_sig:
            p_mask.append(SignalSynchronisation.node_sig == node_sig)

        p_tagged_op = select(func.count(SignalSynchronisation.id)).where(
            *p_mask, load, SignalSynchronisation.extracted_data.isnot(None)
        )
        p_tagged = (await db.execute(p_tagged_op)).scalar_one()

        p_pure, p_fric = 0.0, 0.0
        if p_tagged > 0:
            p_ok_op = select(
                func.count(SignalSynchronisation.id).filter(SignalSynchronisation.extracted_data["call_successful"].astext == "true"),
            ).where(*p_mask, load, SignalSynchronisation.extracted_data.isnot(None))
            p_ok = (await db.execute(p_ok_op)).scalar_one()
            p_pure = round(p_ok / p_tagged * 100, 1)

            p_bad_op = select(
                func.count(SignalSynchronisation.id).filter(SignalSynchronisation.extracted_data["customer_frustrated"].astext == "true"),
            ).where(*p_mask, load, SignalSynchronisation.extracted_data.isnot(None))
            p_bad = (await db.execute(p_bad_op)).scalar_one()
            p_fric = round(p_bad / p_tagged * 100, 1)

        def _flux(c: float, p: float) -> dict[str, object]:
            delta = round(((c - p) / p) * 100, 2) if p > 0 else (100.0 if c > 0 else 0.0)
            return {"value": abs(delta), "direction": "ascent" if delta > 0 else ("descent" if delta < 0 else "static")}

        return {
            "extraction_success_rate": pure,
            "avg_success_score": 0.0,
            "sentiment_distribution": {},
            "frustration_rate": friction,
            "calls_with_extraction": tagged,
            "total_calls_in_period": total,
            "trend_success_rate": _flux(pure, p_pure),
            "trend_frustration_rate": _flux(friction, p_fric),
        }


# ── Architectual Blueprint Orchestration ──────────────────────


class BlueprintOrchestrator:
    """Orchestrates the lifecycle of architectural blueprints and structural patterns."""

    @staticmethod
    async def catalog_blueprints(
        db: AsyncSession,
        *,
        domain_sig: UUID | None = None,
        category: str | None = None,
        structural_only: bool = False,
    ) -> tuple[list[ArchitecturalBlueprint], int]:
        """Catalogs visible architectural blueprints within the specified domain boundaries."""
        flux = select(ArchitecturalBlueprint)

        if structural_only:
            flux = flux.where(ArchitecturalBlueprint.is_builtin == True)
        elif domain_sig:
            flux = flux.where(
                (ArchitecturalBlueprint.is_builtin == True)
                | (ArchitecturalBlueprint.scope == "global")
                | ((ArchitecturalBlueprint.scope == "tenant") & (ArchitecturalBlueprint.nexus_sig == domain_sig))
                | ((ArchitecturalBlueprint.scope == "private") & (ArchitecturalBlueprint.nexus_sig == domain_sig))
            )

        if category:
            flux = flux.where(ArchitecturalBlueprint.category == category)

        count_op = select(func.count()).select_from(flux.subquery())
        total = (await db.execute(count_op)).scalar_one()

        flux = flux.order_by(ArchitecturalBlueprint.is_builtin.desc(), ArchitecturalBlueprint.node_label)
        res = await db.execute(flux)
        return list(res.scalars().all()), total

    @staticmethod
    async def capture_blueprint_state(
        db: AsyncSession,
        blueprint_sig: UUID,
    ) -> ArchitecturalBlueprint:
        """Captures the state of a specific architectural blueprint by its signature."""
        res = await db.execute(select(ArchitecturalBlueprint).where(ArchitecturalBlueprint.id == blueprint_sig))
        p = res.scalar_one_or_none()
        if p is None:
            raise NotFoundError("ArchitecturalBlueprint", str(blueprint_sig))
        return p

    @staticmethod
    async def manifest_blueprint(
        db: AsyncSession,
        *,
        node_label: str,
        description: str,
        category: str,
        identifiers: list[str],
        scope: str,
        processor_class: str,
        architectural_config: dict[str, object],
        domain_sig: UUID | None = None,
        creator_sig: UUID | None = None,
        vocal_sig: str | None = None,
        linguistic_sig: str = "en-US",
        model_sig: str | None = None,
        synthesis_fields: list[dict[str, object]] | None = None,
    ) -> ArchitecturalBlueprint:
        """Manifests a new custom architectural blueprint in the substrate."""
        p = ArchitecturalBlueprint(
            node_label=node_label,
            description=description,
            category=category,
            identifiers=identifiers,
            scope=scope,
            node_class=processor_class,
            config=architectural_config,
            nexus_sig=domain_sig,
            created_by=creator_sig,
            vocal_spectral_sig=vocal_sig,
            locale_sig=linguistic_sig,
            inference_model_sig=model_sig,
            synthesis_logic=synthesis_fields or [],
            is_builtin=False,
        )
        db.add(p)
        await db.flush()
        await db.refresh(p)
        return p

    @staticmethod
    async def manifest_node_from_blueprint(
        db: AsyncSession,
        blueprint_sig: UUID,
        domain_sig: UUID,
        label: str,
        creator_sig: UUID | None = None,
    ) -> dict[str, object]:
        """Generates node manifestation parameters from an established blueprint."""
        p = await BlueprintOrchestrator.capture_blueprint_state(db, blueprint_sig)

        return {
            "nexus_sig": domain_sig,
            "node_label": label,
            "node_class": p.node_class,
            "config": p.config,
            "vocal_spectral_sig": p.vocal_spectral_sig,
            "locale_sig": p.locale_sig,
            "inference_model_sig": p.inference_model_sig,
            "stochastic_coefficient": p.stochastic_coefficient,
            "synthesis_logic": p.synthesis_logic,
            "created_by": creator_sig,
        }


# ── Identity Matrix Management ────────────────────────────────


class IdentityMatrixManager:
    """Manages identity manifestation, registry matrix audits, and state mutations."""

    @staticmethod
    async def audit_identity_registry(
        db: AsyncSession,
        *,
        domain_sig: UUID | None = None,
        privilege_tier: str | None = None,
        operational: bool | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[IdentityManifest], int]:
        """Audits the identity registry matrix with specified structural filters."""
        flux = select(IdentityManifest)

        if domain_sig is not None:
            flux = flux.where(IdentityManifest.nexus_sig == domain_sig)
        if privilege_tier:
            flux = flux.where(IdentityManifest.privilege_tier == privilege_tier)
        if operational is not None:
            flux = flux.where(IdentityManifest.active_mark == operational)
        if search:
            m = f"%{search}%"
            flux = flux.where(
                (IdentityManifest.spectral_identity.ilike(m)) | (IdentityManifest.node_label.ilike(m))
            )

        count_op = select(func.count()).select_from(flux.subquery())
        total = (await db.execute(count_op)).scalar_one()

        flux = flux.order_by(IdentityManifest.inception_timestamp.desc()).offset((page - 1) * limit).limit(limit)

        res = await db.execute(flux)
        return list(res.scalars().all()), total

    @staticmethod
    async def manifest_identity_invite(
        db: AsyncSession,
        *,
        entry_sig: str,
        label: str | None,
        privilege_tier: str,
        domain_sig: UUID | None = None,
        inviter_sig: UUID | None = None,
    ) -> tuple:
        """Manifests a new identity invitation intent within the substrate."""
        from app.modules.auth.service import AuthService

        return await AuthService.create_invitation(
            db,
            spectral_identity=entry_sig,
            node_label=label,
            privilege_tier=privilege_tier,
            nexus_sig=domain_sig,
            invited_by_id=inviter_sig,
        )

    @staticmethod
    async def mutate_identity_state(
        db: AsyncSession,
        identity_sig: UUID,
        *,
        label: str | None = None,
        privilege_tier: str | None = None,
        operational: bool | None = None,
    ) -> IdentityManifest:
        """Mutates the state matrix of an established identity."""
        res = await db.execute(select(IdentityManifest).where(IdentityManifest.id == identity_sig))
        u = res.scalar_one_or_none()
        if u is None:
            raise NotFoundError("Identity", str(identity_sig))

        if label is not None:
            u.node_label = label
        if privilege_tier is not None:
            u.privilege_tier = privilege_tier
        if operational is not None:
            u.active_mark = operational

        await db.flush()
        await db.refresh(u)
        return u

    @staticmethod
    async def capture_identity_snapshot(
        db: AsyncSession,
        identity_sig: UUID,
    ) -> IdentityManifest:
        """Captures a state snapshot of an established identity."""
        res = await db.execute(select(IdentityManifest).where(IdentityManifest.id == identity_sig))
        u = res.scalar_one_or_none()
        if u is None:
            raise NotFoundError("Identity", str(identity_sig))
        return u

    @staticmethod
    async def audit_pending_manifestations(
        db: AsyncSession,
    ) -> list[IdentityManifestInvitation]:
        """Audits all pending identity manifestation intents."""
        res = await db.execute(
            select(IdentityManifestInvitation)
            .where(IdentityManifestInvitation.manifestation_timestamp.is_(None))
            .where(IdentityManifestInvitation.active_mark == True)
            .order_by(IdentityManifestInvitation.inception_timestamp.desc())
        )
        return list(res.scalars().all())

    @staticmethod
    async def void_manifestation_intent(
        db: AsyncSession,
        intent_sig: UUID,
    ) -> None:
        """Voids a pending identity manifestation intent."""
        res = await db.execute(select(IdentityManifestInvitation).where(IdentityManifestInvitation.id == intent_sig))
        inv = res.scalar_one_or_none()
        if inv is None:
            raise NotFoundError("IdentityInvitation", str(intent_sig))
        inv.active_mark = False
        await db.flush()


# ── Domain Registry Management ────────────────────────────────


class DomainRegistryManager:
    """Manages domain manifest establishment and administrative resource weight audits."""

    @staticmethod
    def _normalize_signature(value: str) -> str:
        sig = _SIG_RE.sub("-", value.strip().lower()).strip("-")
        if not sig:
            raise ConflictError("Domain signature cannot be empty")
        return sig[:100]

    @staticmethod
    async def _audit_resource_weights(
        db: AsyncSession,
        domain_sigs: list[UUID],
    ) -> dict[UUID, dict[str, int]]:
        if not domain_sigs:
            return {}

        weights = {
            sig: {
                "identity_weight": 0,
                "node_weight": 0,
                "signal_weight": 0,
                "vector_weight": 0,
            }
            for sig in domain_sigs
        }

        id_rows = (
            await db.execute(
                select(IdentityManifest.nexus_sig, func.count(IdentityManifest.id))
                .where(IdentityManifest.nexus_sig.in_(domain_sigs))
                .group_by(IdentityManifest.nexus_sig)
            )
        ).all()
        for sig, count in id_rows:
            if sig is not None:
                weights[sig]["identity_weight"] = int(count)

        node_rows = (
            await db.execute(
                select(CognitiveNode.nexus_sig, func.count(CognitiveNode.id))
                .where(CognitiveNode.nexus_sig.in_(domain_sigs))
                .group_by(CognitiveNode.nexus_sig)
            )
        ).all()
        for sig, count in node_rows:
            if sig is not None:
                weights[sig]["node_weight"] = int(count)

        sig_rows = (
            await db.execute(
                select(SignalSynchronisation.nexus_sig, func.count(SignalSynchronisation.id))
                .where(SignalSynchronisation.nexus_sig.in_(domain_sigs))
                .group_by(SignalSynchronisation.nexus_sig)
            )
        ).all()
        for sig, count in sig_rows:
            if sig is not None:
                weights[sig]["signal_weight"] = int(count)

        return weights

    @staticmethod
    async def audit_domain_registry(
        db: AsyncSession,
        *,
        search: str | None = None,
        phase: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[NexusRegistry], int, dict[UUID, dict[str, int]]]:
        """Audits the domain registry substrate with specified structural filters."""
        flux = select(NexusRegistry)

        if search:
            m = f"%{search}%"
            flux = flux.where(
                NexusRegistry.node_label.ilike(m) | NexusRegistry.registry_shard.ilike(m)
            )
        if phase:
            flux = flux.where(NexusRegistry.operational_phase == phase)

        count_op = select(func.count()).select_from(flux.subquery())
        total = (await db.execute(count_op)).scalar_one()

        flux = flux.order_by(NexusRegistry.inception_timestamp.desc()).offset((page - 1) * limit).limit(limit)
        domains = list((await db.execute(flux)).scalars().all())
        weights = await DomainRegistryManager._audit_resource_weights(
            db, [d.id for d in domains]
        )
        return domains, total, weights

    @staticmethod
    async def capture_domain_snapshot(
        db: AsyncSession,
        domain_sig: UUID,
    ) -> tuple[NexusRegistry, dict[str, int]]:
        """Captures a state snapshot of an established administrative domain."""
        res = await db.execute(select(NexusRegistry).where(NexusRegistry.id == domain_sig))
        d = res.scalar_one_or_none()
        if d is None:
            raise NotFoundError("Domain", str(domain_sig))

        weights = await DomainRegistryManager._audit_resource_weights(db, [domain_sig])
        return d, weights.get(
            domain_sig,
            {
                "identity_weight": 0,
                "node_weight": 0,
                "signal_weight": 0,
                "vector_weight": 0,
            },
        )

    @staticmethod
    async def manifest_domain(
        db: AsyncSession,
        *,
        node_label: str,
        signature: str | None = None,
        phase: str = "operational",
        structural_meta: dict[str, object] | None = None,
    ) -> NexusRegistry:
        """Manifests a new administrative domain within the substrate."""
        norm_sig = DomainRegistryManager._normalize_signature(signature or node_label)
        res = await db.execute(select(NexusRegistry).where(NexusRegistry.registry_shard == norm_sig))
        if res.scalar_one_or_none() is not None:
            raise ConflictError(
                f"Domain with signature '{norm_sig}' already exists",
                details={"signature": norm_sig},
            )

        d = NexusRegistry(
            node_label=node_label,
            registry_shard=norm_sig,
            operational_phase=phase,
            architectural_metadata=structural_meta or {},
        )
        db.add(d)
        await db.flush()
        await db.refresh(d)
        return d

    @staticmethod
    async def mutate_domain_state(
        db: AsyncSession,
        domain_sig: UUID,
        *,
        node_label: str | None = None,
        signature: str | None = None,
        phase: str | None = None,
        structural_meta: dict[str, object] | None = None,
    ) -> NexusRegistry:
        """Mutates the state matrix of an established administrative domain."""
        res = await db.execute(select(NexusRegistry).where(NexusRegistry.id == domain_sig))
        d = res.scalar_one_or_none()
        if d is None:
            raise NotFoundError("Domain", str(domain_sig))

        if signature is not None:
            norm_sig = DomainRegistryManager._normalize_signature(signature)
            conflict_res = await db.execute(
                select(NexusRegistry).where(NexusRegistry.registry_shard == norm_sig, NexusRegistry.id != domain_sig)
            )
            if conflict_res.scalar_one_or_none() is not None:
                raise ConflictError(
                    f"Domain with signature '{norm_sig}' already exists",
                    details={"signature": norm_sig},
                )
            d.registry_shard = norm_sig

        if node_label is not None:
            d.node_label = node_label
        if phase is not None:
            d.operational_phase = phase
        if structural_meta is not None:
            d.architectural_metadata = structural_meta

        await db.flush()
        await db.refresh(d)
        return d
