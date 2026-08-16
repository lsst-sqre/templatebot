"""Tests for the Slack Web API client."""

from __future__ import annotations

import httpx
import pytest
import respx
import structlog
from pydantic import SecretStr
from structlog.testing import capture_logs

from templatebot.storage.slack import SlackWebApiClient


@pytest.fixture
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the retry helper's backoff instantaneous."""

    async def fake_sleep(delay: float) -> None:
        return

    monkeypatch.setattr("templatebot.storage.retry._sleep", fake_sleep)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_post_json_retries_transient_failures(
    respx_mock: respx.MockRouter,
) -> None:
    """Two read timeouts are retried away and the third attempt's payload is
    returned, leaving one retry log line per retry.
    """
    route = respx_mock.post("https://slack.com/api/chat.update").mock(
        side_effect=[
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.Response(200, json={"ok": True, "ts": "1234.5678"}),
        ]
    )

    with capture_logs() as logs:
        async with httpx.AsyncClient() as http_client:
            client = SlackWebApiClient(
                http_client=http_client,
                token=SecretStr("xoxb-testing-123"),
                logger=structlog.get_logger(__name__),
            )
            result = await client.post_json(
                method="chat.update", body={"channel": "C1", "ts": "1234"}
            )

    assert result == {"ok": True, "ts": "1234.5678"}
    assert route.call_count == 3
    retries = [entry for entry in logs if entry["event"] == "http_retry"]
    assert len(retries) == 2
    assert all(entry["slack_method"] == "chat.update" for entry in retries)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_get_retries_transient_failures(
    respx_mock: respx.MockRouter,
) -> None:
    """``get`` is opted into the same retry behavior as ``post_json``."""
    route = respx_mock.get("https://slack.com/api/users.info").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json={"ok": True, "user": {"id": "U1"}}),
        ]
    )

    with capture_logs() as logs:
        async with httpx.AsyncClient() as http_client:
            client = SlackWebApiClient(
                http_client=http_client,
                token=SecretStr("xoxb-testing-123"),
                logger=structlog.get_logger(__name__),
            )
            result = await client.get(
                method="users.info", params={"user": "U1"}
            )

    assert result == {"ok": True, "user": {"id": "U1"}}
    assert route.call_count == 2
    assert len([e for e in logs if e["event"] == "http_retry"]) == 1
