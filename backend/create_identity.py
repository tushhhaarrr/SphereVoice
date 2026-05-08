import asyncio
import uuid
from sqlalchemy import text
from app.core.database import async_engine, async_session_factory, Base
from app.core.security import hash_password

# Import the auth models so SQLAlchemy knows about the 'identity_manifests' table
from app.modules.auth import models as auth_models

async def setup_identity():
    print("🛠️ Creating missing 'identity_manifests' table...")
    
    # 1. Force SQLAlchemy to create the table if it doesn't exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("👤 Seeding admin account into identity_manifests...")
    pw_hash = hash_password("SphereDev2026!")
    admin_id = uuid.uuid4()
    
    # 2. Insert the admin user into the newly created table
    async with async_session_factory() as db:
        await db.execute(text("""
            INSERT INTO identity_manifests 
            (id, spectral_identity, label, privilege_tier, credential_hash, active_mark) 
            VALUES (:id, :email, 'Global Admin', 'admin', :pw, true)
            ON CONFLICT (spectral_identity) DO UPDATE SET credential_hash = EXCLUDED.credential_hash
        """), {
            "id": admin_id, 
            "email": "admin@sphere.ai", 
            "pw": pw_hash
        })
        await db.commit()
        
    print("✅ Success! The table is created and the Admin is seeded. You can now log in.")

if __name__ == "__main__":
    asyncio.run(setup_identity())