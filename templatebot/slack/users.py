"""Workflow for working with the Slack users web API.
"""
__all__ = ('get_user_info',)

import yarl


async def get_user_info(*, user, logger, app):
    """Get information about a Slack user through the ``users.info`` web API.

    Parameters
    ----------
    user : `str`
        The user's ID (not their handle, but a Slack ID).
    logger
        Logger instance.
    app
        Application instance.
    """
    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/x-www-form-urlencoded; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
    }
    url = 'https://slack.com/api/users.info'
    body = {
        'token': app["root"]["templatebot/slackToken"],
        'user': user
    }
    encoded_body = yarl.URL.build(query=body).query_string.encode('utf-8')
    async with httpsession.post(url, data=encoded_body, headers=headers) \
            as response:
        response_json = await response.json()
        logger.debug(
            'users.info reponse',
            response=response_json)
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from users.info',
            response=response_json)

    return response_json
