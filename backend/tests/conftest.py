"""Shared test fixtures for SphereVoice backend tests.

Provides:
- Async test client
- Test database session
- Test user fixtures (admin, developer, read_only, client_user)
- JWT token helpers
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.dependencies import set_tenant_context
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.auth.models import Tenant, User

settings = get_settings()

# Use a separate test database
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/SphereVoice_dev", "/SphereVoice_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=True)
test_session_factory = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional test database session."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with overridden DB dependency."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_set_tenant_context() -> AsyncSession:
        """Skip RLS setup in tests — SphereVoice_app role may not exist in test DB."""
        return db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[set_tenant_context] = override_set_tenant_context

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Test data ────────────────────────────────────────────────────────

TENANT_1_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_2_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ADMIN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DEVELOPER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
READ_ONLY_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
CLIENT_USER_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
CLIENT_USER_2_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")

TEST_PASSWORD = "TestPassword123!"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


@pytest_asyncio.fixture
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(id=TENANT_1_ID, name="Test Corp", slug="test-corp")
    tenant = await db_session.merge(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def test_tenant_2(db_session: AsyncSession) -> Tenant:
    """Create a second test tenant for isolation tests."""
    tenant = Tenant(id=TENANT_2_ID, name="Other Corp", slug="other-corp")
    tenant = await db_session.merge(tenant)
    await db_session.flush()
    return tenant


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin employee user (no tenant)."""
    user = User(
        id=ADMIN_ID,
        email="admin@Sphere.com",
        name="Admin User",
        role="admin",
        tenant_id=None,
        credential_hash=TEST_PASSWORD_HASH,
        is_active=True,
    )
    user = await db_session.merge(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def developer_user(db_session: AsyncSession) -> User:
    """Create a developer employee user (no tenant)."""
    user = User(
        id=DEVELOPER_ID,
        email="dev@Sphere.com",
        name="Developer User",
        role="developer",
        tenant_id=None,
        credential_hash=TEST_PASSWORD_HASH,
        is_active=True,
    )
    user = await db_session.merge(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def read_only_user(db_session: AsyncSession) -> User:
    """Create a read-only employee user (no tenant)."""
    user = User(
        id=READ_ONLY_ID,
        email="viewer@Sphere.com",
        name="Viewer User",
        role="read_only",
        tenant_id=None,
        credential_hash=TEST_PASSWORD_HASH,
        is_active=True,
    )
    user = await db_session.merge(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def client_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create a client user scoped to tenant 1."""
    user = User(
        id=CLIENT_USER_ID,
        email="client@testcorp.com",
        name="Client User",
        role="client_user",
        tenant_id=TENANT_1_ID,
        credential_hash=TEST_PASSWORD_HASH,
        is_active=True,
    )
    user = await db_session.merge(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def client_user_2(
    db_session: AsyncSession, test_tenant_2: Tenant
) -> User:
    """Create a client user scoped to tenant 2."""
    user = User(
        id=CLIENT_USER_2_ID,
        email="client@othercorp.com",
        name="Client User 2",
        role="client_user",
        tenant_id=TENANT_2_ID,
        credential_hash=TEST_PASSWORD_HASH,
        is_active=True,
    )
    user = await db_session.merge(user)
    await db_session.flush()
    return user


# ── Token helpers ────────────────────────────────────────────────────


def make_token(user: User) -> str:
    """Generate a valid access token for a test user."""
    return create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
        }
    )


def auth_headers(user: User) -> dict[str, str]:
    """Return Authorization header dict for a test user."""
    return {"Authorization": f"Bearer {make_token(user)}"}


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict[str, str]:
    """Auth headers for admin user."""
    return auth_headers(admin_user)


@pytest_asyncio.fixture
async def developer_headers(developer_user: User) -> dict[str, str]:
    """Auth headers for developer user."""
    return auth_headers(developer_user)


@pytest_asyncio.fixture
async def read_only_headers(read_only_user: User) -> dict[str, str]:
    """Auth headers for read-only user."""
    return auth_headers(read_only_user)


@pytest_asyncio.fixture
async def client_headers(client_user: User) -> dict[str, str]:
    """Auth headers for client user (tenant 1)."""
    return auth_headers(client_user)
