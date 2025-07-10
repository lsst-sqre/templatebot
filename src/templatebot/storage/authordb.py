"""Storage interface for lsst-texmf's authordb.yaml file."""

from __future__ import annotations

from httpx import AsyncClient
from pydantic import BaseModel, Field, HttpUrl
from uritemplate import URITemplate

__all__ = ["Address", "Affiliation", "Author", "AuthorDb"]


class AuthorDb:
    """An interface for Ook author API."""

    def __init__(self, http_client: AsyncClient) -> None:
        """Initialize the interface."""
        self._http_client = http_client
        self._author_endpoint = URITemplate(
            "https://roundtable.lsst.cloud/ook/authors/{author_id}"
        )

    async def get_author(self, author_id: str) -> Author:
        """Get an author entry by ID."""
        r = await self._http_client.get(
            self._author_endpoint.expand(author_id=author_id)
        )
        r.raise_for_status()
        return Author.model_validate_json(r.text)


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
