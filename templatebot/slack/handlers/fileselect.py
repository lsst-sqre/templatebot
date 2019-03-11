"""Slack handler for when a user selects a file template from a menu.
"""

__all__ = ('handle_file_select_action',)

import json
from pathlib import Path
import uuid


async def handle_file_select_action(*, event_data, action_data, logger, app):
    """Handle the selection from a ``templatebot_file_select`` action ID.

    The key steps are:

    1. Use the ``chat.update`` method to replace the original message
       containing a selection menu with a confirmation message. This prevents
       someone from interacting with the menu again.
    2. Open a Slack dialog to let the user fill in template variables based
       on the ``cookiecutter.json`` file.
    """
    await _confirm_selection(event_data=event_data, action_data=action_data,
                             logger=logger, app=app)
    await _open_dialog(event_data=event_data, action_data=action_data,
                       logger=logger, app=app)


async def _confirm_selection(*, event_data, action_data, logger, app):
    """Confirm the menu selection by replacing the menu with a static message.
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


async def _open_dialog(*, event_data, action_data, logger, app):
    """Open a Slack dialog containing fields based on the user query.
    """
    selected_template = action_data['selected_option']['value']
    elements = _create_dialog_elements(
        template_name=selected_template,
        app=app)
    # State that's needed by handle_file_dialog_submission
    state = {
        'template_name': selected_template
    }
    dialog_body = {
        'trigger_id': event_data['trigger_id'],
        'dialog': {
            "title": selected_template,
            "callback_id": f'templatebot_file_dialog_{str(uuid.uuid4())}',
            'state': json.dumps(state),
            'notify_on_cancel': True,
            'elements': elements
        }
    }

    httpsession = app['root']['api.lsst.codes/httpSession']
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {app["root"]["templatebot/slackToken"]}'
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
            'Got a Slack error from dialog.open',
            contents=response_json)


def _create_dialog_elements(*, template_name, app):
    repo = app['templatebot/repo'].get_repo(
        gitref=app['root']['templatebot/repoRef']
    )
    template = repo[template_name]
    cookiecutter_path = Path(template.cookiecutter_json_path)
    cookiecutter_options = json.loads(cookiecutter_path.read_text())

    elements = []
    for var_name, option in cookiecutter_options.items():
        if var_name.startswith('_'):
            # Private variables (like _extensions) shouldn't be exposed in
            # the dialog.
            continue
        elif isinstance(option, list):
            element = _generate_select_element(var_name=var_name,
                                               options=option)
        else:
            element = _generate_text_element(var_name=var_name,
                                             default=option)
        elements.append(element)

    if len(elements) > 5:
        # This is the maximum length supported by Slack dialogs at the moment.
        elements = elements[:5]

    return elements


def _generate_select_element(*, var_name, options):
    """Generate the JSON specification of a ``select`` element in a dialog.
    """
    short_var_name = var_name
    if len(short_var_name) > 75:
        # FIXME: max allowable length by Slack
        short_var_name = short_var_name[:75]
    option_elements = []
    for v in options:
        if len(v) > 75:
            # FIXME: max allowable length by Slack
            v = v[:75]  # max allowed length by Slack
        option_elements.append({'label': v, 'value': v})
    element = {
        'label': short_var_name,
        'type': 'select',
        'name': short_var_name,
        'options': option_elements
    }
    return element


def _generate_text_element(*, var_name, default):
    """Generate the JSON specification of a text element in a dialog.
    """
    short_var_name = var_name
    if len(short_var_name) > 75:
        # FIXME: max allowable length by Slack
        short_var_name = short_var_name[:75]
    short_default = default
    if len(short_default) > 75:
        # FIXME: max allowable length by Slack
        short_default = short_default[:75]
    element = {
        'label': short_var_name,
        'name': short_var_name,
        "type": "text",
        "placeholder": short_default
    }
    return element
