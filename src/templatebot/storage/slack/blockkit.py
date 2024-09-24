"""Slack Block Kit models."""

from __future__ import annotations

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
    "SlackPlainTextObject",
    "SlackSectionBlock",
    "SlackSectionBlockAccessoryTypes",
    "SlackStaticSelectElement",
    "SlackTextObjectTypes",
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
    )

    element: SlackStaticSelectElement = Field(
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
    )

    optional: bool = Field(
        False,
        description=(
            "A boolean value that indicates whether the input element may be "
            "empty when a user submits the modal."
        ),
    )

    @model_validator(mode="after")
    def validate_text_length(self) -> Self:
        """Ensure that the text length is not more than 2000 characters."""
        if len(self.label.text) > 2000:
            raise ValueError("The length of the label text must be <= 2000.")
        if self.hint and len(self.hint.text) > 2000:
            raise ValueError("The length of the hint text must be <= 2000.")
        return self


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

    @model_validator(mode="after")
    def validate_text_length(self) -> Self:
        """Ensure that the text length is not more than 75 characters."""
        if len(self.text.text) > 75:
            raise ValueError("The length of the text must be <= 75.")
        if self.description and len(self.description.text) > 75:
            raise ValueError("The length of the description must be <= 75.")
        return self


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
    )

    options: list[SlackOptionObject] = Field(
        ...,
        description=(
            "An array of option objects that belong to this specific group."
        ),
        min_length=1,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_text_length(self) -> Self:
        """Ensure that the text length is not more than 75 characters."""
        if len(self.label.text) > 75:
            raise ValueError("The length of the label text must be <= 75.")
        return self


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
    )

    text: SlackPlainTextObject = Field(
        ...,
        description=(
            "A text object that defines the explanatory text that appears in "
            "the confirm dialog. Maximum length of 300 characters."
        ),
    )

    confirm: SlackPlainTextObject = Field(
        ...,
        description=(
            "A plain text object that defines the text of the button that "
            "confirms the action. Maximum length of 30 characters."
        ),
    )

    deny: SlackPlainTextObject = Field(
        ...,
        description=(
            "A plain text object that defines the text of the button that "
            "denies the action. Maximum length of 30 characters."
        ),
    )

    style: Literal["primary", "danger"] = Field(
        "primary",
        description=(
            "A string value to determine the color of the confirm button. "
            "Options include `primary` and `danger`."
        ),
    )

    @model_validator(mode="after")
    def validate_text_length(self) -> Self:
        """Ensure that the text length is not more than 300 characters."""
        if len(self.title.text) > 100:
            raise ValueError("The length of the title text must be <= 100.")
        if len(self.text.text) > 300:
            raise ValueError("The length of the text must be <= 300.")
        if len(self.confirm.text) > 300:
            raise ValueError("The length of the confirm text must be <= 30.")
        if len(self.deny.text) > 300:
            raise ValueError("The length of the deny text must be <= 30.")
        return self


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

    @model_validator(mode="after")
    def validate_text_length(self) -> Self:
        """Ensure that the text length is not more than 150 characters."""
        if len(self.placeholder.text) > 150:
            raise ValueError(
                "The length of the placeholder text must be <= 150."
            )
        return self


SlackBlock = SlackSectionBlock | SlackContextBlock | SlackInputBlock
"""A generic type alias for Slack Block Kit blocks."""

SlackTextObjectTypes = SlackPlainTextObject | SlackMrkdwnTextObject
"""A type alias for Slack Block Kit text objects."""

SlackSectionBlockAccessoryTypes = SlackStaticSelectElement
"""A type alias for Slack Block Kit section block accessory types."""
