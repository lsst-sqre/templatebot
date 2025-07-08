"""Service for operations with template repositories."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TypeVar

from structlog.stdlib import BoundLogger
from templatekit.repo import BaseTemplate

from templatebot.constants import (
    SELECT_FILE_TEMPLATE_ACTION,
    SELECT_PROJECT_TEMPLATE_ACTION,
)
from templatebot.storage.repo import RepoManager
from templatebot.storage.slack import (
    SlackChatPostMessageRequest,
    SlackWebApiClient,
)
from templatebot.storage.slack.blockkit import (
    SlackMrkdwnTextObject,
    SlackOptionGroupObject,
    SlackOptionObject,
    SlackPlainTextObject,
    SlackSectionBlock,
    SlackStaticSelectElement,
)

__all__ = ["TemplateRepoService"]

T = TypeVar("T", bound=BaseTemplate)
"""A type variable for a templatekit template type."""


class TemplateRepoService:
    """A service for operations with template repositories.

    This service is reponsible letting users select a template.
    """

    def __init__(
        self,
        repo_manager: RepoManager,
        logger: BoundLogger,
        slack_client: SlackWebApiClient,
    ) -> None:
        self._repo_manager = repo_manager
        self._logger = logger
        self._slack_client = slack_client

    async def handle_file_template_selection(
        self,
        user_id: str,
        channel_id: str,
        parent_ts: str | None,
    ) -> None:
        """Handle a file template selection."""
        repo = self._repo_manager.get_repo(gitref="main")

        option_groups = await self._generate_menu_options(
            repo.iter_file_templates
        )
        select_element = SlackStaticSelectElement(
            placeholder=SlackPlainTextObject(text="Select a template"),
            option_groups=option_groups,
            action_id=SELECT_FILE_TEMPLATE_ACTION,
        )
        block = SlackSectionBlock(
            text=SlackMrkdwnTextObject(
                text=(
                    f"<@{user_id}> what type of file or snippet do you want "
                    "to make?"
                )
            ),
            accessory=select_element,
        )
        message = SlackChatPostMessageRequest(
            channel=channel_id,
            text="Select a file template",
            blocks=[block],
            thread_ts=parent_ts,
        )
        await self._slack_client.send_chat_post_message(message)

    async def handle_project_template_selection(
        self,
        user_id: str,
        channel_id: str,
        parent_ts: str | None,
    ) -> None:
        """Handle a project template selection."""
        repo = self._repo_manager.get_repo(gitref="main")

        option_groups = await self._generate_menu_options(
            repo.iter_project_templates
        )
        select_element = SlackStaticSelectElement(
            placeholder=SlackPlainTextObject(text="Select a template"),
            option_groups=option_groups,
            action_id=SELECT_PROJECT_TEMPLATE_ACTION,
        )
        block = SlackSectionBlock(
            text=SlackMrkdwnTextObject(
                text=(
                    f"<@{user_id}> what type of project do you want to make?"
                )
            ),
            accessory=select_element,
        )
        message = SlackChatPostMessageRequest(
            channel=channel_id,
            text="Select a project template",
            blocks=[block],
            thread_ts=parent_ts,
        )
        await self._slack_client.send_chat_post_message(message)

    async def _generate_menu_options(
        self,
        template_iterator: Callable[[], Iterator[T]],
    ) -> list[SlackOptionGroupObject]:
        """Generate a menu of template options."""
        # Group the templates
        grouped_templates: dict[str, list[T]] = {}
        for template in template_iterator():
            group = template.config["group"]
            if group in grouped_templates:
                grouped_templates[group].append(template)
            else:
                grouped_templates[group] = [template]

        # Sort the groups by name label
        group_names = sorted(grouped_templates.keys())
        # Always put 'General' at the beginning
        if "General" in group_names:
            group_names.insert(
                0, group_names.pop(group_names.index("General"))
            )

        # Sort templates by label within each group
        for group in grouped_templates.values():
            group.sort(key=lambda x: x.config["name"])

        # Convert into a list of SlackOptionGroupObject
        option_groups: list[SlackOptionGroupObject] = []
        for group_name in group_names:
            group = grouped_templates[group_name]
            options = []
            for template in group:
                option = SlackOptionObject(
                    text=SlackPlainTextObject(text=template.config["name"]),
                    value=template.name,
                )
                options.append(option)
            option_group = SlackOptionGroupObject(
                label=SlackPlainTextObject(text=group_name),
                options=options,
            )
            option_groups.append(option_group)

        return option_groups
