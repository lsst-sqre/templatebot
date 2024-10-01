import nox

# Default sessions
nox.options.sessions = ["lint", "typing", "test"]

# Other nox defaults
nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True


# Pip installable dependencies
PIP_DEPENDENCIES = [
    ("-r", "requirements/main.txt"),
    ("-r", "requirements/dev.txt"),
    ("-e", "."),
]


def _install(session: nox.Session) -> None:
    """Install the application and all dependencies into the session."""
    session.install("--upgrade", "uv")
    for deps in PIP_DEPENDENCIES:
        session.install(*deps)


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
    }
    if overrides:
        env_vars.update(overrides)
    return env_vars


def _install_dev(session: nox.Session, bin_prefix: str = "") -> None:
    """Install the application and all development dependencies into the
    session.
    """
    python = f"{bin_prefix}python"
    precommit = f"{bin_prefix}pre-commit"

    # Install dev dependencies
    session.run(python, "-m", "pip", "install", "uv", external=True)
    for deps in PIP_DEPENDENCIES:
        session.run(python, "-m", "uv", "pip", "install", *deps, external=True)
    session.run(
        python,
        "-m",
        "uv",
        "pip",
        "install",
        "nox",
        "pre-commit",
        external=True,
    )
    # Install pre-commit hooks
    session.run(precommit, "install", external=True)


@nox.session(name="venv-init")
def init_dev(session: nox.Session) -> None:
    """Set up a development venv."""
    # Create a venv in the current directory, replacing any existing one
    session.run("python", "-m", "venv", ".venv", "--clear")
    _install_dev(session, bin_prefix=".venv/bin/")

    print(
        "\nTo activate this virtual env, run:\n\n\tsource .venv/bin/activate\n"
    )


@nox.session(name="init", venv_backend=None, python=False)
def init(session: nox.Session) -> None:
    """Set up the development environment in the current virtual env."""
    _install_dev(session, bin_prefix="")


@nox.session
def lint(session: nox.Session) -> None:
    """Run pre-commit hooks."""
    session.install("pre-commit")
    session.run("pre-commit", "run", "--all-files", *session.posargs)


@nox.session
def typing(session: nox.Session) -> None:
    """Run mypy."""
    _install(session)
    session.install("mypy")
    session.run("mypy", "noxfile.py", "src", "tests")


@nox.session
def test(session: nox.Session) -> None:
    """Run pytest."""
    from testcontainers.kafka import KafkaContainer

    _install(session)

    with KafkaContainer().with_kraft() as kafka:
        session.run(
            "pytest",
            "--cov=templatebot",
            "--cov-branch",
            *session.posargs,
            env=_make_env_vars(
                {"KAFKA_BOOTSTRAP_SERVERS": kafka.get_bootstrap_server()}
            ),
        )


@nox.session(name="scriv-create")
def scriv_create(session: nox.Session) -> None:
    """Create a scriv entry."""
    session.install("scriv")
    session.run("scriv", "create")


@nox.session(name="scriv-collect")
def scriv_collect(session: nox.Session) -> None:
    """Collect scriv entries."""
    session.install("scriv")
    session.run("scriv", "collect", "--add", "--version", *session.posargs)


@nox.session(name="update-deps")
def update_deps(session: nox.Session) -> None:
    """Update pinned server dependencies and pre-commit hooks."""
    session.install("--upgrade", "uv", "pre-commit")
    session.run("pre-commit", "autoupdate")

    # Dependencies are unpinned for compatibility with the unpinned client
    # dependency.
    session.run(
        "uv",
        "pip",
        "compile",
        "--upgrade",
        "--universal",
        "--generate-hashes",
        "--output-file",
        "requirements/main.txt",
        "requirements/main.in",
    )

    session.run(
        "uv",
        "pip",
        "compile",
        "--upgrade",
        "--universal",
        "--generate-hashes",
        "--output-file",
        "requirements/dev.txt",
        "requirements/dev.in",
    )

    print("\nTo refresh the development venv, run:\n\n\tnox -s init\n")


@nox.session(name="run")
def run(session: nox.Session) -> None:
    """Run the application in development mode."""
    _install(session)

    from testcontainers.kafka import KafkaContainer

    with KafkaContainer().with_kraft() as kafka:
        session.run(
            "uvicorn",
            "templatebot.main:app",
            "--reload",
            env=_make_env_vars(
                {"KAFKA_BOOTSTRAP_SERVERS": kafka.get_bootstrap_server()}
            ),
        )
