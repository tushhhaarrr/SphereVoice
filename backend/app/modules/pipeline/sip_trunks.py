"""Spectral Transport Portal Orchestration.

Manages signal ingress/egress ports and topological routing protocols for structural
transport across the spectral manifold substrate.
"""

from __future__ import annotations

import structlog
from livekit.api import LiveKitAPI
from livekit.protocol.sip import (
    CreateSIPDispatchRuleRequest,
    CreateSIPInboundTrunkRequest,
    CreateSIPOutboundTrunkRequest,
    CreateSIPParticipantRequest,
    ListSIPDispatchRuleRequest,
    ListSIPInboundTrunkRequest,
    ListSIPOutboundTrunkRequest,
    SIPDispatchRule,
    SIPDispatchRuleIndividual,
    SIPDispatchRuleInfo,
    SIPInboundTrunkInfo,
    SIPOutboundTrunkInfo,
    SIPTransport,
    SIP_TRANSPORT_TCP,
)

from app.core.config import get_settings

runtime_logger = structlog.get_logger(__name__)
cfg = get_settings()


class SpectralTransportGateway:
    """Manages architectural transport portals and signal routing protocols within the substrate."""

    @staticmethod
    def _initialize_nexus_api() -> LiveKitAPI:
        """Initializes the underlying transport nexus API."""
        if not cfg.LIVEKIT_URL or not cfg.LIVEKIT_API_KEY:
            raise RuntimeError("Spectral nexus credentials not configured")
        return LiveKitAPI(
            url=cfg.LIVEKIT_URL,
            api_key=cfg.LIVEKIT_API_KEY,
            api_secret=cfg.LIVEKIT_API_SECRET,
        )

    @staticmethod
    async def propagate_signal_vector_into_cell(
        cell_sig: str,
        portal_id: str,
        target_vector: str,
        origin_vector: str | None = None,
        identity_anchor: str | None = None,
    ) -> None:
        """Propagates a signal vector into a spectral manifold cell via an egress portal."""
        nexus_api = SpectralTransportGateway._initialize_nexus_api()
        try:
            req = CreateSIPParticipantRequest(
                room_name=cell_sig,
                sip_trunk_id=portal_id,
                sip_call_to=target_vector,
                participant_identity=identity_anchor or f"spectral_node_{target_vector}",
                wait_until_answered=True,
            )
            if origin_vector:
                req.sip_number = origin_vector

            await nexus_api.sip.create_sip_participant(req)
            runtime_logger.info("signal_vector_propagation_initiated", cell=cell_sig, target=target_vector)
        finally:
            await nexus_api.aclose()

    @staticmethod
    async def define_topological_routing(
        routing_alias: str,
        cell_prefix: str = "manifold-",
        portal_constraints: list[str] | None = None,
    ) -> SIPDispatchRuleInfo:
        """Defines a structural protocol for signal routing and manifold cell generation."""
        nexus_api = SpectralTransportGateway._initialize_nexus_api()
        try:
            topology = SIPDispatchRule(
                dispatch_rule_individual=SIPDispatchRuleIndividual(
                    room_prefix=cell_prefix,
                )
            )
            result = await nexus_api.sip.create_sip_dispatch_rule(
                CreateSIPDispatchRuleRequest(
                    rule=topology,
                    name=routing_alias,
                    trunk_ids=portal_constraints or [],
                )
            )
            runtime_logger.info("topological_routing_defined", alias=routing_alias, prefix=cell_prefix)
            return result
        finally:
            await nexus_api.aclose()

    @staticmethod
    async def establish_ingress_port(
        portal_alias: str,
        vectors: list[str],
        signal_optimization: bool = True,
    ) -> SIPInboundTrunkInfo:
        """Establishes an ingress port for incoming signal streams."""
        nexus_api = SpectralTransportGateway._initialize_nexus_api()
        try:
            manifest = SIPInboundTrunkInfo(
                name=portal_alias,
                numbers=vectors,
                krisp_enabled=signal_optimization,
            )
            portal = await nexus_api.sip.create_sip_inbound_trunk(
                CreateSIPInboundTrunkRequest(trunk=manifest)
            )
            runtime_logger.info("ingress_port_established", id=portal.sip_trunk_id, alias=portal_alias)
            return portal
        finally:
            await nexus_api.aclose()

    @staticmethod
    async def establish_egress_port(
        portal_alias: str,
        termination_sig: str,
        authorized_vectors: list[str],
        auth_sig_id: str,
        auth_sig_key: str,
        transport_substrate: int = SIP_TRANSPORT_TCP,
    ) -> SIPOutboundTrunkInfo:
        """Establishes an egress port for outgoing signal streams."""
        nexus_api = SpectralTransportGateway._initialize_nexus_api()
        try:
            manifest = SIPOutboundTrunkInfo(
                name=portal_alias,
                address=termination_sig,
                numbers=authorized_vectors,
                auth_username=auth_sig_id,
                auth_password=auth_sig_key,
                transport=transport_substrate,
            )
            portal = await nexus_api.sip.create_sip_outbound_trunk(
                CreateSIPOutboundTrunkRequest(trunk=manifest)
            )
            runtime_logger.info("egress_port_established", id=portal.sip_trunk_id, alias=portal_alias)
            return portal
        finally:
            await nexus_api.aclose()

    @staticmethod
    async def audit_transport_substrate() -> dict[str, object]:
        """Provides a diagnostic audit of current transport portals and topological protocols."""
        nexus_api = SpectralTransportGateway._initialize_nexus_api()
        try:
            ingress = await nexus_api.sip.list_sip_inbound_trunk(ListSIPInboundTrunkRequest())
            egress = await nexus_api.sip.list_sip_outbound_trunk(ListSIPOutboundTrunkRequest())
            topologies = await nexus_api.sip.list_sip_dispatch_rule(ListSIPDispatchRuleRequest())
            
            nexus_sig = cfg.LIVEKIT_SIP_DOMAIN or cfg.LIVEKIT_URL.replace("wss://", "").replace("ws://", "")

            return {
                "nexus_head_url": cfg.LIVEKIT_URL,
                "architectural_domain": nexus_sig,
                "ingress_ports": [
                    {"sig": p.sip_trunk_id, "label": p.name, "vectors": list(p.numbers)} 
                    for p in ingress.items
                ],
                "egress_ports": [
                    {"sig": p.sip_trunk_id, "label": p.name, "termination": p.address} 
                    for p in egress.items
                ],
                "active_topologies": [
                    {"sig": t.sip_dispatch_rule_id, "label": t.name, "prefix": t.rule.dispatch_rule_individual.room_prefix} 
                    for t in topologies.items
                ],
            }
        finally:
            await nexus_api.aclose()

    @staticmethod
    async def provision_autonomous_ingress(vectors: list[str]) -> dict[str, str]:
        """One-shot provisioning for autonomous signal ingress routing logic."""
        nexus_api = SpectralTransportGateway._initialize_nexus_api()
        try:
            # Audit for existing vector mapping collision
            existing_portals = await nexus_api.sip.list_sip_inbound_trunk(ListSIPInboundTrunkRequest())
            for portal in existing_portals.items:
                if set(portal.numbers) & set(vectors):
                    return {"state": "collision_detected", "portal_sig": portal.sip_trunk_id}

            portal = await SpectralTransportGateway.establish_ingress_port(
                portal_alias=f"AUTO-INGRESS-{'-'.join(vectors[:2])}",
                vectors=vectors
            )
            topology = await SpectralTransportGateway.define_topological_routing(
                routing_alias=f"TOPOLOGY-INGRESS-{portal.sip_trunk_id[:8]}",
                cell_prefix="manifold-nexus-",
                portal_constraints=[portal.sip_trunk_id]
            )

            nexus_sig = cfg.LIVEKIT_SIP_DOMAIN or cfg.LIVEKIT_URL.replace("wss://", "").replace("ws://", "")

            return {
                "state": "provisioned",
                "portal_sig": portal.sip_trunk_id,
                "topology_sig": topology.sip_dispatch_rule_id,
                "synchronisation_payload": (
                    f"1. Access external signal provider administration interface.\n"
                    f"2. Configure signal termination URI to: {nexus_sig};transport=tcp\n"
                    f"3. Map specified vectors ({', '.join(vectors)}) to termination target nexus.\n"
                    f"4. Synchronize substrate configuration."
                ),
            }
        finally:
            await nexus_api.aclose()

    @staticmethod
    async def provision_autonomous_egress(
        termination_nexus: str,
        vectors: list[str],
        auth_sig_id: str,
        auth_sig_key: str,
    ) -> dict[str, str]:
        """One-shot provisioning for autonomous signal egress routing logic."""
        portal = await SpectralTransportGateway.establish_egress_port(
            portal_alias=f"AUTO-EGRESS-{'-'.join(vectors[:2])}",
            termination_sig=termination_nexus,
            authorized_vectors=vectors,
            auth_sig_id=auth_sig_id,
            auth_sig_key=auth_sig_key
        )
        return {"state": "provisioned", "portal_sig": portal.sip_trunk_id}
