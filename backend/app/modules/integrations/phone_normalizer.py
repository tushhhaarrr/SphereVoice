"""Phone number normalization for CRM lookup.

Converts messy phone formats from Zoho CRM sheets and Twilio webhooks
into a consistent set of search variants so we can match a caller
regardless of how the number was stored.

Current focus: Indian numbers (+91).  Designed to be extended with more
country configs later.

Example inputs and how they're handled:
    +919876543210     → ["+919876543210", "919876543210", "09876543210", "9876543210"]
    919876543210      → ["+919876543210", "919876543210", "09876543210", "9876543210"]
    09876543210       → ["+919876543210", "919876543210", "09876543210", "9876543210"]
    98765 43210       → ["+919876543210", "919876543210", "09876543210", "9876543210"]
    +1 (415) 555-0101 → ["+14155550101", "14155550101", "4155550101"]  (US fallback)
"""

from __future__ import annotations

import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ── Country configs ──────────────────────────────────────────
# Each entry: (country_code_digits, local_number_length, trunk_prefix)
# trunk_prefix is what locals dial before the number (e.g. "0" in India)

_COUNTRY_CONFIGS: dict[str, dict[str, Any]] = {
    "IN": {
        "code": "91",
        "local_length": 10,    # 10-digit mobile/landline
        "trunk_prefix": "0",   # Indians dial 0xxxx for STD
    },
    "US": {
        "code": "1",
        "local_length": 10,
        "trunk_prefix": "1",   # US doesn't use trunk prefix in same way
    },
}

# Default country when no country code is detected
_DEFAULT_COUNTRY = "IN"


def _strip_formatting(phone: str) -> str:
    """Remove all formatting characters, keeping only digits and leading +."""
    stripped = phone.strip()
    if stripped.startswith("+"):
        return "+" + re.sub(r"[^\d]", "", stripped[1:])
    return re.sub(r"[^\d]", "", stripped)


def normalize_phone(
    phone: str,
    *,
    default_country: str = _DEFAULT_COUNTRY,
) -> str:
    """Normalize a phone number to E.164 format.

    Returns the canonical E.164 form (e.g. "+919876543210") using the
    *default_country* when no country code is detected.

    This is the single canonical form stored/compared in our system.
    """
    clean = _strip_formatting(phone)
    if not clean:
        return phone  # Can't normalize empty input

    country_cfg = _COUNTRY_CONFIGS.get(default_country, _COUNTRY_CONFIGS["IN"])
    code = country_cfg["code"]
    local_len = country_cfg["local_length"]
    trunk = country_cfg["trunk_prefix"]

    # Already has + prefix → trust it
    if clean.startswith("+"):
        return clean

    digits = clean

    # Check if it starts with the country code
    if digits.startswith(code) and len(digits) == len(code) + local_len:
        return f"+{digits}"

    # Check if it starts with trunk prefix (e.g. "0" in India)
    if trunk and digits.startswith(trunk) and len(digits) == len(trunk) + local_len:
        return f"+{code}{digits[len(trunk):]}"

    # Bare local number
    if len(digits) == local_len:
        return f"+{code}{digits}"

    # Fallback: prepend + if looks like it has a country code
    if len(digits) > local_len:
        return f"+{digits}"

    # Can't determine format — return with + prefix as best guess
    return f"+{digits}"


def phone_search_variants(
    phone: str,
    *,
    default_country: str = _DEFAULT_COUNTRY,
) -> list[str]:
    """Generate all format variants for CRM search.

    Zoho CRM contacts may store the phone in any format. We generate
    all common variants and search for each until we find a match.

    Returns a deduplicated list ordered from most specific to least.
    """
    e164 = normalize_phone(phone, default_country=default_country)
    clean = _strip_formatting(phone)
    if not clean:
        return [phone]

    country_cfg = _COUNTRY_CONFIGS.get(default_country, _COUNTRY_CONFIGS["IN"])
    code = country_cfg["code"]
    local_len = country_cfg["local_length"]
    trunk = country_cfg["trunk_prefix"]

    variants: list[str] = []

    # 1. Full E.164: +919876543210
    variants.append(e164)

    # 2. Without +: 919876543210
    if e164.startswith("+"):
        variants.append(e164[1:])

    # 3. Extract the local part
    digits = e164.lstrip("+")
    local_part: str | None = None

    if digits.startswith(code) and len(digits) >= len(code) + local_len:
        local_part = digits[len(code) : len(code) + local_len]
    elif len(digits) == local_len:
        local_part = digits

    if local_part:
        # 4. With trunk prefix: 09876543210
        if trunk and trunk != code:
            variants.append(f"{trunk}{local_part}")

        # 5. Bare local: 9876543210
        variants.append(local_part)

        # 6. Common Indian display formats for broader matching
        if default_country == "IN" and len(local_part) == 10:
            # +91-98765-43210 (hyphenated)
            variants.append(f"+{code}-{local_part[:5]}-{local_part[5:]}")
            # +91 98765 43210 (spaced)
            variants.append(f"+{code} {local_part[:5]} {local_part[5:]}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)

    return unique
