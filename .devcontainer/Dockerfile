# Dev container image for templatebot: Python 3.13 (matches .python-version)
# plus uv for dependency management. The uv:<version> tag is kept in sync with
# uv.lock / the CI UV_VERSION env var by scripts/update-uv-version.sh.
FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

# Install uv (https://docs.astral.sh/uv/).
COPY --from=ghcr.io/astral-sh/uv:0.7.19 /uv /uvx /bin/
