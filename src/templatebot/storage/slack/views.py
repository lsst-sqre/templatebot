"""Models for Slack views (including modals)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .blockkit import SlackBlock, SlackPlainTextObject

__all__ = ["SlackModalView"]


class SlackModalView(BaseModel):
    """Slack modal view."""

    type: Literal["modal"] = Field("modal", description="The type of view.")

    title: SlackPlainTextObject = Field(
        ...,
        description="The title of the view. Maximum length is 24 characters.",
        max_length=24,
    )

    blocks: list[SlackBlock] = Field(
        description="The blocks that make up the view."
    )

    close: SlackPlainTextObject | None = Field(
        None,
        description=(
            "The text for the close button. Maximum length is 24 characters."
        ),
        max_length=24,
    )

    submit: SlackPlainTextObject | None = Field(
        None,
        description=(
            "The text for the submit button. Maximum length is 24 characters."
        ),
        max_length=24,
    )

    private_metadata: str | None = Field(
        None,
        description=(
            "A string that will be sent to your app when the view is "
            "submitted."
        ),
        max_length=3000,
    )

    callback_id: str | None = Field(
        None,
        description=(
            "An identifier for the view. Maximum length is 255 characters."
        ),
        max_length=255,
    )

    clear_on_close: bool = Field(
        False,
        description="Whether the view should be cleared when it's closed.",
    )

    notify_on_close: bool = Field(
        False,
        description=(
            "Whether your app should be notified when the view is closed with "
            "the `view_closed` event."
        ),
    )

    external_id: str | None = Field(
        None, description="A unique identifier for the view."
    )
