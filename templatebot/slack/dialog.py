"""Tools for opening Slack dialogs with template variables as fields and
working with the resulting data.
"""

__all__ = ('open_template_dialog', 'post_process_dialog_submission')

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
            if 'preset_options' in field:
                # Handle preset menu
                element = _generate_preset_element(field=field)
            elif 'preset_groups' in field:
                # Handle group preset menu
                element = _generate_preset_groups_element(field=field)
            else:
                # Handle regular select menu
                element = _generate_select_element(field=field)
        else:
            element = _generate_text_element(field=field)
        elements.append(element)

    if len(elements) > 5:
        # This is the maximum length supported by Slack dialogs at the moment.
        elements = elements[:5]

    return elements


def _generate_preset_groups_element(*, field):
    """Generate the JSON specification for a ``preset_groups`` flavor of
    a ``select`` element.
    """
    option_groups = []
    for group in field['preset_groups']:
        menu_group = {
            'label': group['group_label'],
            'options': []
        }
        for group_option in group['options']:
            menu_group['options'].append({
                'label': group_option['label'],
                'value': group_option['label']
            })
        option_groups.append(menu_group)
    element = {
        'label': field['label'],
        'type': 'select',
        'name': field['label'],
        'option_groups': option_groups,
        'optional': field['optional'],
    }
    return element


def _generate_preset_element(*, field):
    """Generate the JSON specification for a ``preset_options`` flavor of
    a ``select`` element.
    """
    option_elements = []
    for option in field['preset_options']:
        option_elements.append({
            'label': option['label'],
            'value': option['value']
        })
    element = {
        'label': field['label'],
        'type': 'select',
        'name': field['label'],
        'options': option_elements,
        'optional': field['optional'],
    }
    return element


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


def post_process_dialog_submission(*, submission_data, template):
    """Process the ``submission`` data from a Slack dialog submission.

    Parameters
    ----------
    submission_data : `dict`
        The ``submission_data`` from the Slack dialog's event payload. Keys are
        the ``name`` attributes of fields. Values are the user contents of the
        fields, or the ``value`` attributes from select menus.
    template : `templatekit.repo.BaseTemplate`
        The corresponding template instance.

    Returns
    -------
    data : `dict`
        A cleaned-up copy of the ``submission_data`` parameter. See Notes
        for details of the post processing steps.

    Notes
    -----
    The following steps occur to process ``submission_data``

    - Drop any null values from select fields so that we get defaults from
      ``cookiecutter.json``.
    - Replace any truncated values from select fields with the full values.
    """
    # Drop any null fields so that we get the defaults from cookiecutter.
    data = {k: v for k, v in submission_data.items() if v is not None}

    for field in template.config['dialog_fields']:

        if 'preset_groups' in field:
            # Handle as a preset_groups select menu
            selected_label = data[field['label']]
            for option_group in field['preset_groups']:
                for option in option_group['options']:
                    if option['label'] == selected_label:
                        for k, v in option['presets'].items():
                            data[k] = v
            del data[field['label']]

        elif 'preset_options' in field:
            # Handle as a preset select menu
            selected_value = data[field['label']]
            for option in field['preset_options']:
                if option['value'] == selected_value:
                    for k, v in option['presets'].items():
                        data[k] = v
            del data[field['label']]

        elif field['component'] == 'select':
            # Handle as a regular select menu
            try:
                selected_value = data[field['key']]
            except KeyError:
                # If field not in data, then it was not set, so use defaults
                continue

            # Replace any truncated values from select fields with full values
            for option in field['options']:
                if option['value'] == selected_value:
                    data[field['key']] = option['template_value']
                    continue

    return data
