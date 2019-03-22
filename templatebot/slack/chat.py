"""Slack helpers for working with the Slack ``chat`` web API methods.
"""

__all__ = ('update_message',)


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
    """
    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
    }

    logger.info(
        'chat.update',
        body=body)

    url = 'https://slack.com/api/chat.update'
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
        logger.debug(
            'chat.update reponse',
            response=response_json)
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from chat.update',
            contents=response_json)
