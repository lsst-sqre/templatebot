"""Handler for help messages.
"""

__all__ = ('handle_generic_help',)


async def handle_generic_help(*, event, app, logger):
    """Handle an event from a user asking for help with the bot.

    Note that this is a generic help request, so all backends will be
    responding.

    Parameters
    ----------
    event : `dict`
        The body of the Slack event.
    app : `aiohttp.web.Application`
        The application instance.
    logger
        A structlog logger, typically with event information already
        bound to it.
    """
    event_channel = event['event']['channel']
    thread_ts = event['event']['ts']
    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
    }
    body = {
        'token': app["root"]["templatebot/slackToken"],
        'channel': event_channel,
        'thread_ts': thread_ts,
        'text': _make_text_summary(),
        'mrkdwn': True,
        'blocks': _make_blocks()
    }
    url = 'https://slack.com/api/chat.postMessage'
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from chat.postMessage',
            contents=response_json)


def _make_text_summary():
    return (
        "Create a new GitHub repo from a template: `create project`.\\n"
        "Create a snippet of file from a template: `create file`."
    )


def _make_blocks():
    main_section = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "• Create a GitHub repo from a template: "
                "```create project```\n"
                "• Create a file or snippet from a template: "
                "```create file```"),
        }
    }
    context = {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": (
                    "Handled by <https://github.com/lsst-sqre/templatebot"
                    "|templatebot>. The template repository is "
                    "https://github.com/lsst/templates."
                )
            }
        ]
    }

    return [main_section, context]
