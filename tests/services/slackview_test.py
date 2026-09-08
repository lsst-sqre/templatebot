"""Tests for the Slack view submission service."""

from __future__ import annotations

from typing import Any, Literal, cast

import httpx
import pytest
import respx
import structlog
from pydantic import HttpUrl, SecretStr
from rubin.squarebot.models.kafka import SquarebotSlackViewSubmissionValue
from rubin.squarebot.models.slack import SlackTeam, SlackUser
from safir.slack.webhook import SlackWebhookClient
from structlog.testing import capture_logs
from templatekit.repo import BaseTemplate, FileTemplate, ProjectTemplate

from templatebot.constants import TEMPLATE_VARIABLES_MODAL_CALLBACK_ID
from templatebot.services.slackview import SlackViewService
from templatebot.services.template import TemplateService
from templatebot.storage.authordb import AuthorServiceError
from templatebot.storage.repo import RepoManager
from templatebot.storage.slack import SlackWebApiClient
from templatebot.storage.slack.variablesmodal import (
    TemplateVariablesModalMetadata,
)
from tests.services.template_test import (
    CHANNEL_ID,
    CHAT_UPDATE_URL,
    MESSAGE_TS,
    OK,
    TEMPLATES_DIR,
    FakeGitHubClient,
    make_service,
)

CHAT_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"
ALERT_WEBHOOK_URL = "https://hooks.slack.com/services/T000/B000/testing"
AUTHOR_LOOKUP_URL = "https://roundtable.lsst.cloud/ook/authors/nobody"

TEAM_ID = "T12345678"
USER_ID = "U87654321"

TECHNOTE_MODAL_VALUES = {
    "title": "A test technote",
    "description": "Testing the failure path.",
    "Series": "test",
}

AUTHOR_MODAL_VALUES = TECHNOTE_MODAL_VALUES | {"author_id": "nobody"}


class FakeRepoManager:
    """Serve a single template by name without cloning anything."""

    def __init__(self, template: BaseTemplate) -> None:
        self._template = template

    def get_repo(self, gitref: str) -> dict[str, BaseTemplate]:
        return {self._template.name: self._template}


def make_metadata(
    *,
    template_name: str,
    template_type: Literal["file", "project"],
    trigger_channel_id: str | None = CHANNEL_ID,
    trigger_message_ts: str | None = MESSAGE_TS,
) -> TemplateVariablesModalMetadata:
    """Build the private metadata Slack round-trips through the modal."""
    return TemplateVariablesModalMetadata(
        type=template_type,
        template_name=template_name,
        git_ref="main",
        repo_url=HttpUrl("https://github.com/lsst/templates"),
        trigger_message_ts=trigger_message_ts,
        trigger_channel_id=trigger_channel_id,
    )


def make_payload(
    *,
    metadata: TemplateVariablesModalMetadata,
    modal_values: dict[str, str],
) -> SquarebotSlackViewSubmissionValue:
    """Build a view submission payload carrying the given modal values."""
    return SquarebotSlackViewSubmissionValue(
        type="view_submission",
        team=SlackTeam(id=TEAM_ID, domain="example"),
        user=SlackUser(id=USER_ID, username="someone", team_id=TEAM_ID),
        api_app_id="A12345678",
        view={
            "callback_id": TEMPLATE_VARIABLES_MODAL_CALLBACK_ID,
            "private_metadata": metadata.model_dump_json(),
            "state": {
                "values": {
                    key: {key: {"type": "plain_text_input", "value": value}}
                    for key, value in modal_values.items()
                }
            },
        },
        slack_interaction="{}",
    )


async def submit_view(
    *,
    template: BaseTemplate,
    github_client: FakeGitHubClient,
    metadata: TemplateVariablesModalMetadata,
    modal_values: dict[str, str],
    alert_webhook: str | None = None,
) -> None:
    """Drive ``handle_view_submission`` against the fakes."""
    logger = structlog.get_logger("templatebot")
    alert_client = (
        SlackWebhookClient(
            hook_url=alert_webhook,
            application="templatebot",
            logger=logger,
        )
        if alert_webhook is not None
        else None
    )
    async with httpx.AsyncClient() as http_client:
        service = SlackViewService(
            logger=logger,
            slack_client=SlackWebApiClient(
                http_client=http_client,
                token=SecretStr("xoxb-testing-123"),
                logger=logger,
            ),
            repo_manager=cast("RepoManager", FakeRepoManager(template)),
            template_service=make_service(
                http_client, github_client=github_client
            ),
            slack_alert_client=alert_client,
        )
        await service.handle_view_submission(
            make_payload(metadata=metadata, modal_values=modal_values)
        )


async def submit_failing_technote(
    github_client: FakeGitHubClient,
    *,
    trigger_channel_id: str | None = CHANNEL_ID,
    trigger_message_ts: str | None = MESSAGE_TS,
    alert_webhook: str | None = None,
) -> None:
    """Submit a technote modal whose serial assignment is doomed to fail."""
    await submit_view(
        template=ProjectTemplate(
            str(TEMPLATES_DIR / "project_templates" / "technote_rst")
        ),
        github_client=github_client,
        metadata=make_metadata(
            template_name="technote_rst",
            template_type="project",
            trigger_channel_id=trigger_channel_id,
            trigger_message_ts=trigger_message_ts,
        ),
        modal_values=dict(TECHNOTE_MODAL_VALUES),
        alert_webhook=alert_webhook,
    )


async def submit_author_lookup_technote(
    *,
    trigger_channel_id: str | None = CHANNEL_ID,
    trigger_message_ts: str | None = MESSAGE_TS,
    alert_webhook: str | None = None,
) -> None:
    """Submit a technote modal naming an author ID.

    How the lookup of that ID turns out is the caller's to decide with a
    respx route on `AUTHOR_LOOKUP_URL`.
    """
    await submit_view(
        template=ProjectTemplate(
            str(TEMPLATES_DIR / "project_templates" / "technote_rst")
        ),
        github_client=FakeGitHubClient(),
        metadata=make_metadata(
            template_name="technote_rst",
            template_type="project",
            trigger_channel_id=trigger_channel_id,
            trigger_message_ts=trigger_message_ts,
        ),
        modal_values=dict(AUTHOR_MODAL_VALUES),
        alert_webhook=alert_webhook,
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_unknown_author_id_is_answered_with_guidance(
    respx_mock: respx.MockRouter,
) -> None:
    """A mistyped author ID is the user's to fix, so the seam replaces the
    trigger message with instructions -- exactly once, and without the
    generic apology -- and lets the submission end quietly.
    """
    respx_mock.get(AUTHOR_LOOKUP_URL).mock(return_value=httpx.Response(404))
    route = respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    await submit_author_lookup_technote()

    # The opening status update, then the guidance -- and nothing after it.
    assert route.call_count == 2
    report = route.calls[-1].request.content.decode()
    assert "nobody" in report
    # The author list spreadsheet and the lsst-texmf pull request.
    assert "1_zXLp7GaIJnzihKsyEAz298_xdbrgxRgZ1_86kwhGPY" in report
    assert "lsst/lsst-texmf" in report
    assert "authordb.yaml" in report
    # The submitted modal values, dumped for the user to paste into a retry.
    assert "A test technote" in report
    assert "Sorry, something went wrong" not in report


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_unknown_author_id_alerts_the_operator_softly(
    respx_mock: respx.MockRouter,
) -> None:
    """The operator alert names the author ID without dressing a user's typo
    up as an incident: no exception block, no abandoned-creation wording.
    """
    respx_mock.get(AUTHOR_LOOKUP_URL).mock(return_value=httpx.Response(404))
    respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )
    alert_route = respx_mock.post(ALERT_WEBHOOK_URL).mock(
        return_value=httpx.Response(200, text="ok")
    )

    await submit_author_lookup_technote(alert_webhook=ALERT_WEBHOOK_URL)

    assert alert_route.call_count == 1
    alert = alert_route.calls[-1].request.content.decode()
    assert "could not find author ID" in alert
    assert "nobody" in alert
    assert "technote_rst" in alert
    assert CHANNEL_ID in alert
    assert USER_ID in alert
    assert "Exception" not in alert
    assert "Abandoned" not in alert


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_unknown_author_id_logs_a_warning_not_an_incident(
    respx_mock: respx.MockRouter,
) -> None:
    """The marker log for a missing author ID is its own warning-level event,
    so an operator scanning for abandoned creations never trips over one.
    """
    respx_mock.get(AUTHOR_LOOKUP_URL).mock(return_value=httpx.Response(404))
    respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    with capture_logs() as logs:
        await submit_author_lookup_technote()

    markers = [
        entry for entry in logs if entry["event"] == "author_id_not_found"
    ]
    assert len(markers) == 1
    assert markers[0]["log_level"] == "warning"
    assert markers[0]["author_id"] == "nobody"
    assert markers[0]["template"] == "technote_rst"
    assert markers[0]["template_type"] == "project"
    assert markers[0]["channel"] == CHANNEL_ID
    assert markers[0]["message_ts"] == MESSAGE_TS
    assert markers[0]["user"] == USER_ID
    assert not [
        entry
        for entry in logs
        if entry["event"] == "project_creation_abandoned"
    ]


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_author_guidance_falls_back_to_a_new_message(
    respx_mock: respx.MockRouter,
) -> None:
    """Guidance the user cannot see is no guidance, so a ``chat.update``
    that fails every retry falls back to a new message in the channel.
    """
    respx_mock.get(AUTHOR_LOOKUP_URL).mock(return_value=httpx.Response(404))
    respx_mock.post(CHAT_UPDATE_URL).mock(
        side_effect=httpx.ReadTimeout("timed out")
    )
    post_route = respx_mock.post(CHAT_POST_MESSAGE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    await submit_author_lookup_technote()

    assert post_route.call_count == 1
    report = post_route.calls[-1].request.content.decode()
    assert CHANNEL_ID in report
    assert "nobody" in report


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_author_guidance_without_a_configured_webhook(
    respx_mock: respx.MockRouter,
) -> None:
    """Alerting is opt-in here too: with no webhook the user still gets their
    guidance and the operator still gets the log.
    """
    respx_mock.get(AUTHOR_LOOKUP_URL).mock(return_value=httpx.Response(404))
    update_route = respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )
    alert_route = respx_mock.post(ALERT_WEBHOOK_URL).mock(
        return_value=httpx.Response(200, text="ok")
    )

    with capture_logs() as logs:
        await submit_author_lookup_technote()

    assert alert_route.call_count == 0
    # The opening status update, then the guidance.
    assert update_route.call_count == 2
    assert "nobody" in update_route.calls[-1].request.content.decode()
    assert [entry for entry in logs if entry["event"] == "author_id_not_found"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_author_service_outage_asks_the_user_to_try_again(
    respx_mock: respx.MockRouter,
) -> None:
    """An author database that never answers says nothing about the author
    ID, so the user is asked to try again later rather than sent off to
    check an ID that is probably fine.
    """
    respx_mock.get(AUTHOR_LOOKUP_URL).mock(return_value=httpx.Response(500))
    route = respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    with pytest.raises(AuthorServiceError):
        await submit_author_lookup_technote()

    # The opening status update, then the report -- and nothing after it.
    assert route.call_count == 2
    report = route.calls[-1].request.content.decode()
    assert "author database" in report
    assert "try again later" in report
    # The submitted modal values, dumped for the user to paste into a retry.
    assert "A test technote" in report
    # None of the not-found guidance: there is nothing for the user to fix.
    assert "author ID" not in report
    assert "docs.google.com" not in report
    assert "lsst-texmf" not in report


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_author_service_outage_alerts_the_operator_fully(
    respx_mock: respx.MockRouter,
) -> None:
    """The gentler message to the user buys the operator nothing: an
    unreachable author database is a real incident and gets the full
    abandoned-creation alert, exception block and all.
    """
    respx_mock.get(AUTHOR_LOOKUP_URL).mock(return_value=httpx.Response(500))
    respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )
    alert_route = respx_mock.post(ALERT_WEBHOOK_URL).mock(
        return_value=httpx.Response(200, text="ok")
    )

    with pytest.raises(AuthorServiceError):
        await submit_author_lookup_technote(alert_webhook=ALERT_WEBHOOK_URL)

    assert alert_route.call_count == 1
    alert = alert_route.calls[-1].request.content.decode()
    assert "Abandoned" in alert
    assert "Exception" in alert
    assert "AuthorServiceError" in alert
    assert "technote_rst" in alert
    assert CHANNEL_ID in alert
    assert USER_ID in alert


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_author_service_outage_is_logged_as_an_abandoned_creation(
    respx_mock: respx.MockRouter,
) -> None:
    """An outage loses a submission like any other terminal failure, so it
    keeps the error-level marker and propagates for FastStream's traceback.
    """
    respx_mock.get(AUTHOR_LOOKUP_URL).mock(return_value=httpx.Response(500))
    respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    with capture_logs() as logs, pytest.raises(AuthorServiceError):
        await submit_author_lookup_technote()

    markers = [
        entry
        for entry in logs
        if entry["event"] == "project_creation_abandoned"
    ]
    assert len(markers) == 1
    assert markers[0]["log_level"] == "error"
    assert markers[0]["error_type"] == "AuthorServiceError"
    assert markers[0]["template"] == "technote_rst"
    assert markers[0]["channel"] == CHANNEL_ID
    assert markers[0]["user"] == USER_ID
    # Nothing here says the author ID was wrong; it was never looked up.
    assert not [
        entry for entry in logs if entry["event"] == "author_id_not_found"
    ]


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_abandoned_project_is_reported_to_the_channel(
    respx_mock: respx.MockRouter,
) -> None:
    """A failure inside ``_assign_technote_repo_serial`` must reach the user
    as a ``chat.update`` on the trigger message, and must still propagate so
    FastStream logs the traceback.
    """
    github_client = FakeGitHubClient()
    github_client.getiter_error = RuntimeError("GitHub is down")
    route = respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    with pytest.raises(RuntimeError, match="GitHub is down"):
        await submit_failing_technote(github_client)

    # The opening "I'm creating your new project..." update, then the report.
    assert route.call_count == 2
    report = route.calls[-1].request.content.decode()
    assert CHANNEL_ID in report
    assert MESSAGE_TS in report
    assert "technote_rst" in report
    # A failure with no better account of itself keeps the generic message.
    assert "Sorry, something went wrong" in report
    assert "RuntimeError" in report


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_abandoned_project_emits_marker_log(
    respx_mock: respx.MockRouter,
) -> None:
    """The marker log names the request that was lost, so an operator can
    find it and recreate the project by hand.
    """
    github_client = FakeGitHubClient()
    github_client.getiter_error = RuntimeError("GitHub is down")
    respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    with capture_logs() as logs, pytest.raises(RuntimeError):
        await submit_failing_technote(github_client)

    markers = [
        entry
        for entry in logs
        if entry["event"] == "project_creation_abandoned"
    ]
    assert len(markers) == 1
    assert markers[0]["template"] == "technote_rst"
    assert markers[0]["template_type"] == "project"
    assert markers[0]["channel"] == CHANNEL_ID
    assert markers[0]["message_ts"] == MESSAGE_TS
    assert markers[0]["user"] == USER_ID
    assert markers[0]["error_type"] == "RuntimeError"


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_report_falls_back_to_a_new_message(
    respx_mock: respx.MockRouter,
) -> None:
    """A broken ``chat.update`` is what caused this incident, so the report
    must not depend on one: it falls back to a new message in the channel.
    """
    github_client = FakeGitHubClient()
    github_client.getiter_error = RuntimeError("GitHub is down")
    respx_mock.post(CHAT_UPDATE_URL).mock(
        side_effect=[
            # The opening status update, swallowed by TemplateService.
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            # The failure report, failing every retry too.
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
        ]
    )
    post_route = respx_mock.post(CHAT_POST_MESSAGE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    with pytest.raises(RuntimeError, match="GitHub is down"):
        await submit_failing_technote(github_client)

    assert post_route.call_count == 1
    report = post_route.calls[-1].request.content.decode()
    assert CHANNEL_ID in report
    assert "technote_rst" in report


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_failed_report_does_not_mask_the_original_error(
    respx_mock: respx.MockRouter,
) -> None:
    """When Slack is unreachable altogether, the caller must still see the
    error that actually abandoned the project.
    """
    github_client = FakeGitHubClient()
    github_client.getiter_error = RuntimeError("GitHub is down")
    respx_mock.post(CHAT_UPDATE_URL).mock(
        side_effect=httpx.ReadTimeout("timed out")
    )
    respx_mock.post(CHAT_POST_MESSAGE_URL).mock(
        side_effect=httpx.ReadTimeout("timed out")
    )

    with capture_logs() as logs, pytest.raises(RuntimeError) as exc_info:
        await submit_failing_technote(github_client)

    assert str(exc_info.value) == "GitHub is down"
    assert [
        entry["event"]
        for entry in logs
        if entry["event"].startswith("slack_failure_report")
    ] == ["slack_failure_report_update_failed", "slack_failure_report_failed"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_abandoned_project_alerts_the_operator(
    respx_mock: respx.MockRouter,
) -> None:
    """A configured webhook gets an alert naming the template, channel, and
    user, so an operator learns about the loss without reading the logs.
    """
    github_client = FakeGitHubClient()
    github_client.getiter_error = RuntimeError("GitHub is down")
    respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )
    alert_route = respx_mock.post(ALERT_WEBHOOK_URL).mock(
        return_value=httpx.Response(200, text="ok")
    )

    with pytest.raises(RuntimeError, match="GitHub is down"):
        await submit_failing_technote(
            github_client, alert_webhook=ALERT_WEBHOOK_URL
        )

    assert alert_route.call_count == 1
    alert = alert_route.calls[-1].request.content.decode()
    assert "technote_rst" in alert
    assert CHANNEL_ID in alert
    assert USER_ID in alert
    assert "RuntimeError" in alert


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_no_alert_without_a_configured_webhook(
    respx_mock: respx.MockRouter,
) -> None:
    """Alerting is opt-in: with no webhook the failure path is unchanged."""
    github_client = FakeGitHubClient()
    github_client.getiter_error = RuntimeError("GitHub is down")
    update_route = respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )
    alert_route = respx_mock.post(ALERT_WEBHOOK_URL).mock(
        return_value=httpx.Response(200, text="ok")
    )

    with pytest.raises(RuntimeError, match="GitHub is down"):
        await submit_failing_technote(github_client)

    assert alert_route.call_count == 0
    # The opening status update, then the user-facing report.
    assert update_route.call_count == 2


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_failing_alert_does_not_affect_the_user_report(
    respx_mock: respx.MockRouter,
) -> None:
    """A broken alert webhook must not cost the user their error message,
    nor mask the error that abandoned the project.
    """
    github_client = FakeGitHubClient()
    github_client.getiter_error = RuntimeError("GitHub is down")
    update_route = respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )
    respx_mock.post(ALERT_WEBHOOK_URL).mock(
        side_effect=httpx.ReadTimeout("timed out")
    )

    with pytest.raises(RuntimeError, match="GitHub is down"):
        await submit_failing_technote(
            github_client, alert_webhook=ALERT_WEBHOOK_URL
        )

    assert update_route.call_count == 2
    report = update_route.calls[-1].request.content.decode()
    assert "technote_rst" in report


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_abandoned_file_creation_is_reported(
    respx_mock: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """File-template submissions run through the same seam as projects."""

    async def explode(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("rendering exploded")

    monkeypatch.setattr(TemplateService, "create_file_from_template", explode)
    route = respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    with pytest.raises(RuntimeError, match="rendering exploded"):
        await submit_view(
            template=FileTemplate(
                str(TEMPLATES_DIR / "file_templates" / "copyright")
            ),
            github_client=FakeGitHubClient(),
            metadata=make_metadata(
                template_name="copyright", template_type="file"
            ),
            modal_values={},
        )

    assert route.call_count == 1
    report = route.calls[-1].request.content.decode()
    assert "copyright" in report
    assert "file" in report
