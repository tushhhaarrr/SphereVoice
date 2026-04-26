"""Seed script for SphereVoice development database.

Creates:
- 2 tenants (Acme Corp, Beta Labs)
- 3 users per tenant (admin, developer, client_user)
- 1 Sphere admin user (no tenant)
- Default provider keys (Sphere-owned)
- Sample agents per tenant

Usage:
    cd backend && python seed.py
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_engine, async_session_factory
from app.core.encryption import encrypt
from app.core.security import hash_password

settings = get_settings()

# Fixed UUIDs for reproducibility
Sphere_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TENANT_ACME_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_BETA_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

ACME_ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-aaaaaaaaaaaa")
ACME_DEV_ID = uuid.UUID("11111111-1111-1111-1111-bbbbbbbbbbbb")
ACME_CLIENT_ID = uuid.UUID("11111111-1111-1111-1111-cccccccccccc")

BETA_ADMIN_ID = uuid.UUID("22222222-2222-2222-2222-aaaaaaaaaaaa")
BETA_DEV_ID = uuid.UUID("22222222-2222-2222-2222-bbbbbbbbbbbb")
BETA_CLIENT_ID = uuid.UUID("22222222-2222-2222-2222-cccccccccccc")

DEFAULT_PASSWORD = hash_password("SphereDev2026!")


async def seed_tenants(session: AsyncSession) -> None:
    """Create tenant organisations."""
    await session.execute(text("""
        INSERT INTO nexus_registry (id, label, registry_shard, operational_phase, metadata) VALUES
        (:acme_id, 'Acme Corporation', 'acme-corp', 'active', '{"plan": "enterprise"}'::jsonb),
        (:beta_id, 'Beta Labs', 'beta-labs', 'active', '{"plan": "startup"}'::jsonb)
        ON CONFLICT (registry_shard) DO NOTHING
    """), {"acme_id": TENANT_ACME_ID, "beta_id": TENANT_BETA_ID})


async def seed_users(session: AsyncSession) -> None:
    """Create users — 1 global admin + 3 per tenant. Wipes existing rows first."""
    # Force-delete all existing identity manifests to avoid stale credential hashes
    await session.execute(text("DELETE FROM identity_manifests"))
    print("  [OK] Wiped existing identity_manifests table")

    # Print the hash so we can verify it in the DB
    print(f"  [HASH] bcrypt hash for SphereDev2026! = {DEFAULT_PASSWORD}")

    await session.execute(text("""
        INSERT INTO identity_manifests (id, spectral_identity, label, privilege_tier, nexus_sig, credential_hash, active_mark) VALUES
        -- Sphere admin (no tenant)
        (:admin_id, 'admin@sphere.ai', 'Sphere Admin', 'nexus_admin', NULL, :pw, true),
        -- Acme Corp users
        (:acme_admin, 'admin@acme.com', 'Acme Admin', 'client_user', :acme_tid, :pw, true),
        (:acme_dev, 'dev@acme.com', 'Acme Developer', 'client_user', :acme_tid, :pw, true),
        (:acme_client, 'client@acme.com', 'Acme Client', 'client_user', :acme_tid, :pw, true),
        -- Beta Labs users
        (:beta_admin, 'admin@betalabs.io', 'Beta Admin', 'client_user', :beta_tid, :pw, true),
        (:beta_dev, 'dev@betalabs.io', 'Beta Developer', 'client_user', :beta_tid, :pw, true),
        (:beta_client, 'client@betalabs.io', 'Beta Client', 'client_user', :beta_tid, :pw, true)
    """), {
        "admin_id": Sphere_ADMIN_ID,
        "acme_admin": ACME_ADMIN_ID,
        "acme_dev": ACME_DEV_ID,
        "acme_client": ACME_CLIENT_ID,
        "beta_admin": BETA_ADMIN_ID,
        "beta_dev": BETA_DEV_ID,
        "beta_client": BETA_CLIENT_ID,
        "acme_tid": TENANT_ACME_ID,
        "beta_tid": TENANT_BETA_ID,
        "pw": DEFAULT_PASSWORD,
    })


async def seed_provider_keys(session: AsyncSession) -> None:
    """Create default (Sphere-owned) provider keys."""
    # Encrypt placeholder API keys
    providers = [
        ("deepgram", "stt", "dg-placeholder-key", True),
        ("openai", "llm", "sk-placeholder-key", True),
        ("groq", "llm", "gsk-placeholder-key", False),
        ("inworld", "tts", "inworld-placeholder-key", True),
        ("cartesia", "tts", "cart-placeholder-key", False),
        ("elevenlabs", "tts", "el-placeholder-key", False),
        ("twilio", "telephony", "twilio-placeholder-key", True),
    ]
    for name, category, key, is_default in providers:
        encrypted_key = encrypt(key)
        await session.execute(text("""
            INSERT INTO provider_keys (tenant_id, provider_name, provider_category, api_key_encrypted, is_default, is_active)
            VALUES (NULL, :name, :category, :key, :is_default, true)
            ON CONFLICT DO NOTHING
        """), {
            "name": name,
            "category": category,
            "key": encrypted_key,
            "is_default": is_default,
        })


async def seed_agents(session: AsyncSession) -> None:
    """Create sample agents for each tenant."""
    await session.execute(text("""
        INSERT INTO agents (tenant_id, name, type, status, config, created_by) VALUES
        -- Acme agents
        (:acme_tid, 'Acme Sales Bot', 'single_prompt', 'draft',
         '{"system_prompt": "You are a friendly sales assistant for Acme Corporation."}'::jsonb,
         :acme_dev),
        (:acme_tid, 'Acme Support Flow', 'conversation_flow', 'draft',
         '{"nodes": [], "edges": []}'::jsonb,
         :acme_dev),
        -- Beta agents
        (:beta_tid, 'Beta Booking Agent', 'single_prompt', 'draft',
         '{"system_prompt": "You help customers book appointments for Beta Labs."}'::jsonb,
         :beta_dev)
        ON CONFLICT DO NOTHING
    """), {
        "acme_tid": TENANT_ACME_ID,
        "beta_tid": TENANT_BETA_ID,
        "acme_dev": ACME_DEV_ID,
        "beta_dev": BETA_DEV_ID,
    })


async def main() -> None:
    """Run the seed script."""
    print("Seeding SphereVoice database...")
    start = datetime.now(UTC)

    async with async_session_factory() as session:
        # Disable RLS for seeding (we're running as superuser)
        await session.execute(text("SET app.user_role = 'admin'"))

        await seed_tenants(session)
        print("  [OK] Tenants created (Acme Corp, Beta Labs)")

        await seed_users(session)
        print("  [OK] Users created (7 users: 1 admin + 3 per tenant)")

        await seed_provider_keys(session)
        print("  [OK] Provider keys created (6 default providers)")

        await seed_agents(session)
        print("  [OK] Sample agents created (3 agents)")

        await session.commit()

    elapsed = (datetime.now(UTC) - start).total_seconds()
    print(f"\n[DONE] Seed complete in {elapsed:.2f}s")
    print("\nLogin credentials:")
    print("  admin@sphere.ai    / SphereDev2026!  (Global Admin)")
    print("  admin@acme.com     / SphereDev2026!  (Acme Client User)")
    print("  dev@acme.com       / SphereDev2026!  (Acme Client User)")
    print("  client@acme.com    / SphereDev2026!  (Acme Client User)")
    print("  admin@betalabs.io  / SphereDev2026!  (Beta Client User)")
    print("  dev@betalabs.io    / SphereDev2026!  (Beta Client User)")
    print("  client@betalabs.io / SphereDev2026!  (Beta Client User)")


if __name__ == "__main__":
    asyncio.run(main())
