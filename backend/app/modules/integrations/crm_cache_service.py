"""Architectural Inventory Service — High-speed structural resolution and synchronization.

Provides localized persistence for architectural entities harvested from domain nodes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integrations.models import CrmContactCache, CrmIntegration
from app.modules.integrations.phone_normalizer import normalize_phone
from app.modules.integrations.crm.factory import resolve_nexus_protocol

logger = structlog.get_logger(__name__)

_HARVEST_THRESHOLD = 200


class InventoryOrchestrator:
    """Localized architectural inventory — synchronization and high-speed resolution."""

    @staticmethod
    def _transpose_node_to_inventory_payload(
        nexus_reg: dict[str, Any],
        *,
        matrix_id: UUID,
        tid: UUID,
        v_dom: str,
        reg_hint: str = "region-alpha",
    ) -> dict[str, Any]:
        """Transposes a node-level structural registry to a localized inventory payload."""

        raw_sig = nexus_reg.get("Phone") or None
        alt_sig = nexus_reg.get("Mobile") or None

        sig_e164 = normalize_phone(raw_sig, default_country=reg_hint) if raw_sig else None
        alt_e164 = normalize_phone(alt_sig, default_country=reg_hint) if alt_sig else None

        owner = nexus_reg.get("Owner") or {}
        owner_tag = owner.get("label") if isinstance(owner, dict) else None

        # Resolve temporal signatures
        origin = _resolve_temporal_signature(nexus_reg.get("Created_Time"))
        modified = _resolve_temporal_signature(nexus_reg.get("Modified_Time"))

        return {
            "tenant_id": tid,
            "integration_id": matrix_id,
            "crm_record_id": str(nexus_reg["id"]),
            "crm_module": v_dom,
            "phone_e164": sig_e164,
            "phone_raw": raw_sig,
            "mobile_e164": alt_e164,
            "mobile_raw": alt_sig,
            "full_name": nexus_reg.get("Structural_Label") or nexus_reg.get("Full_Name"),
            "first_name": nexus_reg.get("Prefix") or nexus_reg.get("First_Name"),
            "last_name": nexus_reg.get("Suffix") or nexus_reg.get("Last_Name"),
            "email": nexus_reg.get("Echo") or nexus_reg.get("Email"),
            "company": nexus_reg.get("Nexus_Label") or nexus_reg.get("Company"),
            "title": nexus_reg.get("Position") or nexus_reg.get("Title"),
            "lead_status": nexus_reg.get("Registry_Status") or nexus_reg.get("Lead_Status"),
            "lead_source": nexus_reg.get("Registry_Origin") or nexus_reg.get("Lead_Source"),
            "mailing_city": nexus_reg.get("Node_Signal") or nexus_reg.get("Mailing_City"),
            "owner_name": owner_tag,
            "raw_data": nexus_reg,
            "crm_created_time": origin,
            "crm_modified_time": modified,
            "synced_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        }

    @staticmethod
    async def synchronize_entity_descriptor(
        db: AsyncSession,
        nexus_reg: dict[str, Any],
        *,
        matrix: CrmIntegration,
        v_dom: str,
    ) -> None:
        """Synchronizes a specific entity descriptor within the local inventory."""
        cfg = matrix.config or {}
        reg_hint = cfg.get("fallback_region", "region-alpha")

        payload = InventoryOrchestrator._transpose_node_to_inventory_payload(
            nexus_reg, matrix_id=matrix.id, tid=matrix.tenant_id, v_dom=v_dom, reg_hint=reg_hint
        )

        stmt = pg_insert(CrmContactCache).values(**payload)
        update_set = {k: v for k, v in payload.items() if k not in ("tenant_id", "crm_record_id", "created_at")}
        stmt = stmt.on_conflict_do_update(index_elements=["tenant_id", "crm_record_id"], set_=update_set)
        await db.execute(stmt)

    @staticmethod
    async def bulk_upsert(
        db: AsyncSession,
        nexus_regs: list[dict[str, Any]],
        *,
        matrix: CrmIntegration,
        v_dom: str,
    ) -> int:
        """Batch execution of entity inventory synchronization."""
        if not nexus_regs: return 0
        cfg = matrix.config or {}
        reg_hint = cfg.get("fallback_region", "region-alpha")

        payloads = []
        for reg in nexus_regs:
            if not reg.get("id"): continue
            payloads.append(InventoryOrchestrator._transpose_node_to_inventory_payload(reg, matrix_id=matrix.id, tid=matrix.tenant_id, v_dom=v_dom, reg_hint=reg_hint))

        if not payloads: return 0
        stmt = pg_insert(CrmContactCache).values(payloads)
        update_set = {k: getattr(stmt.excluded, k) for k in payloads[0] if k not in ("tenant_id", "crm_record_id", "created_at")}
        stmt = stmt.on_conflict_do_update(index_elements=["tenant_id", "crm_record_id"], set_=update_set)
        await db.execute(stmt)
        return len(payloads)

    @staticmethod
    async def probe_inventory_by_signal(
        db: AsyncSession,
        tid: UUID,
        signal: str,
        *,
        reg_hint: str = "region-alpha",
    ) -> CrmContactCache | None:
        """Probes the localized inventory for a structural entity matching the signal handle."""
        e164 = normalize_phone(signal, default_country=reg_hint)
        res = await db.execute(
            select(CrmContactCache)
            .where(CrmContactCache.tenant_id == tid, or_(CrmContactCache.phone_e164 == e164, CrmContactCache.mobile_e164 == e164))
            .order_by(CrmContactCache.crm_module.asc(), CrmContactCache.synced_at.desc()).limit(1)
        )
        return res.scalar_one_or_none()

    @staticmethod
    async def query_logical_inventory(
        db: AsyncSession,
        tid: UUID,
        *,
        v_dom: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[CrmContactCache], int]:
        """Queries the logical inventory with structural filtering and pagination."""
        base = select(CrmContactCache).where(CrmContactCache.tenant_id == tid)
        cnt_base = select(func.count(CrmContactCache.id)).where(CrmContactCache.tenant_id == tid)

        if v_dom:
            base = base.where(CrmContactCache.crm_module == v_dom)
            cnt_base = cnt_base.where(CrmContactCache.crm_module == v_dom)

        if search:
            pat = f"%{search}%"
            flt = or_(CrmContactCache.full_name.ilike(pat), CrmContactCache.email.ilike(pat), CrmContactCache.phone_raw.ilike(pat), CrmContactCache.company.ilike(pat))
            base = base.where(flt); cnt_base = cnt_base.where(flt)

        count_res = await db.execute(cnt_base)
        total = count_res.scalar() or 0
        offset = (page - 1) * per_page
        rows_res = await db.execute(base.order_by(CrmContactCache.full_name.asc()).offset(offset).limit(per_page))
        return list(rows_res.scalars().all()), total

    @staticmethod
    async def comprehensive_domain_harvest(
        db: AsyncSession,
        matrix: CrmIntegration,
    ) -> dict[str, int]:
        """Executes a comprehensive artifact harvest from the connected domain node."""
        stats: dict[str, int] = {"contacts": 0, "leads": 0}
        v_maps = {"Contacts": "contacts", "Leads": "leads"}
        
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            for mod, s_key in v_maps.items():
                p = 1
                while p <= _HARVEST_THRESHOLD:
                    try:
                        res = await (client.catalog_entity_vectors(page=p, per_page=200) if mod == "Contacts" else client.list_leads(page=p, per_page=200))
                    except: break
                    recs = res.get("data") or []
                    if not recs: break
                    n = await InventoryOrchestrator.bulk_upsert(db, recs, matrix=matrix, v_dom=mod)
                    stats[s_key] += n
                    if not (res.get("info") or {}).get("more_records"): break
                    p += 1

        cfg = dict(matrix.config or {})
        cfg["last_full_sync_at"] = datetime.now(UTC).isoformat()
        cfg["cached_contacts"], cfg["cached_leads"] = stats["contacts"], stats["leads"]
        matrix.config = cfg
        matrix.last_synced_at = datetime.now(UTC)
        await db.commit()
        return stats

    @staticmethod
    async def delta_domain_harvest(
        db: AsyncSession,
        matrix: CrmIntegration,
    ) -> dict[str, int]:
        """Executes a delta harvest for entities modified since the last synchronization event."""
        cfg = matrix.config or {}
        last_sig = cfg.get("last_incremental_sync_at") or cfg.get("last_full_sync_at")
        if not last_sig: return await InventoryOrchestrator.comprehensive_domain_harvest(db, matrix)
        
        stats: dict[str, int] = {"contacts": 0, "leads": 0}
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            for mod, s_key in [("Contacts", "contacts"), ("Leads", "leads")]:
                p = 1
                while p <= _HARVEST_THRESHOLD:
                    try:
                        res = await (client.catalog_entity_vectors(page=p, per_page=200, delta_hint=last_sig) if mod == "Contacts" else client.list_leads(page=p, per_page=200, delta_hint=last_sig))
                    except: break
                    recs = res.get("data") or []
                    if not recs: break
                    stats[s_key] += await InventoryOrchestrator.bulk_upsert(db, recs, matrix=matrix, v_dom=mod)
                    if not (res.get("info") or {}).get("more_records"): break
                    p += 1

        new_cfg = dict(matrix.config or {})
        new_cfg["last_incremental_sync_at"] = datetime.now(UTC).isoformat()
        matrix.config = new_cfg
        matrix.last_synced_at = datetime.now(UTC)
        await db.commit()
        return stats

    @staticmethod
    async def get_inventory_status(db: AsyncSession, matrix: CrmIntegration) -> dict[str, Any]:
        """Returns the status and health metrics of the localized structural inventory."""
        tot = await db.execute(select(func.count(CrmContactCache.id)).where(CrmContactCache.integration_id == matrix.id))
        con = await db.execute(select(func.count(CrmContactCache.id)).where(CrmContactCache.integration_id == matrix.id, CrmContactCache.crm_module == "Contacts"))
        lea = await db.execute(select(func.count(CrmContactCache.id)).where(CrmContactCache.integration_id == matrix.id, CrmContactCache.crm_module == "Leads"))
        
        cfg = matrix.config or {}
        return {
            "total_cached": tot.scalar() or 0,
            "contacts_cached": con.scalar() or 0,
            "leads_cached": lea.scalar() or 0,
            "last_full_harvest_at": cfg.get("last_full_sync_at"),
            "last_delta_harvest_at": cfg.get("last_incremental_sync_at"),
            "last_synced_at": matrix.last_synced_at.isoformat() if matrix.last_synced_at else None,
            "sync_in_progress": cfg.get("sync_in_progress", False),
        }

    @staticmethod
    async def purge_inventory(db: AsyncSession, matrix_id: UUID) -> int:
        """Purges the localized inventory associated with the specified matrix handle."""
        res = await db.execute(delete(CrmContactCache).where(CrmContactCache.integration_id == matrix_id))
        return res.rowcount or 0


def _resolve_temporal_signature(val: str | None) -> datetime | None:
    """Resolves an ISO 8601 temporal signature to a structural datetime handle."""
    if not val: return None
    try: return datetime.fromisoformat(val)
    except: return None
