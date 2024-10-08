"""Storage interface to a GitHub repository."""

from __future__ import annotations

from typing import Any

from gidgethub.httpx import GitHubAPI
from structlog.stdlib import BoundLogger

__all__ = ["GitHubRepo"]


class GitHubRepo:
    """Storage interface to a GitHub repository."""

    def __init__(
        self,
        *,
        owner: str,
        name: str,
        github_client: GitHubAPI,
        logger: BoundLogger,
    ) -> None:
        self._owner = owner
        self._name = name
        self._github_client = github_client
        self._logger = logger

    async def create_repo(
        self,
        *,
        homepage: str | None = None,
        description: str | None = None,
        allow_squash_merge: bool = False,
        allow_merge_commit: bool = True,
        allow_rebase_merge: bool = False,
        delete_branch_on_merge: bool = True,
    ) -> dict[str, Any]:
        """Create the GitHub repository."""
        # Construct arguments to GitHub
        data = {
            "name": self._name,
            # We want an empty repo for the render step.
            "auto_init": False,
            # Defaults for LSST
            "has_projects": False,
            "has_wiki": False,
            "allow_squash_merge": allow_squash_merge,
            "allow_merge_commit": allow_merge_commit,
            "allow_rebase_merge": allow_rebase_merge,
            "delete_branch_on_merge": delete_branch_on_merge,
        }
        if homepage is not None:
            data["homepage"] = homepage
        if description is not None:
            data["description"] = description
        self._logger.info("Creating repo", request_data=data)
        return await self._github_client.post(
            "/orgs{/org_name}/repos",
            url_vars={"org_name": self._owner},
            data=data,
        )
