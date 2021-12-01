"""Utilities for working with the GitHub API."""

__all__ = ["get_authenticated_user"]


async def get_authenticated_user(*, app, logger):
    """Get information about the authenticated GitHub user.

    This function wraps the `GET /user
    <https://developer.github.com/v3/users/#get-the-authenticated-user>`_
    method.

    Parameters
    ----------
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.

    Returns
    -------
    response : `dict`
        The parsed JSON response body from GitHub.
    """
    ghclient = app["root"]["templatebot/gidgethub"]
    response = await ghclient.getitem("/user")
    return response
