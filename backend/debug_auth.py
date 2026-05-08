import asyncio
from sqlalchemy import text
from app.core.database import async_session_factory
from app.core.security import hash_password, verify_password
from app.core.config import get_settings

settings = get_settings()

async def debug_login():
    email = "admin@sphere.ai"
    password = "SphereDev2026!"
    
    print(f"--- Auth Debugger ---")
    print(f"Current JWT_SECRET_KEY: {settings.JWT_SECRET_KEY}")
    
    # 1. Generate a fresh hash using live app logic
    correct_hash = hash_password(password)
    
    async with async_session_factory() as db:
        # 2. Get the hash currently in the DB
        result = await db.execute(
            text("SELECT password_hash FROM users WHERE email = :email"),
            {"email": email}
        )
        db_hash = result.scalar()
        
        if not db_hash:
            print(f"❌ User {email} not found in database.")
            return

        print(f"DB Hash: {db_hash}")
        print(f"New Hash: {correct_hash}")
        
        # 3. Test verification
        match = verify_password(password, db_hash)
        
        if match:
            print(f"✅ SUCCESS: Password matches DB hash.")
        else:
            print(f"❌ FAIL: Password does NOT match DB hash.")
            print(f"🔄 Updating DB with verified hash now...")
            await db.execute(
                text("UPDATE users SET password_hash = :ph WHERE email = :email"),
                {"ph": correct_hash, "email": email}
            )
            await db.commit()
            print(f"✨ DB updated. Try logging in now with: {password}")

if __name__ == "__main__":
    asyncio.run(debug_login())