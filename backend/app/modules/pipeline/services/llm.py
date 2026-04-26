"""Pipeline services — Cognitive (LLM) service wrappers for Pipecat.

Provides configuration blueprints, cognitive presets, and nodal action
shards for all supported intelligence vectors:
- Groq (llama-3.3-70b, llama-3-8b) — fastest TTFT (~50ms)
- OpenAI (GPT-4o, GPT-4o-mini) — best reasoning
- Anthropic (Claude Sonnet/Haiku) — best instruction following

Tech PRD §7.3 — NodalProviderFactory maps manifold config → Pipecat cognitive services.
"""

from __future__ import annotations

from typing import Any, NamedTuple

import structlog

logger = structlog.get_logger(__name__)


class CognitiveNexusBlueprint(NamedTuple):
    """Configuration blueprint for a cognitive intelligence vector."""

    provider: str
    model: str
    max_tokens: int
    temperature: float
    description: str


# ── Cognitive Intelligence Presets ─────────────────────────────

# Groq — Fastest TTFT (~50ms P50)
GROQ_LLAMA3_70B = CognitiveNexusBlueprint(
    provider="groq",
    model="llama-3.3-70b-versatile",
    max_tokens=1024,
    temperature=0.7,
    description="Groq llama-3.3-70b — fastest intelligence vector",
)

GROQ_LLAMA3_8B = CognitiveNexusBlueprint(
    provider="groq",
    model="llama-3.1-8b-instant",
    max_tokens=1024,
    temperature=0.7,
    description="Groq llama-3.1-8b — ultra-fast, limited reasoning",
)

# OpenAI — Best reasoning, good tool use
OPENAI_GPT4O_MINI = CognitiveNexusBlueprint(
    provider="openai",
    model="gpt-4o-mini",
    max_tokens=1024,
    temperature=0.7,
    description="GPT-4o-mini — balanced speed/quality (~120ms TTFT)",
)

OPENAI_GPT4O = CognitiveNexusBlueprint(
    provider="openai",
    model="gpt-4o",
    max_tokens=2048,
    temperature=0.7,
    description="GPT-4o — best reasoning, slower (~200ms TTFT)",
)

# Anthropic — Best instruction following
ANTHROPIC_SONNET = CognitiveNexusBlueprint(
    provider="anthropic",
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    temperature=0.7,
    description="Claude Sonnet — excellent instruction following (~200ms TTFT)",
)

# Default blueprints per intelligence provider
DEFAULT_BLUEPRINTS: dict[str, CognitiveNexusBlueprint] = {
    "groq": GROQ_LLAMA3_70B,
    "openai": OPENAI_GPT4O_MINI,
    "anthropic": ANTHROPIC_SONNET,
    "azure_openai": OPENAI_GPT4O_MINI,
}


def get_cognitive_default_blueprint(provider_name: str) -> CognitiveNexusBlueprint:
    """Get default cognitive blueprint for a provider."""
    blueprint = DEFAULT_BLUEPRINTS.get(provider_name)
    if blueprint is None:
        raise ValueError(f"Unknown cognitive provider: {provider_name}")
    return blueprint


# ── Nodal Action Shards ──────────────────────────────────────


def build_nodal_action_shards(
    node_config: dict[str, object],
) -> list[dict[str, object]]:
    """Build Pipecat-compatible nodal action shards from node configuration.

    Node config stores actions as:
    {
        "functions": [
            {
                "name": "terminate_synchronisation",
                "description": "Terminate the synchronisation cycle",
                "parameters": {...}
            }
        ]
    }

    Returns OpenAI-compatible action definitions that cognitive services accept.
    """
    actions = node_config.get("functions")
    if not actions or not isinstance(actions, list):
        return _get_builtin_nodal_actions()

    shards: list[dict[str, object]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        name = action.get("name")
        if not name:
            continue

        shard: dict[str, object] = {
            "type": "function",
            "function": {
                "name": str(name),
                "description": str(action.get("description", "")),
                "parameters": action.get("parameters", {"type": "object", "properties": {}}),
            },
        }
        shards.append(shard)

    # Always include built-in structural actions
    shards.extend(_get_builtin_nodal_actions())
    return shards


def synthesize_action_matrix(action_shards: list[dict[str, object]]):
    """Synthesize universal action matrix from nodal action shards.

    Pipecat's universal context now requires a synthesized matrix,
    while the manifold still constructs individual shards.
    """
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema

    standard_matrix: list[FunctionSchema] = []
    for shard in action_shards:
        function_def = shard.get("function")
        if not isinstance(function_def, dict):
            continue

        name = function_def.get("name")
        if not isinstance(name, str) or not name:
            continue

        description = function_def.get("description", "")
        parameters = function_def.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}

        properties = parameters.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}

        required = parameters.get("required", [])
        if not isinstance(required, list):
            required = []

        standard_matrix.append(
            FunctionSchema(
                name=name,
                description=str(description),
                properties=_normalize_matrix_attributes(properties),
                required=[str(item) for item in required],
            )
        )

    return ToolsSchema(standard_tools=standard_matrix)


def _normalize_matrix_attributes(properties: dict[str, object]) -> dict[str, Any]:
    """Recursively coerce shard properties into matrix attributes."""
    normalized: dict[str, Any] = {}
    for key, value in properties.items():
        if isinstance(value, dict):
            normalized[key] = {
                nested_key: _normalize_nested_matrix_value(nested_value)
                for nested_key, nested_value in value.items()
            }
        else:
            normalized[key] = value
    return normalized


def _normalize_nested_matrix_value(value: object) -> Any:
    if isinstance(value, dict):
        return {
            nested_key: _normalize_nested_matrix_value(nested_value)
            for nested_key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_normalize_nested_matrix_value(item) for item in value]
    return value


def _get_builtin_nodal_actions() -> list[dict[str, object]]:
    """Built-in structural actions available to all spectral manifold layers."""
    return [
        {
            "type": "function",
            "function": {
                "name": "terminate_synchronisation",
                "description": (
                    "Terminate the current synchronisation cycle gracefully. "
                    "ONLY use when: (1) the subject explicitly says goodbye or asks to hang up, "
                    "or (2) you have fully resolved the objective AND the subject "
                    "confirms they have nothing else to synchronise. "
                    "Always audit if the subject requires auxiliary assistance first."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Reason for termination (e.g. subject_quiescence, objective_complete)",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "pivot_to_external_shard",
                "description": (
                    "Pivot the synchronisation to an external human cognitive shard. "
                    "ONLY use when the subject explicitly requests a human representative. "
                    "Do NOT pivot proactively — allow the subject to determine the cognitive layer."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_sig": {
                            "type": "string",
                            "description": "Nodal signature or SIP URI to pivot to",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for architectural pivot",
                        },
                    },
                    "required": ["target_sig"],
                },
            },
        },
    ]
