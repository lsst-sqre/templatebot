"""Service for processing Slack messages."""

from __future__ import annotations

from rubin.squarebot.models.kafka import SquarebotSlackMessageValue
from structlog.stdlib import BoundLogger

from templatebot.storage.slack import (
    SlackChatPostMessageRequest,
    SlackWebApiClient,
)


class SlackMessageService:
    """A service for processing Slack messages."""

    def __init__(
        self, logger: BoundLogger, slack_client: SlackWebApiClient
    ) -> None:
        self._logger = logger
        self._slack_client = slack_client

    async def handle_message(
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
        )
        # Process the message
        text = message.text.lower().strip()
        if text.startswith("create project"):
            await self._handle_create_project(message)
        elif text.startswith("create file"):
            await self._handle_create_file(message)
        elif text.startswith("help"):
            await self._handle_help(message)

    async def _handle_create_project(
        self, message: SquarebotSlackMessageValue
    ) -> None:
        """Handle a "create project" message."""
        self._logger.info("Creating a project")
        reply = SlackChatPostMessageRequest(
            channel=message.channel,
            text="Creating a project…",
        )
        await self._slack_client.send_chat_post_message(reply)

    async def _handle_create_file(
        self, message: SquarebotSlackMessageValue
    ) -> None:
        """Handle a "create file" message."""
        self._logger.info("Creating a file")
        reply = SlackChatPostMessageRequest(
            channel=message.channel,
            text="Creating a file…",
        )
        await self._slack_client.send_chat_post_message(reply)

    async def _handle_help(self, message: SquarebotSlackMessageValue) -> None:
        """Handle a "help" message."""
        self._logger.info("Sending help message")
        reply = SlackChatPostMessageRequest(
            channel=message.channel,
            text="Sending help…",
        )
        await self._slack_client.send_chat_post_message(reply)
