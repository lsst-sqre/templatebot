"""A service for handling Slack view interactions."""

from __future__ import annotations

from rubin.squarebot.models.kafka import SquarebotSlackViewSubmissionValue
from structlog.stdlib import BoundLogger

from templatebot.storage.slack import SlackWebApiClient


class SlackViewService:
    """A service for handling Slack view interactions."""

    def __init__(
        self, logger: BoundLogger, slack_client: SlackWebApiClient
    ) -> None:
        self._logger = logger
        self._slack_client = slack_client

    async def handle_view_submission(
        self, payload: SquarebotSlackViewSubmissionValue
    ) -> None:
        """Handle a Slack view submission interaction."""
        self._logger.debug(
            "Got view submission", payload=payload.model_dump(mode="json")
        )
