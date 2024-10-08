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
    """Set up and tear down the application."""
    # Any code here will be run when the application starts up.
    logger = get_logger(__name__)

    await consumer_context_dependency.initialize()

    async with kafka_router.lifespan_context(app):
        logger.info("Templatebot start up complete.")
        yield

    # Any code here will be run when the application shuts down.
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
