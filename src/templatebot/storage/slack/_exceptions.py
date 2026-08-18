"""Exceptions raised by the Slack Web API client."""

from __future__ import annotations

from typing import Any

__all__ = ["SlackApiError"]


class SlackApiError(Exception):
    """Slack accepted the HTTP request but rejected the call itself.

    The Slack Web API reports application-level failures with an HTTP 200
    carrying ``{"ok": false, "error": "..."}``, so
    `httpx.Response.raise_for_status` never fires for them. Raising this
    instead of returning the payload keeps a Slack-side rejection from looking
    identical to a success.

    Parameters
    ----------
    method
        The Slack API method that was called, e.g. ``chat.update``.
    error
        Slack's own error code from the response, e.g. ``channel_not_found``.
        See https://api.slack.com/web#responses for the vocabulary.
    body
        The request payload: the JSON body for a POST, or the query parameters
        for a GET. Slack's error codes are terse, so keeping the payload lets a
        caller log what was actually rejected.

    Attributes
    ----------
    method : str
        The Slack API method that was called.
    error : str
        Slack's error code from the response.
    body : dict
        The request payload that Slack rejected.
    """

    def __init__(
        self, *, method: str, error: str, body: dict[str, Any]
    ) -> None:
        self.method = method
        self.error = error
        self.body = body
        super().__init__(f"Slack API method {method} failed: {error}")
