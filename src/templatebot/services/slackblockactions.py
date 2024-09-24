"""Slack service for handling block actions."""

from __future__ import annotations

from rubin.squarebot.models.kafka import SquarebotSlackBlockActionsValue
from rubin.squarebot.models.slack import (
    SlackBlockActionBase,
    SlackStaticSelectAction,
)
from structlog.stdlib import BoundLogger

from templatebot.constants import SELECT_PROJECT_TEMPLATE_ACTION
from templatebot.storage.slack import SlackWebApiClient
from templatebot.storage.slack._models import SlackChatUpdateMessageRequest

__all__ = ["SlackBlockActionsService"]


class SlackBlockActionsService:
    """A service for processing Slack block actions."""

    def __init__(
        self, logger: BoundLogger, slack_client: SlackWebApiClient
    ) -> None:
        self._logger = logger
        self._slack_client = slack_client

    async def handle_block_actions(
        self, payload: SquarebotSlackBlockActionsValue
    ) -> None:
        """Handle a Slack block_actions interaction."""
        for action in payload.actions:
            if action.action_id == SELECT_PROJECT_TEMPLATE_ACTION:
                await self.handle_project_template_selection(
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

        updated_messsage = SlackChatUpdateMessageRequest(
            channel=original_message_channel,
            ts=original_message_ts,
            text=(
                f"We'll create a project with the {selected_option.text.text} "
                "template"
            ),
        )
        await self._slack_client.update_message(updated_messsage)
