"""Slack listener that handles the initial interaction where a user wants to
see a listing of file templates.
"""

__all__ = ('handle_file_creation',)


async def handle_file_creation(*, event, app, logger):
    """Handle an initial event from a user asking to make a new file or
    snippet.

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
    menu_options = _generate_menu_options(app, logger)

    event_channel = event['event']['channel']
    calling_user = event['event']['user']

    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
    }
    body = {
        'token': app["root"]["templatebot/slackToken"],
        'channel': event_channel,
        # Since there are `blocks`, this is a fallback for notifications
        "text": (
            f"<@{calling_user}>, what type of file or snippet do you "
            "want to make?"
        ),
        'blocks': [
            {
                "type": "section",
                "block_id": "templatebot_file_select",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"<@{calling_user}>, what type of file or snippet do "
                        "you want to make?"
                    )
                },
                "accessory": {
                    "type": "static_select",
                    "action_id": "templatebot_file_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a template",
                        "emoji": True
                    },
                    "options": menu_options
                }
            }
        ]
    }
    url = 'https://slack.com/api/chat.postMessage'
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from chat.postMessage',
            contents=response_json)


def _generate_menu_options(app, logger):
    repo = app['templatebot/repo'].get_repo(
        gitref=app['root']['templatebot/repoRef']
    )
    template_names = [t.name for t in repo.iter_file_templates()]
    template_names.sort()

    options = []
    for name in template_names:
        option = {
            "text": {
                "type": "plain_text",
                "text": name,
                "emoji": True
            },
            "value": name
        }
        options.append(option)
    return options
