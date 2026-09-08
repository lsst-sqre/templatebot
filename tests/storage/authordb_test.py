"""Tests for the Ook author database client."""

from __future__ import annotations

import httpx
import pytest
import respx
import structlog
from pydantic import ValidationError

from templatebot.storage.authordb import (
    AuthorDb,
    AuthorNotFoundError,
    AuthorServiceError,
)
from templatebot.storage.retry import MAX_ATTEMPTS

AUTHOR_URL = "https://roundtable.lsst.cloud/ook/authors/nobody"


def make_client(http_client: httpx.AsyncClient) -> AuthorDb:
    """Build an `AuthorDb` bound to a test HTTP client."""
    return AuthorDb(http_client, structlog.get_logger(__name__))


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_missing_author_is_not_found(
    respx_mock: respx.MockRouter,
) -> None:
    """A 404 is the user's own typo, so it becomes an `AuthorNotFoundError`
    naming the ID and is never retried.
    """
    route = respx_mock.get(AUTHOR_URL).mock(return_value=httpx.Response(404))

    async with httpx.AsyncClient() as http_client:
        with pytest.raises(AuthorNotFoundError) as exc_info:
            await make_client(http_client).get_author("nobody")

    assert exc_info.value.author_id == "nobody"
    assert "nobody" in str(exc_info.value)
    assert route.call_count == 1


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_persistent_server_error_is_a_service_error(
    respx_mock: respx.MockRouter,
) -> None:
    """A 5xx is transient, so it is retried; once the attempts are spent it
    becomes an `AuthorServiceError` rather than a bare httpx error.
    """
    route = respx_mock.get(AUTHOR_URL).mock(return_value=httpx.Response(503))

    async with httpx.AsyncClient() as http_client:
        with pytest.raises(AuthorServiceError) as exc_info:
            await make_client(http_client).get_author("nobody")

    assert route.call_count == MAX_ATTEMPTS
    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_transport_failure_is_a_service_error(
    respx_mock: respx.MockRouter,
) -> None:
    """A connection that never reaches Ook is an outage, not a bad ID."""
    respx_mock.get(AUTHOR_URL).mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    async with httpx.AsyncClient() as http_client:
        with pytest.raises(AuthorServiceError) as exc_info:
            await make_client(http_client).get_author("nobody")

    assert isinstance(exc_info.value.__cause__, httpx.ConnectError)


@pytest.mark.asyncio
async def test_unparsable_body_is_a_service_error(
    respx_mock: respx.MockRouter,
) -> None:
    """A 200 carrying something that is not an author is the service
    misbehaving, so it is reported the same way as an outage.
    """
    respx_mock.get(AUTHOR_URL).mock(
        return_value=httpx.Response(200, json={"unexpected": "payload"})
    )

    async with httpx.AsyncClient() as http_client:
        with pytest.raises(AuthorServiceError) as exc_info:
            await make_client(http_client).get_author("nobody")

    assert isinstance(exc_info.value.__cause__, ValidationError)


@pytest.mark.asyncio
async def test_successful_lookup_returns_the_author(
    respx_mock: respx.MockRouter,
) -> None:
    """The happy path is untouched by the error handling around it."""
    route = respx_mock.get(
        "https://roundtable.lsst.cloud/ook/authors/sickj"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "internal_id": "sickj",
                "family_name": "Sick",
                "given_name": "Jonathan",
                "orcid": "https://orcid.org/0000-0003-3001-676X",
                "affiliations": [
                    {"name": "Rubin Observatory", "internal_id": "RubinObs"}
                ],
            },
        )
    )

    async with httpx.AsyncClient() as http_client:
        author = await make_client(http_client).get_author("sickj")

    assert author.internal_id == "sickj"
    assert author.family_name == "Sick"
    assert author.given_name == "Jonathan"
    assert author.affiliations[0].name == "Rubin Observatory"
    assert route.call_count == 1
