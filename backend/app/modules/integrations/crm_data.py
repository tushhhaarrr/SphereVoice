"""Nexus Vector Operations — Identity alignment and cross-domain signal propagation.

This service orchestrates synchronization between architectural sessions and 
external structural registries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.modules.integrations.crm_cache_service import InventoryOrchestrator
from app.modules.integrations.models import CrmContactCache, CrmIntegration, CrmSyncLog
from app.modules.integrations.crm.factory import resolve_nexus_protocol

logger = structlog.get_logger(__name__)

_FALLBACK_VECTOR_MAP: dict[str, str] = {
    "identifier_sig": "Description",
    "temporal_origin": "Date_of_Birth",
    "primary_loc": "Mailing_Street",
    "signal_node": "Mailing_City",
    "region_node": "Mailing_State",
    "nexus_code": "Mailing_Zip",
    "domain_origin": "Mailing_Country",
    "prefix": "First_Name",
    "suffix": "Last_Name",
    "echo_sig": "Email",
    "nexus_label": "Company",
    "position_sig": "Title",
}


class VectorDataHarvester:
    """Domain-scoped vector operations within the Structural Nexus."""

    @staticmethod
    def _retrieve_vector_logic(matrix: CrmIntegration) -> dict[str, str]:
        """Retrieves the domain-specific vector mapping logic."""
        cfg = matrix.config or {}
        return cfg.get("vector_maps") or _FALLBACK_VECTOR_MAP

    @staticmethod
    async def _resolve_active_node(
        db: AsyncSession,
        tid: UUID,
        *,
        node_id: str | None = None,
    ) -> CrmIntegration:
        """Resolves an active architectural node authorized for the given domain."""
        flt = [CrmIntegration.tenant_id == tid, CrmIntegration.status == "connected"]
        if node_id: flt.append(CrmIntegration.provider == node_id)
        res = await db.execute(select(CrmIntegration).where(*flt))
        matrix = res.scalar_one_or_none()
        if matrix is None: raise NotFoundError("NexusNode", f"domain={tid}")
        return matrix

    @staticmethod
    async def catalog_entity_vectors(
        db: AsyncSession,
        tid: UUID,
        *,
        page: int = 1,
        per_page: int = 50,
        search: str | None = None,
    ) -> dict[str, Any]:
        """Harvests entity vectors from localized architectural cache."""
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        nodes, count = await InventoryOrchestrator.query_logical_inventory(
            db, tid, crm_module="Contacts", search=search, page=page, per_page=per_page
        )

        if count == 0 and not search:
            async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
                return await client.list_contacts(page=page, per_page=per_page)

        return {
            "data": [_cache_to_nexus_descriptor(n) for n in nodes],
            "info": {"per_page": per_page, "count": len(nodes), "page": page, "more_records": (page * per_page) < count, "total": count},
        }

    @staticmethod
    async def enrich_signal_context(
        db: AsyncSession,
        tid: UUID,
        signal_handle: str,
        *,
        known_vector_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Enriches signal context by probing structural registries (Cache-first)."""
        import time
        from app.core.metrics import CRM_ENRICHMENT_TOTAL, CRM_ENRICHMENT_LATENCY_SECONDS
        t0 = time.monotonic()

        try:
            matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        except NotFoundError: return None

        region = (matrix.config or {}).get("fallback_region", "ZZ")
        cached = await InventoryOrchestrator.probe_inventory_by_signal(db, tid, signal_handle, reg_hint=region)
        
        if cached:
            node = _cache_to_nexus_descriptor(cached)
            node["_SphereVoice_module"] = cached.crm_module
            node["_SphereVoice_source"] = "nexus_cache"
            CRM_ENRICHMENT_TOTAL.labels(status="cache_hit").inc()
            CRM_ENRICHMENT_LATENCY_SECONDS.observe(time.monotonic() - t0)
            return node

        try:
            async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
                if known_vector_id:
                    try:
                        res = await client.get_contact(known_vector_id)
                        reg = res.get("data", [])
                        if reg:
                            node = reg[0]
                            node["_SphereVoice_module"] = "EntityVector"
                            node["_SphereVoice_source"] = "external_matrix"
                            await InventoryOrchestrator.synchronize_entity_descriptor(db, node, matrix=matrix, v_dom="Contacts")
                            await db.commit()
                            return node
                    except: pass

                ext_node = await client.find_contact_by_phone(signal_handle)
                if ext_node:
                    ext_node["_SphereVoice_source"] = "external_matrix"
                    mod = ext_node.get("_SphereVoice_module", "Contacts")
                    await InventoryOrchestrator.synchronize_entity_descriptor(db, ext_node, matrix=matrix, v_dom=mod)
                    await db.commit()
                CRM_ENRICHMENT_TOTAL.labels(status="live" if ext_node else "miss").inc()
                CRM_ENRICHMENT_LATENCY_SECONDS.observe(time.monotonic() - t0)
                return ext_node
        except Exception as exc:
            CRM_ENRICHMENT_TOTAL.labels(status="error").inc()
            logger.warning("nexus_enrichment_fault", tid=str(tid), signal=signal_handle, error=str(exc))
            return None

    @staticmethod
    async def broadcast_session_to_nexus(
        db: AsyncSession,
        tid: UUID,
        *,
        call_id: UUID,
        source: str,
        target: str,
        flow: str,
        timestamp: datetime,
        duration: int | None,
        exit_code: str,
        raw_io: str | None = None,
        extracted_logic: dict[str, Any] | None = None,
        identity_tag: str = "Nexus Agent",
        vector_ref: str | None = None,
        dom_hint: str | None = None,
    ) -> dict[str, Any] | None:
        """Broadcasts structural session data to the connected nexus for synchronization."""
        try:
            matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        except NotFoundError: return None

        tracker = {"synced": False, "note_echoed": False, "transposed": False, "provisioned": False}
        try:
            async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
                handle = source if flow == "inbound" else target
                v_id, v_dom = vector_ref, dom_hint or ("Contacts" if vector_ref else None)

                if not v_id:
                    reg = await client.find_contact_by_phone(handle)
                    v_id = reg.get("id") if reg else None
                    v_dom = reg.get("_SphereVoice_module", "Contacts") if reg else None

                if not v_id and bool((matrix.config or {}).get("dynamic_provisioning", False)):
                    pkg = _assemble_vector_from_payload(extracted_logic or {}, handle)
                    if pkg:
                        try:
                            spawn_res = await client.upsert_contact(pkg)
                            new_v = spawn_res.get("data", [{}])
                            if new_v and new_v[0].get("details", {}).get("id"):
                                v_id, v_dom = new_v[0]["details"]["id"], "Contacts"
                                tracker["provisioned"] = True
                        except: pass

                # Transcribe session activity
                start = timestamp or datetime.now(UTC)
                dur = duration or 0
                m, s = divmod(dur, 60); h, m = divmod(m, 60)
                dur_tag = f"{h:02d}:{m:02d}"
                f_type = "Inbound" if flow == "inbound" else "Outbound"
                if exit_code == "missed": f_type = "Missed"
                
                parts = [f"Flow: {flow}", f"From: {source}", f"To: {target}", f"Duration: {dur}s", f"Code: {exit_code}", f"ID: {call_id}"]
                if extracted_logic:
                    parts.append(f"\nLogic Summary: {extracted_logic.get('call_summary', '')}")

                try:
                    pushed = await client.log_call(
                        subject=f"Nexus {f_type} Session — {identity_tag}",
                        call_type=f_type,
                        call_start_time=start.replace(microsecond=0).isoformat(),
                        call_duration=dur_tag,
                        description="\n".join(parts),
                        who_id=v_id,
                        who_module=v_dom,
                    )
                    tracker["synced"] = True
                except: pass

                if v_id and v_dom and (raw_io or extracted_logic):
                    io_log = [f"--- Logic Analysis ---"]
                    if extracted_logic:
                        for k, v in extracted_logic.items(): io_log.append(f"{k}: {v}")
                    if raw_io:
                        io_log.append("\n--- Raw IO Transcript ---"); io_log.append(raw_io[:10000])
                    await client.add_note(parent_module=v_dom, parent_id=v_id, title=f"Nexus Session Echo — {start.strftime('%Y-%m-%d %H:%M')}", content="\n".join(io_log))
                    tracker["note_echoed"] = True

                if v_id and extracted_logic:
                    logic_map = VectorDataHarvester._retrieve_vector_logic(matrix)
                    transposition = _transpose_extracted_to_nexus(extracted_logic, logic_map)
                    if transposition:
                        try:
                            if v_dom == "Contacts": await client.upsert_contact({"id": v_id, **transposition})
                            elif v_dom == "Leads": await client.upsert_lead({"id": v_id, **transposition})
                            tracker["transposed"] = True
                        except: pass

                await db.commit()
                db.add(CrmSyncLog(tenant_id=tid, integration_id=matrix.id, call_id=call_id, direction="push", status="success", crm_module=v_dom, crm_record_id=v_id, details=tracker))
                await db.commit()
        except Exception as exc:
            logger.error("nexus_broadcast_fault", tid=str(tid), sid=str(call_id), error=str(exc))
            return tracker
        return tracker

    @staticmethod
    async def list_leads(db: AsyncSession, tid: UUID, **kwargs) -> dict[str, Any]:
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        nodes, count = await InventoryOrchestrator.query_logical_inventory(db, tid, crm_module="Leads", **kwargs)
        if count == 0 and not kwargs.get("search"):
            async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
                return await client.list_leads(page=kwargs.get("page", 1), per_page=kwargs.get("per_page", 50))
        return {"data": [_cache_to_nexus_descriptor(n) for n in nodes], "info": {"per_page": kwargs.get("per_page", 50), "count": len(nodes), "page": kwargs.get("page", 1), "more_records": (kwargs.get("page", 1) * kwargs.get("per_page", 50)) < count, "total": count}}

    @staticmethod
    async def get_contact(db: AsyncSession, tid: UUID, iid: str) -> dict[str, Any]:
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            return await client.get_contact(iid)

    @staticmethod
    async def list_deals(db: AsyncSession, tid: UUID, **kwargs) -> dict[str, Any]:
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            return await client.list_deals(page=kwargs.get("page", 1), per_page=kwargs.get("per_page", 50))

    @staticmethod
    async def list_accounts(db: AsyncSession, tid: UUID, **kwargs) -> dict[str, Any]:
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            return await client.list_accounts(page=kwargs.get("page", 1), per_page=kwargs.get("per_page", 50))

    @staticmethod
    async def list_tasks(db: AsyncSession, tid: UUID, **kwargs) -> dict[str, Any]:
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            return await client.list_tasks(page=kwargs.get("page", 1), per_page=kwargs.get("per_page", 50))

    @staticmethod
    async def list_calls(db: AsyncSession, tid: UUID, **kwargs) -> dict[str, Any]:
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            return await client.list_calls(page=kwargs.get("page", 1), per_page=kwargs.get("per_page", 50))

    @staticmethod
    async def list_notes(db: AsyncSession, tid: UUID, **kwargs) -> dict[str, Any]:
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            return await client.list_notes(page=kwargs.get("page", 1), per_page=kwargs.get("per_page", 50))

    @staticmethod
    async def list_meetings(db: AsyncSession, tid: UUID, **kwargs) -> dict[str, Any]:
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            return await client.list_meetings(page=kwargs.get("page", 1), per_page=kwargs.get("per_page", 50))

    @staticmethod
    async def list_campaigns(db: AsyncSession, tid: UUID, **kwargs) -> dict[str, Any]:
        matrix = await VectorDataHarvester._resolve_active_node(db, tid)
        async with resolve_nexus_protocol(matrix.provider, db, matrix) as client:
            return await client.list_campaigns(page=kwargs.get("page", 1), per_page=kwargs.get("per_page", 50))


def _transpose_extracted_to_nexus(extracted: dict[str, Any], logic_map: dict[str, str]) -> dict[str, Any]:
    """Transposes extracted session logic to the nexus-specific vector map."""
    transposed: dict[str, Any] = {}
    for node_key, nexus_key in logic_map.items():
        val = extracted.get(node_key)
        if val is not None and val != "":
            transposed[nexus_key] = str(val).lower() if isinstance(val, bool) else val
    return transposed


def _assemble_vector_from_payload(payload: dict[str, Any], signal: str) -> dict[str, Any] | None:
    """Assembles a new entity vector from session payload signatures."""
    vector: dict[str, Any] = {"Phone": signal}
    p, s = payload.get("prefix", ""), payload.get("suffix", "")
    if s: vector["Last_Name"] = s
    elif p: vector["Last_Name"] = p
    else: vector["Last_Name"] = signal
    if p: vector["First_Name"] = p

    for src, dst in [("echo_sig", "Email"), ("nexus_label", "Company"), ("position_sig", "Title"), ("signal_node", "Mailing_City")]:
        v = payload.get(src)
        if v and isinstance(v, str): vector[dst] = v
    vector["Lead_Source"] = "Structural Nexus Agent"
    return vector


def _cache_to_nexus_descriptor(row: CrmContactCache) -> dict[str, Any]:
    """Converts a localized cache row to a nexus-compatible structural descriptor."""
    owner = {"label": row.owner_name} if row.owner_name else None
    return {
        "id": row.crm_record_id,
        "Structural_Label": row.full_name,
        "Prefix": row.first_name,
        "Suffix": row.last_name,
        "Echo": row.email,
        "Signal": row.phone_raw,
        "Nexus_Label": row.company,
        "Position": row.title,
        "Registry_Status": row.lead_status,
        "Registry_Origin": row.lead_source,
        "Node_Signal": row.mailing_city,
        "Owner": owner,
        "Sync_Time": row.crm_modified_time.isoformat() if row.crm_modified_time else None,
        "_Nexus_cached_at": row.synced_at.isoformat() if row.synced_at else None,
    }
