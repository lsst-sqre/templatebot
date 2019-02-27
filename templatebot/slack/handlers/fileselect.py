"""Slack handler for when a user selects a file template from a menu.
"""

__all__ = ('handle_file_select_action',)

import uuid


async def handle_file_select_action(*, event_data, action_data, logger, app):
    """Handle the selection from a ``templatebot_file_select`` action ID.
    """
    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
    }

    text_content = (
        f"<@{event_data['user']['id']}> :raised_hands: "
        "Nice! I'll help you create boilerplate for a "
        f"`{action_data['selected_option']['text']['text']}` snippet."
    )
    body = {
        'token': app["root"]["templatebot/slackToken"],
        'channel': event_data['container']['channel_id'],
        'text': text_content,
        "ts": event_data['container']['message_ts'],
        "blocks": [
            {
                "type": "section",
                "text": {
                    "text": text_content,
                    "type": "mrkdwn"
                }
            }
        ]
    }

    logger.info(
        'templatebot_file_select chat.update',
        body=body)

    url = 'https://slack.com/api/chat.update'
    async with httpsession.post(url, json=body, headers=headers) as response:
        response_json = await response.json()
        logger.info(
            'templatebot_file_select reponse',
            response=response_json)
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from chat.update',
            contents=response_json)

    dialog_body = {
        'trigger_id': event_data['trigger_id'],
        'dialog': {
            "title": "Create a file",
            "callback_id": f'templatebot_file_dialog_{str(uuid.uuid4())}',
            'state': '',
            'notify_on_cancel': True,
            'elements': [
                {
                    "label": "Email Address",
                    "name": "email",
                    "type": "text",
                    "subtype": "email",
                    "placeholder": "you@example.com"
                },
                {
                    "label": "Additional information",
                    "name": "comment",
                    "type": "textarea",
                    "hint": "Provide additional information if needed."
                },
                {
                    "label": "Meal preferences",
                    "type": "select",
                    "name": "meal_preferences",
                    "options": [
                        {
                            "label": "Hindu (Indian) vegetarian",
                            "value": "hindu"
                        },
                        {
                            "label": "Strict vegan",
                            "value": "vegan"
                        },
                        {
                            "label": "Kosher",
                            "value": "kosher"
                        },
                        {
                            "label": "Just put it in a burrito",
                            "value": "burrito"
                        }
                    ]
                }
            ]
        },
    }
    url = 'https://slack.com/api/dialog.open'
    async with httpsession.post(url, json=dialog_body, headers=headers) \
            as response:
        response_json = await response.json()
        logger.info(
            'templatebot_file_select reponse',
            response=response_json)
    if not response_json['ok']:
        logger.error(
            'Got a Slack error from chat.update',
            contents=response_json)
