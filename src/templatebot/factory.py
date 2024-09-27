"""Factory for templatebot services and other components."""

from dataclasses import dataclass
from typing import Self

import structlog
from httpx import AsyncClient
from structlog.stdlib import BoundLogger

from templatebot.services.slackblockactions import SlackBlockActionsService
from templatebot.services.slackmessage import SlackMessageService
from templatebot.services.slackview import SlackViewService
from templatebot.services.templaterepo import TemplateRepoService
from templatebot.storage.repo import RepoManager
from templatebot.storage.slack import SlackWebApiClient

from .config import config

__all__ = ["Factory", "ProcessContext"]


@dataclass(kw_only=True, frozen=True, slots=True)
class ProcessContext:
    """Holds singletons in the context of a Ook process, which might be a
    API server or a CLI command.
    """

    http_client: AsyncClient
    """Shared HTTP client."""

    repo_manager: RepoManager
    """Template repository manager. This maintains an on-disk cache of
    template repository clones.
    """

    @classmethod
    async def create(cls) -> Self:
        """Create a new process context."""
        http_client = AsyncClient()
        repo_manager = RepoManager(
            url=str(config.template_repo_url),
            cache_dir=config.template_cache_dir,
            logger=structlog.get_logger(__name__),
        )

        return cls(http_client=http_client, repo_manager=repo_manager)

    async def aclose(self) -> None:
        """Close any resources held by the context."""
        await self.http_client.aclose()


class Factory:
    """Factory for Squarebot services and other components."""

    def __init__(
        self,
        *,
        logger: BoundLogger,
        process_context: ProcessContext,
    ) -> None:
        self._process_context = process_context
        self._logger = logger

    def set_logger(self, logger: BoundLogger) -> None:
        """Reset the logger for the factory.

        This is typically used by the ConsumerContext when values are bound
        to the logger.

        Parameters
        ----------
        logger
            The new logger to use.
        """
        self._logger = logger

    def create_slack_web_client(self) -> SlackWebApiClient:
        """Create a Slack web API client."""
        return SlackWebApiClient(
            http_client=self._process_context.http_client,
            token=config.slack_token,
            logger=self._logger,
        )

    def create_slack_message_service(self) -> SlackMessageService:
        """Create a new Slack message handling service."""
        return SlackMessageService(
            logger=self._logger,
            slack_client=self.create_slack_web_client(),
            template_repo_service=self.create_template_repo_service(),
        )

    def create_slack_block_actions_service(self) -> SlackBlockActionsService:
        """Create a new Slack block actions handling service."""
        return SlackBlockActionsService(
            logger=self._logger, slack_client=self.create_slack_web_client()
        )

    def create_slack_view_service(self) -> SlackViewService:
        """Create a new Slack view handling service."""
        return SlackViewService(
            logger=self._logger, slack_client=self.create_slack_web_client()
        )

    def create_template_repo_service(self) -> TemplateRepoService:
        """Create a new template repository service."""
        return TemplateRepoService(
            logger=self._logger,
            repo_manager=self._process_context.repo_manager,
            slack_client=self.create_slack_web_client(),
        )
