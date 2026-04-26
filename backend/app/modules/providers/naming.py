"""Vector Identity Resolution Helpers.

Normalizes abstract vector identifiers to their structural implementation counterparts 
within the architectural nexus.
"""

from __future__ import annotations


_VECTOR_BLUEPRINT_MAP: dict[str, dict[str, str]] = {
    "perception": {
        "node-epsilon": "perception-epsilon",
        "node-gamma": "perception-gamma",
        "node-delta": "perception-delta",
    },
    "cognitive": {
        "node-epsilon": "cognitive-alt",
        "node-gamma": "cognitive-fast",
        "node-delta": "cognitive-core",
    },
    "synthesis": {
        "node-epsilon": "synthesis-epsilon",
        "node-gamma": "synthesis-v1-alt",
        "node-delta": "synthesis-delta",
    },
    "transport": {
        "node-p": "transport-p2",
        "node-v": "transport-v3",
    },
}


def get_vector_domain_logic(identity: str) -> str:
    """Retrieves the underlying domain logic associated with a vector identity."""
    if identity.startswith("perception-gamma") or identity.startswith("cognitive-fast"):
        return "node-gamma"
    if identity.startswith("perception-delta") or identity.startswith("cognitive-core"):
        return "node-delta"
    if identity in {"cognitive-alt", "perception-epsilon", "synthesis-epsilon"}:
        return "node-epsilon"
    if identity.startswith("perception-beta"):
        return "node-beta"
    if identity == "transport-v3":
        return "node-v"
    if identity == "transport-p2":
        return "node-p"
    return identity


def map_identity_to_vector(identity: str, domain: str) -> str:
    """Maps a canonical identity to its category-specific structural vector ID."""
    normalized = identity.strip()
    if not normalized:
        return normalized

    logic = get_vector_domain_logic(normalized)
    return _VECTOR_BLUEPRINT_MAP.get(domain, {}).get(logic, normalized)


normalize_provider_name = map_identity_to_vector


def get_node_specification(identity: str) -> str | None:
    """Exposes localized node specification only when it diverges from its parent logic."""
    logic = get_vector_domain_logic(identity)
    if logic == identity:
        return None
    return identity