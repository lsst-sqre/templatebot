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
                    "options": [
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "config_topic",
                                "emoji": True
                            },
                            "value": "config_topic"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "copyright",
                                "emoji": True
                            },
                            "value": "copyright"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "license_gplv3",
                                "emoji": True
                            },
                            "value": "license_gplv3"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "stack_license_preamble_cpp",
                                "emoji": True
                            },
                            "value": "stack_license_preamble_cpp"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "stack_license_preamble_py",
                                "emoji": True
                            },
                            "value": "stack_license_preamble_py"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "stack_license_preamble_txt",
                                "emoji": True
                            },
                            "value": "stack_license_preamble_txt"
                        },
                        {
                            "text": {
                                "type": "plain_text",
                                "text": "task_topic",
                                "emoji": True
                            },
                            "value": "task_topic"
                        },
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
