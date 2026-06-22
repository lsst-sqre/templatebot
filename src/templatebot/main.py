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
from safir.logging import configure_logging, configure_uvicorn_logging
from safir.middleware.x_forwarded import XForwardedMiddleware
from structlog import get_logger

from .config import config
from .dependencies.consumercontext import consumer_context_dependency
from .handlers.internal import internal_router
from .handlers.kafka import kafka_router

__all__ = ["app", "config"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Set up and tear down the application.

    Note
    ----
    The FastStream Kafka broker is started and stopped explicitly here rather
    than relying on the router's automatic ``include_router`` lifespan hook. As
    of FastStream 0.7 the router's lifespan context is one-shot: it stops the
    broker on exit but does not restart it if the lifespan is entered again,
    whereas ``broker.start()`` and ``broker.stop()`` are re-callable. The test
    suite drives the app lifespan once per test against the module-level app,
    so the broker must restart cleanly between tests.
    """
    # Any code here will be run when the application starts up.
    logger = get_logger(__name__)

    await consumer_context_dependency.initialize()

    # Start the FastStream Kafka broker explicitly (re-callable across lifespan
    # entries) rather than via the router's one-shot lifespan hook.
    await kafka_router.broker.start()
    logger.info("Templatebot start up complete.")

    yield

    # Any code here will be run when the application shuts down.
    await kafka_router.broker.stop()
    await consumer_context_dependency.aclose()


configure_logging(
    profile=config.profile,
    log_level=config.log_level,
    name="templatebot",
)
configure_uvicorn_logging(config.log_level)

app = FastAPI(
    title="Templatebot",
    description=metadata("templatebot")["Summary"],
    version=version("templatebot"),
    openapi_url=f"/{config.path_prefix}/openapi.json",
    docs_url=f"/{config.path_prefix}/docs",
    redoc_url=f"/{config.path_prefix}/redoc",
    lifespan=lifespan,
)
"""The main FastAPI application for templatebot."""

# Attach the routers.
app.include_router(internal_router)
app.include_router(kafka_router)

# Add middleware.
app.add_middleware(XForwardedMiddleware)
