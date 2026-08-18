"""Factory for templatebot services and other components."""

from dataclasses import dataclass
from typing import Self

import structlog
from httpx import AsyncClient, Timeout
from safir.slack.webhook import SlackWebhookClient
from structlog.stdlib import BoundLogger

from templatebot.services.slackblockactions import SlackBlockActionsService
from templatebot.services.slackmessage import SlackMessageService
from templatebot.services.slackview import SlackViewService
from templatebot.services.template import TemplateService
from templatebot.services.templaterepo import TemplateRepoService
from templatebot.storage.githubappclientfactory import GitHubAppClientFactory
from templatebot.storage.ltdclient import LtdClient
from templatebot.storage.repo import RepoManager
from templatebot.storage.slack import SlackWebApiClient

from .config import config

__all__ = ["CONNECT_TIMEOUT", "Factory", "ProcessContext"]

CONNECT_TIMEOUT = 10.0
"""Timeout, in seconds, for establishing a connection to an HTTP server.

Connecting is bounded separately from the rest of a request so that
`~templatebot.config.Config.http_timeout` stays the single operator-facing
knob for how long a slow *response* is tolerated.
"""


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
        http_client = AsyncClient(
            timeout=Timeout(config.http_timeout, connect=CONNECT_TIMEOUT)
        )
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

    def create_slack_alert_client(self) -> SlackWebhookClient | None:
        """Create a Slack webhook client for operator alerts.

        Returns
        -------
        safir.slack.webhook.SlackWebhookClient or None
            A client that posts to the configured alert webhook, or `None`
            when `~templatebot.config.Config.slack_alert_webhook` is unset.
            Alerting is opt-in so that the app runs unchanged without the
            secret; callers treat `None` as "do not alert".

        Notes
        -----
        This client does not use the shared HTTP client from the process
        context: Safir's ``SlackWebhookClient`` gets its own client from
        ``safir.dependencies.http_client.http_client_dependency``. It also
        logs and swallows any error posting the message, so an alert can
        never turn into a second failure for the caller to handle.
        """
        if config.slack_alert_webhook is None:
            return None
        return SlackWebhookClient(
            hook_url=config.slack_alert_webhook,
            application=config.name,
            logger=self._logger,
        )

    def create_github_client_factory(self) -> GitHubAppClientFactory:
        """Create a new GitHub client factory."""
        return GitHubAppClientFactory(
            id=config.github_app_id,
            key=config.github_app_private_key.get_secret_value(),
            name="templatebot",
            http_client=self._process_context.http_client,
        )

    def create_ltd_client(self) -> LtdClient:
        """Create a new LSST the Docs client."""
        return LtdClient(
            username=config.ltd_username,
            password=config.ltd_password,
            http_client=self._process_context.http_client,
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
            logger=self._logger,
            slack_client=self.create_slack_web_client(),
            repo_manager=self._process_context.repo_manager,
            template_service=self.create_template_service(),
        )

    def create_slack_view_service(self) -> SlackViewService:
        """Create a new Slack view handling service."""
        return SlackViewService(
            logger=self._logger,
            slack_client=self.create_slack_web_client(),
            repo_manager=self._process_context.repo_manager,
            template_service=self.create_template_service(),
            slack_alert_client=self.create_slack_alert_client(),
        )

    def create_template_repo_service(self) -> TemplateRepoService:
        """Create a new template repository service."""
        return TemplateRepoService(
            logger=self._logger,
            repo_manager=self._process_context.repo_manager,
            slack_client=self.create_slack_web_client(),
        )

    def create_template_service(self) -> TemplateService:
        """Create a new template service."""
        return TemplateService(
            logger=self._logger,
            slack_client=self.create_slack_web_client(),
            http_client=self._process_context.http_client,
            github_client_factory=self.create_github_client_factory(),
            ltd_client=self.create_ltd_client(),
        )
