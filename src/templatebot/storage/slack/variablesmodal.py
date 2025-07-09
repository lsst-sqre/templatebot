"""Storage model for the Slack modal configuring template variables."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, HttpUrl
from templatekit.repo import FileTemplate, ProjectTemplate

from templatebot.constants import TEMPLATE_VARIABLES_MODAL_CALLBACK_ID

from .blockkit import (
    SlackBlock,
    SlackInputBlock,
    SlackOptionGroupObject,
    SlackOptionObject,
    SlackPlainTextInputElement,
    SlackPlainTextObject,
    SlackStaticSelectElement,
)
from .views import SlackModalView

__all__ = ["TemplateVariablesModal", "TemplateVariablesModalMetadata"]


class TemplateVariablesModalMetadata(BaseModel):
    """Private metadata for the template variables modal.

    This metadata is encoded as JSON. It includes information about what
    template is being configured.
    """

    type: Annotated[
        Literal["file", "project"],
        Field(description="The type of template being configured."),
    ]

    template_name: Annotated[
        str, Field(description="The name of the template being configured.")
    ]

    git_ref: Annotated[
        str,
        Field(
            description="The Git reference (branch or tag) for the template."
        ),
    ]

    repo_url: Annotated[
        HttpUrl,
        Field(
            description=(
                "The URL of the repository where the template is stored."
            )
        ),
    ]

    trigger_message_ts: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "The timestamp of the message that triggered the modal "
                "(i.e., the message that the user clicked on to open the "
                "modal). Templatebot will update this message with the "
                "results of the modal and project creation."
            ),
        ),
    ] = None

    trigger_channel_id: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "The channel ID of the message that triggered the modal. "
                "Used with `trigger_message_ts` to update the source message."
            ),
        ),
    ] = None


class TemplateVariablesModal(SlackModalView):
    """A modal for configuring template variables.

    The callback ID for this modal is
    `templatebot.constants.TEMPLATE_VARIABLES_MODAL_CALLBACK_ID` and the
    private metadata is JSON-encoded `TemplateVariablesModalMetadata`.
    """

    @classmethod
    def create(
        cls,
        *,
        template: FileTemplate | ProjectTemplate,
        git_ref: str,
        repo_url: str,
        trigger_message_ts: str | None = None,
        trigger_channel_id: str | None = None,
    ) -> TemplateVariablesModal:
        """Create a modal for configuring template variables."""
        blocks = cls._create_template_modal(template)
        modal_metadata = TemplateVariablesModalMetadata(
            type="file" if isinstance(template, FileTemplate) else "project",
            template_name=template.name,
            git_ref=git_ref,
            repo_url=HttpUrl(repo_url),
            trigger_message_ts=trigger_message_ts,
            trigger_channel_id=trigger_channel_id,
        )
        return cls(
            title=SlackPlainTextObject(text=template.config["dialog_title"]),
            submit=SlackPlainTextObject(text="Submit"),
            close=SlackPlainTextObject(text="Cancel"),
            blocks=blocks,
            callback_id=TEMPLATE_VARIABLES_MODAL_CALLBACK_ID,
            private_metadata=modal_metadata.model_dump_json(),
        )

    @classmethod
    def _create_template_modal(
        cls,
        template: FileTemplate | ProjectTemplate,
    ) -> list[SlackBlock]:
        """Create a modal for configuring a template."""
        blocks: list[SlackBlock] = []
        for field in template.config["dialog_fields"]:
            if field["component"] == "select":
                if "preset_options" in field:
                    # Handle preset menu
                    element = cls._generate_preset_options_input(field)
                elif "preset_groups" in field:
                    # Handle group preset menu
                    element = cls._generate_preset_groups_input(field)
                else:
                    # Handle regular select menu
                    element = cls._generate_select_input(field)
            else:
                element = cls._generate_text_input(
                    field, multiline=field["component"] == "textarea"
                )
            blocks.append(element)
        return blocks

    @staticmethod
    def _generate_text_input(
        field: dict[str, Any],
        *,
        multiline: bool = False,
    ) -> SlackInputBlock:
        """Generate a text input for a default field type for the template
        creation modal.
        """
        return SlackInputBlock(
            label=SlackPlainTextObject(text=field["label"]),
            block_id=field["key"],  # TODO(jonathansick): have a common prefix?
            element=SlackPlainTextInputElement(
                action_id=field["key"],
                placeholder=SlackPlainTextObject(
                    text=field["placeholder"],
                )
                if "placeholder" in field and len(field["placeholder"]) > 0
                else None,
                multiline=multiline,
            ),
            hint=SlackPlainTextObject(text=field["hint"])
            if "hint" in field
            else None,
            optional=field.get("optional", False),
        )

    @staticmethod
    def _generate_select_input(field: dict[str, Any]) -> SlackInputBlock:
        """Generate an select element input block for a template creation
        modal.
        """
        return SlackInputBlock(
            label=SlackPlainTextObject(text=field["label"]),
            block_id=field["key"],
            element=SlackStaticSelectElement(
                action_id=field["key"],
                placeholder=SlackPlainTextObject(
                    text=field["placeholder"],
                )
                if "placeholder" in field and len(field["placeholder"]) > 0
                else None,
                options=[
                    SlackOptionObject(
                        text=SlackPlainTextObject(text=v["label"]),
                        value=v["value"],
                        # note individual options can now have descriptions
                    )
                    for v in field["options"]
                ],
            ),
            hint=SlackPlainTextObject(text=field["hint"])
            if "hint" in field
            else None,
            optional=field.get("optional", False),
        )

    @staticmethod
    def _generate_preset_options_input(
        field: dict[str, Any],
    ) -> SlackInputBlock:
        """Generate the select element input blocks for a ``preset_options``
        flavour of field in a template creation modal.
        """
        return SlackInputBlock(
            label=SlackPlainTextObject(text=field["label"]),
            block_id=field["label"],
            element=SlackStaticSelectElement(
                action_id=field["label"],
                placeholder=SlackPlainTextObject(
                    text=field["placeholder"],
                )
                if "placeholder" in field and len(field["placeholder"]) > 0
                else None,
                options=[
                    SlackOptionObject(
                        text=SlackPlainTextObject(text=v["label"]),
                        value=v["value"],
                        # note individual options can now have descriptions
                    )
                    for v in field["preset_options"]
                ],
            ),
            hint=SlackPlainTextObject(text=field["hint"])
            if "hint" in field
            else None,
            optional=field.get("optional", False),
        )

    @staticmethod
    def _generate_preset_groups_input(
        field: dict[str, Any],
    ) -> SlackInputBlock:
        """Generate the select input element for a ``preset_groups`` flavor of
        field in a template creation modal.
        """
        option_groups: list[SlackOptionGroupObject] = []
        for group in field["preset_groups"]:
            menu_group = SlackOptionGroupObject(
                label=SlackPlainTextObject(text=group["group_label"]),
                options=[
                    SlackOptionObject(
                        text=SlackPlainTextObject(text=group_option["label"]),
                        value=group_option["label"],
                    )
                    for group_option in group["options"]
                ],
            )
            option_groups.append(menu_group)

        return SlackInputBlock(
            label=SlackPlainTextObject(text=field["label"]),
            block_id=field["label"],
            element=SlackStaticSelectElement(
                action_id=field["label"],
                placeholder=SlackPlainTextObject(
                    text=field["placeholder"],
                )
                if "placeholder" in field and len(field["placeholder"]) > 0
                else None,
                option_groups=option_groups,
            ),
            hint=SlackPlainTextObject(text=field["hint"])
            if "hint" in field
            else None,
            optional=field.get("optional", False),
        )
