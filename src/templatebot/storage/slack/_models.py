"""Slack Web API models."""

from __future__ import annotations

from typing import Annotated, Self

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

    channel: Annotated[
        str, Field(description="The channel ID.", examples=["C1234567890"])
    ]

    thread_ts: Annotated[
        str | None,
        Field(
            default=None,
            description="The timestamp of the parent message in a thread.",
        ),
    ] = None

    reply_broadcast: Annotated[
        bool | None,
        Field(
            default=None,
            description=(
                "Whether to broadcast the message to the channel from a "
                "thread (see ``thread_ts``)."
            ),
        ),
    ] = None

    text: Annotated[
        str | None,
        Field(
            default=None,
            description="The text of the message as a fallback for blocks.",
        ),
    ] = None

    mrkdwn: Annotated[
        bool,
        Field(
            default=True,
            description="Whether the text is formatted using Slack markdown.",
        ),
    ] = True

    blocks: Annotated[
        list[SlackBlock] | None,
        Field(
            default=None, description="The blocks that make up the message."
        ),
    ] = None

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

    channel: Annotated[
        str, Field(description="The channel ID.", examples=["C1234567890"])
    ]

    ts: Annotated[
        str, Field(description="The timestamp of the message to update.")
    ]

    text: Annotated[
        str | None,
        Field(default=None, description="The new text of the message."),
    ] = None

    blocks: Annotated[
        list[SlackBlock] | None,
        Field(
            default=None,
            description="The new blocks that make up the message.",
        ),
    ] = None

    @model_validator(mode="after")
    def validate_text_or_blocks(self) -> Self:
        """Ensure that either text or blocks are provided."""
        if not self.text and not self.blocks:
            raise ValueError("Either `text` or `blocks` must be provided.")
        return self
