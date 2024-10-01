"""Template service."""

from __future__ import annotations

from structlog.stdlib import BoundLogger
from templatekit.repo import FileTemplate, ProjectTemplate

from templatebot.storage.slack import (
    SlackChatUpdateMessageRequest,
    SlackWebApiClient,
)
from templatebot.storage.slack.variablesmodal import TemplateVariablesModal

__all__ = ["TemplateService"]


class TemplateService:
    """A service for operating with templates.

    Features include:

    - Having a user configure a template through a Slack modal view
    - Rendering a template with user-provided values and running the
      configuration of that repository and LSST the Docs services.
    """

    def __init__(
        self, *, logger: BoundLogger, slack_client: SlackWebApiClient
    ) -> None:
        self._logger = logger
        self._slack_client = slack_client

    async def show_file_template_modal(
        self,
        *,
        user_id: str,
        trigger_id: str,
        message_ts: str,
        channel_id: str,
        template: FileTemplate,
        git_ref: str,
        repo_url: str,
    ) -> None:
        """Show a modal for selecting a file template."""
        if len(template.config["dialog_fields"]) == 0:
            await self._respond_with_nonconfigurable_content(
                template=template,
                channel_id=channel_id,
                trigger_message_ts=message_ts,
            )
        else:
            await self._open_template_modal(
                template=template,
                trigger_id=trigger_id,
                git_ref=git_ref,
                repo_url=repo_url,
                trigger_message_ts=message_ts,
                trigger_channel_id=channel_id,
            )

    async def show_project_template_modal(
        self,
        *,
        user_id: str,
        trigger_id: str,
        message_ts: str,
        channel_id: str,
        template: ProjectTemplate,
        git_ref: str,
        repo_url: str,
    ) -> None:
        """Show a modal for selecting a project template."""
        await self._open_template_modal(
            template=template,
            trigger_id=trigger_id,
            git_ref=git_ref,
            repo_url=repo_url,
            trigger_message_ts=message_ts,
            trigger_channel_id=channel_id,
        )

    async def _open_template_modal(
        self,
        *,
        template: FileTemplate | ProjectTemplate,
        trigger_id: str,
        git_ref: str,
        repo_url: str,
        trigger_message_ts: str | None = None,
        trigger_channel_id: str | None = None,
    ) -> None:
        """Open a modal for configuring a template."""
        modal_view = TemplateVariablesModal.create(
            template=template,
            git_ref=git_ref,
            repo_url=repo_url,
            trigger_message_ts=trigger_message_ts,
            trigger_channel_id=trigger_channel_id,
        )
        await self._slack_client.open_view(
            trigger_id=trigger_id, view=modal_view
        )

    async def _respond_with_nonconfigurable_content(
        self,
        *,
        template: FileTemplate,
        channel_id: str,
        trigger_message_ts: str,
    ) -> None:
        """Respond with non-configurable content."""
        # TODO(jonathansick): render the template and send it back to the user
        await self._slack_client.update_message(
            message_update_request=SlackChatUpdateMessageRequest(
                channel=channel_id,
                ts=trigger_message_ts,
                text=(
                    f"The {template.name} template does not require "
                    "configuration."
                ),
            )
        )

    async def create_project_from_template(
        self,
        *,
        template: ProjectTemplate,
        modal_values: dict[str, str],
        trigger_message_ts: str | None,
        trigger_channel_id: str | None,
    ) -> None:
        """Create a GitHub repository and set up a project from a template."""
        # TODO(jonathansick): implement this
        if trigger_channel_id and trigger_message_ts:
            await self._slack_client.update_message(
                message_update_request=SlackChatUpdateMessageRequest(
                    channel=trigger_channel_id,
                    ts=trigger_message_ts,
                    text=(
                        f"Creating a project from the {template.name} "
                        "template."
                    ),
                )
            )

    async def create_file_from_template(
        self,
        *,
        template: FileTemplate,
        modal_values: dict[str, str],
        trigger_message_ts: str | None,
        trigger_channel_id: str | None,
    ) -> None:
        """Create a file from a template."""
        # TODO(jonathansick): implement this
        if trigger_channel_id and trigger_message_ts:
            await self._slack_client.update_message(
                message_update_request=SlackChatUpdateMessageRequest(
                    channel=trigger_channel_id,
                    ts=trigger_message_ts,
                    text=(
                        f"Creating a file from the {template.name} template."
                    ),
                )
            )
