"""Tests for the Kafka consumers."""

from __future__ import annotations

from typing import cast

import httpx
import pytest
import respx
from faststream.kafka import TestKafkaBroker
from templatekit.repo import ProjectTemplate

from templatebot.config import config
from templatebot.dependencies.consumercontext import (
    consumer_context_dependency,
)
from templatebot.factory import ProcessContext
from templatebot.handlers.kafka import kafka_broker
from templatebot.storage.repo import RepoManager
from tests.services.slackview_test import (
    AUTHOR_LOOKUP_URL,
    AUTHOR_MODAL_VALUES,
    FakeRepoManager,
    make_metadata,
    make_payload,
)
from tests.services.template_test import CHAT_UPDATE_URL, OK, TEMPLATES_DIR


@pytest.fixture
def _fake_process_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Build the process context around a template served from test data.

    The real `ProcessContext` would clone lsst/templates on the first
    ``get_repo``; everything else about it, including the shared HTTP client
    that respx intercepts, is left alone.
    """
    template = ProjectTemplate(
        str(TEMPLATES_DIR / "project_templates" / "technote_rst")
    )
    create = ProcessContext.create

    async def create_with_fake_repos() -> ProcessContext:
        real = await create()
        return ProcessContext(
            http_client=real.http_client,
            repo_manager=cast("RepoManager", FakeRepoManager(template)),
        )

    monkeypatch.setattr(ProcessContext, "create", create_with_fake_repos)


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep", "_fake_process_context")
async def test_view_submission_survives_an_unknown_author_id(
    respx_mock: respx.MockRouter,
) -> None:
    """An unknown author ID must not reach the consumer as an exception.

    The seam answers the user and returns, so the subscriber completes
    normally and FastStream logs no traceback for what is only a user's typo.
    Driving this through the broker exercises the real `Factory` wiring that
    the service-level tests replace with hand-built fakes.
    """
    respx_mock.get(AUTHOR_LOOKUP_URL).mock(return_value=httpx.Response(404))
    update_route = respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )
    payload = make_payload(
        metadata=make_metadata(
            template_name="technote_rst", template_type="project"
        ),
        modal_values=dict(AUTHOR_MODAL_VALUES),
    )

    await consumer_context_dependency.initialize()
    try:
        async with TestKafkaBroker(kafka_broker) as broker:
            await broker.publish(
                payload.model_dump(mode="json"),
                topic=config.view_submission_topic,
            )
    finally:
        await consumer_context_dependency.aclose()

    # The opening status update, then the author guidance.
    assert update_route.call_count == 2
    assert "nobody" in update_route.calls[-1].request.content.decode()
