"""Tests for Block Kit models."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field, ValidationError

from templatebot.storage.slack import blockkit


def test_plain_text_object_length() -> None:
    """Test that the length of a plain text object is correct."""

    class Model(BaseModel):
        text: blockkit.SlackPlainTextObject = Field(..., max_length=5)

    data = Model.model_validate(
        {"text": {"type": "plain_text", "text": "Hello"}}
    )
    assert data.text.text == "Hello"
    assert data.text.type == "plain_text"

    with pytest.raises(ValidationError):
        Model.model_validate(
            {"text": {"type": "plain_text", "text": "Hello!"}}
        )


def test_mrkdwn_text_object_length() -> None:
    """Test that the length of a mrkdwn text object is correct."""

    class Model(BaseModel):
        text: blockkit.SlackMrkdwnTextObject = Field(..., max_length=5)

    data = Model.model_validate({"text": {"type": "mrkdwn", "text": "Hello"}})
    assert data.text.text == "Hello"
    assert data.text.type == "mrkdwn"

    with pytest.raises(ValidationError):
        Model.model_validate({"text": {"type": "mrkdwn", "text": "Hello!"}})
