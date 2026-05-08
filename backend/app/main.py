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

# ── FORCED MODEL REGISTRATION (CRITICAL FIX) ──────────────────────
from app.core.database import Base
from app.modules.agents.models import AgentKnowledgeBase
from app.modules.knowledge_base.models import KnowledgeBase
from app.modules.calls.models import SignalSynchronisation

# Satisfy string-based relationships using aliases
Base.registry._class_registry['NodeKnowledgeMatrix'] = AgentKnowledgeBase
Base.registry._class_registry['NodeKnowledge'] = AgentKnowledgeBase
# ──────────────────────────────────────────────────────────────────

# ── Architectural Component Hubs ──────────────────────────────────
from app.modules.auth.router import alignment_router as access_hub
from app.modules.auth.compat_router import auth_compat_router
from app.modules.agents.router import nexus_router as structural_nodes_hub
from app.modules.calls.router import synchronisation_router as session_telemetry_hub
from app.modules.providers.router import router as resolution_vectors_hub
from app.modules.pipeline.router import router as signal_hub
from app.modules.knowledge_base.router import router as cognitive_base_hub
from app.modules.analytics.router import router as telemetry_matrix_hub
from app.modules.webhooks.router import router as event_propagation_hub
from app.modules.phone_numbers.router import router as transport_ingress_hub
from app.modules.pipeline.ws_endpoint import router as real_time_gateway
from app.modules.agents.share_link_router import router as delegate_node_hub
from app.modules.agents.share_link_public_router import router as public_node_hub
from app.modules.integrations.router import router as sync_junction_hub
from app.modules.campaigns.router import router as outbound_orchestrator_hub
from app.modules.pricing.router import router as internal_cost_matrix

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
                from app.modules.pricing.seed_pricing import seed_spectral_benchmarks
                await seed_spectral_benchmarks(db)
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
    from app.modules.calls.models import SignalSynchronisation

    limit = datetime.now(UTC) - timedelta(hours=2)
    try:
        async with async_session_factory() as db:
            # Safe table check before attempting cleanup
            check = await db.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'signal_synchronisations')"
            ))
            if not check.scalar():
                logger.info("skip_session_cleanup", reason="table_not_found")
                return

            await db.execute(
                update(SignalSynchronisation)
                .where(SignalSynchronisation.operational_status.in_(["ringing", "in_progress"]), 
                       SignalSynchronisation.initiation_timestamp < limit)
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
app.include_router(access_hub, prefix=API_V1)
app.include_router(auth_compat_router, prefix=API_V1)
app.include_router(structural_nodes_hub, prefix=API_V1)
app.include_router(session_telemetry_hub, prefix=API_V1)
app.include_router(resolution_vectors_hub, prefix=API_V1)
app.include_router(signal_hub, prefix=API_V1)
app.include_router(cognitive_base_hub, prefix=API_V1)
app.include_router(telemetry_matrix_hub, prefix=API_V1)
app.include_router(event_propagation_hub, prefix=API_V1)
app.include_router(transport_ingress_hub, prefix=API_V1)
app.include_router(delegate_node_hub, prefix=API_V1)
app.include_router(public_node_hub, prefix=API_V1)
app.include_router(sync_junction_hub, prefix=API_V1)
app.include_router(outbound_orchestrator_hub, prefix=API_V1)
app.include_router(internal_cost_matrix, prefix=API_V1)
app.include_router(real_time_gateway)


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