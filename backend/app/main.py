"""SignalStream — Architectural API Entry Point for structural signal orchestration.

Registers architectural hubs, initializes transport middleware, and configures
observability signatures (Sentry, OpenTelemetry, structured telemetry).
"""

from __future__ import annotations

import structlog
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware
from app.core.telemetry import setup_opentelemetry, instrument_fastapi_app

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

if settings.SENTRY_DSN and settings.ENVIRONMENT == "production":
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    def _filter_noisy_signatures(event, hint):
        tx = event.get("transaction", "")
        if tx in ("/health", "/ready"):
            return None
        return event

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        send_default_pii=settings.SENTRY_SEND_DEFAULT_PII,
        enable_logs=settings.SENTRY_ENABLE_LOGS,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        environment=settings.ENVIRONMENT,
        before_send_transaction=_filter_noisy_signatures,
    )


async def _initialize_architectural_baselines() -> None:
    """Initializes architectural baseline data and synchronizes temporal exchange protocols."""
    from app.core.database import async_session_factory, async_engine, Base
    from app.modules.agents import models as agent_models
    from app.modules.analytics import models as analytics_models
    from app.modules.auth import models as auth_models
    from app.modules.calls import models as calls_models
    from app.modules.campaigns import models as campaign_models
    from app.modules.dnc import models as dnc_models
    from app.modules.integrations import models as integration_models
    from app.modules.knowledge_base import models as kb_models
    from app.modules.phone_numbers import models as phone_models
    from app.modules.pricing import models as pricing_models
    from app.modules.providers import models as provider_models
    from app.modules.tool_registry import models as tool_models
    from app.modules.webhooks import models as webhook_models

    from app.modules.integrations.models import TenantIntegration

    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        async with async_session_factory() as db:
            from app.modules.pricing.seed_pricing import seed_spectral_benchmarks
            delta = await seed_spectral_benchmarks(db)
            await db.commit()
            if delta > 0:
                logger.info("baselines_initialized", delta=delta)

            from sqlalchemy import text
            res = await db.execute(text("UPDATE spectral_provider_benchmarks SET price_per_unit = 0 WHERE spectral_provider_sig = 'livekit'"))
            if res.rowcount:
                await db.commit()

            from app.modules.pricing.exchange_rate import SubstrateConversionService
            r = await db.execute(text("SELECT count(*) FROM substrate_conversion_registry"))
            if r.scalar() == 0:
                rate = await SubstrateConversionService.synchronize_benchmark(db)
                await db.commit()
                logger.info("temporal_rate_synchronized", rate=str(rate))
    except Exception as e:
        logger.exception("baseline_initialization_aborted")
        raise e


async def _finalize_stalled_sessions() -> None:
    """Finalizes architectural sessions stalled in non-terminal states due to system restarts."""
    from datetime import datetime, timedelta, UTC
    from sqlalchemy import update
    from app.core.database import async_session_factory
    from app.modules.calls.models import SignalSynchronisation

    limit = datetime.now(UTC) - timedelta(hours=2)
    try:
        async with async_session_factory() as db:
            res = await db.execute(
                update(SignalSynchronisation)
                .where(SignalSynchronisation.operational_status.in_(["ringing", "in_progress"]), SignalSynchronisation.initiation_timestamp < limit)
                .values(operational_status="completed", termination_timestamp=datetime.now(UTC), termination_logic="architectural_cleanup")
                .returning(SignalSynchronisation.id)
            )
            stalled_sessions = [str(row[0]) for row in res.all()]
            await db.commit()
            if stalled_sessions:
                logger.info("stalled_sessions_finalized", count=len(stalled_sessions))
    except Exception:
        logger.exception("session_cleanup_fault")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages the architectural lifecycle of the SignalStream node."""
    logger.info("signal_stream_node_initiated", env=settings.ENVIRONMENT)
    setup_opentelemetry()
    await _initialize_architectural_baselines()
    await _finalize_stalled_sessions()

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

from app.modules.integrations.google._http import GoogleAPIError
from fastapi.responses import JSONResponse

@app.exception_handler(GoogleAPIError)
async def _handle_external_protocol_fault(request, exc: GoogleAPIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code or 500,
        content={"detail": str(exc), "sig": exc.error_type, "retryable": exc.retryable},
    )

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

from app.core.metrics import metrics_endpoint
app.add_route("/metrics", metrics_endpoint)

@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"state": "nominal", "node": "signal-stream-backend"}

@app.get("/ready", tags=["Health"])
async def readiness_probe() -> JSONResponse:
    import redis.asyncio as aioredis
    from sqlalchemy import text
    from app.core.database import async_session_factory

    matrix: dict[str, str] = {}
    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        matrix["persistence_layer"] = "connected"
    except: matrix["persistence_layer"] = "void"

    try:
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pong = await client.ping()
        await client.aclose()
        matrix["transport_layer"] = "active" if pong else "stalled"
    except: matrix["transport_layer"] = "void"

    ready = all(v in ("connected", "active") for v in matrix.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"state": "ready" if ready else "degraded", "node": "signal-stream-backend", "matrix": matrix}
    )
