"""Slack Block Kit models."""

from __future__ import annotations

from abc import ABC
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "SlackBlock",
    "SlackConfirmationDialogObject",
    "SlackContextBlock",
    "SlackInputBlock",
    "SlackMrkdwnTextObject",
    "SlackOptionGroupObject",
    "SlackOptionObject",
    "SlackPlainTextInputElement",
    "SlackPlainTextObject",
    "SlackSectionBlock",
    "SlackSectionBlockAccessoryTypes",
    "SlackStaticSelectElement",
    "SlackTextObjectBase",
    "SlackTextObjectType",
]

block_id_field: str | None = Field(
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

    text: SlackTextObjectType | None = Field(
        None,
        description=(
            "The text to display in the block. Not required if `fields` is "
            "provided."
        ),
    )

    # Fields can take other types of elements.
    fields: list[SlackTextObjectType] | None = Field(
        None,
        description=(
            "An array of text objects. Each element of the array is a "
            "text object, and is rendered as a separate paragraph."
        ),
        min_length=1,
        max_length=10,
    )

    accessory: SlackSectionBlockAccessoryTypes | None = Field(
        None,
        description=(
            "An accessory is an interactive element that can be displayed "
            "within a section block. For example, a button, select menu, "
            "or datepicker."
        ),
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
    elements: list[SlackTextObjectType] = Field(
        ...,
        description=(
            "An array of text objects. Each element of the array is a "
            "text or image object, and is rendered in a separate context line."
            "Maximum of 10 elements."
        ),
        min_length=1,
        max_length=10,
    )


class SlackInputBlock(BaseModel):
    """A Slack input block for collecting user input.

    Reference: https://api.slack.com/reference/block-kit/blocks#input
    """

    type: Literal["input"] = Field(
        "input",
        description=(
            "The type of block. Reference: "
            "https://api.slack.com/reference/block-kit/blocks"
        ),
    )

    block_id: Annotated[str | None, block_id_field] = None

    label: SlackPlainTextObject = Field(
        ...,
        description=(
            "A label that appears above an input element. "
            "Maximum length of 2000 characters."
        ),
        max_length=2000,
    )

    element: SlackStaticSelectElement | SlackPlainTextInputElement = Field(
        ..., description="An input element."
    )

    dispatch_action: bool = Field(
        False,
        description=(
            "A boolean value that indicates whether the input element "
            "should dispatch action payloads."
        ),
    )

    hint: SlackPlainTextObject | None = Field(
        None,
        description=(
            "A plain text object that defines a plain text element that "
            "apppears below an input element in a lighter font. "
            "Maximum length of 2000 characters."
        ),
        max_length=2000,
    )

    optional: bool = Field(
        False,
        description=(
            "A boolean value that indicates whether the input element may be "
            "empty when a user submits the modal."
        ),
    )


class SlackTextObjectBase(BaseModel, ABC):
    """A base class for Slack Block Kit text objects."""

    type: Literal["plain_text", "mrkdwn"] = Field(
        ..., description="The type of object."
    )

    text: str = Field(..., description="The text to display.")

    def __len__(self) -> int:
        """Return the length of the text."""
        return len(self.text)


class SlackPlainTextObject(SlackTextObjectBase):
    """A plain_text composition object.

    https://api.slack.com/reference/block-kit/composition-objects#text
    """

    type: Literal["plain_text"] = Field(
        "plain_text", description="The type of object."
    )

    emoji: bool = Field(
        True,
        description=(
            "Indicates whether emojis in text should be escaped into colon "
            "emoji format."
        ),
    )


class SlackMrkdwnTextObject(SlackTextObjectBase):
    """A mrkdwn text composition object.

    https://api.slack.com/reference/block-kit/composition-objects#text
    """

    type: Literal["mrkdwn"] = Field(
        "mrkdwn", description="The type of object."
    )

    verbatim: bool = Field(
        False,
        description=(
            "Indicates whether the text should be treated as verbatim. When "
            "`True`, URLs will not be auto-converted into links and "
            "channel names will not be auto-converted into links."
        ),
    )


SlackTextObjectType = SlackPlainTextObject | SlackMrkdwnTextObject
"""A type alias for Slack Block Kit text objects."""


class SlackOptionObject(BaseModel):
    """An option object for Slack Block Kit elements.

    Typically used with `SlackStaticSelectElement`.

    Reference: https://api.slack.com/reference/block-kit/composition-objects#option
    """

    # Check boxes and radio buttons could use SlackMrkdwnTextObject
    text: SlackPlainTextObject = Field(
        ...,
        description=(
            "A plain text object that defines the text shown in the option. "
            "Maximum length of 75 characters."
        ),
        max_length=75,
    )

    value: str = Field(
        ...,
        description=(
            "A unique string value that will be passed to your app when this "
            "option is selected."
        ),
        max_length=150,
    )

    # Check boxes and radio buttons could use SlackMrkdwnTextObject
    description: SlackPlainTextObject | None = Field(
        None,
        description=(
            "A plain text object that defines a line of descriptive text "
            "shown below the text. Maximum length of 75 characters."
        ),
        max_length=75,
    )

    url: str | None = Field(
        None,
        description=(
            "A URL to load in the user's browser when the option is clicked. "
            "The url attribute is only available in overflow menus. The url "
            "attribute is only available in overflow menus. Maximum length of "
            "3000 characters."
        ),
        max_length=3000,
    )


class SlackOptionGroupObject(BaseModel):
    """An option group object for Slack Block Kit elements.

    Typically used with `SlackStaticSelectElement`.

    Reference: https://api.slack.com/reference/block-kit/composition-objects#option_group
    """

    label: SlackPlainTextObject = Field(
        ...,
        description=(
            "A plain text object that defines the label shown above this "
            "group of options. Maximum length of 75 characters."
        ),
        max_length=75,
    )

    options: list[SlackOptionObject] = Field(
        ...,
        description=(
            "An array of option objects that belong to this specific group."
        ),
        min_length=1,
        max_length=100,
    )


class SlackConfirmationDialogObject(BaseModel):
    """A confirmation dialog object for Slack Block Kit elements.

    Reference: https://api.slack.com/reference/block-kit/composition-objects#confirm
    """

    title: SlackPlainTextObject = Field(
        ...,
        description=(
            "A plain text object that defines the dialog's title. Maximum "
            "length of 100 characters."
        ),
        max_length=100,
    )

    text: SlackPlainTextObject = Field(
        ...,
        description=(
            "A text object that defines the explanatory text that appears in "
            "the confirm dialog. Maximum length of 300 characters."
        ),
        max_length=300,
    )

    confirm: SlackPlainTextObject = Field(
        ...,
        description=(
            "A plain text object that defines the text of the button that "
            "confirms the action. Maximum length of 30 characters."
        ),
        max_length=30,
    )

    deny: SlackPlainTextObject = Field(
        ...,
        description=(
            "A plain text object that defines the text of the button that "
            "denies the action. Maximum length of 30 characters."
        ),
        max_length=30,
    )

    style: Literal["primary", "danger"] = Field(
        "primary",
        description=(
            "A string value to determine the color of the confirm button. "
            "Options include `primary` and `danger`."
        ),
    )


class SlackStaticSelectElement(BaseModel):
    """A static select element for Slack Block Kit.

    Reference: https://api.slack.com/reference/block-kit/block-elements#static_select
    """

    type: Literal["static_select"] = Field(
        "static_select",
        description=(
            "The type of element. Reference: "
            "https://api.slack.com/reference/block-kit/block-elements"
        ),
    )

    placeholder: SlackPlainTextObject | None = Field(
        None,
        description=(
            "A plain text object that defines the placeholder text shown on "
            "the static select element. Maximum length of 150 characters."
        ),
        max_length=150,
        min_length=1,
    )

    options: list[SlackOptionObject] | None = Field(
        None,
        description=(
            "An array of option objects that populate the static select menu."
        ),
        min_length=1,
        max_length=100,
    )

    option_groups: list[SlackOptionGroupObject] | None = Field(
        None,
        description=(
            "An array of option group objects that populate the select menu "
            "with groups of options."
        ),
    )

    action_id: str = Field(
        ...,
        description=(
            "An identifier for the action triggered when a menu option is "
            "selected."
        ),
        max_length=255,
    )

    initial_option: SlackOptionObject | None = Field(
        None,
        description=(
            "A single option that exactly matches one of the options within "
            "options. This option will be selected when the menu initially "
            "loads."
        ),
    )

    confirm: SlackConfirmationDialogObject | None = Field(
        None,
        description=(
            "A confirmation dialog that appears after a menu item is selected."
        ),
    )

    focus_on_load: bool = Field(
        False,
        description=(
            "A boolean value indicating whether the element should be "
            "pre-focused when the view opens."
        ),
    )

    @model_validator(mode="after")
    def validate_options_or_option_groups(self) -> Self:
        """Ensure that either `options` or `option_groups` is provided."""
        if not self.options and not self.option_groups:
            raise ValueError(
                "Either `options` or `option_groups` must be provided."
            )
        if self.options and self.option_groups:
            raise ValueError(
                "Only one of `options` or `option_groups` can be provided."
            )
        return self


class SlackPlainTextInputElement(BaseModel):
    """A plain text input element for Slack Block Kit.

    Works with `SlackInputBlock`.

    Reference: https://api.slack.com/reference/block-kit/block-elements#input
    """

    type: Literal["plain_text_input"] = Field(
        "plain_text_input", description="The type of element."
    )

    action_id: str = Field(
        ...,
        description=(
            "An identifier for the input's value when the parent modal is "
            "submitted. This should be unique among all other action_ids used "
            "in the containing block. Maximum length of 255 characters."
        ),
        max_length=255,
    )

    initial_value: str | None = Field(
        None,
        description=(
            "The initial (default) value in the plain-text input when it is "
            "loaded."
        ),
    )

    placeholder: SlackPlainTextObject | None = Field(
        None,
        description=(
            "A plain text object that defines the placeholder text shown in "
            "the plain-text input. Maximum length of 150 characters."
        ),
        max_length=150,
        min_length=1,
    )

    multiline: bool = Field(
        False,
        description=(
            "A boolean value indicating whether the input will be a single "
            "line (false) or a larger textarea (true)."
        ),
    )

    min_length: int | None = Field(
        None,
        description=(
            "The minimum length of input that the user must provide."
        ),
        ge=1,
        le=3000,
    )

    max_length: int | None = Field(
        None,
        description=("The maximum length of input that the user can provide."),
        ge=1,
        le=3000,
    )

    focus_on_load: bool = Field(
        False,
        description=(
            "A boolean value indicating whether the element should be "
            "pre-focused when the view opens."
        ),
    )

    # dispatch_action_config is not implemented yet.

    @model_validator(mode="after")
    def validate_min_max_length(self) -> Self:
        """Ensure that the min_length is less than or equal to max_length."""
        if (
            self.min_length
            and self.max_length
            and self.min_length > self.max_length
        ):
            raise ValueError(
                "The min_length must be less than or equal to max_length."
            )
        return self


SlackBlock = SlackSectionBlock | SlackContextBlock | SlackInputBlock
"""A generic type alias for Slack Block Kit blocks."""

SlackSectionBlockAccessoryTypes = SlackStaticSelectElement
"""A type alias for Slack Block Kit section block accessory types."""
