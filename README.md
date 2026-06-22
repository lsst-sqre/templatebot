# Templatebot

Templatebot creates new projects and files based on templates in Rubin Observatory's https://github.com/lsst/templates repository.
Templatebot works with the [Squarebot](https://github.com/lsst-sqre/squarebot) Slack front-end.

## Development

Development requires [uv](https://docs.astral.sh/uv/) (0.11.x) for managing the
virtual environment and dependencies, and Python 3.14 (see `.python-version`).
The test suite stands up Kafka with [testcontainers](https://testcontainers.com),
so Docker (or Colima on macOS) must be running.

To bootstrap a development environment, sync the dependencies from the committed
`uv.lock` and install the pre-commit hooks:

```bash
make init
```

This runs `uv sync --frozen --all-groups` followed by `pre-commit install`. uv
manages the `.venv` for you, so no manual `uv venv` / `source` is needed.

Common tasks are exposed as `make` targets that delegate to nox and pre-commit:

```bash
make lint     # Lint the code with pre-commit
make typing   # Run mypy
make test     # Run the test suite (requires Docker for Kafka)
make run      # Run the application in development mode
```

The underlying nox sessions can also be run directly. nox lives in its own
dependency group, so invoke it through uv:

```bash
uv run --only-group=nox nox                  # Run lint, typing, and test
uv run --only-group=nox nox -s lint          # Run linters through pre-commit
uv run --only-group=nox nox -s typing        # Run mypy
uv run --only-group=nox nox -s test          # Run tests (requires Docker)
uv run --only-group=nox nox -s test-coverage # Run tests with a coverage report
uv run --only-group=nox nox -s run           # Run the dev server with auto-reload
```

To update the uv lockfile, refresh the pre-commit hooks, and re-install
dependencies:

```bash
make update
```
