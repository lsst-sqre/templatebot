"""Tests for the outbound HTTP retry helper."""

from __future__ import annotations

import httpx
import pytest
import structlog

from templatebot.storage.retry import RetryPolicy, retry_async


def patch_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace the retry helper's sleep with a recorder and return the log
    of the delays it was asked to wait.
    """
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("templatebot.storage.retry._sleep", fake_sleep)
    return delays


def failing_response(
    status_code: int, headers: dict[str, str] | None = None
) -> httpx.HTTPStatusError:
    """Build an ``HTTPStatusError`` for a response with a given status."""
    request = httpx.Request("POST", "https://example.com/api")
    response = httpx.Response(
        status_code, headers=headers, request=request, json={}
    )
    return httpx.HTTPStatusError(
        f"status {status_code}", request=request, response=response
    )


@pytest.mark.asyncio
async def test_retries_transient_failure_and_returns_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient failure is retried and the eventual success returned."""
    patch_sleep(monkeypatch)
    attempts = 0

    async def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("timed out")
        return "succeeded"

    result = await retry_async(flaky, logger=structlog.get_logger(__name__))

    assert result == "succeeded"
    assert attempts == 2


@pytest.mark.asyncio
async def test_reraises_once_attempts_are_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The final exception propagates after the last attempt fails."""
    patch_sleep(monkeypatch)
    attempts = 0

    async def always_failing() -> str:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("connection refused")

    with pytest.raises(httpx.ConnectError, match="connection refused"):
        await retry_async(
            always_failing,
            policy=RetryPolicy(max_attempts=4),
            logger=structlog.get_logger(__name__),
        )

    assert attempts == 4


@pytest.mark.asyncio
async def test_retry_after_sets_the_delay_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 429's ``Retry-After`` is waited out before the next attempt."""
    delays = patch_sleep(monkeypatch)
    attempts = 0

    async def rate_limited() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise failing_response(429, {"Retry-After": "30"})
        return "succeeded"

    result = await retry_async(
        rate_limited, logger=structlog.get_logger(__name__)
    )

    assert result == "succeeded"
    assert delays == pytest.approx([30.0])


@pytest.mark.asyncio
async def test_non_transient_status_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 400 is the caller's own fault, so it raises on the first attempt."""
    delays = patch_sleep(monkeypatch)
    attempts = 0

    async def bad_request() -> str:
        nonlocal attempts
        attempts += 1
        raise failing_response(400)

    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        await retry_async(bad_request, logger=structlog.get_logger(__name__))

    assert excinfo.value.response.status_code == 400
    assert attempts == 1
    assert delays == []
