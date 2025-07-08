import nox
from nox_uv import session
from testcontainers.kafka import KafkaContainer

# Default sessions
nox.options.sessions = ["lint", "typing", "test"]

# Other nox defaults
nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True


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
        "TEMPLATEBOT_ENVIRONMENT_URL": "http://example.com/",
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
