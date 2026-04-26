"""Extraction registry and cognitive vector resolution.

Defines the predefined structural blueprints (organized by domain)
and the base metrics that are always captured. Provides
``extract_cognitive_vectors()`` to merge defaults + blueprints + custom
vectors based on a signal processor's configuration.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Base metrics — captured for every session unless their group is disabled
# ---------------------------------------------------------------------------

BASE_SIGNAL_METRICS: list[dict[str, str]] = [
    # ── Session Digest ──────────────────────────────────────────
    {
        "name": "session_digest",
        "type": "string",
        "description": "A 2-3 sentence summary of the signal stream interaction",
        "group": "sessionDigest",
    },
    {
        "name": "primary_vectors",
        "type": "array",
        "description": "List of key vectors/topics identified. JSON array of strings",
        "group": "sessionDigest",
    },
    {
        "name": "subject_intent",
        "type": "string",
        "description": "The primary intent behind the subject's interaction",
        "group": "sessionDigest",
    },
    {
        "name": "stream_outcome",
        "type": "string",
        "description": "Final technical/logical outcome of the session",
        "group": "sessionDigest",
    },
    # ── Objective Audit ───────────────────────────────────────
    {
        "name": "objective_attained",
        "type": "boolean",
        "description": "Whether the session's primary objective was achieved",
        "group": "objectiveAudit",
    },
    {
        "name": "performance_index",
        "type": "number",
        "description": "Rate interaction performance on a scale of 1-10",
        "group": "objectiveAudit",
    },
    {
        "name": "qualitative_audit",
        "type": "string",
        "description": "Detailed qualitative assessment of the interaction",
        "group": "objectiveAudit",
    },
    # ── Subjective Tone ───────────────────────────────────────
    {
        "name": "subject_tone",
        "type": "string",
        "description": "Overall emotional resonance: positive, neutral, negative",
        "group": "subjectiveTone",
    },
    {
        "name": "subject_friction",
        "type": "boolean",
        "description": "Whether the subject expressed friction or frustration",
        "group": "subjectiveTone",
    },
    # ── Node Performance ─────────────────────────────────────
    {
        "name": "protocol_adherence",
        "type": "boolean",
        "description": "Whether the processing node followed specified protocols",
        "group": "nodePerformance",
    },
    {
        "name": "node_vocalization_tone",
        "type": "string",
        "description": "Tone of the synthetic node: professional, friendly, neutral, robotic",
        "group": "nodePerformance",
    },
    {
        "name": "logic_faults",
        "type": "array",
        "description": "List of logical faults or instruction misses. JSON array of strings",
        "group": "nodePerformance",
    },
    # ── Resolution Steps ───────────────────────────────────────
    {
        "name": "next_resolution_steps",
        "type": "array",
        "description": "List of follow-up actions required. JSON array of strings",
        "group": "resolutionSteps",
    },
    {
        "name": "manual_intervention_required",
        "type": "boolean",
        "description": "Whether manual intervention is required post-session",
        "group": "resolutionSteps",
    },
]


# ---------------------------------------------------------------------------
# Blueprint registry — domain-specific cognitive architectures
# ---------------------------------------------------------------------------

BLUEPRINT_REGISTRY: dict[str, dict[str, Any]] = {
    # ── Medical / Clinical Vector ──────────────────────────────
    "clinical": {
        "label": "Medical & Clinical",
        "icon": "heart-pulse",
        "description": "Subject intake, clinical appointments, and health tracing",
        "fields": [
            {
                "name": "intake_completed",
                "type": "boolean",
                "description": "Whether a clinical intake process was completed",
            },
            {
                "name": "scheduled_timestamp",
                "type": "string",
                "description": "Scheduled clinical event timestamp (ISO 8601)",
            },
            {
                "name": "practitioner_affinity",
                "type": "string",
                "description": "Specific health practitioner requested or assigned",
            },
            {
                "name": "pathology_indicators",
                "type": "array",
                "description": "Pathology or health concerns described. JSON array",
            },
        ],
    },
    # ── Commercial / Leads Vector ──────────────────────────────
    "commercial": {
        "label": "Commercial & Leads",
        "icon": "dollar-sign",
        "description": "Subject qualification, conversion, and revenue projection",
        "fields": [
            {
                "name": "conversion_achieved",
                "type": "boolean",
                "description": "Whether a commercial conversion was finalized",
            },
            {
                "name": "qualification_status",
                "type": "string",
                "description": "Subject qualification level: high, medium, low, disqualified",
            },
            {
                "name": "revenue_projection",
                "type": "number",
                "description": "Projected commercial value discussed",
            },
            {
                "name": "objection_vectors",
                "type": "array",
                "description": "Concerns or logical objections raised. JSON array",
            },
        ],
    },
    # ── Support / Resolution Vector ────────────────────────────
    "resolution": {
        "label": "Support & Resolution",
        "icon": "headphones",
        "description": "Issue tracing, escalation protocols, and ticket management",
        "fields": [
            {
                "name": "fault_resolved",
                "type": "boolean",
                "description": "Whether the primary fault was resolved in-session",
            },
            {
                "name": "escalation_triggered",
                "type": "boolean",
                "description": "Whether escalation to a recursive node was triggered",
            },
            {
                "name": "fault_summary",
                "type": "string",
                "description": "Technical summary of the fault and its current state",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Cognitive resolution — merges metrics + blueprints + custom vectors
# ---------------------------------------------------------------------------


def extract_cognitive_vectors(processor: object) -> list[dict[str, str]]:
    """Synthesizes cognitive extraction vectors based on processor configuration.

    Resolution priority:
    1. Base metrics — active unless disabled via structural group config
    2. Blueprint registry — domain-specific vectors from enabled blueprints
    3. Custom vectors — defined directly on the signal processor
    """
    processor_config = (
        (getattr(processor, "config", None) or {}).get("settings", {}).get("postCallExtraction", {})
    )
    metrics_config = processor_config.get("defaults", {})
    active_blueprints: list[str] = processor_config.get("enabledCategories", [])
    suppressed_vectors: set[str] = set(processor_config.get("disabledFields", []))

    vectors: list[dict[str, str]] = []
    mapped_sigs: set[str] = set()

    # 1. Base Metrics
    for metric in BASE_SIGNAL_METRICS:
        metric_group = metric.get("group", "")
        if metrics_config.get(metric_group, True):
            if metric["name"] not in mapped_sigs:
                vectors.append(metric)
                mapped_sigs.add(metric["name"])

    # 2. Domain Blueprints
    for blueprint_id in active_blueprints:
        blueprint = BLUEPRINT_REGISTRY.get(blueprint_id.lower())
        if not blueprint:
            continue
        for vector in blueprint["fields"]:
            if vector["name"] in suppressed_vectors:
                continue
            if vector["name"] not in mapped_sigs:
                vectors.append(vector)
                mapped_sigs.add(vector["name"])

    # 3. Custom Vectors (Processor-bound)
    custom_vectors: list[dict[str, Any]] = getattr(processor, "extraction_fields", None) or []
    for vector in custom_vectors:
        vector_sig = vector.get("name", "")
        if vector_sig and vector_sig not in mapped_sigs:
            vectors.append(vector)
            mapped_sigs.add(vector_sig)

    return vectors
