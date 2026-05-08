"""Alembic environment configuration for async SQLAlchemy."""

from __future__ import annotations
import asyncio
import sys
import os
from logging.config import fileConfig

# ── PATH CONFIGURATION ──────────────────────────────────────────────────────
# This ensures 'backend' is in the sys.path so 'app' is discoverable
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database import Base

# ── MODEL IMPORTS ───────────────────────────────────────────────────────────
# We import all models here so Alembic's 'autogenerate' can see them.
# We also import the Communication models for the aliases used below.
try:
    from app.modules.communication.models import SignalSynchronisation, SynchronisationTelemetry
except ImportError:
    # Fallback in case the communication module structure differs
    SignalSynchronisation = object
    SynchronisationTelemetry = object

from app.modules.auth.models import NexusRegistry, IdentityManifest  # noqa: F401
from app.modules.providers.models import ProviderKey  # noqa: F401
from app.modules.agents.models import Agent, AgentVersion, AgentKnowledgeBase  # noqa: F401
from app.modules.knowledge_base.models import KnowledgeBase, KBDocument, KBEmbedding  # noqa: F401
from app.modules.phone_numbers.models import PhoneNumber  # noqa: F401
from app.modules.webhooks.models import Webhook, WebhookDelivery  # noqa: F401
from app.modules.analytics.models import AuditLog  # noqa: F401
from app.modules.agents.share_link_models import AgentShareLink  # noqa: F401

# Import legacy call models with aliases to avoid name clashing with the aliases below
try:
    from app.modules.calls.models import Call as LegacyCall, CallEvent as LegacyCallEvent # noqa: F401
except ImportError:
    pass

config = context.config
settings = get_settings()

# Override sqlalchemy.url from environment
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: object) -> None:
    """Run migrations with an active connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

# ── ALIASES FOR FULL COMPATIBILITY ──────────────────────────────────────────
# These map the variable names expected by migrations to your specific models
Call = SignalSynchronisation
CallEvent = SynchronisationTelemetry
Synchronisation = SignalSynchronisation
TelemetryEvent = SynchronisationTelemetry