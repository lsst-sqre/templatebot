"""Slack Block Kit models."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "SlackBlock",
    "SlackContextBlock",
    "SlackMrkdwnTextObject",
    "SlackPlainTextObject",
    "SlackSectionBlock",
]

block_id_field = Field(
    None,
    description="A unique identifier for the block.",
    max_length=255,
)


class SlackSectionBlock(BaseModel):
    """A Slack section Block Kit block.

    Reference: https://api.slack.com/reference/block-kit/blocks#section
    """

    type: Literal["section"] = Field(
        "section",
        description=(
            "The type of block. Reference: "
            "https://api.slack.com/reference/block-kit/blocks"
        ),
    )

    block_id: Annotated[str | None, block_id_field] = None

    text: SlackTextObjectTypes | None = Field(
        None,
        description=(
            "The text to display in the block. Not required if `fields` is "
            "provided."
        ),
    )

    # Fields can take other types of elements.
    fields: list[SlackTextObjectTypes] | None = Field(
        None,
        description=(
            "An array of text objects. Each element of the array is a "
            "text object, and is rendered as a separate paragraph."
        ),
        min_length=1,
        max_length=10,
    )

    @model_validator(mode="after")
    def validate_text_or_fields(self) -> Self:
        """Ensure that either `text` or `fields` is provided."""
        if not self.text and not self.fields:
            raise ValueError("Either `text` or `fields` must be provided.")
        return self

    @model_validator(mode="after")
    def validate_fields_length(self) -> Self:
        """Ensure that the max length of all text objects is not more than
        2000 characters.
        """
        for i, field in enumerate(self.fields or []):
            if len(field.text) > 2000:
                raise ValueError(
                    f"The length of a field text element {i} must be <= 2000."
                )
        return self

    @model_validator(mode="after")
    def validate_text_length(self) -> Self:
        """Ensure that the text length is not more than 3000 characters."""
        if self.text and len(self.text.text) > 3000:
            raise ValueError("The length of the text must be <= 3000.")
        return self


class SlackContextBlock(BaseModel):
    """A Slack block for displaying contextual info.

    Reference: https://api.slack.com/reference/block-kit/blocks#context
    """

    type: Literal["context"] = Field(
        "context",
        description=(
            "The type of block. Reference: "
            "https://api.slack.com/reference/block-kit/blocks"
        ),
    )

    block_id: Annotated[str | None, block_id_field] = None

    # image elements can also be supported when available
    elements: list[SlackTextObjectTypes] = Field(
        ...,
        description=(
            "An array of text objects. Each element of the array is a "
            "text or image object, and is rendered in a separate context line."
            "Maximum of 10 elements."
        ),
        min_length=1,
        max_length=10,
    )


class SlackPlainTextObject(BaseModel):
    """A plain_text composition object.

    https://api.slack.com/reference/block-kit/composition-objects#text
    """

    type: Literal["plain_text"] = Field(
        "plain_text", description="The type of object."
    )

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

    type: Literal["mrkdwn"] = Field(
        "mrkdwn", description="The type of object."
    )

    text: str = Field(..., description="The text to display.")

    verbatim: bool = Field(
        False,
        description=(
            "Indicates whether the text should be treated as verbatim. When "
            "`True`, URLs will not be auto-converted into links and "
            "channel names will not be auto-converted into links."
        ),
    )


SlackBlock = SlackSectionBlock | SlackContextBlock
"""A generic type alias for Slack Block Kit blocks."""

SlackTextObjectTypes = SlackPlainTextObject | SlackMrkdwnTextObject
"""A type alias for Slack Block Kit text objects."""
