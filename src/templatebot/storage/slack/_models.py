"""Slack Web API models."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator

from .blockkit import SlackBlock

__all__ = [
    "SlackChatPostMessageRequest",
    "SlackChatUpdateMessageRequest",
]


class SlackChatPostMessageRequest(BaseModel):
    """A request body for the Slack ``chat.postMessage`` method.

    See https://api.slack.com/methods/chat.postMessage for more information.
    """

    channel: str = Field(
        ..., description="The channel ID.", examples=["C1234567890"]
    )

    thread_ts: str | None = Field(
        None,
        description="The timestamp of the parent message in a thread.",
    )

    reply_broadcast: bool | None = Field(
        None,
        description=(
            "Whether to broadcast the message to the channel from a thread "
            "(see ``thread_ts``)."
        ),
    )

    text: str | None = Field(
        None, description="The text of the message as a fallback for blocks."
    )

    mrkdwn: bool = Field(
        True, description="Whether the text is formatted using Slack markdown."
    )

    blocks: list[SlackBlock] | None = Field(
        None, description="The blocks that make up the message."
    )

    @model_validator(mode="after")
    def validate_text_fallback(self) -> Self:
        """Ensure that the text field is provided if blocks are not."""
        if not self.text and not self.blocks:
            raise ValueError("Either `text` or `blocks` must be provided.")
        return self


class SlackChatUpdateMessageRequest(BaseModel):
    """A request body for the Slack ``chat.update`` method.

    See https://api.slack.com/methods/chat.update for more information.
    """

    channel: str = Field(
        ..., description="The channel ID.", examples=["C1234567890"]
    )

    ts: str = Field(..., description="The timestamp of the message to update.")

    text: str | None = Field(None, description="The new text of the message.")

    blocks: list[SlackBlock] | None = Field(
        None, description="The new blocks that make up the message."
    )

    @model_validator(mode="after")
    def validate_text_or_blocks(self) -> Self:
        """Ensure that either text or blocks are provided."""
        if not self.text and not self.blocks:
            raise ValueError("Either `text` or `blocks` must be provided.")
        return self
