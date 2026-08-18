"""Tests for the process context and factory."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import structlog
from pydantic import SecretStr

from templatebot.config import config
from templatebot.factory import Factory, ProcessContext


@pytest.mark.asyncio
async def test_shared_client_default_timeout() -> None:
    context = await ProcessContext.create()
    try:
        timeout = context.http_client.timeout
        assert timeout.connect == 10.0
        assert timeout.read == 30.0
        assert timeout.write == 30.0
        assert timeout.pool == 30.0
    finally:
        await context.aclose()


@pytest.mark.asyncio
async def test_shared_client_configured_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "http_timeout", 45.5)
    context = await ProcessContext.create()
    try:
        timeout = context.http_client.timeout
        assert timeout.read == 45.5
        assert timeout.write == 45.5
        assert timeout.pool == 45.5
        assert timeout.connect == 10.0
    finally:
        await context.aclose()


@pytest_asyncio.fixture
async def factory() -> AsyncIterator[Factory]:
    """Return a factory backed by a real (unused) process context."""
    context = await ProcessContext.create()
    try:
        yield Factory(
            logger=structlog.get_logger("templatebot"),
            process_context=context,
        )
    finally:
        await context.aclose()


@pytest.mark.asyncio
async def test_no_alert_client_without_a_webhook(factory: Factory) -> None:
    """Operator alerting is opt-in, so an unset webhook disables it."""
    assert config.slack_alert_webhook is None
    assert factory.create_slack_alert_client() is None


@pytest.mark.asyncio
async def test_alert_client_from_configured_webhook(
    factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        config,
        "slack_alert_webhook",
        SecretStr("https://hooks.slack.com/services/T000/B000/xxx"),
    )
    client = factory.create_slack_alert_client()
    assert client is not None


@pytest.mark.asyncio
async def test_view_service_gets_the_alert_client(
    factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The view submission service is where alerts are raised, so it must be
    handed the client the factory builds.
    """
    assert factory.create_slack_view_service()._slack_alert_client is None

    monkeypatch.setattr(
        config,
        "slack_alert_webhook",
        SecretStr("https://hooks.slack.com/services/T000/B000/xxx"),
    )
    assert factory.create_slack_view_service()._slack_alert_client is not None
