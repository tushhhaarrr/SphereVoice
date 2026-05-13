"""SignalStream — Architectural API Entry Point for structural signal orchestration."""

from __future__ import annotations

import structlog
import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse, JSONResponse

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware
from app.core.telemetry import setup_opentelemetry, instrument_fastapi_app
from app.core.errors import setup_exception_handlers

# ── FORCED MODEL REGISTRATION (CRITICAL FIX) ──────────────────────
from app.core.database import Base
from app.modules.agents.models import AgentKnowledgeBase
from app.modules.knowledge_base.models import KnowledgeBase
from app.modules.calls.models import VoiceEngine

# Satisfy string-based relationships using aliases
Base.registry._class_registry['NodeKnowledgeMatrix'] = AgentKnowledgeBase
Base.registry._class_registry['NodeKnowledge'] = AgentKnowledgeBase
# ──────────────────────────────────────────────────────────────────

# ── Architectural Component Hubs ──────────────────────────────────
from app.modules.auth.router import auth_router
from app.modules.auth.compat_router import auth_compat_router
from app.modules.agents.router import agents_router
from app.modules.calls.router import synchronisation_router as calls_router
from app.modules.providers.router import router as providers_router
from app.modules.pipeline.router import router as pipeline_router
from app.modules.knowledge_base.router import router as knowledge_base_router
from app.modules.knowledge_base.router import node_library_router
from app.modules.analytics.router import router as analytics_router
from app.modules.webhooks.router import router as webhooks_router
from app.modules.phone_numbers.router import router as phone_numbers_router
from app.modules.pipeline.ws_endpoint import router as ws_router
from app.modules.agents.share_link_router import router as agents_share_router
from app.modules.agents.share_link_public_router import router as agents_public_router
from app.modules.integrations.router import router as integrations_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.pricing.router import router as pricing_router
from app.modules.integrations.google.router import router as google_integrations_router
from app.modules.integrations.calendly.router import router as calendly_integrations_router
from app.modules.tool_registry.router import router as tool_registry_router
from app.modules.dnc.router import router as dnc_router

setup_logging()
settings = get_settings()
logger = structlog.get_logger(__name__)


async def _initialize_architectural_baselines() -> None:
    """Initializes architectural baseline data and ensures all tables exist."""
    from app.core.database import async_session_factory, async_engine, Base
    from sqlalchemy import text
    
    # ── TOTAL TABLE DISCOVERY ─────────────────────────────────────────
    # We import all models here so SQLAlchemy knows about every table 
    # BEFORE running create_all. This stops UndefinedTable errors.
    from app.modules.pricing import models as pricing_models
    from app.modules.calls import models as call_models
    from app.modules.auth import models as auth_models
    from app.modules.agents import models as agent_models
    from app.modules.analytics import models as analytics_models
    from app.modules.knowledge_base import models as kb_models
    from app.modules.phone_numbers import models as phone_models
    # ──────────────────────────────────────────────────────────────────
    
    try:
        # 1. Ensure all tables exist in the database
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with async_session_factory() as db:
            # 2. Seed pricing benchmarks
            try:
                from app.modules.pricing.seed_pricing import seed_billing
                await seed_billing(db)
            except Exception as e:
                logger.warning("pricing_seed_skipped", error=str(e))
            
            # 3. Sync exchange rates
            try:
                from app.modules.pricing.exchange_rate import SubstrateConversionService
                await SubstrateConversionService.synchronize_benchmark(db)
            except Exception as e:
                logger.warning("exchange_rate_sync_skipped", error=str(e))
            
            await db.commit()
            logger.info("architectural_baselines_synchronized")
    except Exception as e:
        logger.error("baseline_initialization_failed", error=str(e))


async def _finalize_stalled_sessions() -> None:
    """Finalizes architectural sessions stalled in non-terminal states."""
    from datetime import datetime, timedelta, UTC
    from sqlalchemy import update, text
    from app.core.database import async_session_factory
    from app.modules.calls.models import VoiceEngine

    limit = datetime.now(UTC) - timedelta(hours=2)
    try:
        async with async_session_factory() as db:
            # Safe table check before attempting cleanup
            check = await db.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'voice_engines')"
            ))
            if not check.scalar():
                logger.info("skip_session_cleanup", reason="table_not_found")
                return

            await db.execute(
                update(VoiceEngine)
                .where(VoiceEngine.operational_status.in_(["ringing", "in_progress"]), 
                       VoiceEngine.initiation_timestamp < limit)
                .values(operational_status="completed", termination_logic="architectural_cleanup")
            )
            await db.commit()
    except Exception:
        logger.warning("session_cleanup_deferred", reason="Database tables may still be initializing")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages the architectural lifecycle of the SignalStream node."""
    logger.info("signal_stream_node_initiated", env=settings.ENVIRONMENT)
    setup_opentelemetry()
    
    # 1. Initialize DB tables and seed critical data
    await _initialize_architectural_baselines()
    
    # 2. Attempt cleanup of old sessions
    await _finalize_stalled_sessions()

    # 3. Start background workers
    from app.modules.pipeline.orchestrator import start_manifold_duration_watchdog, stop_manifold_duration_watchdog
    start_manifold_duration_watchdog()

    yield

    stop_manifold_duration_watchdog()
    logger.info("signal_stream_node_terminated")


app = FastAPI(
    title="SignalStream API",
    description="Structural Signal Orchestration & Architectural Node Protocol",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    redirect_slashes=False,
)

setup_middleware(app)
instrument_fastapi_app(app)

API_V1 = settings.API_V1_PREFIX
app.include_router(auth_router, prefix=API_V1)
app.include_router(auth_compat_router, prefix=API_V1)
app.include_router(agents_router, prefix=API_V1)
app.include_router(calls_router, prefix=API_V1)
app.include_router(providers_router, prefix=API_V1)
app.include_router(pipeline_router, prefix=API_V1)
app.include_router(knowledge_base_router, prefix=API_V1)
app.include_router(node_library_router, prefix=API_V1)
app.include_router(analytics_router, prefix=API_V1)
app.include_router(webhooks_router, prefix=API_V1)
app.include_router(phone_numbers_router, prefix=API_V1)
app.include_router(agents_share_router, prefix=API_V1)
app.include_router(agents_public_router, prefix=API_V1)
app.include_router(integrations_router, prefix=API_V1)
app.include_router(campaigns_router, prefix=API_V1)
app.include_router(pricing_router, prefix=API_V1)
app.include_router(google_integrations_router, prefix=API_V1)
app.include_router(calendly_integrations_router, prefix=API_V1)
app.include_router(tool_registry_router, prefix=API_V1)
app.include_router(dnc_router, prefix=API_V1)
app.include_router(ws_router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"state": "nominal", "node": "signal-stream-backend"}


@app.get("/ready", tags=["Health"])
async def readiness_probe() -> JSONResponse:
    from app.core.database import async_session_factory
    from sqlalchemy import text
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        return JSONResponse(status_code=200, content={"state": "ready"})
    except Exception:
        return JSONResponse(status_code=503, content={"state": "degraded"})