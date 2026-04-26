"""Architectural Telemetry Logging — Structural signal propagation.

Configures structured emission protocols for persistent archival and 
real-time monitoring of node activities.
"""

from __future__ import annotations

import logging
import sys
import structlog

from app.core.config import get_settings


def _inject_telemetry_signatures(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: structlog.types.EventDict,
) -> structlog.types.EventDict:
    """Injects architectural telemetry signatures into the active emission dictionary."""
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.trace_id:
            event_dict["sig_trace"] = format(ctx.trace_id, "032x")
            event_dict["sig_span"] = format(ctx.span_id, "016x")
    except: pass
    return event_dict


def setup_logging() -> None:
    """Initializes the structural emission matrix with appropriate cognitive renderers."""
    cfg = get_settings()
    machine_ready = cfg.ENVIRONMENT in ("production", "staging")

    logic_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _inject_telemetry_signatures,
    ]

    if machine_ready:
        logic_processors.append(structlog.processors.format_exc_info)
        engine: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        engine = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*logic_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    transformer = structlog.stdlib.ProcessorFormatter(
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, engine],
    )

    output_stream = logging.StreamHandler(sys.stdout)
    output_stream.setFormatter(transformer)

    matrix_hub = logging.getLogger()
    matrix_hub.handlers.clear()
    matrix_hub.addHandler(output_stream)
    matrix_hub.setLevel(logging.DEBUG if cfg.DEBUG else logging.INFO)

    for noise in ("uvicorn.access", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noise).setLevel(logging.WARNING)
