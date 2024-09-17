"""Slack Web API models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .blockkit import SlackBlock


class SlackChatPostMessageRequest(BaseModel):
    """A request body for the Slack ``chat.postMessage`` method."""

    channel: str = Field(
        ..., description="The channel ID.", examples=["C1234567890"]
    )

    text: str | None = Field(
        None, description="The text of the message as a fallback for blocks."
    )

    blocks: list[SlackBlock] | None = Field(
        None, description="The blocks that make up the message."
    )
