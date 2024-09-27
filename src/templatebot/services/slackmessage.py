"""Service for processing Slack messages."""

from __future__ import annotations

import re

from rubin.squarebot.models.kafka import (
    SquarebotSlackAppMentionValue,
    SquarebotSlackMessageValue,
)
from structlog.stdlib import BoundLogger

from templatebot.storage.slack import (
    SlackChatPostMessageRequest,
    SlackWebApiClient,
)
from templatebot.storage.slack.blockkit import (
    SlackContextBlock,
    SlackMrkdwnTextObject,
    SlackSectionBlock,
)

from .templaterepo import TemplateRepoService

MENTION_PATTERN = re.compile(r"<(@[a-zA-Z0-9]+|!subteam\^[a-zA-Z0-9]+)>")
"""Pattern for Slack mentions."""


class SlackMessageService:
    """A service for processing Slack messages."""

    def __init__(
        self,
        logger: BoundLogger,
        slack_client: SlackWebApiClient,
        template_repo_service: TemplateRepoService,
    ) -> None:
        self._logger = logger
        self._slack_client = slack_client
        self._template_repo_service = template_repo_service

    async def handle_im_message(
        self, message: SquarebotSlackMessageValue
    ) -> None:
        """Handle a Slack message.

        In the Squarebot ecosystem, all apps consume all messages and act on
        a message if it contains content the app cares about. Templatebot
        cares about the "create project" and "create file" commands.
        """
        self._logger.debug(
            "Slack message text",
            text=message.text,
            is_bot=message.is_bot,
            username=message.user,
        )
        self._logger.debug(
            "Full Slack IM message",
            body=message.model_dump(mode="json"),
        )
        if message.is_bot:
            self._logger.debug("Ignoring message from bot")
            return
        # Process the message
        await self._handle_message_text(message.text, message)

    async def handle_app_mention(
        self, message: SquarebotSlackAppMentionValue
    ) -> None:
        """Handle a Slack app mention."""
        self._logger.debug(
            "Slack app mention text",
            text=message.text,
        )
        # Process the message
        await self._handle_message_text(message.text, message)

    async def _handle_message_text(
        self,
        text: str,
        original_message: SquarebotSlackMessageValue
        | SquarebotSlackAppMentionValue,
    ) -> None:
        """Handle a message text."""
        self._logger.debug(
            "Slack message text",
            text=text,
        )
        # Process the message
        text = text.lower().strip()
        if "create project" in text:
            await self._handle_create_project(original_message)
        elif "create file" in text:
            await self._handle_create_file(original_message)
        else:
            # Strip out mentions
            text = MENTION_PATTERN.sub("", original_message.text)
            # normalize
            text = " ".join(text.lower().split())

            # determine if "help" is the only word
            if text in ("help", "help!", "help?"):
                await self._handle_help(original_message)

    async def _handle_create_project(
        self,
        message: SquarebotSlackMessageValue | SquarebotSlackAppMentionValue,
    ) -> None:
        """Handle a "create project" message."""
        self._logger.info("Creating a project")
        thread_ts: str | None = None
        if hasattr(message, "thread_ts") and message.thread_ts:
            thread_ts = message.thread_ts

        if not message.user:
            self._logger.warning(
                "Project creation is being requested via a message that "
                "doesn't have a user ID",
                message=message.model_dump(mode="json"),
            )
            return
        await self._template_repo_service.handle_project_template_selection(
            user_id=message.user,
            channel_id=message.channel,
            parent_ts=thread_ts if isinstance(thread_ts, str) else None,
        )

    async def _handle_create_file(
        self,
        message: SquarebotSlackMessageValue | SquarebotSlackAppMentionValue,
    ) -> None:
        """Handle a "create file" message."""
        self._logger.info("Creating a file")
        thread_ts: str | None = None
        if hasattr(message, "thread_ts") and message.thread_ts:
            thread_ts = message.thread_ts
        if not message.user:
            self._logger.warning(
                "File creation is being requested via a message that "
                "doesn't have a user ID",
                message=message.model_dump(mode="json"),
            )
            return
        await self._template_repo_service.handle_file_template_selection(
            user_id=message.user,
            channel_id=message.channel,
            parent_ts=thread_ts if isinstance(thread_ts, str) else None,
        )

    async def _handle_help(
        self,
        message: SquarebotSlackMessageValue | SquarebotSlackAppMentionValue,
    ) -> None:
        """Handle a "help" message."""
        self._logger.info("Sending help message")
        help_summary = (
            "Create a new GitHub repo from a template: `create project`.\\n"
            "Create a snippet of file from a template: `create file`."
        )
        section_bock = SlackSectionBlock(
            text=SlackMrkdwnTextObject(
                text=(
                    "• Create a GitHub repo from a template: "
                    "```create project```\n"
                    "• Create a file or snippet from a template: "
                    "```create file```"
                )
            )
        )
        context_block = SlackContextBlock(
            elements=[
                SlackMrkdwnTextObject(
                    text=(
                        "Handled by <https://github.com/lsst-sqre/templatebot"
                        "|templatebot>. The template repository is "
                        "https://github.com/lsst/templates."
                    )
                )
            ]
        )
        thread_ts: str | None = None
        if hasattr(message, "thread_ts") and message.thread_ts:
            thread_ts = message.thread_ts
        reply = SlackChatPostMessageRequest(
            channel=message.channel,
            thread_ts=thread_ts,
            text=help_summary,
            blocks=[section_bock, context_block],
        )
        await self._slack_client.send_chat_post_message(reply)
