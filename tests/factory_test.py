"""Tests for the process context and factory."""

from __future__ import annotations

import pytest

from templatebot.config import config
from templatebot.factory import ProcessContext


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
