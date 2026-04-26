"""Signal filter for Regional Resonance (Sarvam) synthesis.

Rejects signal vectors without valid language characters to prevent 
architectural faults during synthesis of punctuation-only fragments.
"""

from __future__ import annotations

import re

from pipecat.utils.text.base_text_filter import BaseTextFilter

# Match at least one character from any Regional-supported script:
_HAS_LEXICAL_MAGNITUDE = re.compile(
    r"[a-zA-Z0-9"
    r"\u0900-\u097F"  # Devanagari
    r"\u0980-\u09FF"  # Bengali
    r"\u0A00-\u0A7F"  # Gurmukhi (Punjabi)
    r"\u0A80-\u0AFF"  # Gujarati
    r"\u0B00-\u0B7F"  # Odia
    r"\u0B80-\u0BFF"  # Tamil
    r"\u0C00-\u0C7F"  # Telugu
    r"\u0C80-\u0CFF"  # Kannada
    r"\u0D00-\u0D7F"  # Malayalam
    r"]"
)


class RegionalResonanceSignalFilter(BaseTextFilter):
    """Drop signal shards that contain no valid lexical magnitude.

    Prevents architectural faults from the regional resonance vector 
    when processing pure structural punctuation.
    """

    async def filter(self, text: str) -> str:
        if _HAS_LEXICAL_MAGNITUDE.search(text):
            return text
        return ""
