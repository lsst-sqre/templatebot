"""Slack client."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient
from pydantic import SecretStr
from structlog.stdlib import BoundLogger

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
            Raised if the request fails.
        """
        url = self._format_url(method)
        r = await self._http_client.post(
            url,
            json=body,
            headers=self.create_headers(),
        )
        r.raise_for_status()
        resp_json = r.json()
        if not resp_json["ok"]:
            self._logger.error(
                "Failed to send Slack message",
                response=resp_json,
                status_code=r.status_code,
                message=body,
            )
        return resp_json

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
            Raised if the request fails.
        """
        url = self._format_url(method)

        r = await self._http_client.get(
            url,
            params=params,
            headers=self.create_headers(),
        )
        r.raise_for_status()
        return r.json()

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
