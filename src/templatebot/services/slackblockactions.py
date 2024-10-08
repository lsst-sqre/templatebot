"""Slack service for handling block actions."""

from __future__ import annotations

from rubin.squarebot.models.kafka import SquarebotSlackBlockActionsValue
from rubin.squarebot.models.slack import (
    SlackBlockActionBase,
    SlackStaticSelectAction,
)
from structlog.stdlib import BoundLogger
from templatekit.repo import FileTemplate, ProjectTemplate

from templatebot.config import config
from templatebot.constants import (
    SELECT_FILE_TEMPLATE_ACTION,
    SELECT_PROJECT_TEMPLATE_ACTION,
)
from templatebot.services.template import TemplateService
from templatebot.storage.repo import RepoManager
from templatebot.storage.slack import SlackWebApiClient

__all__ = ["SlackBlockActionsService"]


class SlackBlockActionsService:
    """A service for processing Slack block actions."""

    def __init__(
        self,
        logger: BoundLogger,
        slack_client: SlackWebApiClient,
        template_service: TemplateService,
        repo_manager: RepoManager,
    ) -> None:
        self._logger = logger
        self._slack_client = slack_client
        self._template_service = template_service
        self._repo_manager = repo_manager

    async def handle_block_actions(
        self, payload: SquarebotSlackBlockActionsValue
    ) -> None:
        """Handle a Slack block_actions interaction."""
        for action in payload.actions:
            if action.action_id == SELECT_PROJECT_TEMPLATE_ACTION:
                await self.handle_project_template_selection(
                    action=action, payload=payload
                )
            elif action.action_id == SELECT_FILE_TEMPLATE_ACTION:
                await self.handle_file_template_selection(
                    action=action, payload=payload
                )

    async def handle_project_template_selection(
        self,
        *,
        action: SlackBlockActionBase,
        payload: SquarebotSlackBlockActionsValue,
    ) -> None:
        """Handle a project template selection."""
        if not isinstance(action, SlackStaticSelectAction):
            raise TypeError(
                f"Expected action for {SELECT_PROJECT_TEMPLATE_ACTION} to be "
                f"a SlackStaticSelectAction, but got {type(action)}"
            )
        selected_option = action.selected_option
        self._logger.debug(
            "Selected project template",
            value=selected_option.value,
            text=selected_option.text.text,
        )

        if not payload.channel:
            raise ValueError("No channel in payload")
        original_message_channel = payload.channel.id
        if not payload.message:
            raise ValueError("No message in payload")
        original_message_ts = payload.message.ts

        git_ref = "main"

        template = self._repo_manager.get_repo(gitref=git_ref)[
            selected_option.value
        ]
        if not isinstance(template, ProjectTemplate):
            raise TypeError(
                f"Expected {selected_option.value} template to be a "
                f"ProjectTemplate, but got {type(template)}"
            )

        await self._template_service.show_project_template_modal(
            user_id=payload.user.id,
            trigger_id=payload.trigger_id,
            message_ts=original_message_ts,
            channel_id=original_message_channel,
            template=template,
            git_ref=git_ref,
            repo_url=str(config.template_repo_url),
        )

    async def handle_file_template_selection(
        self,
        *,
        action: SlackBlockActionBase,
        payload: SquarebotSlackBlockActionsValue,
    ) -> None:
        """Handle a file template selection."""
        if not isinstance(action, SlackStaticSelectAction):
            raise TypeError(
                f"Expected action for {SELECT_FILE_TEMPLATE_ACTION} to be "
                f"a SlackStaticSelectAction, but got {type(action)}"
            )
        selected_option = action.selected_option
        self._logger.debug(
            "Selected file template",
            value=selected_option.value,
            text=selected_option.text.text,
        )

        if not payload.channel:
            raise ValueError("No channel in payload")
        original_message_channel = payload.channel.id
        if not payload.message:
            raise ValueError("No message in payload")
        original_message_ts = payload.message.ts

        git_ref = "main"

        template = self._repo_manager.get_repo(gitref=git_ref)[
            selected_option.value
        ]
        if not isinstance(template, FileTemplate):
            raise TypeError(
                f"Expected {selected_option.value} template to be a "
                f"ProjectTemplate, but got {type(template)}"
            )

        await self._template_service.show_file_template_modal(
            user_id=payload.user.id,
            trigger_id=payload.trigger_id,
            message_ts=original_message_ts,
            channel_id=original_message_channel,
            template=template,
            git_ref=git_ref,
            repo_url=str(config.template_repo_url),
        )
