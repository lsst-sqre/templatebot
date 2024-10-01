"""A service for handling Slack view interactions."""

from __future__ import annotations

from rubin.squarebot.models.kafka import SquarebotSlackViewSubmissionValue
from structlog.stdlib import BoundLogger

from templatebot.constants import TEMPLATE_VARIABLES_MODAL_CALLBACK_ID
from templatebot.storage.repo import RepoManager
from templatebot.storage.slack import SlackWebApiClient
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
    ) -> None:
        self._logger = logger
        self._slack_client = slack_client
        self._repo_manager = repo_manager
        self._template_service = template_service

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
