"""Tools for opening Slack dialogs with template variables as fields.
"""

__all__ = ('open_template_dialog',)

import json
import uuid


async def open_template_dialog(*, template, event_data, callback_id_root,
                               logger, app):
    """Open a Slack dialog containing fields based on the template.

    Parameters
    ----------
    template : `templatekit.repo.BaseTemplate`
        Template instance.
    event_data : `dict`
        The payload of the event.
    callback_id_root : `str`
        The root (prefix) of the ``dialog.callback_id`` field. This function
        adds a UUID4 suffix to make the callback ID unique. The router can
        find responses to this type of dialog by matching the ``callback_id``
        of the ``dialog_submission`` event.
    app : `aiohttp.web.Application`
        The application instance.
    logger
        A structlog logger, typically with event information already
        bound to it.
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
            "callback_id": f'{callback_id_root}_{str(uuid.uuid4())}',
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
        'options': option_elements,
        'optional': field['optional'],
    }
    return element


def _generate_text_element(*, field):
    """Generate the JSON specification of a text element in a dialog.
    """
    element = {
        'label': field['label'],
        'name': field['key'],
        "type": "text",
        'optional': field['optional'],
    }
    if 'placeholder' in field and len(field['placeholder']) > 0:
        element['placeholder'] = field['placeholder']
    if 'hint' in field and len(field['hint']) > 0:
        element['hint'] = field['hint']
    return element
