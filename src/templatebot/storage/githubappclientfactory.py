"""GitHub App client factory."""

from __future__ import annotations

from gidgethub.httpx import GitHubAPI
from safir.github import GitHubAppClientFactory as SafirGitHubAppClientFactory

__all__ = ["GitHubAppClientFactory"]

# TODO(jonathansick): Upstream this to Safir


class GitHubAppClientFactory(SafirGitHubAppClientFactory):
    """GitHub App client factory that can get an installation in an org."""

    async def create_installation_client_for_org(
        self,
        owner: str,
    ) -> GitHubAPI:
        """Create a client authenticated as an installation of the GitHub App
        for an organization.

        Parameters
        ----------
        owner
            The organization name.

        Returns
        -------
        gidgethub.httpx.GitHubAPI
            The installation client.
        """
        app_jwt = self.get_app_jwt()
        anon_client = self.create_anonymous_client()

        installation_url = "/app/installations"
        async for installation in anon_client.getiter(
            installation_url, jwt=app_jwt, iterable_key=None
        ):
            if installation["target_type"] == "Organization":
                if installation["account"]["login"] == owner:
                    installation_id = installation["id"]
                    return await self.create_installation_client(
                        installation_id
                    )

        raise ValueError(f"No installation found for {owner}")
