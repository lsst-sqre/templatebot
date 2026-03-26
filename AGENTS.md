# Templatebot

## Project Overview

Templatebot is a Squarebot backend that creates projects and files from templates in the [lsst/templates](https://github.com/lsst/templates) repository. It receives Slack events via Kafka (through the Squarebot ecosystem), presents interactive Slack modals for template configuration, then renders templates with Cookiecutter and creates GitHub repositories.

## Common Commands

### Setup
```bash
make init          # Install all deps (frozen) + pre-commit hooks
make update-deps   # Update uv.lock + pre-commit hooks
```

### Testing and Linting (via nox)
```bash
uv run --only-group=nox nox                                          # Run all default sessions (lint, typing, test)
uv run --only-group=nox nox -s lint                                  # Pre-commit hooks
uv run --only-group=nox nox -s typing                                # mypy
uv run --only-group=nox nox -s test                                  # pytest (requires Docker for Kafka testcontainer)
uv run --only-group=nox nox -s test -- tests/handlers/internal_test.py  # Single test file
uv run --only-group=nox nox -s test -- tests/handlers/internal_test.py::test_get_index  # Single test
uv run --only-group=nox nox -s run                                   # Dev server with auto-reload + Kafka testcontainer
```

Note: nox is installed in its own dependency group. If `nox` isn't on PATH, use `uv run --only-group=nox nox`.

### Changelog
```bash
uv run --only-group=nox nox -s scriv-create                          # Create changelog fragment
uv run --only-group=nox nox -s scriv-collect -- --add --version X.Y.Z  # Collect fragments for release
```

## Architecture

### Layered Design

**Handlers** (`handlers/`) → **Services** (`services/`) → **Storage** (`storage/`)

- **Handlers**: Kafka consumers (`kafka.py`) receive Slack events (messages, app mentions, block actions, view submissions) via FastStream's `KafkaRouter`. Internal HTTP endpoints serve health/metadata.
- **Services**: Business logic layer. `SlackMessageService` parses commands, `SlackBlockActionsService` handles interactive selections, `SlackViewService` processes modal submissions, `TemplateService` renders templates and creates GitHub repos, `TemplateRepoService` browses templates and builds Slack UI.
- **Storage**: External API clients — Slack Web API, GitHub App (JWT auth), LSST the Docs, template repo caching (`RepoManager`), Ook author database.

### Dependency Injection

`ProcessContext` (dataclass) holds process-wide singletons (HTTP client, RepoManager). `Factory` creates per-request services. `ConsumerContext` provides per-Kafka-message context with a bound logger and factory. Handlers receive `ConsumerContext` via FastAPI `Depends()`.

### Configuration

`config.py` uses `pydantic_settings.BaseSettings`. Environment variable prefixes: `TEMPLATEBOT_` for app settings, `KAFKA_` for Kafka connection. Sensitive values use `SecretStr`. The noxfile provides test defaults for all required env vars.

## Code Conventions

- **Python 3.13** (`.python-version`)
- **Line length**: 79 characters
- **Ruff**: `select = ["ALL"]` with curated ignores (see `ruff-shared.toml`). Format and lint via pre-commit.
- **mypy**: Strict — `disallow_untyped_defs`, `disallow_incomplete_defs`, Pydantic plugin enabled.
- **Docstrings**: NumPy convention. Not required for handlers (`D103` ignored) or tests.
- **pytest**: `asyncio_mode = "strict"` — all async tests/fixtures need `@pytest.mark.asyncio`. Test files named `*_test.py`.
- **Logging**: structlog with context binding through the dependency injection chain.
- **Imports**: Relative imports within the package. isort knows `templatebot` and `tests` as first-party.
