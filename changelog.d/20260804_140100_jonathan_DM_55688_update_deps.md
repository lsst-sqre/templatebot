### Other changes

- Update pinned dependencies and pre-commit hooks. Notable bumps: uv 0.11.29 to 0.12.1 (also applied to `.pre-commit-config.yaml`, the `Dockerfile`, and the `UV_VERSION` in both CI workflows), ruff 0.15.22 to 0.16.1, websockets 16.1.1 to 17.0.1, uvicorn 0.51.0 to 0.52.1, testcontainers 4.14.2 to 4.15.0, and redis 8.0.1 to 8.1.0. The `fastapi<0.140` cap is deliberately retained.
