import json
import logging
import os
import re
import subprocess

import nox
from nox_uv import session

# Default sessions
nox.options.sessions = ["lint", "typing", "test"]

# Other nox defaults
nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True


def _setup_testcontainers_logging() -> None:
    """Suppress overly-verbose testcontainers logging."""
    logging.getLogger("testcontainers").setLevel(logging.ERROR)
    logging.getLogger("docker").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)


def _setup_testcontainers_env() -> None:
    """Configure testcontainers environment variables for Colima on macOS.

    This must be called before any containers are started to ensure the
    Reaper can connect properly when using Colima as the Docker runtime.
    """
    # Set testcontainers host override for Colima on macOS. This fixes
    # "nodename nor servname provided, or not known" errors.
    docker_host = os.getenv("DOCKER_HOST", "")
    m = re.search(r"\.colima/(?P<profile>[^/]+)/docker\.sock$", docker_host)
    if m:
        # Extract the Colima VM IP address for the active profile.
        # colima ls -j emits one JSON object per line (one per profile).
        try:
            result = subprocess.run(
                ["colima", "ls", "-j"],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                colima_info = json.loads(line)
                if colima_info.get("name") == m["profile"] and colima_info.get(
                    "address"
                ):
                    os.environ["TESTCONTAINERS_HOST_OVERRIDE"] = colima_info[
                        "address"
                    ]
                    break
        except (
            subprocess.CalledProcessError,
            json.JSONDecodeError,
            KeyError,
        ):
            # If we can't get the Colima address, don't set the override.
            pass


@session(uv_only_groups=["lint"], uv_no_install_project=True)
def lint(session: nox.Session) -> None:
    """Run pre-commit hooks."""
    session.run("pre-commit", "run", "--all-files", *session.posargs)


@session(uv_groups=["typing", "dev"])
def typing(session: nox.Session) -> None:
    """Run mypy."""
    session.run("mypy", "noxfile.py", "src", "tests")


@session(uv_groups=["dev"])
def test(session: nox.Session) -> None:
    """Run pytest."""
    _setup_testcontainers_logging()
    _setup_testcontainers_env()

    # Import after setting environment variables so config is read correctly.
    from testcontainers.kafka import KafkaContainer  # noqa: PLC0415

    with KafkaContainer().with_kraft() as kafka:
        env_vars = _make_env_vars(
            {
                "KAFKA_BOOTSTRAP_SERVERS": kafka.get_bootstrap_server(),
            }
        )
        session.run(
            "pytest",
            "--cov=templatebot",
            "--cov-branch",
            *session.posargs,
            env=env_vars,
        )


@session(name="test-coverage", uv_groups=["dev"])
def test_coverage(session: nox.Session) -> None:
    """Run tests and generate a coverage report."""
    test(session)
    session.run("coverage", "report")


@session(name="scriv-create")
def scriv_create(session: nox.Session) -> None:
    """Create a scriv entry."""
    session.install("scriv")
    session.run("scriv", "create")


@session(name="scriv-collect")
def scriv_collect(session: nox.Session) -> None:
    """Collect scriv entries."""
    session.install("scriv")
    session.run("scriv", "collect", "--add", "--version", *session.posargs)


@session(name="run", uv_groups=["dev"])
def run(session: nox.Session) -> None:
    """Run the application in development mode."""
    _setup_testcontainers_logging()
    _setup_testcontainers_env()

    # Import after setting environment variables so config is read correctly.
    from testcontainers.kafka import KafkaContainer  # noqa: PLC0415

    with KafkaContainer().with_kraft() as kafka:
        env_vars = _make_env_vars(
            {
                "KAFKA_BOOTSTRAP_SERVERS": kafka.get_bootstrap_server(),
            }
        )
        session.run(
            "uvicorn",
            "templatebot.main:app",
            "--reload",
            env=env_vars,
        )


def _make_env_vars(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Create a environment variable dictionary for test sessions that enables
    the app to start up.
    """
    env_vars = {
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
        "TEMPLATEBOT_PROFILE": "development",
        "TEMPLATEBOT_LOG_LEVEL": "DEBUG",
        "TEMPLATEBOT_SLACK_TOKEN": "xoxb-testing-123",
        "TEMPLATEBOT_SLACK_APP_ID": "A123456",
        "TEMPLATEBOT_TEMPLATE_REPO_URL": "https://github.com/lsst/templates",
        "TEMPLATEBOT_TEMPLATE_CACHE_DIR": ".tmp/template_cache",
        "TEMPLATEBOT_GITHUB_APP_ID": "1234",
        "TEMPLATEBOT_GITHUB_APP_PRIVATE_KEY": "test",
        "TEMPLATEBOT_LTD_USERNAME": "test",
        "TEMPLATEBOT_LTD_PASSWORD": "test",
    }
    if overrides:
        env_vars.update(overrides)
    return env_vars
