"""Models for Slack views (including modals)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .blockkit import SlackBlock, SlackPlainTextObject

__all__ = ["SlackModalView"]


class SlackModalView(BaseModel):
    """Slack modal view."""

    type: Annotated[
        Literal["modal"],
        Field(default="modal", description="The type of view."),
    ] = "modal"

    title: Annotated[
        SlackPlainTextObject,
        Field(
            description=(
                "The title of the view. Maximum length is 24 characters."
            ),
            max_length=24,
        ),
    ]

    blocks: Annotated[
        list[SlackBlock],
        Field(description="The blocks that make up the view."),
    ]

    close: Annotated[
        SlackPlainTextObject | None,
        Field(
            default=None,
            description=(
                "The text for the close button. Maximum length is "
                "24 characters."
            ),
            max_length=24,
        ),
    ] = None

    submit: Annotated[
        SlackPlainTextObject | None,
        Field(
            default=None,
            description=(
                "The text for the submit button. Maximum length is "
                "24 characters."
            ),
            max_length=24,
        ),
    ] = None

    private_metadata: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "A string that will be sent to your app when the view is "
                "submitted."
            ),
            max_length=3000,
        ),
    ] = None

    callback_id: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "An identifier for the view. Maximum length is 255 characters."
            ),
            max_length=255,
        ),
    ] = None

    clear_on_close: Annotated[
        bool,
        Field(
            default=False,
            description="Whether the view should be cleared when it's closed.",
        ),
    ] = False

    notify_on_close: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "Whether your app should be notified when the view is closed "
                "with the `view_closed` event."
            ),
        ),
    ] = False

    external_id: Annotated[
        str | None,
        Field(default=None, description="A unique identifier for the view."),
    ] = None
