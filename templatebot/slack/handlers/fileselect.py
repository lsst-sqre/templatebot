"""Slack handler for when a user selects a file template from a menu.
"""

__all__ = ('handle_file_select_action',)

import json
import uuid

from .filedialogsubmission import render_template


async def handle_file_select_action(*, event_data, action_data, logger, app):
    """Handle the selection from a ``templatebot_file_select`` action ID.

    The key steps are:

    1. Use the ``chat.update`` method to replace the original message
       containing a selection menu with a confirmation message. This prevents
       someone from interacting with the menu again.
    2. Open a Slack dialog to let the user fill in template variables based
       on the ``cookiecutter.json`` file. If the template doens't have any
       variables, then respond with the rendered template immediately instead
       of openening the dialog.
    """
    await _confirm_selection(event_data=event_data, action_data=action_data,
                             logger=logger, app=app)

    selected_template = action_data['selected_option']['value']
    repo = app['templatebot/repo'].get_repo(
        gitref=app['root']['templatebot/repoRef']
    )
    template = repo[selected_template]
    if len(template.config['dialog_fields']) == 0:
        await _respond_with_nonconfigurable_content(
            template=template, event_data=event_data, logger=logger,
            app=app)
    else:
        await _open_dialog(template=template, event_data=event_data,
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


async def _respond_with_nonconfigurable_content(*, template, event_data,
                                                logger, app):
    """Respond to the user on Slack with the content of a non-configurable
    template.

    This is an alternative pathway to `_open_dialog`.
    """
    channel_id = event_data['channel']['id']
    user_id = event_data['user']['id']
    await render_template(
        template=template,
        template_variables={},
        channel_id=channel_id,
        user_id=user_id,
        logger=logger,
        app=app)


async def _open_dialog(*, template, event_data, logger, app):
    """Open a Slack dialog containing fields based on the user query.
    """
    elements = _create_dialog_elements(template=template)

    # State that's needed by handle_file_dialog_submission
    state = {
        'template_name': template.name
    }
    dialog_title = template.config['dialog_title']
    dialog_body = {
        'trigger_id': event_data['trigger_id'],
        'dialog': {
            "title": dialog_title,
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


def _create_dialog_elements(*, template):
    elements = []
    for field in template.config['dialog_fields']:
        if field['component'] == 'select':
            element = _generate_select_element(
                field=field
            )
        else:
            element = _generate_text_element(
                field=field
            )
        elements.append(element)

    if len(elements) > 5:
        # This is the maximum length supported by Slack dialogs at the moment.
        elements = elements[:5]

    return elements


def _generate_select_element(*, field):
    """Generate the JSON specification of a ``select`` element in a dialog.
    """
    option_elements = []
    for v in field['options']:
        option_elements.append({'label': v['label'], 'value': v['value']})
    element = {
        'label': field['label'],
        'type': 'select',
        'name': field['key'],
        'options': option_elements
    }
    return element


def _generate_text_element(*, field):
    """Generate the JSON specification of a text element in a dialog.
    """
    element = {
        'label': field['label'],
        'name': field['key'],
        "type": "text",
    }
    if 'placeholder' in field:
        element['placeholder'] = field['placeholder']
    if 'hint' in field and len(field['hint']) > 0:
        element['hint'] = field['hint']
    return element
