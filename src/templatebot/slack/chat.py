"""Slack helpers for working with the Slack ``chat`` web API methods."""

__all__ = [
    "post_message",
    "update_message",
]


async def post_message(
    body=None, text=None, channel=None, thread_ts=None, *, logger, app
):
    """Send a ``chat.postMessage`` request to Slack.

    Parameters
    ----------
    body : `dict`, optional
        The ``chat.postMessage`` payload. See
        https://api.slack.com/methods/chat.postMessage. Set this parameter to
        have full control over the message. If you only need to send a simple
        message, see ``text``.
    text : `str`, optional
        Text content of the message. Use this parameter to send simple markdown
        messages rather than fully specifying the ``body``.
    channel : `str`, optional
        The channel ID, only used if the ``text`` parameter is used.
    thread_ts : `str`, optional
        The ``thread_ts`` to send a threaded message. Only use this parameter
        if ``text`` is set and you want to send a threaded message.
    logger
        Logger instance.
    app
        Application instance.

    Returns
    -------
    data : `dict`
        Response payload from the ``chat.postMessage`` method. See
        https://api.slack.com/methods/chat.postMessage
    """
    if body is None:
        if text is None or channel is None:
            raise ValueError(
                'If "body" is not set, then set "text" and "channel" '
                "for post_message"
            )

        body = {
            "token": app["root"]["templatebot/slackToken"],
            "channel": channel,
            "text": text,
        }
        if thread_ts is not None:
            body["thread_ts"] = thread_ts

    httpsession = app["root"]["api.lsst.codes/httpSession"]
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f'Bearer {app["root"]["templatebot/slackToken"]}',
    }

    logger.info("chat.postMessage", body=body)

    url = "https://slack.com/api/chat.postMessage"
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
        logger.debug("chat.postMessage reponse", response=response_json)
    if not response_json["ok"]:
        logger.error(
            "Got a Slack error from chat.postMessage", contents=response_json
        )

    return response_json


async def update_message(*, body, logger, app):
    """Send a ``chat.update`` request to Slack.

    Parameters
    ----------
    body : `dict`
        The ``chat.update`` payload. See
        https://api.slack.com/methods/chat.update
    logger
        Logger instance.
    app
        Application instance.

    Returns
    -------
    data : `dict`
        Response payload from the ``chat.update`` method. See
        https://api.slack.com/methods/chat.update
    """
    httpsession = app["root"]["api.lsst.codes/httpSession"]
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f'Bearer {app["root"]["templatebot/slackToken"]}',
    }

    logger.info("chat.update", body=body)

    url = "https://slack.com/api/chat.update"
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
        logger.debug("chat.update reponse", response=response_json)
    if not response_json["ok"]:
        logger.error(
            "Got a Slack error from chat.update", contents=response_json
        )

    return response_json
