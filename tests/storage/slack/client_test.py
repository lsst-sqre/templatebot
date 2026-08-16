"""Tests for the Slack Web API client."""

from __future__ import annotations

import httpx
import pytest
import respx
import structlog
from pydantic import SecretStr
from structlog.testing import capture_logs

from templatebot.storage.slack import SlackApiError, SlackWebApiClient


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


@pytest.mark.asyncio
async def test_post_json_raises_on_slack_rejection(
    respx_mock: respx.MockRouter,
) -> None:
    """A ``ok: false`` payload becomes a `SlackApiError` that names both the
    API method and Slack's error code.
    """
    route = respx_mock.post("https://slack.com/api/chat.update").mock(
        return_value=httpx.Response(
            200, json={"ok": False, "error": "channel_not_found"}
        )
    )

    body = {"channel": "C1", "ts": "1234", "text": "hello"}
    async with httpx.AsyncClient() as http_client:
        client = SlackWebApiClient(
            http_client=http_client,
            token=SecretStr("xoxb-testing-123"),
            logger=structlog.get_logger(__name__),
        )
        with pytest.raises(SlackApiError) as exc_info:
            await client.post_json(method="chat.update", body=body)

    exc = exc_info.value
    assert exc.method == "chat.update"
    assert exc.error == "channel_not_found"
    assert exc.body == body
    assert "chat.update" in str(exc)
    assert "channel_not_found" in str(exc)
    # An ok:false arrives on an HTTP 200, so it is not retried.
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_get_raises_on_slack_rejection(
    respx_mock: respx.MockRouter,
) -> None:
    """``get`` surfaces ``ok: false`` the same way ``post_json`` does, with
    the query parameters standing in for the request body.
    """
    respx_mock.get("https://slack.com/api/users.info").mock(
        return_value=httpx.Response(
            200, json={"ok": False, "error": "user_not_found"}
        )
    )

    async with httpx.AsyncClient() as http_client:
        client = SlackWebApiClient(
            http_client=http_client,
            token=SecretStr("xoxb-testing-123"),
            logger=structlog.get_logger(__name__),
        )
        with pytest.raises(SlackApiError) as exc_info:
            await client.get(method="users.info", params={"user": "U1"})

    exc = exc_info.value
    assert exc.method == "users.info"
    assert exc.error == "user_not_found"
    assert exc.body == {"user": "U1"}


@pytest.mark.asyncio
async def test_post_json_returns_payload_when_ok(
    respx_mock: respx.MockRouter,
) -> None:
    """A successful response is still returned decoded and unchanged."""
    payload = {"ok": True, "channel": "C1", "ts": "1234.5678"}
    respx_mock.post("https://slack.com/api/chat.update").mock(
        return_value=httpx.Response(200, json=payload)
    )

    async with httpx.AsyncClient() as http_client:
        client = SlackWebApiClient(
            http_client=http_client,
            token=SecretStr("xoxb-testing-123"),
            logger=structlog.get_logger(__name__),
        )
        result = await client.post_json(
            method="chat.update", body={"channel": "C1", "ts": "1234"}
        )

    assert result == payload
