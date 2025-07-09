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

    type: Annotated[
        Literal["section"],
        Field(
            default="section",
            description=(
                "The type of block. Reference: "
                "https://api.slack.com/reference/block-kit/blocks"
            ),
        ),
    ] = "section"

    block_id: Annotated[str | None, block_id_field] = None

    text: Annotated[
        SlackTextObjectType | None,
        Field(
            default=None,
            description=(
                "The text to display in the block. Not required if "
                "`fields` is provided."
            ),
        ),
    ] = None

    # Fields can take other types of elements.
    fields: Annotated[
        list[SlackTextObjectType] | None,
        Field(
            default=None,
            description=(
                "An array of text objects. Each element of the array is a "
                "text object, and is rendered as a separate paragraph."
            ),
            min_length=1,
            max_length=10,
        ),
    ] = None

    accessory: Annotated[
        SlackSectionBlockAccessoryTypes | None,
        Field(
            default=None,
            description=(
                "An accessory is an interactive element that can be displayed "
                "within a section block. For example, a button, select menu, "
                "or datepicker."
            ),
        ),
    ] = None

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

    type: Annotated[
        Literal["context"],
        Field(
            default="context",
            description=(
                "The type of block. Reference: "
                "https://api.slack.com/reference/block-kit/blocks"
            ),
        ),
    ] = "context"

    block_id: Annotated[str | None, block_id_field] = None

    # image elements can also be supported when available
    elements: Annotated[
        list[SlackTextObjectType],
        Field(
            description=(
                "An array of text objects. Each element of the array is a "
                "text or image object, and is rendered in a separate context "
                "line. Maximum of 10 elements."
            ),
            min_length=1,
            max_length=10,
        ),
    ]


class SlackInputBlock(BaseModel):
    """A Slack input block for collecting user input.

    Reference: https://api.slack.com/reference/block-kit/blocks#input
    """

    type: Annotated[
        Literal["input"],
        Field(
            default="input",
            description=(
                "The type of block. Reference: "
                "https://api.slack.com/reference/block-kit/blocks"
            ),
        ),
    ] = "input"

    block_id: Annotated[str | None, block_id_field] = None

    label: Annotated[
        SlackPlainTextObject,
        Field(
            description=(
                "A label that appears above an input element. "
                "Maximum length of 2000 characters."
            ),
            max_length=2000,
        ),
    ]

    element: Annotated[
        SlackStaticSelectElement | SlackPlainTextInputElement,
        Field(description="An input element."),
    ]

    dispatch_action: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "A boolean value that indicates whether the input element "
                "should dispatch action payloads."
            ),
        ),
    ] = False

    hint: Annotated[
        SlackPlainTextObject | None,
        Field(
            default=None,
            description=(
                "A plain text object that defines a plain text element that "
                "apppears below an input element in a lighter font. "
                "Maximum length of 2000 characters."
            ),
            max_length=2000,
        ),
    ] = None

    optional: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "A boolean value that indicates whether the input element "
                "may be empty when a user submits the modal."
            ),
        ),
    ] = False


class SlackTextObjectBase(BaseModel, ABC):
    """A base class for Slack Block Kit text objects."""

    type: Annotated[
        Literal["plain_text", "mrkdwn"],
        Field(description="The type of object."),
    ]

    text: Annotated[str, Field(description="The text to display.")]

    def __len__(self) -> int:
        """Return the length of the text."""
        return len(self.text)


class SlackPlainTextObject(SlackTextObjectBase):
    """A plain_text composition object.

    https://api.slack.com/reference/block-kit/composition-objects#text
    """

    type: Annotated[
        Literal["plain_text"],
        Field(default="plain_text", description="The type of object."),
    ] = "plain_text"

    emoji: Annotated[
        bool,
        Field(
            default=True,
            description=(
                "Indicates whether emojis in text should be escaped into "
                "colon emoji format."
            ),
        ),
    ] = True


class SlackMrkdwnTextObject(SlackTextObjectBase):
    """A mrkdwn text composition object.

    https://api.slack.com/reference/block-kit/composition-objects#text
    """

    type: Annotated[
        Literal["mrkdwn"],
        Field(default="mrkdwn", description="The type of object."),
    ] = "mrkdwn"

    verbatim: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "Indicates whether the text should be treated as verbatim. "
                "When `True`, URLs will not be auto-converted into links and "
                "channel names will not be auto-converted into links."
            ),
        ),
    ] = False


SlackTextObjectType = SlackPlainTextObject | SlackMrkdwnTextObject
"""A type alias for Slack Block Kit text objects."""


class SlackOptionObject(BaseModel):
    """An option object for Slack Block Kit elements.

    Typically used with `SlackStaticSelectElement`.

    Reference: https://api.slack.com/reference/block-kit/composition-objects#option
    """

    # Check boxes and radio buttons could use SlackMrkdwnTextObject
    text: Annotated[
        SlackPlainTextObject,
        Field(
            description=(
                "A plain text object that defines the text shown in the "
                "option. Maximum length of 75 characters."
            ),
            max_length=75,
        ),
    ]

    value: Annotated[
        str,
        Field(
            description=(
                "A unique string value that will be passed to your app when "
                "this option is selected."
            ),
            max_length=150,
        ),
    ]

    # Check boxes and radio buttons could use SlackMrkdwnTextObject
    description: Annotated[
        SlackPlainTextObject | None,
        Field(
            default=None,
            description=(
                "A plain text object that defines a line of descriptive "
                "text shown below the text. Maximum length of 75 characters."
            ),
            max_length=75,
        ),
    ] = None

    url: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "A URL to load in the user's browser when the option is "
                "clicked. The url attribute is only available in overflow "
                "menus. The url attribute is only available in overflow "
                "menus. Maximum length of 3000 characters."
            ),
            max_length=3000,
        ),
    ] = None


class SlackOptionGroupObject(BaseModel):
    """An option group object for Slack Block Kit elements.

    Typically used with `SlackStaticSelectElement`.

    Reference: https://api.slack.com/reference/block-kit/composition-objects#option_group
    """

    label: Annotated[
        SlackPlainTextObject,
        Field(
            description=(
                "A plain text object that defines the label shown above this "
                "group of options. Maximum length of 75 characters."
            ),
            max_length=75,
        ),
    ]

    options: Annotated[
        list[SlackOptionObject],
        Field(
            description=(
                "An array of option objects that belong to this specific "
                "group."
            ),
            min_length=1,
            max_length=100,
        ),
    ]


class SlackConfirmationDialogObject(BaseModel):
    """A confirmation dialog object for Slack Block Kit elements.

    Reference: https://api.slack.com/reference/block-kit/composition-objects#confirm
    """

    title: Annotated[
        SlackPlainTextObject,
        Field(
            description=(
                "A plain text object that defines the dialog's title. "
                "Maximum length of 100 characters."
            ),
            max_length=100,
        ),
    ]

    text: Annotated[
        SlackPlainTextObject,
        Field(
            description=(
                "A text object that defines the explanatory text that "
                "appears in the confirm dialog. Maximum length of "
                "300 characters."
            ),
            max_length=300,
        ),
    ]

    confirm: Annotated[
        SlackPlainTextObject,
        Field(
            description=(
                "A plain text object that defines the text of the button "
                "that confirms the action. Maximum length of 30 characters."
            ),
            max_length=30,
        ),
    ]

    deny: Annotated[
        SlackPlainTextObject,
        Field(
            description=(
                "A plain text object that defines the text of the button "
                "that denies the action. Maximum length of 30 characters."
            ),
            max_length=30,
        ),
    ]

    style: Annotated[
        Literal["primary", "danger"],
        Field(
            default="primary",
            description=(
                "A string value to determine the color of the confirm "
                "button. Options include `primary` and `danger`."
            ),
        ),
    ] = "primary"


class SlackStaticSelectElement(BaseModel):
    """A static select element for Slack Block Kit.

    Reference: https://api.slack.com/reference/block-kit/block-elements#static_select
    """

    type: Annotated[
        Literal["static_select"],
        Field(
            default="static_select",
            description=(
                "The type of element. Reference: "
                "https://api.slack.com/reference/block-kit/block-elements"
            ),
        ),
    ] = "static_select"

    placeholder: Annotated[
        SlackPlainTextObject | None,
        Field(
            default=None,
            description=(
                "A plain text object that defines the placeholder text shown "
                "on the static select element. Maximum length of "
                "150 characters."
            ),
            max_length=150,
            min_length=1,
        ),
    ] = None

    options: Annotated[
        list[SlackOptionObject] | None,
        Field(
            default=None,
            description=(
                "An array of option objects that populate the static select "
                "menu."
            ),
            min_length=1,
            max_length=100,
        ),
    ] = None

    option_groups: Annotated[
        list[SlackOptionGroupObject] | None,
        Field(
            default=None,
            description=(
                "An array of option group objects that populate the select "
                "menu with groups of options."
            ),
        ),
    ] = None

    action_id: Annotated[
        str,
        Field(
            description=(
                "An identifier for the action triggered when a menu option "
                "is selected."
            ),
            max_length=255,
        ),
    ]

    initial_option: Annotated[
        SlackOptionObject | None,
        Field(
            default=None,
            description=(
                "A single option that exactly matches one of the options "
                "within options. This option will be selected when the menu "
                "initially loads."
            ),
        ),
    ] = None

    confirm: Annotated[
        SlackConfirmationDialogObject | None,
        Field(
            default=None,
            description=(
                "A confirmation dialog that appears after a menu item is "
                "selected."
            ),
        ),
    ] = None

    focus_on_load: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "A boolean value indicating whether the element should be "
                "pre-focused when the view opens."
            ),
        ),
    ] = False

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

    type: Annotated[
        Literal["plain_text_input"],
        Field(default="plain_text_input", description="The type of element."),
    ] = "plain_text_input"

    action_id: Annotated[
        str,
        Field(
            description=(
                "An identifier for the input's value when the parent modal "
                "is submitted. This should be unique among all other "
                "action_ids used in the containing block. Maximum length of "
                "255 characters."
            ),
            max_length=255,
        ),
    ]

    initial_value: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "The initial (default) value in the plain-text input when it "
                "is loaded."
            ),
        ),
    ] = None

    placeholder: Annotated[
        SlackPlainTextObject | None,
        Field(
            default=None,
            description=(
                "A plain text object that defines the placeholder text shown "
                "in the plain-text input. Maximum length of 150 characters."
            ),
            max_length=150,
            min_length=1,
        ),
    ] = None

    multiline: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "A boolean value indicating whether the input will be a "
                "single line (false) or a larger textarea (true)."
            ),
        ),
    ] = False

    min_length: Annotated[
        int | None,
        Field(
            default=None,
            description=(
                "The minimum length of input that the user must provide."
            ),
            ge=1,
            le=3000,
        ),
    ] = None

    max_length: Annotated[
        int | None,
        Field(
            default=None,
            description=(
                "The maximum length of input that the user can provide."
            ),
            ge=1,
            le=3000,
        ),
    ] = None

    focus_on_load: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "A boolean value indicating whether the element should be "
                "pre-focused when the view opens."
            ),
        ),
    ] = False

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
