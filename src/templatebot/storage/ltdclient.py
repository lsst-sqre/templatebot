"""LSST the Docs admin API client."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient, BasicAuth
from pydantic import SecretStr
from structlog.stdlib import BoundLogger

__all = ["LtdClient"]


class LtdClient:
    """A client for interacting with the LSST the Docs admin API."""

    def __init__(
        self,
        *,
        username: str,
        password: SecretStr,
        http_client: AsyncClient,
        logger: BoundLogger,
    ) -> None:
        self._username = username
        self._password = password
        self._http_client = http_client
        self._logger = logger

    async def get_token(self) -> str:
        """Get an auth token for LSST the Docs.

        Returns
        -------
        token : `str`
            The auth token (use in the 'username' field of basic auth, without
            a separate password).
        """
        url = "https://keeper.lsst.codes/token"
        auth = BasicAuth(
            username=self._username, password=self._password.get_secret_value()
        )
        response = await self._http_client.get(url, auth=auth, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data["token"]

    async def register_ltd_product(
        self,
        *,
        slug: str,
        title: str,
        github_repo: str,
        main_mode: str = "git_refs",
    ) -> dict[str, Any]:
        """Register a new product on LSST the Docs.

        Parameters
        ----------
        slug
            The *slug* is the sub-domain component of the lsst.io domain.
        title
            The product's title.
        github_repo
            The URL of the product's source repository.
        main_mode
            The tracking mode of the main edition. See
            https://ltd-keeper.lsst.io/editions.html#tracking-modes

        Returns
        -------
        dict
            The product resource, see
            https://ltd-keeper.lsst.io/products.html#get--products-(slug)
        """
        url = "https://keeper.lsst.codes/products/"
        data = {
            "title": title,
            "slug": slug,
            "doc_repo": github_repo,
            "main_mode": main_mode,
            "bucket_name": "lsst-the-docs",
            "root_domain": "lsst.io",
            "root_fastly_domain": "n.global-ssl.fastly.net",
        }

        self._logger.debug("Registering product on LTD", url=url, payload=data)

        token = await self.get_token()
        auth = BasicAuth(username=token, password="")

        r = await self._http_client.post(url, json=data, auth=auth)
        r.raise_for_status()
        product_url = r.headers["Location"]

        # Get data about the product
        r = await self._http_client.get(product_url, auth=auth)
        r.raise_for_status()
        return r.json()
