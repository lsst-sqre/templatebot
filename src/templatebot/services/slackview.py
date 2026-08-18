"""A service for handling Slack view interactions."""

from __future__ import annotations

from httpx import HTTPError
from rubin.squarebot.models.kafka import SquarebotSlackViewSubmissionValue
from safir.slack.blockkit import SlackCodeBlock, SlackMessage, SlackTextField
from safir.slack.webhook import SlackWebhookClient
from structlog.stdlib import BoundLogger

from templatebot.constants import TEMPLATE_VARIABLES_MODAL_CALLBACK_ID
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

        # Extract the variables from the submission. Note that the submission
        # values aren't the same as the template variables because templatekit
        # offers compuound variables like preset_groups and preset_options
        # that effectively set multiple cookiecutter template variables
        # based on a modal value. The Template service is responsible for
        # translating these submission values into template variables.
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
        except Exception as e:
            await self._report_abandoned_creation(
                error=e,
                metadata=private_metadata,
                user_id=payload.user.id,
            )
            raise

    async def _report_abandoned_creation(
        self,
        *,
        error: Exception,
        metadata: TemplateVariablesModalMetadata,
        user_id: str,
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
        await self._report_failure_to_user(error=error, metadata=metadata)

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
        channel = metadata.trigger_channel_id or "unknown"
        return SlackMessage(
            message=(
                f"Abandoned {noun} creation from the "
                f"`{metadata.template_name}` template."
            ),
            fields=[
                SlackTextField(
                    heading="Template", text=metadata.template_name
                ),
                SlackTextField(heading="Type", text=metadata.type),
                SlackTextField(heading="Channel", text=channel),
                SlackTextField(heading="User", text=user_id),
            ],
            blocks=[
                SlackCodeBlock(
                    heading="Exception",
                    code=f"{type(error).__name__}: {error!s}",
                )
            ],
        )

    async def _report_failure_to_user(
        self,
        *,
        error: Exception,
        metadata: TemplateVariablesModalMetadata,
    ) -> None:
        """Tell the user their request was abandoned, without ever raising.

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
        text, blocks = self._format_failure_message(
            error=error, metadata=metadata
        )

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
