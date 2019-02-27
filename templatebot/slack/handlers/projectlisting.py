"""Handler for the initial interaction where a user wants to see a list of
project templates.
"""

__all__ = ('handle_project_creation',)


async def handle_project_creation(*, event, app, logger):
    """Handle an initial event from a user asking to make a new project
    (typically a GitHub repository).

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
            f"<@{calling_user}>, what type of project do you "
            "want to make?"
        ),
        'blocks': [
            {
                "type": "section",
                "block_id": "templatebot_project_select",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"<@{calling_user}>, what type of project do you "
                        "want to make?"
                    )
                },
                "accessory": {
                    "type": "static_select",
                    "action_id": "templatebot_project_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select a template",
                        "emoji": True
                    },
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "stack_package",
                                "emoji": True
                            },
                            "value": "stack_package"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "nbreport",
                                "emoji": True
                            },
                            "value": "nbreport"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "technote_rst",
                                "emoji": True
                            },
                            "value": "technote_rst"
                        }
                    ]
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
