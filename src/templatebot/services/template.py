"""Template service."""

from __future__ import annotations

import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from cookiecutter.main import cookiecutter
from httpx import AsyncClient, HTTPError
from pydantic import ValidationError
from structlog.stdlib import BoundLogger
from templatekit.repo import BaseTemplate, FileTemplate, ProjectTemplate

from templatebot.storage.authordb import AuthorDb
from templatebot.storage.gitclone import GitClone
from templatebot.storage.githubappclientfactory import GitHubAppClientFactory
from templatebot.storage.githubrepo import GitHubRepo
from templatebot.storage.ltdclient import LtdClient
from templatebot.storage.slack import (
    SlackChatUpdateMessageRequest,
    SlackWebApiClient,
)
from templatebot.storage.slack.blockkit import (
    SlackBlock,
    SlackMrkdwnTextObject,
    SlackSectionBlock,
)
from templatebot.storage.slack.variablesmodal import TemplateVariablesModal

__all__ = ["TemplateService"]


class TemplateService:
    """A service for operating with templates.

    Features include:

    - Having a user configure a template through a Slack modal view
    - Rendering a template with user-provided values and running the
      configuration of that repository and LSST the Docs services.
    """

    def __init__(
        self,
        *,
        logger: BoundLogger,
        http_client: AsyncClient,
        slack_client: SlackWebApiClient,
        github_client_factory: GitHubAppClientFactory,
        ltd_client: LtdClient,
    ) -> None:
        self._logger = logger
        self._http_client = http_client
        self._slack_client = slack_client
        self._github_client_factory = github_client_factory
        self._ltd_client = ltd_client

    async def show_file_template_modal(
        self,
        *,
        user_id: str,
        trigger_id: str,
        message_ts: str,
        channel_id: str,
        template: FileTemplate,
        git_ref: str,
        repo_url: str,
    ) -> None:
        """Show a modal for selecting a file template."""
        if len(template.config["dialog_fields"]) == 0:
            await self._respond_with_nonconfigurable_content(
                template=template,
                channel_id=channel_id,
                trigger_message_ts=message_ts,
            )
        else:
            await self._open_template_modal(
                template=template,
                trigger_id=trigger_id,
                git_ref=git_ref,
                repo_url=repo_url,
                trigger_message_ts=message_ts,
                trigger_channel_id=channel_id,
            )

    async def show_project_template_modal(
        self,
        *,
        user_id: str,
        trigger_id: str,
        message_ts: str,
        channel_id: str,
        template: ProjectTemplate,
        git_ref: str,
        repo_url: str,
    ) -> None:
        """Show a modal for selecting a project template."""
        await self._open_template_modal(
            template=template,
            trigger_id=trigger_id,
            git_ref=git_ref,
            repo_url=repo_url,
            trigger_message_ts=message_ts,
            trigger_channel_id=channel_id,
        )

    async def _open_template_modal(
        self,
        *,
        template: FileTemplate | ProjectTemplate,
        trigger_id: str,
        git_ref: str,
        repo_url: str,
        trigger_message_ts: str | None = None,
        trigger_channel_id: str | None = None,
    ) -> None:
        """Open a modal for configuring a template."""
        modal_view = TemplateVariablesModal.create(
            template=template,
            git_ref=git_ref,
            repo_url=repo_url,
            trigger_message_ts=trigger_message_ts,
            trigger_channel_id=trigger_channel_id,
        )
        await self._slack_client.open_view(
            trigger_id=trigger_id, view=modal_view
        )

    async def _respond_with_nonconfigurable_content(
        self,
        *,
        template: FileTemplate,
        channel_id: str,
        trigger_message_ts: str,
    ) -> None:
        """Respond with non-configurable content."""
        # TODO(jonathansick): render the template and send it back to the user
        await self._slack_client.update_message(
            message_update_request=SlackChatUpdateMessageRequest(
                channel=channel_id,
                ts=trigger_message_ts,
                text=(
                    f"The {template.name} template does not require "
                    "configuration."
                ),
            )
        )

    async def create_project_from_template(  # noqa: PLR0912 PLR0915 C901
        self,
        *,
        template: ProjectTemplate,
        modal_values: dict[str, str],
        trigger_message_ts: str | None,
        trigger_channel_id: str | None,
    ) -> None:
        """Create a GitHub repository and set up a project from a template."""
        if trigger_channel_id and trigger_message_ts:
            await self._slack_client.update_message(
                message_update_request=SlackChatUpdateMessageRequest(
                    channel=trigger_channel_id,
                    ts=trigger_message_ts,
                    text="I'm creating your new project...",
                )
            )

        # Values for the repository creation. We'll set this when possible
        # during the pre-processing steps.
        github_owner: str | None = None
        github_name: str | None = None
        github_homepage_url: str | None = None
        github_description: str | None = None

        # Preprocessing steps. First convert values from the Slack modal into
        # cookiecutter template variables. This expands the templatekit
        # preset_groups and preset_options into the full set of template
        # variables.
        template_values = self._transform_modal_values(
            template=template, modal_values=modal_values
        )

        # Expand the author_id variable into full author information, if
        # present.
        try:
            await self._expand_author_id_variable(template_values)
        except (HTTPError, ValidationError):
            error_message = (
                "I couldn't find information for "
                f"author ID `{template_values.get('author_id')}`.\n\n"
                "Check <https://docs.google.com/spreadsheets/d/"
                "1_zXLp7GaIJnzihKsyEAz298_xdbrgxRgZ1_86kwhGPY/"
                "edit?pli=1&gid=0#gid=0|the author list> for the correct "
                "author ID, or <https://github.com/lsst/lsst-texmf/"
                "edit/main/etc/authordb.yaml|create a pull request to "
                "https://github.com/lsst/lsst-texmf for `etc/authordb.yaml`>."
            )

            if trigger_channel_id and trigger_message_ts:
                await self._slack_client.update_message(
                    message_update_request=SlackChatUpdateMessageRequest(
                        channel=trigger_channel_id,
                        ts=trigger_message_ts,
                        text=(
                            "There was an error retrieving author information."
                        ),
                        blocks=[
                            SlackSectionBlock(
                                type="section",
                                fields=None,
                                accessory=None,
                                text=SlackMrkdwnTextObject(
                                    type="mrkdwn",
                                    verbatim=False,
                                    text=error_message,
                                ),
                            ),
                            SlackSectionBlock(
                                type="section",
                                fields=None,
                                accessory=None,
                                text=SlackMrkdwnTextObject(
                                    type="mrkdwn",
                                    verbatim=False,
                                    text=(
                                        "Here's your submitted template "
                                        "values for reference:\n\n"
                                        "```\n"
                                        + json.dumps(template_values, indent=2)
                                        + "\n```"
                                    ),
                                ),
                            ),
                        ],
                    )
                )
            raise

        # Variables for LSST the Docs registration
        ltd_slug: str | None = None
        ltd_title: str | None = None
        github_repo_url: str | None = None

        if template.name.startswith("technote_"):
            # Handle preprocessing steps for technotes. These have
            # automatically assigned repository/serial numbers
            await self._assign_technote_repo_serial(template_values)
            github_owner = template_values["github_org"]
            github_name = (
                f"{template_values['series'].lower()}"
                f"-{template_values['serial_number']}"
            )
            github_homepage_url = f"https://{github_name}.lsst.io/"
            github_description = template_values["title"]

            ltd_slug = github_name
            ltd_title = template_values["title"]

        elif template.name == "latex_lsstdoc":
            # Preprocessing steps for change control documents hosted in
            # docushare. These have manually-assigned serial numbers.
            #
            # In the latex_lsstdoc template, the series and serial_number are
            # determined from the handle, which the author enters.
            # This logic attempts to match this metadata
            # and extract it, if necessary and possible.
            handle = template_values["handle"]
            handle_match = re.match(
                r"(?P<series>[A-Z]+)-(?P<serial_number>[0-9]+)", handle
            )
            if handle_match is None:
                # If the handle does not match the expected pattern, then
                # we cannot determine the series and serial number.
                # TODO(jonathansick): send a Slack message to the user
                raise ValueError(
                    f"Cannot determine series and serial number from handle: "
                    f"{handle}"
                )
            # TODO(jonathansick): Verify the document handle is not for a
            # technote or for a document that already exists.
            template_values["series"] = handle_match["series"]
            template_values["serial_number"] = handle_match["serial_number"]
            github_owner = template_values["github_org"]
            github_name = handle.lower()
            github_homepage_url = f"https://{github_name}.lsst.io/"
            github_description = template_values["title"]

            ltd_slug = github_name
            ltd_title = template_values["title"]

        elif template.name == "test_report":
            # In test_report templates the series and serial_number are
            # manually assigned.
            github_name = (
                f"{template_values['series'].lower()}-"
                f"{template_values['serial_number']}"
            )
            github_owner = template_values["github_org"]
            github_homepage_url = f"https://{github_name}.lsst.io/"
            github_description = template_values["title"]

            ltd_slug = github_name
            ltd_title = template_values["title"]

        elif template.name == "stack_package":
            github_name = template_values["package_name"]
            github_owner = template_values["github_org"]
            github_description = "A package in the LSST Science Pipelines."

        else:
            # A generic repository template. By definition the "name"
            # is treated as teh github repo name, and the "github_org"
            # is the owner.
            github_name = template_values["name"]
            github_owner = template_values["github_org"]
            if "summary" in template_values:
                github_description = template_values["summary"]
            elif "description" in template_values:
                github_description = template_values["description"]

        # Create the repository on GitHub
        f = self._github_client_factory
        github_client = await f.create_installation_client_for_org(
            github_owner
        )
        github_repo = GitHubRepo(
            owner=github_owner,
            name=github_name,
            github_client=github_client,
            logger=self._logger,
        )
        github_repo_info = await github_repo.create_repo(
            homepage=github_homepage_url,
            description=github_description,
        )
        github_repo_url = github_repo_info["html_url"]

        if (
            ltd_slug is not None
            and ltd_title is not None
            and github_repo_url is not None
        ):
            ltd_info = await self._ltd_client.register_ltd_product(
                slug=ltd_slug,
                title=ltd_title,
                github_repo=github_repo_url,
                main_mode="lsst_doc"
                if template.name in ("latex_lsstdoc", "test_report")
                else "git_refs",
            )
            self._logger.info(
                "Registered project on LSST the Docs", ltd_info=ltd_info
            )

        if github_repo_url is None:
            raise RuntimeError("No GitHub repository URL was created.")

        # Render the template
        with TemporaryDirectory() as tmp_dir:
            project_dir = self._render_template(
                template=template,
                template_values=template_values,
                tmp_dir=Path(tmp_dir),
            )
            git_repo = GitClone.init_repo(
                path=project_dir, github_client=github_client
            )
            git_repo.commit("Initial commit")
            git_repo.push(remote_url=github_repo_url, branch="main")

        # Update the Slack message with the rendered project details
        reply_blocks: list[SlackBlock] = []
        reply_blocks.append(
            SlackSectionBlock(
                text=SlackMrkdwnTextObject(text="Your new project is ready!")
            )
        )
        if ltd_slug is not None:
            reply_blocks.append(
                SlackSectionBlock(
                    fields=[
                        SlackMrkdwnTextObject(text="*Web page:*"),
                        SlackMrkdwnTextObject(text="*Repository:*"),
                        SlackMrkdwnTextObject(
                            text=github_homepage_url or "Unavailable"
                        ),
                        SlackMrkdwnTextObject(
                            text=github_repo_url or "Unavailable"
                        ),
                    ]
                )
            )
            reply_blocks.append(
                SlackSectionBlock(
                    text=SlackMrkdwnTextObject(
                        text=(
                            "_The homepage link may return a 404 error "
                            "until the site has been built._"
                        )
                    )
                )
            )
            if template.name in ("technote_rst", "technote_md"):
                reply_blocks.append(
                    SlackSectionBlock(
                        text=SlackMrkdwnTextObject(
                            text=(
                                "To learn how to write a Rubin technote "
                                "visit "
                                "https://documenteer.lsst.io/technotes/"
                            )
                        ),
                    )
                )
        else:
            reply_blocks.append(
                SlackSectionBlock(
                    fields=[
                        SlackMrkdwnTextObject(text="*Repository:*"),
                        SlackMrkdwnTextObject(
                            text=github_repo_url or "Unavailable"
                        ),
                    ]
                )
            )

        if trigger_channel_id and trigger_message_ts:
            await self._slack_client.update_message(
                message_update_request=SlackChatUpdateMessageRequest(
                    channel=trigger_channel_id,
                    ts=trigger_message_ts,
                    text="Your new project is ready!",
                    blocks=reply_blocks,
                )
            )

    async def create_file_from_template(
        self,
        *,
        template: FileTemplate,
        modal_values: dict[str, str],
        trigger_message_ts: str | None,
        trigger_channel_id: str | None,
    ) -> None:
        """Create a file from a template."""
        # TODO(jonathansick): implement this
        if trigger_channel_id and trigger_message_ts:
            await self._slack_client.update_message(
                message_update_request=SlackChatUpdateMessageRequest(
                    channel=trigger_channel_id,
                    ts=trigger_message_ts,
                    text=(
                        f"Creating a file from the {template.name} template."
                    ),
                )
            )

    def _transform_modal_values(  # noqa: C901
        self, *, template: BaseTemplate, modal_values: dict[str, str]
    ) -> dict[str, str]:
        """Transform modal values into template variables."""
        # TODO(jonathansick): Relocate this into either TemplateVariablesModal
        # (if we parse submissions back into with a subclass providing state)
        # or into the Template class.

        # Drop any null fields so that we get the defaults from cookiecutter.
        data = {k: v for k, v in modal_values.items() if v is not None}

        for field in template.config["dialog_fields"]:
            if "preset_groups" in field:
                # Handle as a preset_groups select menu
                selected_label = data[field["label"]]
                for option_group in field["preset_groups"]:
                    for option in option_group["options"]:
                        if option["label"] == selected_label:
                            data.update(dict(option["presets"].items()))
                del data[field["label"]]

            elif "preset_options" in field:
                # Handle as a preset select menu
                selected_value = data[field["label"]]
                for option in field["preset_options"]:
                    if option["value"] == selected_value:
                        data.update(dict(option["presets"].items()))
                del data[field["label"]]

            elif field["component"] == "select":
                # Handle as a regular select menu
                try:
                    selected_value = data[field["key"]]
                except KeyError:
                    # If field not in data, then it was not set, use defaults
                    continue

                # Replace any truncated values from select fields
                # with full values
                for option in field["options"]:
                    if option["value"] == selected_value:
                        data[field["key"]] = option["template_value"]
                        continue

        return data

    async def _expand_author_id_variable(
        self, template_values: dict[str, str]
    ) -> None:
        """Expand the author_id variable into full author information
        from lsst-texmf's authordb.yaml.
        """
        author_id = template_values.get("author_id")
        if not author_id:
            return

        authordb = AuthorDb(self._http_client)
        # TODO(jonathansick): handle missing author_id with Slack message
        author_info = await authordb.get_author(author_id)

        template_values["first_author_given"] = (
            author_info.given_name if author_info.given_name else ""
        )
        template_values["first_author_family"] = author_info.family_name
        template_values["first_author_orcid"] = (
            str(author_info.orcid) if author_info.orcid else ""
        )
        template_values["first_author_affil_name"] = (
            author_info.affiliations[0].name
            if author_info.affiliations
            else ""
        )
        template_values["first_author_affil_internal_id"] = (
            author_info.affiliations[0].internal_id
            if author_info.affiliations
            else ""
        )
        template_values["first_author_affil_address"] = (
            author_info.affiliations[0].address.city
            if author_info.affiliations
            and author_info.affiliations[0].address
            and author_info.affiliations[0].address.city
            else ""
        )

    async def _assign_technote_repo_serial(
        self, template_values: dict[str, str]
    ) -> None:
        """Assign a repository serial number for a technote and update the
        template values.

        The following standard technote template values are updated:

        - ``serial_number``
        """
        org_name = template_values["github_org"]
        series = template_values["series"].lower()

        series_pattern = re.compile(r"^" + series + r"-(?P<number>\d+)$")

        # Get repository names from GitHub for this org
        f = self._github_client_factory
        ghclient = await f.create_installation_client_for_org(org_name)
        repo_iter = ghclient.getiter(
            "/orgs{/org}/repos", url_vars={"org": org_name}
        )
        series_numbers = []
        async for repo_info in repo_iter:
            name = repo_info["name"].lower()
            m = series_pattern.match(name)
            if m is None:
                continue
            series_numbers.append(int(m.group("number")))

        self._logger.debug(
            "Collected existing numbers for series, series_numbers",
            series=series,
            series_numbers=series_numbers,
        )

        new_number = self._propose_number([int(n) for n in series_numbers])
        serial_number = f"{new_number:03d}"
        repo_name = f"{series.lower()}-{serial_number}"

        self._logger.info(
            "Selected new technote repo name", name=repo_name, org=org_name
        )

        # Update the template values. This relies on all technotes having
        # the same variables structure.
        template_values["serial_number"] = serial_number

    def _propose_number(self, series_numbers: list[int]) -> int:
        """Propose a technote number given the list of available document
        numbers.

        This algorithm starts from 1, increments numbers by 1, and will fill in
        any gaps in the numbering scheme.
        """
        series_numbers.sort()

        n_documents = len(series_numbers)

        if n_documents == 0:
            return 1

        for i in range(n_documents):
            serial_number = series_numbers[i]

            if i == 0 and serial_number > 1:
                return 1

            if i + 1 == n_documents:
                # it might be the next-highest number
                return series_numbers[i] + 1

            # check if the next number is missing
            if series_numbers[i + 1] != serial_number + 1:
                return serial_number + 1

        raise RuntimeError("propose_number should not be in this state.")

    def _render_template(
        self,
        *,
        template: ProjectTemplate,
        template_values: dict[str, Any],
        tmp_dir: Path,
    ) -> Path:
        """Render a project template to a local directory.

        Returns
        -------
        pathlib.Path
            Path to the rendered project itself, which is a subdirectory of
            tmp_dir.
        """
        cookiecutter(
            str(template.path),
            output_dir=str(tmp_dir),
            overwrite_if_exists=True,
            no_input=True,
            extra_context=template_values,
        )
        self._logger.debug("Rendered cookiecutter project")

        # Find the rendered directory. The actual name is templated so its
        # easier to just find it.
        subdirs = [x for x in tmp_dir.iterdir() if x.is_dir()]
        if len(subdirs) > 1:
            self._logger.warning(
                "Found an unexpected number of possible repo dirs",
                dirs=subdirs,
            )
        return subdirs[0]
