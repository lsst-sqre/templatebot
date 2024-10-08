"""Storage interface to a local Git clone of a project repository."""

from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Self

import git
from gidgethub.httpx import GitHubAPI

from templatebot.config import config

__all__ = ["GitClone"]


class GitClone:
    """Storage interface to a local Git clone of a project repository."""

    def __init__(self, *, repo: git.Repo, github_client: GitHubAPI) -> None:
        self._repo = repo
        self._github_client = github_client

    @classmethod
    def init_repo(
        cls,
        *,
        path: Path,
        github_client: GitHubAPI,
        default_branch: str = "main",
    ) -> Self:
        """Initialize a new Git repository in the given path and stage all
        files.
        """
        repo = git.Repo.init(str(path), b=default_branch)
        repo.index.add(repo.untracked_files)
        return cls(repo=repo, github_client=github_client)

    @property
    def path(self) -> Path:
        """Path to the local Git clone."""
        return Path(self._repo.working_dir)

    @property
    def repo(self) -> git.Repo:
        """The GitPython Repo object."""
        return self._repo

    def _create_authed_url(self, url: str) -> str:
        repo_url_parts = urllib.parse.urlparse(url)
        host = repo_url_parts.netloc.rsplit("@", 1)[-1]
        if not self._github_client.oauth_token:
            # Mostly for mypy's benefit.
            raise RuntimeError("No OAuth token for installation client")
        token = self._github_client.oauth_token
        return repo_url_parts._replace(
            scheme="https", netloc=f"squarebot:{token}@{host}"
        ).geturl()

    def add_remote(self, url: str, *, name: str = "origin") -> git.Remote:
        """Add a remote to the repository."""
        authed_url = self._create_authed_url(url)
        return self._repo.create_remote(name, authed_url)

    def create_bot_actor(self) -> git.Actor:
        """Create an actor for the bot."""
        email = (
            f"{config.github_app_id}+{config.github_username}"
            "[bot]@users.noreply.github.com"
        )
        return git.Actor(config.github_username, email)

    def commit(self, message: str) -> None:
        """Commit all changes in the repository."""
        actor = self.create_bot_actor()
        self._repo.index.commit(message, author=actor, committer=actor)

    def push(self, *, remote_url: str, branch: str = "main") -> None:
        """Push the repository to the remote."""
        authed_url = self._create_authed_url(remote_url)
        remote = self._repo.create_remote("tmp-squarebot", authed_url)

        try:
            push_info = remote.push(f"{branch}:{branch}", force=True)
            for result in push_info:
                if result.flags & git.PushInfo.ERROR:
                    msg = f"Pushing {branch} failed: {result.summary}"
                    raise RuntimeError(msg)
        finally:
            git.Remote.remove(self.repo, "tmp-squarebot")
