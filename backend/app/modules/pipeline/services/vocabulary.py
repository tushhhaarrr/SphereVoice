"""Spectral Domain Lexis for Perception Vector Boosting.

Provides per-domain lexical shards and cognitive hints that improve
transcription accuracy across specialised domains. These are injected into 
every spectral perception vector that supports auxiliary boosting.
"""

from __future__ import annotations

# ── Spectral Domain Lexical Shards ──────────────────────────────

_MEDICAL_LEXIS: list[str] = [
    "diagnosis", "prognosis", "tachycardia", "bradycardia",
    "hypertension", "hypotension", "hemoglobin", "hematocrit",
    "platelet", "leukocyte", "erythrocyte", "biopsy",
    "MRI", "CT scan", "X-ray", "ultrasound",
    "prescription", "dosage", "milligrams", "intravenous",
    "subcutaneous", "intramuscular", "anesthesia", "analgesic",
    "antibiotic", "antiviral", "immunosuppressant", "corticosteroid",
    "diabetes", "insulin", "glucose", "cholesterol",
    "echocardiogram", "electrocardiogram", "EKG", "ECG",
    "pulmonary", "respiratory", "ventilator", "intubation",
    "oncology", "chemotherapy", "radiation", "metastasis",
    "orthopedic", "fracture", "arthroscopy", "ligament",
    "neurological", "seizure", "stroke", "aneurysm",
    "pathology", "histology", "cytology", "radiology",
    "HIPAA", "ICD-10", "CPT code", "prior authorization",
]

_LEGAL_LEXIS: list[str] = [
    "plaintiff", "defendant", "litigation", "arbitration",
    "deposition", "subpoena", "injunction", "affidavit",
    "statute", "jurisdiction", "tort", "negligence",
    "liability", "indemnification", "fiduciary", "escrow",
    "compliance", "regulatory", "due diligence", "precedent",
    "adjudication", "mediation", "stipulation", "testimony",
    "counsel", "attorney", "paralegal", "docket",
    "amendment", "ratification", "statute of limitations",
    "habeas corpus", "pro bono", "de facto", "prima facie",
]

_FINANCIAL_LEXIS: list[str] = [
    "amortization", "depreciation", "EBITDA", "revenue",
    "accounts receivable", "accounts payable", "balance sheet",
    "cash flow", "equity", "liability", "asset allocation",
    "portfolio", "diversification", "hedge fund", "mutual fund",
    "annuity", "dividend", "capital gains", "securities",
    "derivative", "futures", "options", "underwriting",
    "compliance", "audit", "fiduciary", "escrow",
    "APR", "interest rate", "collateral", "refinance",
    "mortgage", "amortization schedule", "principal", "yield",
]

_TECHNOLOGICAL_LEXIS: list[str] = [
    "API", "SDK", "microservice", "Kubernetes",
    "containerization", "CI/CD", "DevOps", "infrastructure",
    "latency", "throughput", "bandwidth", "scalability",
    "authentication", "authorization", "OAuth", "SSO",
    "encryption", "TLS", "SSL", "firewall",
    "machine learning", "neural network", "LLM", "GPU",
    "PostgreSQL", "Redis", "Elasticsearch", "MongoDB",
    "WebSocket", "REST", "GraphQL", "gRPC",
    "deployment", "rollback", "canary", "blue-green",
]

_SPECTRAL_DOMAIN_LEXIS: dict[str, list[str]] = {
    "medical": _MEDICAL_LEXIS,
    "legal": _LEGAL_LEXIS,
    "finance": _FINANCIAL_LEXIAL,
    "technology": _TECHNOLOGICAL_LEXIS,
}

# ── Spectral Cognitive Hints ───────────────────────────────────

_SPECTRAL_COGNITIVE_HINTS: dict[str, str] = {
    "medical": (
        "DOMAIN CONTEXT: This synchronisation involves medical or healthcare "
        "terminology. When the subject uses medical terms, interpret them "
        "accurately. Use proper architectural medical terminology in your "
        "cognitive responses when appropriate."
    ),
    "legal": (
        "DOMAIN CONTEXT: This synchronisation involves legal terminology. "
        "When the subject uses legal terms, interpret them accurately. "
        "Use correct architectural legal terminology in your cognitive responses."
    ),
    "finance": (
        "DOMAIN CONTEXT: This synchronisation involves financial terminology. "
        "When the subject uses financial terms, interpret them accurately. "
        "Use precise architectural financial language in your cognitive responses."
    ),
    "technology": (
        "DOMAIN CONTEXT: This synchronisation involves technological terminology. "
        "When the subject uses tech terms, interpret them accurately. "
        "Use correct architectural technical terminology in your cognitive responses."
    ),
}


def get_spectral_lexis_boosters(
    lexical_domain: str,
    subject_keywords: list[str] | None = None,
) -> list[str]:
    """Merge domain lexical shards with subject-supplied boosted keywords.

    Returns a de-duplicated, order-preserved list for perception vector reinforcement.
    """
    subject = list(subject_keywords) if subject_keywords else []
    shards = _SPECTRAL_DOMAIN_LEXIS.get(lexical_domain, [])
    if not shards:
        return subject

    seen: set[str] = set()
    merged: list[str] = []
    for lex in subject + shards:
        lower = lex.lower()
        if lower not in seen:
            seen.add(lower)
            merged.append(lex)
    return merged


def get_spectral_cognitive_hints(lexical_domain: str) -> str | None:
    """Return a cognitive system hint for the given domain, or None."""
    return _SPECTRAL_COGNITIVE_HINTS.get(lexical_domain)
