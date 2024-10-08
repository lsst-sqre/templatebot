# Templatebot

Templatebot creates new projects and files based on templates in Rubin Observatory's https://github.com/lsst/templates repository.
Templatebot works with the [Squarebot](https://github.com/lsst-sqre/squarebot) Slack front-end.

## Development

To bootstrap a development environment, create a virtual environment and install nox:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U nox
python -m nox -s init
```

To run the tests:

```bash
python -m nox
```

Individual sessions are:

- `init`: Install pre-commit hooks
- `lint`: Run linters through pre-commit
- `typing`: Run mypy
- `test`: Run tests (requires Docker to run testcontainers)
