import asyncio
import uuid
from sqlalchemy import text
from app.core.database import async_session_factory
from app.core.security import hash_password

async def force_seed():
    print("🚀 Forcing data seed...")
    pw_hash = hash_password("SphereDev2026!")
    
    # IDs for consistency
    TENANT_ACME = uuid.UUID("11111111-1111-1111-1111-111111111111")
    TENANT_BETA = uuid.UUID("22222222-2222-2222-2222-222222222222")

    async with async_session_factory() as db:
        # 1. Create Nexus Registries (Tenants)
        await db.execute(text("""
            INSERT INTO nexus_registry (id, label, registry_shard, operational_phase) VALUES
            (:acme, 'Acme Corp', 'acme-corp', 'active'),
            (:beta, 'Beta Labs', 'beta-labs', 'active')
            ON CONFLICT (id) DO UPDATE SET label = EXCLUDED.label
        """), {"acme": TENANT_ACME, "beta": TENANT_BETA})

        # 2. Create Identity Manifests (Users)
        users = [
            (uuid.uuid4(), "admin@sphere.ai", "Global Admin", "admin", None),
            (uuid.uuid4(), "admin@acme.com", "Acme Admin", "user", TENANT_ACME),
            (uuid.uuid4(), "dev@acme.com", "Acme Dev", "user", TENANT_ACME),
            (uuid.uuid4(), "client@acme.com", "Acme Client", "user", TENANT_ACME),
            (uuid.uuid4(), "admin@betalabs.io", "Beta Admin", "user", TENANT_BETA),
            (uuid.uuid4(), "dev@betalabs.io", "Beta Dev", "user", TENANT_BETA),
            (uuid.uuid4(), "client@betalabs.io", "Beta Client", "user", TENANT_BETA),
        ]

        for uid, email, name, role, tid in users:
            await db.execute(text("""
                INSERT INTO identity_manifests (id, spectral_identity, label, privilege_tier, nexus_sig, credential_hash, active_mark)
                VALUES (:id, :email, :name, :role, :tid, :pw, true)
                ON CONFLICT (spectral_identity) DO UPDATE SET credential_hash = EXCLUDED.credential_hash
            """), {"id": uid, "email": email, "name": name, "role": role, "tid": tid, "pw": pw_hash})
        
        await db.commit()
    print("✅ Seed complete. All accounts ready.")

if __name__ == "__main__":
    asyncio.run(force_seed())