"""Tests for the application lifespan."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from safir.dependencies.http_client import http_client_dependency

from templatebot import main


@pytest.mark.asyncio
async def test_lifespan_closes_the_safir_http_client() -> None:
    """Safir's ``SlackWebhookClient`` gets its HTTP client from
    ``http_client_dependency``, which nothing else in templatebot owns, so
    the lifespan has to close it on shutdown.
    """
    async with LifespanManager(main.app):
        client = await http_client_dependency()

    assert client.is_closed
    assert http_client_dependency.http_client is None
