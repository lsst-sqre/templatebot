"""Storage interface for lsst-texmf's authordb.yaml file."""

from __future__ import annotations

from httpx import AsyncClient, HTTPError, HTTPStatusError, Response, codes
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from structlog.stdlib import BoundLogger
from uritemplate import URITemplate

from .retry import retry_async

__all__ = [
    "Address",
    "Affiliation",
    "Author",
    "AuthorDb",
    "AuthorNotFoundError",
    "AuthorServiceError",
]


class AuthorNotFoundError(Exception):
    """The author database has no entry for the requested author ID.

    This is the user's own mistake — a typo, or an author who has not been
    added to lsst-texmf's ``etc/authordb.yaml`` yet — so it is kept distinct
    from the author service simply being unreachable.

    Parameters
    ----------
    author_id
        The author ID that was looked up.

    Attributes
    ----------
    author_id : str
        The author ID that was looked up.
    """

    def __init__(self, author_id: str) -> None:
        self.author_id = author_id
        super().__init__(
            f"Author ID not found in the author database: {author_id}"
        )


class AuthorServiceError(Exception):
    """The author database could not be consulted.

    Distinct from `AuthorNotFoundError`: the lookup never got a usable
    answer, so nothing can be said about whether the author exists. The
    underlying failure is always chained onto this exception with
    ``raise ... from``.
    """


class AuthorDb:
    """An interface for Ook author API."""

    def __init__(self, http_client: AsyncClient, logger: BoundLogger) -> None:
        """Initialize the interface."""
        self._http_client = http_client
        self._logger = logger
        self._author_endpoint = URITemplate(
            "https://roundtable.lsst.cloud/ook/authors/{author_id}"
        )

    async def get_author(self, author_id: str) -> Author:
        """Get an author entry by ID.

        Parameters
        ----------
        author_id
            The author's internal ID in lsst-texmf's ``etc/authordb.yaml``.

        Returns
        -------
        Author
            The author's record.

        Raises
        ------
        AuthorNotFoundError
            Raised if the author database has no entry for ``author_id``.
        AuthorServiceError
            Raised if the author database could not be consulted or did not
            answer usably: exhausted retries against a failing service, a
            transport error, a timeout, or a body that is not an author
            record.

        Notes
        -----
        The lookup is a read with no side effects, so it opts into
        `~templatebot.storage.retry.retry_async`. A 404 is not transient and
        is never retried: the wrapper only treats 5xx and transport failures
        as worth another attempt.
        """
        url = self._author_endpoint.expand(author_id=author_id)

        async def send() -> Response:
            r = await self._http_client.get(url)
            r.raise_for_status()
            return r

        try:
            r = await retry_async(
                send, logger=self._logger.bind(author_id=author_id)
            )
        except HTTPError as e:
            if (
                isinstance(e, HTTPStatusError)
                and e.response.status_code == codes.NOT_FOUND
            ):
                raise AuthorNotFoundError(author_id) from e
            raise AuthorServiceError(
                f"Error looking up author ID {author_id} in the author "
                f"database: {e}"
            ) from e

        try:
            return Author.model_validate_json(r.text)
        except ValidationError as e:
            raise AuthorServiceError(
                f"Could not parse the author database's record for author "
                f"ID {author_id}: {e}"
            ) from e


class Address(BaseModel):
    """An address for an affiliation."""

    street: str | None = Field(
        default=None, description="Street address of the affiliation."
    )

    city: str | None = Field(
        default=None, description="City/town of the affiliation."
    )

    state: str | None = Field(
        default=None, description="State or province of the affiliation."
    )

    postal_code: str | None = Field(
        default=None, description="Postal code of the affiliation."
    )

    country: str | None = Field(
        default=None, description="Country of the affiliation."
    )


class Affiliation(BaseModel):
    """An affiliation."""

    name: str = Field(description="Name of the affiliation.")

    department: str | None = Field(
        default=None, description="Department within the organization."
    )

    internal_id: str = Field(
        description="Internal ID of the affiliation.",
    )

    ror: HttpUrl | None = Field(
        default=None,
        description="ROR URL of the affiliation.",
    )

    address: Address | None = Field(
        default=None, description="Address of the affiliation."
    )


class Author(BaseModel):
    """An author."""

    internal_id: str = Field(
        description="Internal ID of the author.",
    )

    family_name: str = Field(description="Family name of the author.")

    given_name: str | None = Field(
        description="Given name of the author.",
    )

    orcid: HttpUrl | None = Field(
        default=None,
        description="ORCID of the author (URL), or null if not available.",
    )

    notes: list[str] = Field(
        default_factory=list,
        description="Notes about the author.",
    )

    affiliations: list[Affiliation] = Field(
        default_factory=list,
        description="The author's affiliations.",
    )
