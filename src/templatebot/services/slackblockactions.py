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
from templatebot.storage.slack.blockkit import (
    SlackInputBlock,
    SlackMrkdwnTextObject,
    SlackOptionObject,
    SlackPlainTextInputElement,
    SlackPlainTextObject,
    SlackSectionBlock,
    SlackStaticSelectElement,
)
from templatebot.storage.slack.views import SlackModalView

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

        demo_section = SlackSectionBlock(
            text=SlackMrkdwnTextObject(
                text=f"Let's create a {selected_option.text.text} project."
            ),
        )
        demo_select_input = SlackInputBlock(
            label=SlackPlainTextObject(text="License"),
            element=SlackStaticSelectElement(
                placeholder=SlackPlainTextObject(text="Choose a license…"),
                action_id="select_license",
                options=[
                    SlackOptionObject(
                        text=SlackPlainTextObject(text="MIT"),
                        value="mit",
                    ),
                    SlackOptionObject(
                        text=SlackPlainTextObject(text="GPLv3"),
                        value="gplv3",
                    ),
                ],
            ),
            block_id="license",
            hint=SlackPlainTextObject(text="MIT is preferred."),
        )
        demo_text_input = SlackInputBlock(
            label=SlackPlainTextObject(text="Project name"),
            element=SlackPlainTextInputElement(
                placeholder=SlackPlainTextObject(text="Enter a project name…"),
                action_id="project_name",
                min_length=3,
            ),
            block_id="project_name",
        )
        modal = SlackModalView(
            title=SlackPlainTextObject(text="Set up your project"),
            blocks=[demo_section, demo_select_input, demo_text_input],
            submit=SlackPlainTextObject(text="Create project"),
            close=SlackPlainTextObject(text="Cancel"),
        )
        response = await self._slack_client.open_view(
            trigger_id=payload.trigger_id, view=modal
        )
        if not response["ok"]:
            self._logger.error(
                "Failed to open view",
                response=response,
                payload=payload.model_dump(mode="json"),
            )
