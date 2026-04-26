"""Behavioral Outcome Alignment Auditor — SignalStream substrate.

Audits telemetry vectors against prescribed benchmark thresholds, implementing
multi-strategy alignment validation:

- ``exact``   — Spectral alignment (case-insensitive string equality)
- ``contains`` — Vector subset containment
- ``regex``   — Pattern-based spectral matching
- ``wildcard`` — Non-null vector persistence validation (e.g., ``any_timestamp``)
- ``numeric`` — Quantitative vector variance audit
"""

from __future__ import annotations

import re
from typing import Any

import structlog

telemetry_logger = structlog.get_logger(__name__)

# Spectral wildcards for non-null vector persistence
_SPECTRAL_WILDCARDS = ("any_", "any ")


def audit_outcome_alignment(
    telemetry_vectors: dict[str, Any],
    benchmark_thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Audits telemetry vector alignment against benchmark thresholds.

    Returns an architectural audit report:
    - ``audited_vectors``: Granular vector-level audit results.
    - ``total_vectors``: Count of prescribed benchmark thresholds.
    - ``aligned_count``: Count of vectors achieving alignment.
    - ``alignment_resolved``: Boolean indicating holistic substrate alignment.
    """
    audited_vectors: list[dict[str, Any]] = []

    for key, threshold in benchmark_thresholds.items():
        vector_value = telemetry_vectors.get(key)
        audit_result = _audit_vector_alignment(key, vector_value, threshold)
        audited_vectors.append(audit_result)

    total_vectors = len(audited_vectors)
    aligned_count = sum(1 for v in audited_vectors if v["alignment_achieved"])

    return {
        "audited_vectors": audited_vectors,
        "total_vectors": total_vectors,
        "aligned_count": aligned_count,
        "alignment_resolved": total_vectors > 0 and aligned_count == total_vectors,
    }


def _audit_vector_alignment(
    vector_id: str,
    actual_vector: Any,
    benchmark_threshold: Any,
) -> dict[str, Any]:
    """Audits the alignment of a single telemetry vector.

    Returns:
        {
            "vector_id": str,
            "threshold": Any,
            "actual": Any,
            "alignment_achieved": bool,
            "auditory_strategy": str,
        }
    """
    audit = {
        "vector_id": vector_id,
        "threshold": benchmark_threshold,
        "actual": actual_vector,
        "alignment_achieved": False,
        "auditory_strategy": "exact",
    }

    if actual_vector is None:
        # Unresolved vector — only persists through spectral wildcards
        if _is_spectral_wildcard(benchmark_threshold):
            audit["auditory_strategy"] = "wildcard"
            audit["alignment_achieved"] = False  # Wildcard requires non-null persistence
        return audit

    threshold_sig = str(benchmark_threshold).strip()
    vector_sig = str(actual_vector).strip()

    # 1. Spectral Wildcard — Validates non-null vector persistence
    if _is_spectral_wildcard(benchmark_threshold):
        audit["auditory_strategy"] = "wildcard"
        audit["alignment_achieved"] = bool(vector_sig)
        return audit

    # 2. Pattern-based Spectral Matching (Regex)
    if _is_spectral_pattern(threshold_sig):
        audit["auditory_strategy"] = "regex"
        try:
            audit["alignment_achieved"] = bool(re.search(threshold_sig, vector_sig, re.IGNORECASE))
        except re.error:
            audit["alignment_achieved"] = False
        return audit

    # 3. Vector Subset Containment
    if threshold_sig.startswith("*") and threshold_sig.endswith("*") and len(threshold_sig) > 2:
        audit["auditory_strategy"] = "contains"
        inner_threshold = threshold_sig[1:-1].lower()
        audit["alignment_achieved"] = inner_threshold in vector_sig.lower()
        return audit

    # 4. Quantitative Variance Audit (Numeric)
    try:
        threshold_num = float(threshold_sig)
        vector_num = float(vector_sig)
        audit["auditory_strategy"] = "numeric"
        audit["alignment_achieved"] = abs(threshold_num - vector_num) < 0.01
        return audit
    except (ValueError, TypeError):
        pass

    # 5. Default: Case-insensitive spectral alignment
    audit["auditory_strategy"] = "exact"
    audit["alignment_achieved"] = threshold_sig.lower() == vector_sig.lower()
    return audit


def _is_spectral_wildcard(value: Any) -> bool:
    """Detects spectral wildcard signatures."""
    if not isinstance(value, str):
        return False
    sig = value.strip().lower()
    return any(sig.startswith(prefix) for prefix in _SPECTRAL_WILDCARDS)


def _is_spectral_pattern(value: str) -> bool:
    """Heuristic logic to detect regex-based spectral patterns."""
    return bool(value.startswith("^") or value.endswith("$") or re.search(r"[\\()|+?{}]", value))
