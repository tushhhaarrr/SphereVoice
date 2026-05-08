"""One-time script to provision default tools for already-connected Google integrations."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select


async def main():
    url = os.getenv("DATABASE_URL")
    engine = create_async_engine(url)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        try:
            await db.execute(text("SET LOCAL ROLE SphereVoice_app"))
        except Exception:
            pass  # Role may not exist in dev environments
        await db.execute(text("SET LOCAL app.user_role = 'admin'"))
        await db.execute(text("SET LOCAL app.current_tenant_id = '00000000-0000-0000-0000-000000000000'"))

        r = await db.execute(text(
            "SELECT id, tenant_id, provider, status FROM tenant_integrations WHERE provider LIKE 'google_%'"
        ))
        rows = r.fetchall()
        if not rows:
            print("No Google integrations found.")
            await engine.dispose()
            return

        for row in rows:
            print(f"  {row[2]}: id={row[0]}, tenant={row[1]}, status={row[3]}")

        # Now provision tools
        from app.modules.integrations.google.tool_provisioner import provision_default_tools
        for row in rows:
            integration_id, tenant_id, provider, status = row
            if status != "connected":
                print(f"  Skipping {provider} (status={status})")
                continue

            # Set RLS context for this tenant
            await db.execute(text(f"SET LOCAL app.current_tenant_id = '{tenant_id}'"))
            created = await provision_default_tools(db, integration_id, tenant_id, provider)
            if created:
                await db.commit()
                print(f"  Created {len(created)} tools for {provider}: {[t.name for t in created]}")
            else:
                print(f"  Tools already exist for {provider}")

    await engine.dispose()
    print("Done.")


asyncio.run(main())
