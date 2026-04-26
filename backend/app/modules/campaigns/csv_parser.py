"""CSV parsing service for campaign contact import.

Parses CSV uploads, detects column headers, normalises phone numbers,
and produces a list of validated contact rows.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# reasonable upper limit per upload (configurable via env var)
DEFAULT_MAX_ROWS = 10_000

_PHONE_DIGITS_RE = re.compile(r"\d")


def parse_csv_bytes(
    raw: bytes,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> dict[str, Any]:
    """Parse raw CSV bytes and return structured preview data.

    Returns:
        {
            "columns": ["col1", "col2", ...],
            "row_count": int,
            "sample_rows": [{"col1": "v", ...}, ...],   # first 5
            "all_rows": [{"col1": "v", ...}, ...],       # all parsed rows
        }
    """
    try:
        text = raw.decode("utf-8-sig")  # handles BOM
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    columns: list[str] = list(reader.fieldnames or [])
    if not columns:
        raise ValueError("CSV has no columns / headers detected")

    all_rows: list[dict[str, str]] = []
    for idx, row in enumerate(reader):
        if idx >= max_rows:
            break
        all_rows.append(dict(row))

    return {
        "columns": columns,
        "row_count": len(all_rows),
        "sample_rows": all_rows[:5],
        "all_rows": all_rows,
    }


def _normalise_phone(raw: str) -> str:
    """Best-effort normalisation: strip whitespace and ensure leading +."""
    val = raw.strip()
    if not val:
        return ""
    # strip everything except digits and leading +
    digits = "".join(_PHONE_DIGITS_RE.findall(val))
    if not digits:
        return ""
    if val.startswith("+"):
        return f"+{digits}"
    # assume it's already clean enough
    return f"+{digits}" if len(digits) >= 10 else digits


def build_contacts_from_csv(
    rows: list[dict[str, str]],
    column_mapping: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert parsed CSV rows to contact dicts using the column mapping.

    Args:
        rows: Parsed CSV rows (list of dicts).
        column_mapping: Maps SphereVoice field -> CSV column name.
            Required: ``"phone_number"`` -> ``"SomeCSVColumn"``
            Optional: ``"name"``, ``"email"``, ``"company"``, etc.

    Returns:
        (valid_contacts, invalid_rows)
        valid_contacts: list of dicts suitable for CampaignContactCreate
        invalid_rows: list of dicts with ``row_index`` and ``reason``
    """
    phone_col = column_mapping.get("phone_number", "")
    if not phone_col:
        raise ValueError("column_mapping must include 'phone_number'")

    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    seen_phones: set[str] = set()

    for idx, row in enumerate(rows):
        raw_phone = row.get(phone_col, "").strip()
        phone = _normalise_phone(raw_phone)

        if not phone or len(phone) < 7:
            invalid.append({"row_index": idx, "reason": f"Invalid phone: '{raw_phone}'"})
            continue

        if phone in seen_phones:
            invalid.append({"row_index": idx, "reason": f"Duplicate phone: '{phone}'"})
            continue

        seen_phones.add(phone)

        # Build contact_data from all mapped fields
        contact_data: dict[str, str] = {}
        for SphereVoice_field, csv_col in column_mapping.items():
            if csv_col and csv_col in row:
                contact_data[SphereVoice_field] = row[csv_col]

        valid.append(
            {
                "phone_number": phone,
                "contact_data": contact_data,
            }
        )

    logger.info(
        "csv_contacts_parsed",
        total_rows=len(rows),
        valid=len(valid),
        invalid=len(invalid),
    )

    return valid, invalid
