"""The main application factory for the unfurlbot service.

Notes
-----
Be aware that, following the normal pattern for FastAPI services, the app is
constructed when this module is loaded and is not deferred until a function is
called.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import metadata, version

from fastapi import FastAPI
from faststream_fastapi import FastStreamAPI
from safir.dependencies.http_client import http_client_dependency
from safir.logging import configure_logging, configure_uvicorn_logging
from safir.middleware.x_forwarded import XForwardedMiddleware
from structlog import get_logger

from .config import config
from .dependencies.consumercontext import consumer_context_dependency
from .handlers.internal import internal_router
from .handlers.kafka import kafka_broker

__all__ = ["app", "config"]


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI) -> AsyncIterator[None]:
    """Set up and tear down the application.

    Note
    ----
    ``FastStreamAPI`` starts the FastStream Kafka broker inside this
    lifespan: after the startup code here has run, and it stops the broker
    before the shutdown code here runs. Nothing in this lifespan may rely on
    the broker being connected.
    """
    # Any code here will be run when the application starts up.
    logger = get_logger(__name__)

    await consumer_context_dependency.initialize()

    logger.info("Templatebot start up complete.")

    yield

    # Any code here will be run when the application shuts down.
    await consumer_context_dependency.aclose()
    # Templatebot's own HTTP client lives in the process context, but Safir's
    # SlackWebhookClient (used for operator alerts) creates its own through
    # this dependency, and only the lifespan can close it.
    await http_client_dependency.aclose()


configure_logging(
    profile=config.profile,
    log_level=config.log_level,
    name="templatebot",
)
configure_uvicorn_logging(config.log_level)

fastapi_app = FastAPI(
    title="Templatebot",
    description=metadata("templatebot")["Summary"],
    version=version("templatebot"),
    openapi_url=f"/{config.path_prefix}/openapi.json",
    docs_url=f"/{config.path_prefix}/docs",
    redoc_url=f"/{config.path_prefix}/redoc",
    lifespan=lifespan,
)
"""The inner FastAPI application for templatebot."""

# Attach the routers.
fastapi_app.include_router(internal_router)

# Add middleware.
fastapi_app.add_middleware(XForwardedMiddleware)

# Wrap the FastAPI app with the FastStream Kafka broker. This must come
# after all subscriber modules are imported (the `handlers.kafka` import
# above guarantees that).
#
# The ``arg-type`` ignore covers a typing-only mismatch between
# faststream and faststream-fastapi; nothing is wrong at runtime.
# faststream 0.7.6 gave ``KafkaBroker`` a third type argument
# (``BrokerUsecase[..., ..., KafkaBrokerConfig]``), but faststream-fastapi
# 1.3.1 annotates this parameter as ``BrokerUsecase[Any, Any]``, whose
# omitted third parameter defaults to ``BrokerConfig`` and is invariant,
# so mypy rejects the broker. ``unused-ignore`` keeps
# ``warn_unused_ignores`` quiet under version pairs where the mismatch
# does not occur (faststream <= 0.7.5, or a faststream-fastapi release
# that widens its annotation to accept any broker config). Remove the
# ignore and this paragraph once such a faststream-fastapi release is
# the minimum version here.
app = FastStreamAPI(kafka_broker, application=fastapi_app)  # type: ignore[arg-type,unused-ignore]
"""The ASGI application for templatebot, serving both HTTP and Kafka."""
