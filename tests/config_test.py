"""Tests for the application configuration."""

from __future__ import annotations

import pytest

from templatebot.config import Config


def test_http_timeout_default() -> None:
    assert Config().http_timeout == 30.0


def test_http_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEMPLATEBOT_HTTP_TIMEOUT", "45.5")
    assert Config().http_timeout == 45.5
