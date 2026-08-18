"""Tests for the template service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Self, cast

import httpx
import pytest
import respx
import structlog
from pydantic import SecretStr
from structlog.testing import capture_logs
from templatekit.repo import FileTemplate, ProjectTemplate

from templatebot.services.template import TemplateService
from templatebot.storage.githubappclientfactory import GitHubAppClientFactory
from templatebot.storage.ltdclient import LtdClient
from templatebot.storage.slack import SlackWebApiClient

CHANNEL_ID = "C12345678"
MESSAGE_TS = "1234567890.123456"

CHAT_UPDATE_URL = "https://slack.com/api/chat.update"

MODAL_VALUES = {
    "name": "testapp",
    "summary": "A test application.",
    "github_org": "lsst-sqre",
    "flavor": "Default",
    "copyright_holder": "California Institute of Technology",
}

OK = {"ok": True}

TEMPLATES_DIR = Path(__file__).parent.parent / "data" / "templates"


class FakeGitHubClient:
    """Stand-in for a gidgethub installation client.

    Only the two calls the service makes are implemented: the
    ``POST /orgs/{org}/repos`` behind `GitHubRepo.create_repo`, and the
    paginated ``GET /orgs/{org}/repos`` listing that
    ``TemplateService._assign_technote_repo_serial`` walks.
    """

    oauth_token = "gh-token"

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.getiter_error: Exception | None = None
        self.repos: list[str] = []
        self.created: list[dict[str, Any]] = []

    async def post(
        self, url: str, *, url_vars: dict[str, str], data: dict[str, Any]
    ) -> dict[str, Any]:
        if self.error is not None:
            raise self.error
        self.created.append(data)
        org = url_vars["org_name"]
        return {"html_url": f"https://github.com/{org}/{data['name']}"}

    async def getiter(
        self, url: str, *, url_vars: dict[str, str]
    ) -> AsyncIterator[dict[str, Any]]:
        if self.getiter_error is not None:
            raise self.getiter_error
        for name in self.repos:
            yield {"name": name}


class FakeGitHubClientFactory:
    """Hand out a `FakeGitHubClient` for any organization."""

    def __init__(self, client: FakeGitHubClient) -> None:
        self._client = client

    async def create_installation_client_for_org(
        self, owner: str
    ) -> FakeGitHubClient:
        return self._client


class FakeGitClone:
    """Record commits and pushes instead of touching git or the network.

    An instance stands in for the `~templatebot.storage.gitclone.GitClone`
    class itself, since the service only ever reaches it through
    ``GitClone.init_repo``.
    """

    def __init__(self) -> None:
        self.push_error: Exception | None = None
        self.commits: list[str] = []
        self.pushes: list[str] = []

    def init_repo(
        self,
        *,
        path: Path,
        github_client: Any,
        default_branch: str = "main",
    ) -> Self:
        return self

    def commit(self, message: str) -> None:
        self.commits.append(message)

    def push(self, *, remote_url: str, branch: str = "main") -> None:
        if self.push_error is not None:
            raise self.push_error
        self.pushes.append(remote_url)


class FakeRenderer:
    """Stand in for cookiecutter with an empty project directory."""

    def __init__(self) -> None:
        self.error: Exception | None = None

    def __call__(
        self,
        *,
        template: ProjectTemplate,
        template_values: dict[str, Any],
        tmp_dir: Path,
    ) -> Path:
        if self.error is not None:
            raise self.error
        project_dir = tmp_dir / "project"
        project_dir.mkdir()
        return project_dir


@pytest.fixture
def file_template() -> FileTemplate:
    """Return a file template from test data."""
    return FileTemplate(str(TEMPLATES_DIR / "file_templates" / "copyright"))


@pytest.fixture
def github_client() -> FakeGitHubClient:
    return FakeGitHubClient()


@pytest.fixture
def git_clone(monkeypatch: pytest.MonkeyPatch) -> FakeGitClone:
    """Replace the module-level ``GitClone`` with a recording fake."""
    fake = FakeGitClone()
    monkeypatch.setattr("templatebot.services.template.GitClone", fake)
    return fake


@pytest.fixture
def renderer(monkeypatch: pytest.MonkeyPatch) -> FakeRenderer:
    """Replace cookiecutter rendering with a stub."""
    fake = FakeRenderer()
    monkeypatch.setattr(TemplateService, "_render_template", fake)
    return fake


def make_service(
    http_client: httpx.AsyncClient, *, github_client: FakeGitHubClient
) -> TemplateService:
    """Build a `TemplateService` wired to fakes for everything but Slack."""
    logger = structlog.get_logger("templatebot")
    return TemplateService(
        logger=logger,
        http_client=http_client,
        slack_client=SlackWebApiClient(
            http_client=http_client,
            token=SecretStr("xoxb-testing-123"),
            logger=logger,
        ),
        github_client_factory=cast(
            "GitHubAppClientFactory", FakeGitHubClientFactory(github_client)
        ),
        ltd_client=LtdClient(
            username="user",
            password=SecretStr("password"),
            http_client=http_client,
            logger=logger,
        ),
    )


async def create_project(
    *, github_client: FakeGitHubClient, modal_values: dict[str, str] | None
) -> None:
    """Run ``create_project_from_template`` against the fakes."""
    async with httpx.AsyncClient() as http_client:
        service = make_service(http_client, github_client=github_client)
        await service.create_project_from_template(
            template=ProjectTemplate(
                str(TEMPLATES_DIR / "project_templates" / "safir_fastapi_app")
            ),
            modal_values=modal_values or dict(MODAL_VALUES),
            trigger_message_ts=MESSAGE_TS,
            trigger_channel_id=CHANNEL_ID,
        )


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep", "renderer")
async def test_failed_opening_status_update_does_not_abort_creation(
    respx_mock: respx.MockRouter,
    github_client: FakeGitHubClient,
    git_clone: FakeGitClone,
) -> None:
    """A ``chat.update`` that fails every attempt while posting the opening
    status message must not discard the project the user asked for.
    """
    route = respx_mock.post(CHAT_UPDATE_URL).mock(
        side_effect=[
            # The opening "I'm creating your new project..." update, failing
            # on every retry.
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            # The final "Your new project is ready!" summary.
            httpx.Response(200, json=OK),
        ]
    )

    await create_project(github_client=github_client, modal_values=None)

    # The repository was created and pushed despite the failed status update.
    assert [repo["name"] for repo in github_client.created] == ["testapp"]
    assert git_clone.pushes == ["https://github.com/lsst-sqre/testapp"]

    # The final summary was posted on the fourth call.
    assert route.call_count == 4
    assert (
        "Your new project is ready!"
        in route.calls[-1].request.content.decode()
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep", "renderer", "git_clone")
async def test_failed_status_update_is_logged(
    respx_mock: respx.MockRouter,
    github_client: FakeGitHubClient,
) -> None:
    """A swallowed status-update failure still names the Slack method and the
    underlying error, so the operator can find it.
    """
    respx_mock.post(CHAT_UPDATE_URL).mock(
        side_effect=[
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.Response(200, json=OK),
        ]
    )

    with capture_logs() as logs:
        await create_project(github_client=github_client, modal_values=None)

    failures = [
        entry
        for entry in logs
        if entry["event"] == "slack_status_update_failed"
    ]
    assert len(failures) == 1
    assert failures[0]["slack_method"] == "chat.update"
    assert failures[0]["channel"] == CHANNEL_ID
    assert failures[0]["message_ts"] == MESSAGE_TS
    assert failures[0]["error_type"] == "ReadTimeout"
    assert "timed out" in failures[0]["error"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep", "renderer")
async def test_failed_final_summary_does_not_abort_creation(
    respx_mock: respx.MockRouter,
    github_client: FakeGitHubClient,
    git_clone: FakeGitClone,
) -> None:
    """The final summary is cosmetic too: losing it leaves the repository in
    place rather than raising out of the job.
    """
    respx_mock.post(CHAT_UPDATE_URL).mock(
        side_effect=[
            httpx.Response(200, json=OK),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
        ]
    )

    await create_project(github_client=github_client, modal_values=None)

    assert [repo["name"] for repo in github_client.created] == ["testapp"]
    assert git_clone.pushes == ["https://github.com/lsst-sqre/testapp"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep", "renderer", "git_clone")
async def test_lost_final_summary_logs_the_repository_url(
    respx_mock: respx.MockRouter,
    github_client: FakeGitHubClient,
) -> None:
    """A lost final summary is the one swallowed failure that costs the user
    something: the repository exists but its URL never reaches Slack. The log
    event has to carry the URL so an operator can hand it over.
    """
    respx_mock.post(CHAT_UPDATE_URL).mock(
        side_effect=[
            httpx.Response(200, json=OK),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
        ]
    )

    with capture_logs() as logs:
        await create_project(github_client=github_client, modal_values=None)

    failures = [
        entry
        for entry in logs
        if entry["event"] == "slack_status_update_failed"
    ]
    assert len(failures) == 1
    assert (
        failures[0]["github_repo_url"]
        == "https://github.com/lsst-sqre/testapp"
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep", "renderer", "git_clone")
async def test_failed_author_error_report_preserves_original_error(
    respx_mock: respx.MockRouter,
    github_client: FakeGitHubClient,
) -> None:
    """When the author lookup fails and the Slack report of that failure also
    fails, the caller still sees the author lookup's own error.
    """
    respx_mock.get("https://roundtable.lsst.cloud/ook/authors/nobody").mock(
        return_value=httpx.Response(404)
    )
    respx_mock.post(CHAT_UPDATE_URL).mock(
        side_effect=[
            # The opening status update.
            httpx.Response(200, json=OK),
            # The author-ID error report, failing on every retry.
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
        ]
    )

    modal_values = dict(MODAL_VALUES) | {"author_id": "nobody"}
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await create_project(
            github_client=github_client, modal_values=modal_values
        )

    assert exc_info.value.response.status_code == 404
    assert github_client.created == []


@pytest.mark.asyncio
@pytest.mark.usefixtures("_no_retry_sleep")
async def test_create_file_from_template_survives_failed_update(
    respx_mock: respx.MockRouter,
    file_template: FileTemplate,
    github_client: FakeGitHubClient,
) -> None:
    """``create_file_from_template``'s only Slack call is a status update, so
    it must not raise either.
    """
    respx_mock.post(CHAT_UPDATE_URL).mock(
        side_effect=[
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
            httpx.ReadTimeout("timed out"),
        ]
    )

    async with httpx.AsyncClient() as http_client:
        service = make_service(http_client, github_client=github_client)
        await service.create_file_from_template(
            template=file_template,
            modal_values={},
            trigger_message_ts=MESSAGE_TS,
            trigger_channel_id=CHANNEL_ID,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["github", "render", "push"])
async def test_real_failures_still_propagate(
    failure: str,
    respx_mock: respx.MockRouter,
    github_client: FakeGitHubClient,
    git_clone: FakeGitClone,
    renderer: FakeRenderer,
) -> None:
    """Only cosmetic Slack updates are swallowed: the steps that do the real
    work still fail the job.
    """
    respx_mock.post(CHAT_UPDATE_URL).mock(
        return_value=httpx.Response(200, json=OK)
    )

    error = RuntimeError(f"{failure} failed")
    if failure == "github":
        github_client.error = error
    elif failure == "render":
        renderer.error = error
    else:
        git_clone.push_error = error

    with pytest.raises(RuntimeError, match=f"{failure} failed"):
        await create_project(github_client=github_client, modal_values=None)
