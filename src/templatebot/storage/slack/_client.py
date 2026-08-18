"""Slack client."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient, Response
from pydantic import SecretStr
from structlog.stdlib import BoundLogger

from ..retry import retry_async
from ._exceptions import SlackApiError
from ._models import SlackChatPostMessageRequest, SlackChatUpdateMessageRequest
from .views import SlackModalView


class SlackWebApiClient:
    """A Slack client for the Web API.

    See https://api.slack.com/web for more information.
    """

    def __init__(
        self, http_client: AsyncClient, token: SecretStr, logger: BoundLogger
    ) -> None:
        self._http_client = http_client
        self._client_token = token
        self._logger = logger

    async def send_chat_post_message(
        self, message_request: SlackChatPostMessageRequest
    ) -> dict:
        """Send a chat.postMessage request to the Slack web API.

        Parameters
        ----------
        body
            The Slack chat.postMessage request body.

        Returns
        -------
        dict
            The JSON-decoded response from the Slack API as a dictionary.

        Raises
        ------
        httpx.HTTPStatusError
            Raised if the request fails.
        """
        return await self.post_json(
            method="chat.postMessage",
            body=message_request.model_dump(mode="json", exclude_none=True),
        )

    async def update_message(
        self, message_update_request: SlackChatUpdateMessageRequest
    ) -> dict:
        return await self.post_json(
            method="chat.update",
            body=message_update_request.model_dump(
                mode="json", exclude_none=True
            ),
        )

    async def open_view(
        self, *, trigger_id: str, view: SlackModalView
    ) -> dict:
        """Open a view."""
        return await self.post_json(
            method="views.open",
            body={
                "trigger_id": trigger_id,
                "view": view.model_dump(mode="json", exclude_none=True),
            },
        )

    async def post_json(self, *, method: str, body: dict[str, Any]) -> dict:
        """Send JSON-encoded POST request to the Slack web API.

        Parameters
        ----------
        method
            The Slack API method to call. See
            https://api.slack.com/web#methods for a list of methods.
        body
            A JSON-encodable dictionary to send as the request body.

        Returns
        -------
        dict
            The JSON-decoded response from the Slack API as a dictionary.

        Raises
        ------
        httpx.HTTPStatusError
            Raised if the request still fails after the retries are
            exhausted.
        SlackApiError
            Raised if Slack accepts the request but rejects the call with
            ``ok: false``.

        Notes
        -----
        Slack's Web API methods are safe to re-issue after a transport
        failure — a ``chat.postMessage`` that timed out on the read may still
        have posted, but a duplicate Slack message is a far smaller harm than
        silently dropping the update — so this call opts into
        `~templatebot.storage.retry.retry_async`.
        """
        url = self._format_url(method)

        async def send() -> Response:
            r = await self._http_client.post(
                url,
                json=body,
                headers=self.create_headers(),
            )
            r.raise_for_status()
            return r

        r = await retry_async(
            send, logger=self._logger.bind(slack_method=method)
        )
        return self._parse_response(r, method=method, body=body)

    async def get(
        self, *, method: str, params: dict[str, Any] | None = None
    ) -> dict:
        """Send a GET request to the Slack web API.

        Parameters
        ----------
        method
            The Slack API method to call. See
            https://api.slack.com/web#methods for a list of methods.
        params
            A dictionary of query parameters to send with the request.

        Returns
        -------
        dict
            The JSON-decoded response from the Slack API as a dictionary.

        Raises
        ------
        httpx.HTTPStatusError
            Raised if the request still fails after the retries are
            exhausted.
        SlackApiError
            Raised if Slack accepts the request but rejects the call with
            ``ok: false``.

        Notes
        -----
        Reads have no side effects, so this call opts into
        `~templatebot.storage.retry.retry_async`.
        """
        url = self._format_url(method)

        async def send() -> Response:
            r = await self._http_client.get(
                url,
                params=params,
                headers=self.create_headers(),
            )
            r.raise_for_status()
            return r

        r = await retry_async(
            send, logger=self._logger.bind(slack_method=method)
        )
        return self._parse_response(r, method=method, body=params or {})

    def _parse_response(
        self, r: Response, *, method: str, body: dict[str, Any]
    ) -> dict:
        """Decode a Slack response, raising if Slack rejected the call.

        Slack reports application-level failures with an HTTP 200 carrying
        ``{"ok": false}``, so this check has to happen after
        `~templatebot.storage.retry.retry_async` rather than inside the
        retried call: the transport succeeded, and re-issuing the request
        would only be rejected again.
        """
        resp_json = r.json()
        if not resp_json.get("ok", False):
            raise SlackApiError(
                method=method,
                error=resp_json.get("error", "unknown_error"),
                body=body,
            )
        return resp_json

    def _format_url(self, method: str) -> str:
        """Format a URL for a Slack Web API endpoint."""
        if not method.startswith("/"):
            method = method.lstrip("/")
        return f"https://slack.com/api/{method}"

    def create_headers(self) -> dict[str, str]:
        """Create headers for Slack API requests."""
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": (
                f"Bearer {self._client_token.get_secret_value()}"
            ),
        }
