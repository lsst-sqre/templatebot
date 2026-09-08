"""A service for handling Slack view interactions."""

from __future__ import annotations

import json

from httpx import HTTPError
from rubin.squarebot.models.kafka import SquarebotSlackViewSubmissionValue
from safir.slack.blockkit import (
    SlackBaseField,
    SlackCodeBlock,
    SlackMessage,
    SlackTextField,
)
from safir.slack.webhook import SlackWebhookClient
from structlog.stdlib import BoundLogger

from templatebot.constants import TEMPLATE_VARIABLES_MODAL_CALLBACK_ID
from templatebot.storage.authordb import (
    AuthorNotFoundError,
    AuthorServiceError,
)
from templatebot.storage.repo import RepoManager
from templatebot.storage.slack import (
    SlackApiError,
    SlackChatPostMessageRequest,
    SlackChatUpdateMessageRequest,
    SlackWebApiClient,
)
from templatebot.storage.slack.blockkit import (
    SlackBlock,
    SlackMrkdwnTextObject,
    SlackSectionBlock,
)
from templatebot.storage.slack.variablesmodal import (
    TemplateVariablesModalMetadata,
)

from .template import TemplateService

AUTHOR_LIST_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1_zXLp7GaIJnzihKsyEAz298_xdbrgxRgZ1_86kwhGPY/edit?pli=1&gid=0#gid=0"
)
"""The author list spreadsheet, where a user can look up their author ID."""

AUTHORDB_EDIT_URL = (
    "https://github.com/lsst/lsst-texmf/edit/main/etc/authordb.yaml"
)
"""GitHub's editor for lsst-texmf's ``etc/authordb.yaml``.

Opening this URL starts a pull request adding an author, which is the only
way a missing author ID gets fixed.
"""


class SlackViewService:
    """A service for handling Slack view interactions."""

    def __init__(
        self,
        logger: BoundLogger,
        slack_client: SlackWebApiClient,
        repo_manager: RepoManager,
        template_service: TemplateService,
        slack_alert_client: SlackWebhookClient | None = None,
    ) -> None:
        self._logger = logger
        self._slack_client = slack_client
        self._repo_manager = repo_manager
        self._template_service = template_service
        self._slack_alert_client = slack_alert_client

    async def handle_view_submission(
        self, payload: SquarebotSlackViewSubmissionValue
    ) -> None:
        """Handle a Slack view submission interaction.

        This is a glue layer that the Kafka consumer can call directly to
        handle view submission events. This service then delegates to the
        appropriate domain-specific service like TemplateService to handle
        the submission. This serivce is also responsible for extracting
        information from the view submission payload so that the domain
        service can focus on the business logic.
        """
        self._logger.debug(
            "Got view submission", payload=payload.model_dump(mode="json")
        )
        if payload.view["callback_id"] == TEMPLATE_VARIABLES_MODAL_CALLBACK_ID:
            await self._handle_template_render(payload)

    async def _handle_template_render(
        self, payload: SquarebotSlackViewSubmissionValue
    ) -> None:
        """Handle the submission of a template variables modal to create
        either a new file or project.

        See `TemplateVariablesModal` for more information on the modal.
        """
        if "private_metadata" not in payload.view:
            self._logger.error(
                "No private metadata in variables modal view submission",
                payload=payload.model_dump(mode="json"),
            )
            return
        private_metadata = TemplateVariablesModalMetadata.model_validate_json(
            payload.view["private_metadata"]
        )
        templates_repo = self._repo_manager.get_repo(private_metadata.git_ref)
        template = templates_repo[private_metadata.template_name]

        modal_values = self._extract_modal_values(payload)

        # This is the seam where a terminal failure becomes visible. It is
        # the outermost place that still knows which Slack message triggered
        # the modal, and it covers both the file and the project path.
        try:
            if private_metadata.type == "file":
                await self._template_service.create_file_from_template(
                    template=template,
                    modal_values=modal_values,
                    trigger_message_ts=private_metadata.trigger_message_ts,
                    trigger_channel_id=private_metadata.trigger_channel_id,
                )
            elif private_metadata.type == "project":
                await self._template_service.create_project_from_template(
                    template=template,
                    modal_values=modal_values,
                    trigger_message_ts=private_metadata.trigger_message_ts,
                    trigger_channel_id=private_metadata.trigger_channel_id,
                )
        except AuthorNotFoundError as e:
            # A typo, or an author who is not in lsst-texmf yet. The
            # submission is just as lost as any other failure, but the fix
            # belongs to the user, so they get instructions instead of an
            # apology and the operator gets a soft alert instead of an
            # incident. Returning normally keeps a user's typo out of
            # FastStream's traceback log; the offset was committed before
            # this handler ran either way.
            await self._report_author_not_found(
                error=e,
                metadata=private_metadata,
                modal_values=modal_values,
                user_id=payload.user.id,
            )
        except AuthorServiceError as e:
            # The author database never answered, so nothing is known about
            # the author ID: sending the user to the author list would waste
            # their time on an ID that is probably fine. The operator side is
            # unchanged, though -- an outage really is an incident -- and the
            # error is re-raised so FastStream logs the traceback.
            await self._report_abandoned_creation(
                error=e,
                metadata=private_metadata,
                user_id=payload.user.id,
                user_message=self._format_author_service_error_message(
                    metadata=private_metadata, modal_values=modal_values
                ),
            )
            raise
        except Exception as e:
            await self._report_abandoned_creation(
                error=e,
                metadata=private_metadata,
                user_id=payload.user.id,
            )
            raise

    def _extract_modal_values(
        self, payload: SquarebotSlackViewSubmissionValue
    ) -> dict[str, str]:
        """Flatten a view submission's block state into a value per action.

        Note that these submission values aren't the same as the template
        variables, because templatekit offers compound variables like
        preset_groups and preset_options that effectively set multiple
        cookiecutter template variables based on one modal value. The
        template service is responsible for translating these submission
        values into template variables.
        """
        modal_values: dict[str, str] = {}
        for block_state in payload.view["state"]["values"].values():
            for action_id, action_state in block_state.items():
                if action_state["type"] == "plain_text_input":
                    modal_values[action_id] = action_state["value"]
                elif action_state["type"] == "static_select":
                    modal_values[action_id] = action_state["selected_option"][
                        "value"
                    ]
                else:
                    self._logger.warning(
                        "Unhandled action type in view submission",
                        action_id=action_id,
                        action_type=action_state["type"],
                        action_state=action_state,
                    )
        return modal_values

    async def _report_author_not_found(
        self,
        *,
        error: AuthorNotFoundError,
        metadata: TemplateVariablesModalMetadata,
        modal_values: dict[str, str],
        user_id: str,
    ) -> None:
        """Tell the user how to fix an author ID the author database does
        not know, and let the operator know it happened.

        This is the only writer of a failure message for this case: the
        template service leaves the exception untouched precisely so that
        one message, written here, wins the trigger message.

        Parameters
        ----------
        error
            The lookup failure, carrying the author ID that was not found.
        metadata
            The modal's private metadata, carrying the template name and the
            Slack message that triggered it.
        modal_values
            The values the user submitted, echoed back so they can be pasted
            into a retry.
        user_id
            The Slack ID of the user whose submission was lost.
        """
        # Warning, not error: nothing is broken, and no operator has to act.
        self._logger.warning(
            "author_id_not_found",
            template=metadata.template_name,
            template_type=metadata.type,
            channel=metadata.trigger_channel_id,
            message_ts=metadata.trigger_message_ts,
            user=user_id,
            author_id=error.author_id,
        )
        if self._slack_alert_client is not None:
            # Safir's webhook client logs and swallows its own failures, so
            # this cannot turn into a second error on the failure path and
            # needs no guard of its own.
            await self._slack_alert_client.post(
                self._format_author_not_found_alert(
                    error=error, metadata=metadata, user_id=user_id
                )
            )
        text, blocks = self._format_author_not_found_message(
            error=error, metadata=metadata, modal_values=modal_values
        )
        await self._report_to_user(text=text, blocks=blocks, metadata=metadata)

    def _format_author_not_found_alert(
        self,
        *,
        error: AuthorNotFoundError,
        metadata: TemplateVariablesModalMetadata,
        user_id: str,
    ) -> SlackMessage:
        """Compose the soft operator alert for an author ID that was not
        found.

        Unlike `_format_operator_alert` this carries no exception block: the
        lookup worked and gave a definite answer, so there is no failure for
        an operator to investigate. The alert exists only so the team can
        notice a pattern -- an author who keeps being asked for and is still
        missing from lsst-texmf.
        """
        noun = "file" if metadata.type == "file" else "project"
        channel = metadata.trigger_channel_id or "unknown"
        return SlackMessage(
            message=(
                f"Templatebot could not find author ID `{error.author_id}` "
                f"for a `{metadata.template_name}` {noun} requested by "
                f"{user_id} in {channel}. The user was told how to find or "
                "add the author ID."
            ),
            fields=self._alert_fields(metadata=metadata, user_id=user_id),
        )

    def _format_author_not_found_message(
        self,
        *,
        error: AuthorNotFoundError,
        metadata: TemplateVariablesModalMetadata,
        modal_values: dict[str, str],
    ) -> tuple[str, list[SlackBlock]]:
        """Compose the Slack message that tells the user how to fix an
        unknown author ID.

        The submitted values are dumped for the user to paste into a retry,
        the same as on every other failure path through this seam.
        """
        noun = "file" if metadata.type == "file" else "project"
        text = (
            f"I couldn't find information for author ID `{error.author_id}`."
        )
        guidance = (
            f"{text}\n\n"
            f"Check <{AUTHOR_LIST_URL}|the author list> for the correct "
            f"author ID, or <{AUTHORDB_EDIT_URL}|open a pull request for "
            "`etc/authordb.yaml` in lsst/lsst-texmf> to add a new author."
            f"\n\nNo {noun} was created. Here are the values you submitted, "
            "so you can paste them back in when you try again:"
        )
        return text, [
            SlackSectionBlock(text=SlackMrkdwnTextObject(text=guidance)),
            self._submitted_values_block(modal_values),
        ]

    def _submitted_values_block(
        self, modal_values: dict[str, str]
    ) -> SlackBlock:
        """Dump the values a user submitted into a fenced code block.

        These are the raw modal values -- what the user actually typed --
        rather than the expanded cookiecutter variables, so the block pastes
        straight back into a second attempt.
        """
        values = "```\n" + json.dumps(modal_values, indent=2) + "\n```"
        return SlackSectionBlock(text=SlackMrkdwnTextObject(text=values))

    async def _report_abandoned_creation(
        self,
        *,
        error: Exception,
        metadata: TemplateVariablesModalMetadata,
        user_id: str,
        user_message: tuple[str, list[SlackBlock]] | None = None,
    ) -> None:
        """Record and report a creation attempt that was abandoned partway.

        Nothing here re-runs the work: `create_project_from_template` is not
        idempotent, so the only useful responses to a terminal failure are to
        tell the user their request is gone and to leave the operator a
        searchable marker.

        Parameters
        ----------
        error
            The exception that ended the creation attempt. It is reported by
            type rather than by message, since its text is not written for
            the user.
        metadata
            The modal's private metadata, carrying the template name and the
            Slack message that triggered it.
        user_id
            The Slack ID of the user whose submission was lost.
        user_message
            The text and blocks to show the user, for a failure that has a
            more useful account than "something went wrong". Defaults to the
            generic abandoned-creation message. The operator side of the
            report is the same either way.
        """
        # The traceback is deliberately left to the re-raise in the caller,
        # which FastStream logs; this event is the searchable marker that
        # names the request that was lost.
        self._logger.error(
            "project_creation_abandoned",
            template=metadata.template_name,
            template_type=metadata.type,
            channel=metadata.trigger_channel_id,
            message_ts=metadata.trigger_message_ts,
            user=user_id,
            error=str(error),
            error_type=type(error).__name__,
        )
        if self._slack_alert_client is not None:
            # Safir's webhook client logs and swallows its own failures, so
            # this cannot turn into a second error on the failure path and
            # needs no guard of its own.
            await self._slack_alert_client.post(
                self._format_operator_alert(
                    error=error, metadata=metadata, user_id=user_id
                )
            )
        text, blocks = user_message or self._format_failure_message(
            error=error, metadata=metadata
        )
        await self._report_to_user(text=text, blocks=blocks, metadata=metadata)

    def _format_author_service_error_message(
        self,
        *,
        metadata: TemplateVariablesModalMetadata,
        modal_values: dict[str, str],
    ) -> tuple[str, list[SlackBlock]]:
        """Compose the Slack message for an author database that could not
        be reached.

        The lookup never got an answer, so this message says nothing about
        the author ID that was submitted: it is probably fine, and it is not
        the user's to fix either way. What the message does say is that the
        request is gone and worth retrying later, and it hands the submitted
        values back so that retry is a paste rather than a retype.
        """
        noun = "file" if metadata.type == "file" else "project"
        text = "I couldn't reach the author database."
        detail = (
            f"{text}\n\nNo {noun} was created, and your submission wasn't "
            "saved, so please try again later. If it keeps happening, report "
            "it in #dm-square.\n\nHere are the values you submitted, so you "
            "can paste them back in when you try again:"
        )
        return text, [
            SlackSectionBlock(text=SlackMrkdwnTextObject(text=detail)),
            self._submitted_values_block(modal_values),
        ]

    def _format_operator_alert(
        self,
        *,
        error: Exception,
        metadata: TemplateVariablesModalMetadata,
        user_id: str,
    ) -> SlackMessage:
        """Compose the operator alert for an abandoned creation.

        The alert names the request precisely enough to recreate it by hand:
        which template, in which channel, for which user. The exception is
        reported by type and message, matching the marker log; the traceback
        stays in the application logs, where it cannot leak into a Slack
        channel.
        """
        noun = "file" if metadata.type == "file" else "project"
        return SlackMessage(
            message=(
                f"Abandoned {noun} creation from the "
                f"`{metadata.template_name}` template."
            ),
            fields=self._alert_fields(metadata=metadata, user_id=user_id),
            blocks=[
                SlackCodeBlock(
                    heading="Exception",
                    code=f"{type(error).__name__}: {error!s}",
                )
            ],
        )

    def _alert_fields(
        self,
        *,
        metadata: TemplateVariablesModalMetadata,
        user_id: str,
    ) -> list[SlackBaseField]:
        """Name the request an operator alert is about.

        Every operator alert from this seam identifies the submission the
        same way, whatever went wrong with it, so the status channel stays
        skimmable.
        """
        return [
            SlackTextField(heading="Template", text=metadata.template_name),
            SlackTextField(heading="Type", text=metadata.type),
            SlackTextField(
                heading="Channel",
                text=metadata.trigger_channel_id or "unknown",
            ),
            SlackTextField(heading="User", text=user_id),
        ]

    async def _report_to_user(
        self,
        *,
        text: str,
        blocks: list[SlackBlock],
        metadata: TemplateVariablesModalMetadata,
    ) -> None:
        """Deliver a failure report to the user, without ever raising.

        Every failure path through this seam writes the trigger message
        through here, exactly once, so the user is never shown two competing
        accounts of what happened.

        The trigger message is updated in place when there is one. If that
        ``chat.update`` fails even after the client's retries — the exact
        failure mode that made this reporting necessary in the first place —
        the report is posted as a new message in the same channel instead.
        Both Slack failures are logged and swallowed so that the caller
        re-raises the original error rather than this one.
        """
        channel_id = metadata.trigger_channel_id
        if channel_id is None:
            # Nowhere to report: the modal was opened without a trigger
            # message, so the marker log is all the operator gets.
            return

        if metadata.trigger_message_ts is not None:
            try:
                await self._slack_client.update_message(
                    message_update_request=SlackChatUpdateMessageRequest(
                        channel=channel_id,
                        ts=metadata.trigger_message_ts,
                        text=text,
                        blocks=blocks,
                    )
                )
            except (HTTPError, SlackApiError) as e:
                self._logger.warning(
                    "slack_failure_report_update_failed",
                    slack_method="chat.update",
                    channel=channel_id,
                    message_ts=metadata.trigger_message_ts,
                    error=str(e),
                    error_type=type(e).__name__,
                )
            else:
                return

        try:
            await self._slack_client.send_chat_post_message(
                message_request=SlackChatPostMessageRequest(
                    channel=channel_id,
                    text=text,
                    blocks=blocks,
                )
            )
        except (HTTPError, SlackApiError) as e:
            self._logger.warning(
                "slack_failure_report_failed",
                slack_method="chat.postMessage",
                channel=channel_id,
                error=str(e),
                error_type=type(e).__name__,
            )

    def _format_failure_message(
        self,
        *,
        error: Exception,
        metadata: TemplateVariablesModalMetadata,
    ) -> tuple[str, list[SlackBlock]]:
        """Compose the Slack message reporting an abandoned creation."""
        noun = "file" if metadata.type == "file" else "project"
        text = (
            f"Sorry, something went wrong creating your {noun} from the "
            f"`{metadata.template_name}` template."
        )
        detail = (
            f"{text}\n\nThe error was `{type(error).__name__}`. Nothing was "
            "created, and your submission wasn't saved, so please try again. "
            "If it keeps happening, report it in #dm-square."
        )
        blocks: list[SlackBlock] = [
            SlackSectionBlock(text=SlackMrkdwnTextObject(text=detail))
        ]
        return text, blocks
