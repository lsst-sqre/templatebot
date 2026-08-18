"""Test fixtures for unfurlbot tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from faststream_fastapi import FastStreamAPI
from httpx import AsyncClient

from templatebot import main


@pytest.fixture
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the retry helper's backoff instantaneous.

    Any test that drives a call through
    `~templatebot.storage.retry.retry_async` to exhaustion would otherwise
    wait out the real exponential backoff.
    """

    async def fake_sleep(delay: float) -> None:
        return

    monkeypatch.setattr("templatebot.storage.retry._sleep", fake_sleep)


@pytest_asyncio.fixture
async def app() -> AsyncIterator[FastStreamAPI]:
    """Return a configured test application.

    Wraps the application in a lifespan manager so that startup and shutdown
    events are sent during test execution. This also starts and stops the
    Kafka broker around the app's own lifespan.
    """
    async with LifespanManager(main.app):
        yield main.app


@pytest_asyncio.fixture
async def client(app: FastStreamAPI) -> AsyncIterator[AsyncClient]:
    """Return an ``httpx.AsyncClient`` configured to talk to the test app."""
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="https://example.com/"
    ) as client:
        yield client
