"""Slack Block Kit models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

__all__ = [
    "SlackBlock",
    "SlackPlainTextObject",
    "SlackMrkdwnTextObject",
    "SlackSectionBlock",
]


class SlackSectionBlock(BaseModel):
    """A Slack section Block Kit block.

    Reference: https://api.slack.com/reference/block-kit/blocks#section
    """

    type: Literal["section"] = Field(..., description="The type of block.")

    text: SlackPlainTextObject | SlackMrkdwnTextObject | None = Field(
        None,
        description=(
            "The text to display in the block. Not required if `fields` is "
            "provided."
        ),
    )

    # Fields can take other types of elements.
    fields: list[SlackPlainTextObject | SlackMrkdwnTextObject] | None = Field(
        None,
        description=(
            "An array of text objects. Each element of the array is a "
            "text object, and is rendered as a separate paragraph."
        ),
    )


class SlackPlainTextObject(BaseModel):
    """A plain_text composition object.

    https://api.slack.com/reference/block-kit/composition-objects#text
    """

    type: Literal["plain_text"] = Field(..., description="The type of object.")

    text: str = Field(..., description="The text to display.")

    emoji: bool = Field(
        True,
        description=(
            "Indicates whether emojis in text should be escaped into colon "
            "emoji format."
        ),
    )


class SlackMrkdwnTextObject(BaseModel):
    """A mrkdwn text composition object.

    https://api.slack.com/reference/block-kit/composition-objects#text
    """

    type: Literal["mrkdwn"] = Field(..., description="The type of object.")

    text: str = Field(..., description="The text to display.")

    verbatim: bool = Field(
        False,
        description=(
            "Indicates whether the text should be treated as verbatim. When "
            "`True`, URLs will not be auto-converted into links and "
            "channel names will not be auto-converted into links."
        ),
    )


SlackBlock = SlackSectionBlock
"""A generic type alias for Slack Block Kit blocks."""
