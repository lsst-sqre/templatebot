# Templatebot

Templatebot creates new projects and files based on templates in Rubin Observatory's https://github.com/lsst/templates repository.
Templatebot works with the [Squarebot](https://github.com/lsst-sqre/squarebot) Slack front-end.

## Development

To bootstrap a development environment, create a virtual environment and install nox:
Development requires [uv](https://docs.astral.sh/uv/) for managing virtual environments and depedencies.
Set up a virtual environment and install the required dependencies:

```bash
uv venv
source .venv/bin/activate
make init
```

To run the tests:

```bash
uv --only-group=nox nox
```

Individual sessions are:

- `lint`: Run linters through pre-commit
- `typing`: Run mypy
- `test`: Run tests (requires Docker to run testcontainers)

To update the uv lockfile and re-install dependencies:

```bash
make update
```
