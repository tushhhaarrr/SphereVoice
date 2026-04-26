"""Fetch and register ElevenLabs Indic voice metadata for SphereVoice.

Usage:
    # Use ELEVENLABS_API_KEY from .env (requires voices_read permission):
    python scripts/fetch_elevenlabs_indic_voices.py

    # Or pass a key explicitly:
    ELEVENLABS_API_KEY=sk_xxx python scripts/fetch_elevenlabs_indic_voices.py

    # Output as service.py catalog entries:
    python scripts/fetch_elevenlabs_indic_voices.py --format=catalog

The API key must have 'voices_read' permission enabled.
Go to https://elevenlabs.io/app/settings/api-keys to update permissions.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

TARGET_NAMES = [
    "Raju", "Leo", "Krishna", "Muskaan", "Viraj",
    "Riya Rao", "Anjali", "Bunty", "Ranbir", "Aakash Aryan",
]


def _get_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        # Try reading from .env file in the backend directory
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ELEVENLABS_API_KEY=") and not line.startswith("#"):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not key:
        print("ERROR: ELEVENLABS_API_KEY not found in environment or .env file")
        sys.exit(1)
    return key


def api_get(url: str, headers: dict | None = None, params: dict | None = None) -> dict:
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def _extract_voice_meta(v: dict) -> dict:
    labels = v.get("labels", {}) if isinstance(v.get("labels"), dict) else {}
    return {
        "voice_id": v.get("voice_id", ""),
        "name": v.get("name", ""),
        "labels": labels,
        "category": v.get("category", ""),
        "description": (v.get("description") or "")[:200],
        "preview_url": v.get("preview_url", ""),
        "high_quality_base_model_ids": v.get("high_quality_base_model_ids", []),
        "language": labels.get("language", ""),
        "gender": labels.get("gender", ""),
        "accent": labels.get("accent", ""),
    }


def main() -> None:
    api_key = _get_api_key()
    headers = {"xi-api-key": api_key}
    output_format = "catalog" if "--format=catalog" in sys.argv else "json"

    found: dict[str, dict] = {}

    # 1) Check own/saved voices
    print("=== Checking own voices ===")
    try:
        own_voices = api_get("https://api.elevenlabs.io/v1/voices", headers=headers).get("voices", [])
        print(f"  Account has {len(own_voices)} voice(s)")
        for v in own_voices:
            name = v.get("name", "")
            if name in TARGET_NAMES:
                found[name] = _extract_voice_meta(v)
                print(f"  FOUND: {name} -> {v.get('voice_id')}")
    except Exception as e:
        print(f"  Error fetching own voices: {e}")
        print("  NOTE: API key needs 'voices_read' permission.")
        print("  Update at: https://elevenlabs.io/app/settings/api-keys")

    missing = [n for n in TARGET_NAMES if n not in found]
    if missing:
        print(f"\n=== Searching shared library for {len(missing)} missing voices ===")

    # 2) Search shared voice library for missing ones
    for name in missing:
        try:
            data = api_get(
                "https://api.elevenlabs.io/v1/shared-voices",
                headers=headers,
                params={"search": name, "page_size": 5},
            )
            voices = data.get("voices", [])
            matched = False
            for v in voices:
                vname = v.get("name", "")
                if name.lower() in vname.lower():
                    found[name] = _extract_voice_meta(v)
                    print(f"  FOUND: {name} -> {v.get('voice_id')} (shared library)")
                    matched = True
                    break
            if not matched:
                print(f"  NOT FOUND: {name} (searched {len(voices)} results)")
        except Exception as e:
            print(f"  {name}: Error: {e}")
        time.sleep(0.3)  # Rate limit

    # 3) Output results
    print(f"\n\n{'=' * 60}")
    print(f"RESULTS: Found {len(found)}/{len(TARGET_NAMES)} voices")
    print(f"{'=' * 60}\n")

    if output_format == "catalog":
        # Output as _static_provider_voices entries for service.py
        print("# Paste into _static_provider_voices() for provider_name == 'elevenlabs':")
        print("# These voice IDs are from the ElevenLabs voice library.")
        print()
        for name in TARGET_NAMES:
            if name not in found:
                print(f"# WARNING: {name} not found - keeping placeholder ID")
                continue
            v = found[name]
            vid = v["voice_id"]
            gender = v["gender"] or "male"
            lang = v["language"] or "hi"
            accent = v["accent"] or "indian"
            desc = v["description"] or f"{name} - ElevenLabs Indic voice"
            print(
                f'_catalog_item("{vid}", "{name}", '
                f'description="{desc}", '
                f'language="{lang}", locale="hi-IN", '
                f'gender="{gender}", '
                f'tags=["indic", "{accent}", "hindi", "eleven_multilingual_v2"]),'
            )
    else:
        for name in TARGET_NAMES:
            if name in found:
                v = found[name]
                print(f"{name}:")
                print(f"  voice_id: {v['voice_id']}")
                print(f"  gender:   {v['gender']}")
                print(f"  language: {v['language']}")
                print(f"  accent:   {v['accent']}")
                print(f"  category: {v['category']}")
                print(f"  desc:     {v['description'][:80]}")
                print(f"  models:   {v['high_quality_base_model_ids']}")
                print()
            else:
                print(f"{name}: NOT FOUND")
                print()

    not_found = [n for n in TARGET_NAMES if n not in found]
    if not_found:
        print(f"\nMissing voices: {not_found}")
        print("These voices may not be in the ElevenLabs shared library,")
        print("or the API key may need 'voices_read' permission.")
        print("Update at: https://elevenlabs.io/app/settings/api-keys")


if __name__ == "__main__":
    main()
