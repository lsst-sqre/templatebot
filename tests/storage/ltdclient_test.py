"""Tests for the LSST the Docs API client."""

from __future__ import annotations

import httpx
import pytest
import structlog
from pydantic import SecretStr

from templatebot.storage.ltdclient import LtdClient


@pytest.mark.asyncio
async def test_get_token_uses_shared_client_timeout() -> None:
    """``get_token`` inherits the shared client's timeout rather than
    setting its own.
    """
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"token": "ltd-token"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(30.0, connect=10.0),
    ) as http_client:
        client = LtdClient(
            username="user",
            password=SecretStr("password"),
            http_client=http_client,
            logger=structlog.get_logger(__name__),
        )
        token = await client.get_token()

        assert token == "ltd-token"
        assert len(requests) == 1
        assert (
            requests[0].extensions["timeout"] == http_client.timeout.as_dict()
        )
