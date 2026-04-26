#!/usr/bin/env python3
"""One-shot SIP trunk setup for Plivo + LiveKit.

Run:
  cd backend && .venv/bin/python scripts/setup_sip_trunks.py              # inbound only
  cd backend && .venv/bin/python scripts/setup_sip_trunks.py --outbound   # inbound + outbound
  cd backend && .venv/bin/python scripts/setup_sip_trunks.py --status     # show current config

This script reads credentials from backend/.env (via dotenv) and:
1. Lists existing SIP trunks on LiveKit
2. Creates an inbound trunk for configured phone numbers (if not exists)
3. Creates a dispatch rule (if not exists)
4. Verifies Plivo-side config (number has a Zentrunk application)
5. (--outbound) Creates a LiveKit outbound SIP trunk using Plivo Zentrunk creds
6. Prints the env vars to add to .env

Note: Plivo Zentrunk SIP trunking is managed via cx.plivo.com console only —
there is no public API for creating/updating Zentrunk trunks. The Plivo Number
API is used here to verify the number has an application (Zentrunk) assigned.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from livekit.api import LiveKitAPI
from livekit.protocol.sip import (
    CreateSIPDispatchRuleRequest,
    CreateSIPInboundTrunkRequest,
    CreateSIPOutboundTrunkRequest,
    ListSIPDispatchRuleRequest,
    ListSIPInboundTrunkRequest,
    ListSIPOutboundTrunkRequest,
    SIPDispatchRule,
    SIPDispatchRuleIndividual,
    SIPInboundTrunkInfo,
    SIPOutboundTrunkInfo,
    SIP_TRANSPORT_TCP,
)

# ── Load .env ────────────────────────────────────────────
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


def _require(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        print(f"ERROR: {name} is not set in {_env_path}")
        sys.exit(1)
    return val


def verify_plivo_number(phone: str, auth_id: str, auth_token: str) -> dict:
    """Check if a Plivo number has a Zentrunk application assigned."""
    num = phone.lstrip("+")
    url = f"https://api.plivo.com/v1/Account/{auth_id}/Number/{num}/"
    r = requests.get(url, auth=(auth_id, auth_token), timeout=10)
    if r.status_code == 200:
        return r.json()
    return {"error": f"HTTP {r.status_code}", "detail": r.text[:200]}


async def list_status(api: LiveKitAPI) -> None:
    """Print current SIP configuration."""
    inbound_resp = await api.sip.list_sip_inbound_trunk(ListSIPInboundTrunkRequest())
    outbound_resp = await api.sip.list_sip_outbound_trunk(ListSIPOutboundTrunkRequest())
    dispatch_resp = await api.sip.list_sip_dispatch_rule(ListSIPDispatchRuleRequest())

    print(f"\nInbound trunks: {len(inbound_resp.items)}")
    for t in inbound_resp.items:
        print(f"  [{t.sip_trunk_id}] {t.name} -> numbers={list(t.numbers)}")

    print(f"\nOutbound trunks: {len(outbound_resp.items)}")
    for t in outbound_resp.items:
        print(f"  [{t.sip_trunk_id}] {t.name} -> addr={t.address}, numbers={list(t.numbers)}")

    print(f"\nDispatch rules: {len(dispatch_resp.items)}")
    for d in dispatch_resp.items:
        print(f"  [{d.sip_dispatch_rule_id}] {d.name} -> trunks={list(d.trunk_ids)}")


async def setup_inbound(api: LiveKitAPI, phone_numbers: list[str], sip_domain: str) -> str:
    """Create inbound trunk + dispatch rule. Returns trunk_id."""
    inbound_resp = await api.sip.list_sip_inbound_trunk(ListSIPInboundTrunkRequest())
    dispatch_resp = await api.sip.list_sip_dispatch_rule(ListSIPDispatchRuleRequest())

    # Check if inbound trunk already exists
    existing_trunk = None
    for t in inbound_resp.items:
        if set(t.numbers) & set(phone_numbers):
            existing_trunk = t
            break

    if existing_trunk:
        print(f"\n>> Inbound trunk already exists: {existing_trunk.sip_trunk_id}")
        trunk_id = existing_trunk.sip_trunk_id
    else:
        print("\n" + "=" * 60)
        print("Creating inbound SIP trunk...")
        print("=" * 60)

        trunk_info = SIPInboundTrunkInfo(
            name=f"Plivo Inbound ({', '.join(phone_numbers)})",
            numbers=phone_numbers,
            krisp_enabled=True,
        )
        trunk = await api.sip.create_sip_inbound_trunk(
            CreateSIPInboundTrunkRequest(trunk=trunk_info)
        )
        trunk_id = trunk.sip_trunk_id
        print(f"  Created! Trunk ID: {trunk_id}")

    # Check/create dispatch rule
    existing_rule = None
    for d in dispatch_resp.items:
        if trunk_id in list(d.trunk_ids):
            existing_rule = d
            break

    if existing_rule:
        print(f">> Dispatch rule already exists: {existing_rule.sip_dispatch_rule_id}")
    else:
        print("\nCreating dispatch rule...")
        rule = SIPDispatchRule(
            dispatch_rule_individual=SIPDispatchRuleIndividual(
                room_prefix="call-plivo-",
            )
        )
        dispatch = await api.sip.create_sip_dispatch_rule(
            CreateSIPDispatchRuleRequest(
                rule=rule,
                name="SphereVoice Plivo Inbound Dispatch",
                trunk_ids=[trunk_id],
            )
        )
        print(f"  Created! Rule ID: {dispatch.sip_dispatch_rule_id}")

    # Print Plivo console instructions
    print("\n" + "-" * 60)
    print("PLIVO CONSOLE SETUP (Inbound):")
    print("-" * 60)
    print("1. Go to Plivo Console -> Zentrunk -> Inbound Trunks")
    print("2. Create New Inbound Trunk, name it 'LiveKit SphereVoice'")
    print(f"3. Set Primary URI to: {sip_domain};transport=tcp")
    print("4. Go to Phone Numbers -> Your Numbers")
    print(f"5. Select {', '.join(phone_numbers)}")
    print("6. Set Application Type = Zentrunk, select the trunk")
    print("7. Click Update")

    return trunk_id


async def setup_outbound(
    api: LiveKitAPI,
    phone_numbers: list[str],
    termination_domain: str,
    sip_username: str,
    sip_password: str,
) -> str:
    """Create outbound SIP trunk for LiveKit -> Plivo Zentrunk -> PSTN.

    Returns the new trunk_id to set as LIVEKIT_SIP_OUTBOUND_TRUNK_ID.
    """
    outbound_resp = await api.sip.list_sip_outbound_trunk(ListSIPOutboundTrunkRequest())

    # Check if outbound trunk already exists for these numbers
    for t in outbound_resp.items:
        if set(t.numbers) & set(phone_numbers):
            print(f"\n>> Outbound trunk already exists: {t.sip_trunk_id}")
            print(f"   Address: {t.address}")
            print(f"   Numbers: {list(t.numbers)}")
            return t.sip_trunk_id

    print("\n" + "=" * 60)
    print("Creating outbound SIP trunk...")
    print("=" * 60)
    print(f"  Termination domain: {termination_domain}")
    print(f"  Caller IDs:         {phone_numbers}")
    print(f"  SIP username:       {sip_username}")

    trunk_info = SIPOutboundTrunkInfo(
        name=f"Plivo Outbound ({', '.join(phone_numbers)})",
        address=termination_domain,
        numbers=phone_numbers,
        auth_username=sip_username,
        auth_password=sip_password,
        transport=SIP_TRANSPORT_TCP,
    )
    trunk = await api.sip.create_sip_outbound_trunk(
        CreateSIPOutboundTrunkRequest(trunk=trunk_info)
    )
    trunk_id = trunk.sip_trunk_id
    print(f"  Created! Outbound Trunk ID: {trunk_id}")
    return trunk_id


async def verify_plivo_numbers(phone_numbers: list[str], auth_id: str, auth_token: str) -> None:
    """Verify all numbers are configured on the Plivo side."""
    print("\n" + "=" * 60)
    print("Verifying Plivo-side configuration...")
    print("=" * 60)

    all_good = True
    for phone in phone_numbers:
        info = verify_plivo_number(phone, auth_id, auth_token)
        if "error" in info:
            print(f"\n  {phone}: FAILED — {info['error']}")
            print(f"    {info.get('detail', '')}")
            all_good = False
        else:
            app_uri = info.get("application", "")
            voice_enabled = info.get("voice_enabled", False)
            region = info.get("region", "")
            has_app = bool(app_uri)

            status = "OK" if (has_app and voice_enabled) else "NEEDS CONFIG"
            print(f"\n  {phone} ({region}):")
            print(f"    Voice enabled:  {'YES' if voice_enabled else 'NO'}")
            print(f"    Application:    {'SET (Zentrunk linked)' if has_app else 'NOT SET — needs Zentrunk trunk'}")
            print(f"    Status:         {status}")

            if not has_app:
                all_good = False

    if all_good:
        print("\n  >> All numbers verified — Plivo side is configured!")
    else:
        print("\n  >> Some numbers need Plivo Console setup (see instructions above)")


async def main():
    parser = argparse.ArgumentParser(description="Setup SIP trunks for Plivo + LiveKit")
    parser.add_argument("--outbound", action="store_true", help="Also create outbound SIP trunk")
    parser.add_argument("--status", action="store_true", help="Just show current config and exit")
    parser.add_argument(
        "--numbers",
        type=str,
        default="",
        help="Comma-separated E.164 numbers (overrides PLIVO_OUTBOUND_NUMBERS / PLIVO_TEST_NUMBER)",
    )
    args = parser.parse_args()

    # ── Read config from env ──
    livekit_url = _require("LIVEKIT_URL")
    livekit_api_key = _require("LIVEKIT_API_KEY")
    livekit_api_secret = _require("LIVEKIT_API_SECRET")
    plivo_auth_id = _require("PLIVO_AUTH_ID")
    plivo_auth_token = _require("PLIVO_AUTH_TOKEN")

    sip_domain = os.getenv("LIVEKIT_SIP_DOMAIN", "").strip()
    if not sip_domain:
        sip_domain = livekit_url.replace("wss://", "").replace("ws://", "")

    # Resolve phone numbers
    if args.numbers:
        phone_numbers = [n.strip() for n in args.numbers.split(",") if n.strip()]
    else:
        outbound_nums = os.getenv("PLIVO_OUTBOUND_NUMBERS", "").strip()
        test_num = os.getenv("PLIVO_TEST_NUMBER", "").strip()
        if outbound_nums:
            phone_numbers = [n.strip() for n in outbound_nums.split(",") if n.strip()]
        elif test_num:
            phone_numbers = [test_num]
        else:
            print("ERROR: No phone numbers configured. Set PLIVO_OUTBOUND_NUMBERS or PLIVO_TEST_NUMBER in .env")
            sys.exit(1)

    api = LiveKitAPI(
        url=livekit_url,
        api_key=livekit_api_key,
        api_secret=livekit_api_secret,
    )

    try:
        print("=" * 60)
        print("SphereVoice SIP Trunk Setup")
        print("=" * 60)
        print(f"LiveKit:    {livekit_url}")
        print(f"SIP domain: {sip_domain}")
        print(f"Numbers:    {phone_numbers}")

        # ── Status only ──
        if args.status:
            await list_status(api)
            return

        # ── 1. List existing config ──
        print("\n" + "=" * 60)
        print("Current SIP configuration:")
        print("=" * 60)
        await list_status(api)

        # ── 2. Inbound setup ──
        print("\n" + "=" * 60)
        print("INBOUND SETUP")
        print("=" * 60)
        trunk_id = await setup_inbound(api, phone_numbers, sip_domain)

        # ── 3. Verify Plivo side ──
        await verify_plivo_numbers(phone_numbers, plivo_auth_id, plivo_auth_token)

        # ── 4. Outbound setup ──
        outbound_trunk_id = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID", "").strip()
        if args.outbound:
            termination_domain = os.getenv("PLIVO_ZENTRUNK_TERMINATION_DOMAIN", "").strip()
            sip_username = os.getenv("PLIVO_ZENTRUNK_SIP_USERNAME", "").strip()
            sip_password = os.getenv("PLIVO_ZENTRUNK_SIP_PASSWORD", "").strip()

            if not all([termination_domain, sip_username, sip_password]):
                print("\n" + "=" * 60)
                print("OUTBOUND SETUP — MISSING CREDENTIALS")
                print("=" * 60)
                print("\nTo create an outbound trunk, you need Plivo Zentrunk outbound credentials.")
                print("Add these to your backend/.env:")
                print()
                print("  # 1. Go to Plivo Console -> Zentrunk -> Outbound Trunks -> Create")
                print("  # 2. Add a Credential List (username + password for SIP auth)")
                print("  # 3. Copy the Termination SIP Domain shown on the trunk page")
                print()
                print("  PLIVO_ZENTRUNK_TERMINATION_DOMAIN=xxx.zt.plivo.com")
                print("  PLIVO_ZENTRUNK_SIP_USERNAME=your_sip_username")
                print("  PLIVO_ZENTRUNK_SIP_PASSWORD=your_sip_password")
                print("  PLIVO_OUTBOUND_NUMBERS=+918035316038")
                print()
                print("Then re-run: python scripts/setup_sip_trunks.py --outbound")
                sys.exit(1)

            print("\n" + "=" * 60)
            print("OUTBOUND SETUP")
            print("=" * 60)
            outbound_trunk_id = await setup_outbound(
                api,
                phone_numbers=phone_numbers,
                termination_domain=termination_domain,
                sip_username=sip_username,
                sip_password=sip_password,
            )

        # ── 5. Final env vars ──
        print("\n" + "=" * 60)
        print("SETUP COMPLETE — Add/update in backend/.env:")
        print("=" * 60)
        print(f"\nLIVEKIT_SIP_DOMAIN={sip_domain}")
        if outbound_trunk_id:
            print(f"LIVEKIT_SIP_OUTBOUND_TRUNK_ID={outbound_trunk_id}")
        else:
            print("\n(No outbound trunk configured. Run with --outbound to create one.)")

        if not args.outbound and not outbound_trunk_id:
            print("\n" + "-" * 60)
            print("NEXT: Outbound calling setup")
            print("-" * 60)
            print("1. Go to Plivo Console -> Zentrunk -> Outbound Trunks -> Create")
            print("2. Add Credential List with a username + password")
            print("3. Copy the 'Termination SIP Domain' (e.g. xxx.zt.plivo.com)")
            print("4. Add to backend/.env:")
            print("     PLIVO_ZENTRUNK_TERMINATION_DOMAIN=xxx.zt.plivo.com")
            print("     PLIVO_ZENTRUNK_SIP_USERNAME=your_sip_username")
            print("     PLIVO_ZENTRUNK_SIP_PASSWORD=your_sip_password")
            print("     PLIVO_OUTBOUND_NUMBERS=+918035316038")
            print("5. Run: python scripts/setup_sip_trunks.py --outbound")

    finally:
        await api.aclose()


if __name__ == "__main__":
    asyncio.run(main())
