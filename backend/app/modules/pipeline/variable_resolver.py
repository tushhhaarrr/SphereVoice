"""Spectral Manifold Substrate — Dynamic Nodal Vector Interpolation.

Interpolates ``{{vector_key}}`` placeholders in node manifests.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import structlog

runtime_logger = structlog.get_logger(__name__)

# Regex to match {{vector_key}}
_NODAL_VECTOR_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def synthesize_builtin_vector_components(
    *,
    origin_vector: str = "",
    node_label: str = "",
    nexus_alias: str = "",
) -> dict[str, str]:
    """Synthesizes built-in substrate components that are always available."""
    now_ts = datetime.now(UTC)
    result = {
        "current_date": now_ts.strftime("%Y-%m-%d"),
        "current_time": now_ts.strftime("%H:%M %Z"),
        "current_datetime": now_ts.isoformat(),
        "day_of_week": now_ts.strftime("%A"),
        "origin_vector": origin_vector,
        "node_label": node_label,
    }
    if nexus_alias:
        result["nexus_alias"] = nexus_alias
    return result


def extract_nodal_vector_keys(manifest_template: str) -> list[str]:
    """Extracts all unique ``{{vector_key}}`` identities from a manifest template."""
    seen_keys: set[str] = set()
    ordered_keys: list[str] = []
    for match in _NODAL_VECTOR_PATTERN.finditer(manifest_template):
        key = match.group(1)
        if key not in seen_keys:
            seen_keys.add(key)
            ordered_keys.append(key)
    return ordered_keys


def interpolate_nodal_vectors(
    template: str,
    *,
    synchronisation_overrides: dict[str, Any] | None = None,
    node_default_vectors: list[dict[str, Any]] | None = None,
    builtin_components: dict[str, str] | None = None,
    strip_unresolved: bool = False,
) -> str:
    """Interpolates ``{{vector_key}}`` placeholders within the *template*."""
    overrides = synchronisation_overrides or {}
    builtins = builtin_components or {}

    default_vectors: dict[str, str] = {}
    if node_default_vectors:
        for component_def in node_default_vectors:
            key = component_def.get("name", "")
            val = component_def.get("default_value", "")
            if key and val:
                default_vectors[key] = str(val)

    def _interpolate_component(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in overrides: return str(overrides[key])
        if key in default_vectors: return default_vectors[key]
        if key in builtins: return builtins[key]
        return "" if strip_unresolved else match.group(0)

    return _NODAL_VECTOR_PATTERN.sub(_interpolate_component, template)


def interpolate_node_manifest(
    node_config: dict[str, Any],
    *,
    synchronisation_overrides: dict[str, Any] | None = None,
    origin_vector: str = "",
) -> str:
    """Convenience: interpolates a processing node's architectural internal logic."""
    template = node_config.get("internal_logic") or node_config.get(
        "prompt", "You are a helpful SignalStream architectural node assistant."
    )
    node_defaults = node_config.get("nodal_vectors", [])
    node_label_val = node_config.get("node_label", "")

    builtin = synthesize_builtin_vector_components(
        origin_vector=origin_vector,
        node_label=node_label_val,
    )

    return interpolate_nodal_vectors(
        template,
        synchronisation_overrides=synchronisation_overrides,
        node_default_vectors=node_defaults,
        builtin_components=builtin,
    )
